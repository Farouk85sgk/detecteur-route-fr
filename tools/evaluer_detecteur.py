"""Évalue un détecteur sur les images de validation, en tenant compte des zones d'entraînement :
- une détection dans une zone « _ignorer » (objet douteux) ne compte ni comme bonne ni comme fausse ;
- sur les vraies photos (zone « _reel »), les marquages au sol ne sont pas annotés : seuls les panneaux y sont évalués.

Affiche, par classe, la précision moyenne (AP à IoU 0,5), puis précision et rappel au seuil de confiance choisi, et le
rappel des panneaux selon leur taille. Fonctionne aussi avec l'ancien modèle (une classe par panneau) : toutes ses
classes de panneaux sont regroupées en « panneau ».

    python tools/evaluer_detecteur.py --poids weights/route_fr_yolov5n.pt --images datasets/reel/images/val
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "yolov5"))

from models.experimental import attempt_load  # noqa: E402
from utils.general import non_max_suppression  # noqa: E402

from route_fr.classes import DET_IGNORER, DET_PANNEAU, DET_REEL, DETECTEUR  # noqa: E402


def iou_1n(b, B):
    x1, y1, x2, y2 = np.maximum(b[0], B[:, 0]), np.maximum(b[1], B[:, 1]), np.minimum(b[2], B[:, 2]), np.minimum(b[3], B[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    return inter / ((b[2] - b[0]) * (b[3] - b[1]) + (B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1]) - inter + 1e-9), inter


def nms_simple(d, seuil=0.5):
    """Suppression des doublons d'une même classe (après regroupement des classes de panneaux)."""
    garde = []
    for i in np.argsort(-d[:, 4]):
        if not garde or iou_1n(d[i, :4], d[garde, :4])[0].max() < seuil:
            garde.append(i)
    return d[garde]


def lire(fichier, W, H):
    out = []
    if fichier.exists():
        for l in fichier.read_text().split("\n"):
            if l.strip():
                k, x, y, w, h = l.split()
                x, y, w, h = float(x) * W, float(y) * H, float(w) * W, float(h) * H
                out.append([int(k), x - w / 2, y - h / 2, x + w / 2, y + h / 2])
    return np.array(out, np.float32).reshape(-1, 5)


