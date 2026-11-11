"""Entraîne le classifieur de panneaux (second étage) : il reçoit chaque panneau détecté et dit lequel c'est, ou le
rejette (« autre » : panneau hors liste ; « fond » : fausse détection).

Données : vraies vignettes (tools/panoramax_dataset.py --vignettes) et vignettes synthétiques (synth/generate_crops.py),
une classe par dossier, la boîte du panneau notée dans le nom de chaque fichier.

Entrée du réseau : 64 x 96 px (largeur x hauteur). Le recadrage (route_fr/classifier.py : fenetre) est un carré autour
de la boîte détectée, prolongé vers le bas d'une demi-hauteur : le classifieur voit ainsi le panonceau placé sous le
panneau, qui en change le sens (sens interdit « sauf vélos », cédez-le-passage « à 150 m »...). À l'entraînement, le
cadrage est décalé au hasard (boîte de détection imprécise) et l'image dégradée (basse définition d'un panneau lointain,
flou, bruit, éclairage, compression).

Réseau : YOLOv5n-cls, initialisé avec un classifieur existant. Sorties : weights/panneaux_cls.pt et .onnx (application
de bureau), docs/panneaux.onnx et docs/panneaux.json (version web : classes, taille d'entrée).

    python tools/train_classifieur.py --data datasets/vignettes datasets/vignettes_synth
"""

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "yolov5"))  # classes YOLOv5 nécessaires pour relire les poids .pt

from route_fr.classes import SIGNES_DETECTES  # noqa: E402
from route_fr.classifier import H_CLS, MEAN, STD, W_CLS, fenetre  # noqa: E402

CLASSES = SIGNES_DETECTES + ["autre", "fond"]
cv2.setNumThreads(0)


def degrade(img, rng):
    """Ce que voit la caméra d'un téléphone : panneau lointain (peu de pixels), flou, bruit, éclairage, compression."""
    if rng.random() < 0.7:  # basse définition : la boîte ne fait que quelques pixels de large avant agrandissement
        w = int(np.clip(math.exp(rng.uniform(math.log(9), math.log(72))), 9, W_CLS))
        if w < W_CLS:
            img = cv2.resize(cv2.resize(img, (w, round(w * H_CLS / W_CLS)), interpolation=cv2.INTER_AREA), (W_CLS, H_CLS), interpolation=cv2.INTER_LINEAR)
    r = rng.random()
    if r < 0.2:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.3, 1.0))
    elif r < 0.28:  # flou de bougé
        k = rng.choice([3, 5])
        ker = np.zeros((k, k), np.float32)
        ker[k // 2, :] = 1.0 / k
        img = cv2.filter2D(img, -1, cv2.warpAffine(ker, cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), rng.uniform(0, 180), 1), (k, k)))
    x = img.astype(np.float32)
    if rng.random() < 0.2:  # voile, contre-jour : couleurs pâlies
        v = rng.uniform(0.1, 0.4)
        x = x * (1 - v) + x.mean(2, keepdims=True) * 0.3 * v + 255 * 0.7 * v
    x = x * rng.uniform(0.6, 1.4) * np.array([rng.uniform(0.94, 1.06) for _ in range(3)], np.float32) + rng.uniform(-25, 25)
    if rng.random() < 0.3:
        x = 255 * (np.clip(x, 0, 255) / 255) ** rng.uniform(0.7, 1.4)
    if rng.random() < 0.4:
        x = x + np.random.default_rng(rng.getrandbits(32)).normal(0, rng.uniform(1, 8), x.shape)
    img = np.clip(x, 0, 255).astype(np.uint8)
    if rng.random() < 0.3:
        img = cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(30, 80)])[1], cv2.IMREAD_COLOR)
    return img


