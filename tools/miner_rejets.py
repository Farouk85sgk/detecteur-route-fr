"""Second tour du classifieur : récolte ce que le détecteur prend à tort pour un panneau du catalogue.

Le détecteur est passé sur les images réelles d'entraînement (tools/panoramax_dataset.py). Chaque boîte « panneau »
qu'il propose est comparée aux annotations de la vue :
- elle ne recouvre aucune annotation : fausse détection -> vignette ajoutée à la classe « fond » ;
- elle recouvre un objet non identifié (« yes ») que le classifieur actuel ne reconnaît pas non plus -> classe « autre ».
Les vignettes sont découpées dans la vue d'origine, à pleine définition, comme les autres (dossier <out>/train/...).

    python tools/miner_rejets.py --poids weights/route_fr_yolov5n.pt --classifieur weights/panneaux_cls.pt
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "yolov5"))

from models.experimental import attempt_load  # noqa: E402
from utils.general import non_max_suppression  # noqa: E402

from panoramax_dataset import T, vignette  # noqa: E402
from route_fr.classes import DET_PANNEAU  # noqa: E402
from route_fr.classifier import SignClassifier  # noqa: E402
from route_fr.panoramax import code_catalogue  # noqa: E402


def recouvre(b, boites):
    """Plus grande part de la boîte b couverte par une des boîtes, et indice de celle-ci."""
    if not len(boites):
        return 0.0, -1
    x1, y1 = np.maximum(b[0], boites[:, 0]), np.maximum(b[1], boites[:, 1])
    x2, y2 = np.minimum(b[2], boites[:, 2]), np.minimum(b[3], boites[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    part = inter / max((b[2] - b[0]) * (b[3] - b[1]), 1e-6)
    return float(part.max()), int(part.argmax())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poids", default=str(ROOT / "weights" / "route_fr_yolov5n.pt"))
    ap.add_argument("--classifieur", default=str(ROOT / "weights" / "panneaux_cls.pt"))
    ap.add_argument("--reel", default=str(ROOT / "datasets" / "reel"))
    ap.add_argument("--vues", default=str(ROOT / "datasets_src" / "panoramax" / "vues"))
    ap.add_argument("--out", default=str(ROOT / "datasets" / "vignettes"))
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--max", type=int, default=0)
    a = ap.parse_args()
    model = attempt_load(a.poids, device=torch.device("cpu"), fuse=True).eval()
    cls = SignClassifier(a.classifieur, torch.device("cpu"))
    sources = [json.loads(l) for l in open(Path(a.reel) / "sources.jsonl", encoding="utf-8")]
    sources = [s for s in sources if s["split"] == "train"][: a.max or None]
    out, total = Path(a.out) / "train", collections.Counter()
    for d in ("fond", "autre"):
        (out / d).mkdir(parents=True, exist_ok=True)
        for f in (out / d).glob("rejet_*.jpg"):  # récolte précédente
            f.unlink()
    for n, s in enumerate(sources):
        vue = cv2.imread(f"{a.vues}/{s['id']}.jpg")
        meta = json.loads(Path(f"{a.vues}/{s['id']}.json").read_text(encoding="utf-8"))
        if vue is None:
            continue
        annots = np.array([x["box"] for x in meta["annots"]], np.float32).reshape(-1, 4)
        natures = [code_catalogue(x["code"])[0] for x in meta["annots"]]
        for nom, (x0, y0, S) in s["fenetres"].items():
            im = cv2.resize(vue[y0 : y0 + S, x0 : x0 + S], (T, T), interpolation=cv2.INTER_AREA if S > T else cv2.INTER_LINEAR)
            x = torch.from_numpy(im[:, :, ::-1].copy()).permute(2, 0, 1)[None].float() / 255
            with torch.inference_mode(), torch.autocast("cpu", dtype=torch.bfloat16):
                y = model(x)[0].float()
            det = non_max_suppression(y, a.conf, 0.5, classes=[DET_PANNEAU], max_det=30)[0].numpy()
            for k, (bx1, by1, bx2, by2, conf, _) in enumerate(det):
                b = np.array([bx1, by1, bx2, by2]) * S / T + [x0, y0, x0, y0]  # boîte dans la vue d'origine
                if max(b[2] - b[0], b[3] - b[1]) * T / S < 10:
                    continue  # trop petit pour être affiché par l'appli
                part, j = recouvre(b, annots)
                if part >= 0.3 and natures[j] != "inconnu":
                    continue  # vrai panneau annoté
                if part >= 0.3:  # objet non identifié : « autre » si le classifieur ne le reconnaît pas non plus
                    g, p = cls(vue, b[None])
                    if g[0] >= 0 and p[0] >= 0.5:
                        continue
                    classe = "autre"
                elif part > 0.05:
                    continue  # chevauche un panneau : ambigu
                else:
                    classe = "fond"
                r = vignette(vue, b)
                if r is not None:
                    cv2.imwrite(str(out / classe / f"rejet_{nom}_{k}_{r[1]}.jpg"), r[0], [cv2.IMWRITE_JPEG_QUALITY, 92])
                    total[classe] += 1
        if n % 2000 == 0:
            print(f"{n}/{len(sources)}  {dict(total)}", flush=True)
    print(f"Terminé : {dict(total)}")


if __name__ == "__main__":
    main()