def ap50(conf, bon, n_gt):
    if n_gt == 0 or len(conf) == 0:
        return float("nan") if n_gt == 0 else 0.0
    o = np.argsort(-conf)
    tp = np.cumsum(bon[o])
    fp = np.cumsum(~bon[o])
    r, p = tp / n_gt, tp / (tp + fp)
    r, p = np.concatenate([[0], r, [1]]), np.concatenate([[1], p, [0]])
    p = np.flip(np.maximum.accumulate(np.flip(p)))
    x = np.linspace(0, 1, 101)
    return float((getattr(np, "trapezoid", None) or np.trapz)(np.interp(x, r, p), x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poids", required=True)
    ap.add_argument("--images", nargs="+", required=True, help="dossiers .../images/val (étiquettes dans labels_complets/ ou labels/)")
    ap.add_argument("--img", type=int, default=416)
    ap.add_argument("--conf", type=float, default=0.3, help="seuil de confiance pour précision / rappel")
    ap.add_argument("--max", type=int, default=0)
    a = ap.parse_args()
    model = attempt_load(a.poids, device=torch.device("cpu"), fuse=True).eval()
    noms = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
    vers = np.array([DETECTEUR.index(noms[i]) if noms[i] in DETECTEUR else (-1 if noms[i].startswith(("M_", "_")) else DET_PANNEAU) for i in range(len(noms))])
    signes = torch.from_numpy(np.where(vers == DET_PANNEAU)[0])
    nc = DET_IGNORER
    for dossier in a.images:
        dossier = Path(dossier)
        fichiers = sorted(dossier.glob("*.jpg"))[: a.max or None]
        complets = Path(str(dossier).replace("/images/", "/labels_complets/"))
        labels = complets if complets.exists() else Path(str(dossier).replace("/images/", "/labels/"))
        confs, bons, n_gt = [[] for _ in range(nc)], [[] for _ in range(nc)], np.zeros(nc, int)
        tailles = {"moins de 10 px": [0, 0], "10 à 20 px": [0, 0], "plus de 20 px": [0, 0]}
        evaluees = np.zeros(nc, bool)
        for k in range(0, len(fichiers), 32):
            lot = fichiers[k : k + 32]
            ims = [cv2.imread(str(f)) for f in lot]
            x = np.stack([cv2.copyMakeBorder(im, 0, a.img - im.shape[0], 0, a.img - im.shape[1], cv2.BORDER_CONSTANT, value=(114, 114, 114)) for im in ims])
            x = torch.from_numpy(x[..., ::-1].copy()).permute(0, 3, 1, 2).float() / 255
            with torch.no_grad(), torch.autocast("cpu", dtype=torch.bfloat16):
                y = model(x)[0].float()
            if len(signes) > 1:  # ancien modèle : une classe par panneau, regroupées comme le faisait l'appli (somme des probabilités)
                y[..., 5 + signes[0]] = y[..., 5 + signes].sum(-1).clamp(max=1)
                y[..., 5 + signes[1:]] = 0
            dets = non_max_suppression(y, 0.01, 0.5, max_det=300)
            for f, im, d in zip(lot, ims, dets):
                H, W = im.shape[:2]
                gt = lire(labels / f"{f.stem}.txt", W, H)
                d = d.numpy()
                d[:, 5] = vers[d[:, 5].astype(int)]
                d = d[d[:, 5] >= 0]
                ign = gt[gt[:, 0] == DET_IGNORER, 1:]
                reel = gt[gt[:, 0] == DET_REEL, 1:]
                for c in range(nc):
                    g = gt[gt[:, 0] == c, 1:]
                    if c != DET_PANNEAU and len(reel):  # marquages non annotés sur les vraies photos
                        continue
                    evaluees[c] = True
                    dc = nms_simple(d[d[:, 5] == c]) if c == DET_PANNEAU else d[d[:, 5] == c]
                    pris = np.zeros(len(g), bool)
                    trouve = np.zeros(len(g), bool)  # au seuil --conf
                    for b in dc[np.argsort(-dc[:, 4])]:
                        if len(g):
                            ious, _ = iou_1n(b[:4], g)
                            ious[pris] = 0
                            j = int(ious.argmax())
                            if ious[j] >= 0.5:
                                pris[j] = True
                                trouve[j] |= b[4] >= a.conf
                                confs[c].append(b[4])
                                bons[c].append(True)
                                continue
                        if len(ign):
                            _, inter = iou_1n(b[:4], ign)
                            if inter.max() >= 0.5 * (b[2] - b[0]) * (b[3] - b[1]):
                                continue
                        confs[c].append(b[4])
                        bons[c].append(False)
                    n_gt[c] += len(g)
                    if c == DET_PANNEAU:
                        for (x1, y1, x2, y2), t in zip(g, trouve):
                            cote = max(x2 - x1, y2 - y1)
                            cle = "moins de 10 px" if cote < 10 else "10 à 20 px" if cote < 20 else "plus de 20 px"
                            tailles[cle][0] += 1
                            tailles[cle][1] += int(t)
        print(f"\n{dossier} : {len(fichiers)} images, modèle {a.poids}")
        print(f"{'classe':28s} {'objets':>7s} {'AP50':>6s} {'précision':>9s} {'rappel':>7s}   (au seuil {a.conf})")
        aps = []
        for c in range(nc):
            if not evaluees[c] or n_gt[c] == 0:
                continue
            cf, bn = np.array(confs[c]), np.array(bons[c], bool)
            v = ap50(cf, bn, n_gt[c])
            aps.append(v)
            s = cf >= a.conf
            tp, fp = int(bn[s].sum()), int((~bn[s]).sum())
            print(f"{DETECTEUR[c]:28s} {n_gt[c]:7d} {v:6.3f} {tp / max(tp + fp, 1):9.3f} {tp / n_gt[c]:7.3f}")
        print(f"{'moyenne':28s} {'':7s} {np.mean(aps):6.3f}")
        if tailles["10 à 20 px"][0]:
            print("rappel des panneaux par taille : " + ", ".join(f"{k} : {v[1] / max(v[0], 1):.2f} ({v[0]})" for k, v in tailles.items()))


if __name__ == "__main__":
    main()