def recadrage(img, box, rng=None):
    """Recadrage 64 x 96 d'une vignette autour de la boîte du panneau (en fractions du côté), comme le fait l'appli ;
    avec `rng`, la boîte est d'abord décalée et agrandie ou réduite au hasard (détection imprécise)."""
    S = img.shape[0]
    x1, y1, x2, y2 = (v * S for v in box)
    angle = 0.0
    if rng is not None:
        w, h = x2 - x1, y2 - y1
        dx, dy = rng.gauss(0, 0.05) * w, rng.gauss(0, 0.05) * h
        k = math.exp(rng.gauss(0, 0.06))
        cx, cy = (x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy
        w, h = w * k * math.exp(rng.gauss(0, 0.04)), h * k * math.exp(rng.gauss(0, 0.04))
        x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        angle = rng.gauss(0, 2.5)
    fx, fy, fw, fh = fenetre((x1, y1, x2, y2))
    M = np.array([[W_CLS / fw, 0, -fx * W_CLS / fw], [0, H_CLS / fh, -fy * H_CLS / fh]], np.float32)
    if angle:
        R = cv2.getRotationMatrix2D((W_CLS / 2, H_CLS / 3), angle, 1.0)
        M = (np.vstack([R, [0, 0, 1]]) @ np.vstack([M, [0, 0, 1]]))[:2].astype(np.float32)
    return cv2.warpAffine(img, M, (W_CLS, H_CLS), flags=cv2.INTER_AREA if fw > 1.5 * W_CLS else cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def tenseur(img):
    x = (img[:, :, ::-1].astype(np.float32) / 255 - MEAN) / STD
    return torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1)))


class Vignettes(Dataset):
    """Vignettes en mémoire (JPEG) ; chaque accès tire un recadrage 64 x 96 autour de la boîte du panneau. Les fichiers
    listés dans <dossier>/exclus.txt (étiquettes jugées fausses par tools/nettoyer_vignettes.py) sont laissés de côté."""

    def __init__(self, dossiers, split, train, max_par_classe=0, classes=CLASSES):
        self.items, self.fichiers, self.train = [], [], train
        rng = random.Random(0)
        for k, d in enumerate(dossiers):
            liste = Path(d) / "exclus.txt"
            exclus = set(liste.read_text(encoding="utf-8").split("\n")) if liste.exists() else set()
            for c, nom in enumerate(classes):
                fichiers = [f for f in sorted((Path(d) / split / nom).glob("*.jpg")) if f"{split}/{nom}/{f.name}" not in exclus]
                limite = max_par_classe * (8 if nom in ("autre", "fond") else 1)  # les rejets sont très variés
                if limite and len(fichiers) > limite:
                    fichiers = rng.sample(fichiers, limite)
                for f in fichiers:
                    box = [int(v) / 1000 for v in f.stem.split("_")[-4:]]
                    self.items.append((np.frombuffer(f.read_bytes(), np.uint8), c, box, k))
                    self.fichiers.append(f)
        self.y = np.array([it[1] for it in self.items])
        self.source = np.array([it[3] for it in self.items])

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        data, c, box, _ = self.items[i]
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if not self.train:
            return tenseur(recadrage(img, box)), c
        rng = random.Random(random.getrandbits(48))
        return tenseur(degrade(recadrage(img, box, rng), rng)), c


@torch.inference_mode()
def predire(model, ds, bs=512):
    model.eval()
    out = []
    for j in range(0, len(ds), bs):
        x = torch.stack([ds[i][0] for i in range(j, min(j + bs, len(ds)))])
        with torch.autocast("cpu", dtype=torch.bfloat16):
            out.append(torch.softmax(model(x).float(), 1))
    return torch.cat(out).numpy()


