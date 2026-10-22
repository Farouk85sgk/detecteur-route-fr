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
from route_fr.signs_svg import G, P, build, circ, cyclist, pedestrian, rect, svg  # noqa: E402
from synth.markings import bike_raster, longitudinal, make_local, text_raster  # noqa: E402

OUT = ROOT / "route_fr" / "icones"
S = 256  # icônes nettes aussi en grand (quiz, fiches de la version web)


def marking_icon(code):
    """Vue de dessus : 1 m = 14 px pour 128 px d'icône, centre de l'icône = (0, 0) dans le repère de la route."""
    im = np.zeros((S, S, 4), np.uint8)
    cv2.rectangle(im, (0, 0), (S - 1, S - 1), (60, 60, 60, 255), -1)
    k = S / 128
    ppm = 14.0 * k
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
        t = text_raster("STOP" if code == "M_stop_sol" else "BUS", rng, round(100 * k), round(60 * k))
        im[round(34 * k):round(94 * k), round(14 * k):round(114 * k)][t > 100] = color
        return im
    elif code == "M_velo":
        t = bike_raster(rng, round(100 * k), round(100 * k))
        im[round(14 * k):round(114 * k), round(14 * k):round(114 * k)][t > 100] = color
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


FEUX = {"F_rouge": 0, "F_orange": 1, "F_vert": 2}
LAMPES = ["#ff3b30", "#ffb000", "#27d36b"]
ORANGE = "#f07d19"
LOGO = (  # losange jaune « route prioritaire » bordé de bleu nuit, coché : le symbole de l'appli web
    '<rect x="15" y="15" width="70" height="70" rx="12" transform="rotate(45 50 50)" fill="#12163a"/>'
    '<rect x="25" y="25" width="50" height="50" rx="7" transform="rotate(45 50 50)" fill="#ffc61e"/>'
    '<path d="M36 51 L46 61 L65 40" stroke="#12163a" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
)


def moto(c):
    """Motard sur sa moto, de profil."""
    wheel = lambda x: P(f"M {x - 8.5} 8 a 8.5 8.5 0 1 0 17 0 a 8.5 8.5 0 1 0 -17 0", c, 3.6)  # noqa: E731
    return (
        wheel(-17) + wheel(18)
        + P("M -17 8 L -8 -3 L 9 -3 L 18 8", c, 3.6, join="round")
        + rect(-11, -10, 19, 7, c, rx=2.5)
        + P("M 18 8 L 12 -12 L 17 -14", c, 3.0, cap="round", join="round")
        + circ(-1, -24, 4.2, c)
        + P("M -3 -19 L -5 -9", c, 5.0, cap="round")
        + P("M -3 -17 L 10 -12", c, 2.8, cap="round")
        + P("M -5 -9 L 4 -6 L 6 1", c, 3.4, cap="round", join="round")
    )


def extra_svg(code):
    """Icônes de la version web pour les feux et les usagers (détectés par le YOLOv5 COCO d'origine)."""
    if code in FEUX:
        body = rect(36, 4, 56, 120, "#15171c", rx=16)
        for k in range(3):
            y = 26 + 38 * k
            if k == FEUX[code]:
                body += circ(64, y, 18, LAMPES[k] + "55") + circ(64, y, 14, LAMPES[k]) + circ(60, y - 4, 4, "#ffffff99")
            else:
                body += circ(64, y, 14, "#3a3d46")
        return svg(128, 128, body)
    w = "#ffffff"
    picto = {
        "U_pieton": G(pedestrian(w), 64, 66, 2.6),
        "U_cycliste": G(cyclist(w), 64, 72, 2.2),
        "U_deux_roues": G(moto(w), 64, 70, 2.1),
    }[code]
    return svg(128, 128, rect(2, 2, 124, 124, ORANGE, rx=26) + picto)


def app_icons(out):
    """Icônes de l'appli installée (PWA) et favicon, dans docs/."""
    (out / "favicon.svg").write_text(svg(100, 100, LOGO), encoding="utf-8")
    for size, pad in ((192, 0.0), (512, 0.0), (512, 0.12)):
        inner = 100 * (1 - 2 * pad)
        body = rect(0, 0, 100, 100, "#12163a", rx=0 if pad else 22) + G(LOGO, 50 - inner / 2, 50 - inner / 2, inner / 100)
        png = cairosvg.svg2png(bytestring=svg(100, 100, body).encode(), output_width=size, output_height=size)
        name = f"icone-{size}{'-maskable' if pad else ''}.png"
        (out / name).write_bytes(png)


def main():
    OUT.mkdir(exist_ok=True)
    for code in ("F_rouge", "F_orange", "F_vert", "U_pieton", "U_cycliste", "U_deux_roues"):
        png = cairosvg.svg2png(bytestring=extra_svg(code).encode(), output_height=S)
        (OUT / f"{code}.png").write_bytes(png)
    app_icons(ROOT / "docs")
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
