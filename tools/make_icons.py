"""Génère les icônes de l'application (route_fr/icones/<code>.png, copiées dans docs/icones/ par export_web.py) :

- panneaux : schémas officiels de Wikimedia Commons (« France road sign <code>.svg »), réduits à 256 px. Leurs auteurs
  et licences (Licence Ouverte, domaine public, CC BY, CC BY-SA) sont dans data/commons_panneaux.json et recopiés
  dans route_fr/icones/CREDITS.md ; les panneaux assemblés (B6d + M6h...) sont composés à partir de ces schémas ;
- quelques panneaux sans schéma disponible (C2, J3, J13, B19) et les marquages au sol : dessinés ici ;
- feux, usagers et icônes de l'appli installée.

Les rendus PNG des schémas sont lus dans --commons (png/ et libre/) ; ceux qui manquent sont téléchargés.

    python tools/make_icons.py --commons datasets_src/commons
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import MARQUAGES, PANNEAUX  # noqa: E402
from route_fr.signs_svg import BASE_COLORS, G, P, blue_square, circ, cyclist, pedestrian, poly, prohibition, rect, svg, text  # noqa: E402
from synth.markings import bike_raster, make_local, text_raster  # noqa: E402

OUT = ROOT / "route_fr" / "icones"
S = 256  # hauteur des icônes : nettes aussi en grand (quiz, fiches)
UA = "outil-pedagogique-signalisation/1.0"

# code du catalogue -> schéma(s) Commons quand le nom diffère ; un tuple = panneau + panonceau assemblés
SOURCES = {
    "B1_M9v": "B1+M9", "B1_M1": ("B1", "M1"), "B6d_M6h": ("B6d", "M6h"), "B6d_M6a": ("B6d", "M6a"), "B6d_M6i": ("B6d", "M6i"),
    "B6d_M6j": ("B6d", "M6j"), "C1a_M4c": ("C1a", "M4c"), "B33": "B33_(50)", "C4a": "C4a_(50)", "C4b": "C4b_(50)", "B30": "B30_(30)",
    "B51": "B51_(30)", "B25": "B25_(30)", "B43": "B43_(30)", "C24a": "C24a-2", "C64d": "C64d2", "SR3": "SR3d", "M3": "M3a1", "M6d": "M6d1",
    "M8": "M8a", "M9v": "M9v2", "M9z": "M9z-2", "M10": "M10a", "M11": "M11a", "M12d": "M12D", "M12f": "M12F", "M12fd": "M12FD",
    "J10": ["J10_3_barres", "J10_2_barres", "J10_1_barre"],
}  # fmt: skip
DESSINES = ("C2", "J3", "J13", "B19")  # pas de schéma libre : dessinés ci-dessous


def sources(code):
    s = SOURCES.get(code, f"B14_({code[4:]})" if code.startswith("B14_") else code)
    return [s] if isinstance(s, str) else list(s)


def rendu(nom, commons):
    """Rendu PNG (RGBA, rogné) d'un schéma Commons ; téléchargé s'il n'est pas déjà dans le dossier."""
    for d in ("libre", "png"):
        f = commons / d / f"{nom}.png"
        if f.exists():
            break
    else:
        f = commons / "png" / f"{nom}.png"
        f.parent.mkdir(parents=True, exist_ok=True)
        url = "https://commons.wikimedia.org/w/thumb.php?" + urllib.parse.urlencode({"f": f"France_road_sign_{nom}.svg", "w": 512})
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
            f.write_bytes(r.read())
        time.sleep(1.5)
    im = Image.open(f).convert("RGBA")
    return im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())


def ajuste(im, h=None, w=None):
    """Réduit l'image pour tenir dans (w, h) en gardant ses proportions."""
    k = min((h or 1e9) / im.height, (w or 1e9) / im.width)
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)