def bilan(p, y):
    """Exactitude moyenne par classe (chaque classe compte autant), exactitude globale, et détail par classe."""
    k = p.argmax(1)
    par = {c: float(np.mean(k[y == c] == c)) for c in np.unique(y)}
    return float(np.mean(list(par.values()))), float(np.mean(k == y)), par


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", default=[str(ROOT / "datasets" / "vignettes"), str(ROOT / "datasets" / "vignettes_synth")])
    ap.add_argument("--depart", default=str(ROOT / "weights" / "panneaux_cls.pt"), help="classifieur de départ")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--par-epoque", type=int, default=100_000)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--max-par-classe", type=int, default=1500)
    ap.add_argument("--sortie", default=str(ROOT / "weights" / "panneaux_cls.pt"))
    ap.add_argument("--sans-export", action="store_true")
    a = ap.parse_args()
    torch.manual_seed(0)
    random.seed(0)
    train = Vignettes(a.data, "train", True, a.max_par_classe)
    val = Vignettes(a.data[:1], "val", False)  # validation sur les vraies photos seulement
    n = np.bincount(train.y, minlength=len(CLASSES))
    print(f"{len(train)} vignettes d'entraînement ({int((train.source == 0).sum())} réelles), {len(val)} de validation, {len(CLASSES)} classes", flush=True)
    vides = [CLASSES[c] for c in range(len(CLASSES)) if n[c] == 0]
    if vides:
        print("Classes sans exemple :", " ".join(vides))
    reel = np.bincount(train.y[train.source == 0], minlength=len(CLASSES))
    # tirage : les classes rares presque autant que les fréquentes ; le synthétique pèse moitié moins quand le réel suffit
    poids = n[train.y] ** -0.75 * np.where((train.source > 0) & (reel[train.y] >= 50), 0.5, 1.0)
    for c in (len(CLASSES) - 2, len(CLASSES) - 1):  # « autre » et « fond » : dix fois une classe ordinaire
        poids[train.y == c] *= 10
    sampler = WeightedRandomSampler(torch.as_tensor(poids), a.par_epoque, replacement=True)
    loader = DataLoader(train, batch_size=a.batch, sampler=sampler, num_workers=3, drop_last=True, persistent_workers=True)

    ck = torch.load(a.depart, map_location="cpu", weights_only=False)
    model = ck["model"].float()
    tete = model.model[-1]
    if tete.linear.out_features != len(CLASSES):
        tete.linear = nn.Linear(tete.linear.in_features, len(CLASSES))
    model.names = dict(enumerate(CLASSES))
    for p in model.parameters():
        p.requires_grad_(True)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=5e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.epochs * len(loader), pct_start=0.15)
    best = (-1.0, None)
    for ep in range(a.epochs):
        model.train()
        t0, pertes = time.time(), []
        for x, y in loader:
            with torch.autocast("cpu", dtype=torch.bfloat16):
                out = model(x)
            loss = F.cross_entropy(out.float(), y, label_smoothing=0.05)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            pertes.append(loss.item())
        moy, glob, par = bilan(predire(model, val), val.y)
        print(f"époque {ep + 1}/{a.epochs}  perte {np.mean(pertes):.3f}  validation : {moy:.3f} par classe, {glob:.3f} global  {time.time() - t0:.0f} s", flush=True)
        if moy > best[0]:
            best = (moy, {k: v.clone() for k, v in model.state_dict().items()})
    model.load_state_dict(best[1])
    model.eval()
    p = predire(model, val)
    moy, glob, par = bilan(p, val.y)
    faibles = sorted(par.items(), key=lambda kv: kv[1])[:25]
    print(f"Meilleur modèle : {moy:.3f} par classe, {glob:.3f} global sur {len(val)} vraies vignettes")
    print("Classes les moins bien reconnues : " + ", ".join(f"{CLASSES[c]} {v:.2f} ({int((val.y == c).sum())})" for c, v in faibles))
    torch.save({"model": model, "classes": CLASSES, "taille": [W_CLS, H_CLS], "validation": moy}, a.sortie)
    if not a.sans_export:
        from ultralytics.utils.export import torch2onnx

        web = ROOT / "docs"
        torch2onnx(model, torch.zeros(1, 3, H_CLS, W_CLS), web / "panneaux.onnx", opset=17, output_names=["output0"], dynamic={"images": {0: "batch"}, "output0": {0: "batch"}})
        (web / "panneaux.json").write_text(json.dumps({"classes": CLASSES, "taille": [W_CLS, H_CLS]}, ensure_ascii=False), encoding="utf-8")
        import onnx  # noms des classes dans le fichier, comme le fait yolov5/export.py : l'application de bureau les y lit

        m = onnx.load(web / "panneaux.onnx")
        for cle, valeur in (("stride", 32), ("names", dict(enumerate(CLASSES)))):
            meta = m.metadata_props.add()
            meta.key, meta.value = cle, str(valeur)
        onnx.save(m, web / "panneaux.onnx")
        onnx.save(m, Path(a.sortie).with_suffix(".onnx"))
        print(f"Exporté : {web / 'panneaux.onnx'}")


if __name__ == "__main__":
    main()
