"""Génère les icônes PNG du panneau latéral (route_fr/icones/<code>.png) : panneaux depuis les gabarits SVG,
marquages dessinés vus de dessus. À relancer après modification des gabarits (nécessite cairosvg)."""

import random
import sys
from pathlib import Path

import cairosvg
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import CLASSES  # noqa: E402
from route_fr.signs_svg import build  # noqa: E402
from synth.markings import bike_raster, longitudinal, make_local, text_raster  # noqa: E402

OUT = ROOT / "route_fr" / "icones"
S = 128


def marking_icon(code):
    """Vue de dessus : 1 m = 14 px, centre de l'icône = (0, 0) dans le repère de la route."""
    im = np.zeros((S, S, 4), np.uint8)
    cv2.rectangle(im, (0, 0), (S - 1, S - 1), (60, 60, 60, 255), -1)
    ppm = 14.0
    rng = random.Random(3)
    to_px = lambda p: np.stack([S / 2 + p[:, 0] * ppm, S / 2 - p[:, 1] * ppm], 1)  # noqa: E731
    color = (60, 200, 245, 255) if code == "M_zigzag" else (250, 250, 250, 255)
    if code in ("M_ligne_continue", "M_ligne_discontinue", "M_ligne_mixte"):
        mk = longitudinal(code, 0.0, -5, 5, random.Random(1), width=0.25)
        if code != "M_ligne_continue":  # motif lisible : traits de 1,5 m
            mk.polys = [p for p in mk.polys if p[:, 1].max() - p[:, 1].min() > 4] or mk.polys
            if code == "M_ligne_discontinue":
                mk.polys = [np.array([[-0.12, z], [0.12, z], [0.12, z + 1.5], [-0.12, z + 1.5]]) for z in (-4.5, -1.5, 1.5)]
            else:
                mk.polys += [np.array([[0.33, z], [0.57, z], [0.57, z + 1.5], [0.33, z + 1.5]]) for z in (-4.5, -1.5, 1.5)]
        polys = mk.polys
    elif code in ("M_stop_sol", "M_bus"):
        t = text_raster("STOP" if code == "M_stop_sol" else "BUS", rng, 100, 60)
        im[34:94, 14:114][t > 100] = color
        return im
    elif code == "M_velo":
        t = bike_raster(rng, 100, 100)
        im[14:114, 14:114][t > 100] = color
        return im
    else:
        mk = make_local(code, 0.0, 0.0, 3.5, rng, None)
        polys = mk.polys
        if code == "M_passage_pietons":
            polys = [p * [0.6, 0.6] for p in polys]
        if code in ("M_zebras", "M_zigzag"):
            polys = [p * [1.0, 0.33] for p in polys]
    for p in polys:
        cv2.fillPoly(im, [np.round(to_px(np.asarray(p)) * 16).astype(np.int32)], color, cv2.LINE_AA, shift=4)
    return im


def main():
    OUT.mkdir(exist_ok=True)
    for c in CLASSES:
        if c.categorie == "marquage":
            img = marking_icon(c.code)
        else:
            png = cairosvg.svg2png(bytestring=build(c.code).encode(), output_height=S)
            img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
            if img.shape[1] > S * 1.6:  # panneaux d'agglomération : on borne la largeur
                img = cv2.resize(img, (int(S * 1.6), int(img.shape[0] * S * 1.6 / img.shape[1])), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(OUT / f"{c.code}.png"), img)
    print(f"{len(CLASSES)} icônes dans {OUT}")


if __name__ == "__main__":
    main()
