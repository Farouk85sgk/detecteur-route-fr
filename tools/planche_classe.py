"""Planches de contrôle d'une classe de vignettes réelles : toutes ses photos, numérotées, pour repérer à l'œil les
étiquettes fausses (logos, panneaux d'un autre type...). La liste numérotée des fichiers est écrite à côté.

    python tools/planche_classe.py --data datasets/vignettes --out controle B14_100 C4a

Les erreurs repérées se notent dans data/panoramax_corrections.txt (voir tools/corriger_vignettes.py).
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classifier import fenetre  # noqa: E402

T, COLS, LIGNES = 96, 12, 12


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "datasets" / "vignettes"))
    ap.add_argument("--out", default="controle")
    ap.add_argument("classes", nargs="+")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for c in a.classes:
        fs = sorted((Path(a.data) / "train" / c).glob("*.jpg")) + sorted((Path(a.data) / "val" / c).glob("*.jpg"))
        (out / f"{c}.txt").write_text("\n".join(f"{i} {f}" for i, f in enumerate(fs)), encoding="utf-8")
        for p in range(0, len(fs), COLS * LIGNES):
            lot = fs[p : p + COLS * LIGNES]
            planche = np.zeros((-(-len(lot) // COLS) * T, COLS * T, 3), np.uint8)
            for k, f in enumerate(lot):
                im = cv2.imread(str(f))
                S = im.shape[0]
                x, y, w, _ = fenetre([int(v) / 1000 * S for v in f.stem.split("_")[-4:]])
                M = np.array([[T / w, 0, -x * T / w], [0, T / w, -y * T / w]], np.float32)
                v = cv2.warpAffine(im, M, (T, T), flags=cv2.INTER_AREA if w > T else cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                for couleur, e in (((0, 0, 0), 3), ((0, 255, 255), 1)):
                    cv2.putText(v, str(p + k), (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, couleur, e, cv2.LINE_AA)
                r, q = divmod(k, COLS)
                planche[r * T : (r + 1) * T, q * T : (q + 1) * T] = v
            cv2.imwrite(str(out / f"{c}_{p // (COLS * LIGNES)}.jpg"), planche, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"{c} : {len(fs)} vignettes -> {out}/{c}_*.jpg")


if __name__ == "__main__":
    main()
