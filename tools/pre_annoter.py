"""Pré-annote des images avec le modèle actuel (format YOLO) pour accélérer l'annotation manuelle.

Les fichiers .txt produits s'ouvrent dans LabelImg, CVAT, Label Studio ou Roboflow (format « YOLO ») : il suffit
de corriger les erreurs puis de réentraîner avec vos images (voir README, « Améliorer le modèle »).

    python tools/pre_annoter.py mes_images --conf 0.25
"""

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import NAMES  # noqa: E402
from route_fr.detector import Detector  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", help="dossier d'images")
    ap.add_argument("--poids", default=str(ROOT / "weights" / "route_fr_yolov5n.pt"))
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--taille", type=int, nargs="+", default=[640])
    ap.add_argument("--classifieur", default=str(ROOT / "weights" / "panneaux_cls.pt"), help="'' pour ne pas l'utiliser")
    a = ap.parse_args()
    det = Detector(a.poids, a.taille, a.conf, classifier=a.classifieur if a.classifieur and Path(a.classifieur).exists() else None)
    folder = Path(a.images)
    (folder / "classes.txt").write_text("\n".join(NAMES) + "\n")
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"))
    n = 0
    for p in files:
        img = cv2.imread(str(p))
        if img is None:
            continue
        h, w = img.shape[:2]
        lines = []
        for x1, y1, x2, y2, _conf, c in det(img):
            lines.append(f"{int(c)} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
        p.with_suffix(".txt").write_text("\n".join(lines) + ("\n" if lines else ""))
        n += len(lines)
    print(f"{len(files)} images pré-annotées ({n} objets). Corrigez-les puis voir README pour réentraîner.")


if __name__ == "__main__":
    main()