def panneau(code, commons):
    src = sources(code)
    ims = [rendu(n, commons) for n in src]
    if len(ims) == 1:
        return ajuste(ims[0], S, 1.6 * S)
    if isinstance(SOURCES[code], list):  # éléments côte à côte (balises J10)
        ims = [ajuste(im, S) for im in ims]
        gap = round(0.14 * S)
        out = Image.new("RGBA", (sum(im.width for im in ims) + gap * (len(ims) - 1), S))
        x = 0
        for im in ims:
            out.paste(im, (x, 0))
            x += im.width + gap
        return out
    haut = ajuste(ims[0], round(0.66 * S))  # panneau, puis son panonceau dessous
    bas = ajuste(ims[1], round(0.30 * S), round(1.25 * haut.width))
    out = Image.new("RGBA", (max(haut.width, bas.width), S))
    out.paste(haut, ((out.width - haut.width) // 2, 0))
    out.paste(bas, ((out.width - bas.width) // 2, S - bas.height))
    return out


def dessin(code):
    """Panneaux sans schéma disponible, dessinés d'après de vraies photos."""
    p, w, k = dict(BASE_COLORS), "#FFFFFF", "#1B1B1B"
    if code == "C2":  # hôpital
        body = blue_square(text(50, 77, "H", 78, w, "DejaVu Sans"), p)
    elif code == "B19":  # autre interdiction, précisée par une inscription
        body = prohibition("".join(text(0, y, t, 9.5, k, "DejaVu Sans", sx=0.9) for y, t in ((-8, "INTERDIT"), (4, "AUX"), (16, "TROUPEAUX"))), p)
    elif code == "J3":  # balise d'intersection : blanche à anneau rouge
        body = svg(40, 100, poly([(9, 100), (9, 14), (20, 3), (31, 14), (31, 100)], w, "#9a9a9a", 1.4) + rect(9, 34, 22, 20, p["red"]))
    else:  # J13 : balise d'obstacle à chevrons bleus et blancs
        bandes = "".join(poly([(8, y), (32, y - 14), (32, y - 2), (8, y + 12)], p["blue"]) for y in range(20, 120, 24))
        body = svg(40, 100, '<clipPath id="c"><rect x="8" y="4" width="24" height="96" rx="3"/></clipPath>' + rect(8, 4, 24, 96, w, rx=3, stroke="#9a9a9a", sw=1.4) + f'<g clip-path="url(#c)">{bandes}</g>')
    return Image.open(__import__("io").BytesIO(cairosvg.svg2png(bytestring=body.encode(), output_height=S))).convert("RGBA")


def marquage(code):
    """Marquage vu de dessus : 1 m = 28 px, centre de l'icône = (0, 0) dans le repère de la route."""
    im = np.zeros((S, S, 4), np.uint8)
    im[:] = (60, 60, 60, 255)
    ppm, rng = 28.0, random.Random(3)
    to_px = lambda p: np.stack([S / 2 + p[:, 0] * ppm, S / 2 - p[:, 1] * ppm], 1)  # noqa: E731
    blanc, jaune = (250, 250, 250, 255), (60, 200, 245, 255)
    trait = lambda x, z0, z1, e=0.24: np.array([[x - e / 2, z0], [x + e / 2, z0], [x + e / 2, z1], [x - e / 2, z1]])  # noqa: E731
    if code == "M_ligne_continue":
        polys = [trait(0, -5, 5)]
    elif code == "M_ligne_discontinue":
        polys = [trait(0, z, z + 1.5) for z in (-4.5, -1.5, 1.5)]
    elif code == "M_ligne_mixte":
        polys = [trait(-0.22, -5, 5)] + [trait(0.22, z, z + 1.5) for z in (-4.5, -1.5, 1.5)]
    elif code == "M_ligne_dissuasion":  # traits longs, intervalles courts
        polys = [trait(0, z, z + 2.3) for z in (-4.8, -1.6, 1.6)]
    elif code == "M_ligne_rive":  # au bord de la chaussée : accotement à droite
        cv2.rectangle(im, (round(S * 0.72), 0), (S, S), (70, 120, 80, 255), -1)
        polys = [trait(1.55, z, z + 1.6) for z in (-4.6, -1.5, 1.6)]
    elif code in ("M_stop_sol", "M_bus"):
        t = text_raster("STOP" if code == "M_stop_sol" else "BUS", rng, 200, 120)
        im[68:188, 28:228][t > 100] = blanc
        return Image.fromarray(im[..., [2, 1, 0, 3]])
    elif code == "M_velo":
        t = bike_raster(rng, 200, 200)
        im[28:228, 28:228][t > 100] = blanc
        return Image.fromarray(im[..., [2, 1, 0, 3]])
    elif code == "M_zigzag":  # ligne jaune en zigzag de l'arrêt de bus : dents serrées, grossies pour rester lisibles
        pts = np.array([[S / 2 + (26 if k % 2 else -26), 30 + k * 196 / 14] for k in range(15)])
        cv2.polylines(im, [np.round(pts * 16).astype(np.int32)], False, jaune, 9, cv2.LINE_AA, shift=4)
        return Image.fromarray(im[..., [2, 1, 0, 3]])
    elif code == "M_vitesse_sol":  # vitesse rappelée sur la chaussée : grands chiffres blancs allongés
        t = text_raster("30", rng, 150, 190)
        im[33:223, 53:203][t > 100] = blanc
        return Image.fromarray(im[..., [2, 1, 0, 3]])
    elif code == "M_livraison":  # emplacement de livraison : contour jaune en tirets, croix et mot LIVRAISON
        a, b_, e = (34, 58), (222, 198), 7
        for k in range(6):  # tirets des deux grands côtés
            x0 = a[0] + k * 33
            cv2.rectangle(im, (x0, a[1]), (min(x0 + 20, b_[0]), a[1] + e), jaune, -1)
            cv2.rectangle(im, (x0, b_[1] - e), (min(x0 + 20, b_[0]), b_[1]), jaune, -1)
        for k in range(4):  # tirets des deux petits côtés
            y0 = a[1] + 8 + k * 33
            cv2.rectangle(im, (a[0], y0), (a[0] + e, min(y0 + 20, b_[1])), jaune, -1)
            cv2.rectangle(im, (b_[0] - e, y0), (b_[0], min(y0 + 20, b_[1])), jaune, -1)
        cv2.line(im, (a[0] + 16, a[1] + 16), (b_[0] - 16, b_[1] - 16), jaune, 5, cv2.LINE_AA)
        cv2.line(im, (a[0] + 16, b_[1] - 16), (b_[0] - 16, a[1] + 16), jaune, 5, cv2.LINE_AA)
        t = text_raster("LIVRAISON", rng, 160, 30)
        cv2.rectangle(im, (44, 110), (212, 146), (60, 60, 60, 255), -1)
        im[113:143, 48:208][t > 100] = jaune
        return Image.fromarray(im[..., [2, 1, 0, 3]])
    else:
        polys = make_local(code, 0.0, 0.0, 3.5, rng, None).polys
        if code == "M_passage_pietons":
            polys = [p * [0.6, 0.6] for p in polys]
        if code in ("M_zebras", "M_zigzag"):
            polys = [p * [1.0, 0.33] for p in polys]
        if code == "M_ligne_feux":  # traits élargis et épaissis pour rester lisibles
            polys = [np.array([[x, -0.17], [x + 0.85, -0.17], [x + 0.85, 0.17], [x, 0.17]]) for x in np.arange(-3.95, 3.5, 1.4)]
    for p in polys:
        cv2.fillPoly(im, [np.round(to_px(np.asarray(p)) * 16).astype(np.int32)], jaune if code == "M_zigzag" else blanc, cv2.LINE_AA, shift=4)
    return Image.fromarray(im[..., [2, 1, 0, 3]])


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


def enregistrer(im, fichier):
    """PNG à palette (96 couleurs, transparence gardée) : quelques kilo-octets par icône."""
    im.quantize(colors=96, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(fichier, optimize=True)


def credits(utilises):
    index = json.loads((ROOT / "data" / "commons_panneaux.json").read_text(encoding="utf-8"))
    lignes = [
        "# Crédits des icônes de panneaux\n",
        "Les icônes des panneaux sont des réductions (256 px) des schémas vectoriels publiés sur",
        "[Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Diagrams_of_road_signs_of_France), dont les modèles",
        "officiels figurent dans l'instruction interministérielle sur la signalisation routière. Chaque schéma reste sous sa",
        "licence d'origine, indiquée ci-dessous ; les icônes qui en sont tirées (réduction, assemblage d'un panneau et de son",
        "panonceau) sont diffusées sous la même licence. Les icônes C2, J3, J13 et B19, celles des marquages au sol, des feux",
        "et des usagers sont dessinées par ce projet (licence du projet).\n",
        "| Icône | Schéma d'origine | Auteur | Licence |",
        "|---|---|---|---|",
    ]
    for code, noms in utilises:
        for n in noms:
            v = index[n]
            url = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(v["titre"].replace(" ", "_"))
            lignes.append(f"| {code} | [{v['titre'].removeprefix('File:')}]({url}) | {v['auteur']} | {v['licence']} |")
    (OUT / "CREDITS.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commons", default=str(ROOT / "datasets_src" / "commons"), help="dossier des rendus PNG des schémas (png/, libre/)")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    for code in ("F_rouge", "F_orange", "F_vert", "U_pieton", "U_cycliste", "U_deux_roues"):
        (OUT / f"{code}.png").write_bytes(cairosvg.svg2png(bytestring=extra_svg(code).encode(), output_height=S))
    app_icons(ROOT / "docs")
    utilises = []
    for c in PANNEAUX:
        if c.code in DESSINES:
            enregistrer(dessin(c.code), OUT / f"{c.code}.png")
        else:
            enregistrer(panneau(c.code, Path(a.commons)), OUT / f"{c.code}.png")
            utilises.append((c.code, sources(c.code)))
    for c in MARQUAGES:
        marquage(c.code).save(OUT / f"{c.code}.png", optimize=True)
    credits(utilises)
    codes = {c.code for c in PANNEAUX + MARQUAGES} | set(FEUX) | {"U_pieton", "U_cycliste", "U_deux_roues"}
    for f in OUT.glob("*.png"):  # icônes d'anciens codes
        if f.stem not in codes:
            f.unlink()
    print(f"{len(PANNEAUX) + len(MARQUAGES)} icônes dans {OUT} ({sum(f.stat().st_size for f in OUT.glob('*.png')) // 1024} Ko)")


if __name__ == "__main__":
    main()
