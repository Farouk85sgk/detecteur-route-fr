"""Entraîne le modèle d'empreintes de la version web (« Mes panneaux ») sur les identités de synth/generate_identites.py.

Réseau : le classifieur de panneaux (YOLOv5n-cls, déjà habitué aux panneaux routiers) sans sa dernière couche, suivi
d'une projection vers 128 valeurs normalisées. Perte CosFace sur les identités : deux vignettes du même panneau ont
des empreintes proches, deux panneaux différents des empreintes éloignées. La validation porte sur des identités
jamais vues : c'est la situation d'un panneau que l'utilisateur apprend à l'appli.

Sorties : weights/empreinte.pt, docs/empreinte.onnx et docs/empreinte.json (seuil de reconnaissance).

    python tools/train_empreinte.py --data datasets/empreintes
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
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "yolov5"))  # classes YOLOv5 nécessaires pour relire les poids .pt

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


class Crops(Dataset):
    """Vignettes 64 x 64 en mémoire ; à l'entraînement, cadrage décalé (boîte de détection imprécise) et éclairage."""

    def __init__(self, root, train):
        dirs = sorted(p for p in Path(root).iterdir() if p.is_dir())
        files = [(f, k) for k, d in enumerate(dirs) for f in sorted(d.glob("*.jpg"))]
        self.x = np.stack([cv2.imread(str(f)) for f, _ in files])
        self.y = np.array([k for _, k in files])
        self.n, self.train = len(dirs), train

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        img = self.x[i]
        if self.train:
            s, a = random.uniform(0.88, 1.12), math.radians(random.uniform(-6, 6))
            m = cv2.getRotationMatrix2D((32 + random.uniform(-4, 4), 32 + random.uniform(-4, 4)), math.degrees(a), s)
            img = cv2.warpAffine(img, m, (64, 64), borderMode=cv2.BORDER_REPLICATE)
            img = np.clip(img.astype(np.float32) * random.uniform(0.7, 1.3) + random.uniform(-20, 20), 0, 255).astype(np.uint8)
        x = (img[:, :, ::-1].astype(np.float32) / 255 - MEAN) / STD
        return torch.from_numpy(x.transpose(2, 0, 1).copy()), int(self.y[i])


class Empreinte(nn.Module):
    def __init__(self, cls_model, dim=128):
        super().__init__()
        head = cls_model.model[-1]
        self.body, self.conv, self.pool = cls_model.model[:-1], head.conv, head.pool
        self.proj = nn.Linear(head.linear.in_features, dim)

    def forward(self, x):
        return F.normalize(self.proj(self.pool(self.conv(self.body(x))).flatten(1)), dim=1)


@torch.inference_mode()
def embed(model, ds, bs=512):
    model.eval()
    out = [model(torch.stack([ds[i][0] for i in range(j, min(j + bs, len(ds)))])).float() for j in range(0, len(ds), bs)]
    return torch.cat(out).numpy()


def evaluate(E, Y):
    """1 vignette de référence (nette) par identité, les autres en test : bonne réponse au plus proche, rappel au seuil
    qui ne laisse passer que 1 % de confusions avec un autre panneau appris, et seuil de reconnaissance de l'appli :
    0,2 % de chances qu'un panneau quelconque soit pris pour un panneau appris donné."""
    ref = np.array([np.where(Y == k)[0][0] for k in np.unique(Y)])
    test = np.setdiff1d(np.arange(len(Y)), ref)
    S = E[test] @ E[ref].T
    yt = np.searchsorted(np.unique(Y), Y[test])
    same = S[np.arange(len(test)), yt]
    S[np.arange(len(test)), yt] = -1
    other = S.max(1)
    seuil = float(np.percentile(other, 99))
    top1 = float(np.mean(same > other))
    autres = (E[test] @ E[ref].T)[np.arange(len(ref))[None, :] != yt[:, None]]
    return top1, float(np.mean(same > seuil)), float(np.quantile(autres, 0.998))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "datasets" / "empreintes"))
    ap.add_argument("--classifieur", default=str(ROOT / "weights" / "panneaux_cls.pt"))
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--dim", type=int, default=128)
    a = ap.parse_args()
    torch.manual_seed(0)
    random.seed(0)
    train, val = Crops(f"{a.data}/train", True), Crops(f"{a.data}/val", False)
    print(f"{train.n} identités d'entraînement ({len(train)} vignettes), {val.n} de validation", flush=True)
    cls = torch.load(a.classifieur, map_location="cpu", weights_only=False)["model"].float()
    model = Empreinte(cls, a.dim)
    W = nn.Parameter(torch.randn(train.n, a.dim) * 0.01)
    lrs = [1e-3, 1e-3, 5e-3]
    opt = torch.optim.AdamW([{"params": model.body.parameters()}, {"params": model.conv.parameters()}, {"params": list(model.proj.parameters()) + [W]}], weight_decay=1e-4)
    loader = DataLoader(train, batch_size=a.batch, shuffle=True, num_workers=3, drop_last=True, persistent_workers=True)
    total = a.epochs * len(loader)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lrs, total_steps=total, pct_start=0.1)
    s_scale, margin = 24.0, 0.25
    best = (-1, None)
    for ep in range(a.epochs):
        model.train()
        t0, losses = time.time(), []
        for x, y in loader:
            with torch.autocast("cpu", dtype=torch.bfloat16):
                e = model(x)
            cos = e.float() @ F.normalize(W, dim=1).T
            logits = s_scale * (cos - margin * F.one_hot(y, train.n))
            loss = F.cross_entropy(logits, y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            losses.append(loss.item())
        top1, rappel, seuil = evaluate(embed(model, val), val.y)
        print(f"époque {ep + 1}/{a.epochs}  perte {np.mean(losses):.3f}  validation : top1 {top1:.3f}, rappel@1% {rappel:.3f} (seuil appli {seuil:.3f})  {time.time() - t0:.0f} s", flush=True)
        if rappel > best[0]:
            best = (rappel, {k: v.clone() for k, v in model.state_dict().items()}, seuil)
    model.load_state_dict(best[1])
    model.eval()
    torch.save({"state_dict": model.state_dict(), "dim": a.dim, "seuil": best[2]}, ROOT / "weights" / "empreinte.pt")
    from ultralytics.utils.export import torch2onnx

    out = ROOT / "docs" / "empreinte.onnx"
    torch2onnx(model, torch.zeros(1, 3, 64, 64), out, opset=17, output_names=["empreinte"], dynamic={"images": {0: "batch"}, "empreinte": {0: "batch"}})
    (ROOT / "docs" / "empreinte.json").write_text(json.dumps({"dim": a.dim, "seuil": round(best[2], 4)}), encoding="utf-8")
    print(f"Meilleur rappel@1% {best[0]:.3f}, seuil {best[2]:.3f} -> {out}")


if __name__ == "__main__":
    main()
