"""Vignettes d'« identités » de panneaux pour le modèle d'empreintes de la version web (« Mes panneaux »).

Une identité = un dessin précis (forme + contenu) : les 67 panneaux connus, et environ 6 500 panneaux composés au
hasard (textes, chiffres, pictogrammes, flèches dans un disque rouge ou bleu, un triangle, un carré bleu ou un
rectangle blanc). Les vignettes
d'une même identité ne diffèrent que par les couleurs, la police, la perspective, le fond, l'éclairage et la
résolution : le modèle apprend à reconnaître « le même panneau » sans connaître la liste des panneaux, et retrouve
donc aussi un panneau qu'il n'a jamais vu, une fois que l'utilisateur l'a photographié.

Une identité sur dix est gardée pour la validation (jamais vue pendant l'entraînement) ; sa première vignette est
nette, comme la photo prise par l'utilisateur pour apprendre un panneau. Les panneaux trop petits pour être lus
(moins de 24 px) ne sont pas simulés : l'appli ne compare que les panneaux assez grands à l'écran.

Usage : python synth/generate_identites.py --fonds datasets_src/fonds --out datasets/empreintes
"""

import argparse
import json
import math
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import SIGN_CODES  # noqa: E402
from route_fr.signs_svg import (  # noqa: E402
    G,
    _blob,
    _font,
    _lights,
    arrow,
    bicycle,
    blue_square,
    build,
    bus,
    car_rear,
    cyclist,
    danger,
    deer,
    fence,
    locomotive,
    moped,
    obligation,
    palette,
    pedestrian,
    prohibition,
    rect,
    roundabout_arrows,
    svg,
    text,
    tractor,
    truck,
)
from synth.generate_crops import crop_image  # noqa: E402

TEXTES = (
    "10 20 25 40 45 60 100 120 3,5t 5,5t 7,5t 12t 19t 26t 2m 2,5m 3m 3,5m 4,3m 10m 50m 150m 300m 1km "
    "FIN STOP BUS TAXI TRAM VÉLO ZONE PÉAGE DOUANE POLICE ÉCOLE SAUF CAR P+R GPL KM/H SOS ZFE"
).split()
TEXTES += ["HALTE|POLICE", "DOUANE|ZOLL", "SAUF|RIVERAINS", "ZONE|BLEUE", "ALLUMEZ|VOS|FEUX", "SAUF|BUS", "SAUF|LIVRAISONS", "ZONE|DE|RENCONTRE"]
_t = random.Random(11)
TEXTES += sorted({str(_t.randint(1, 199)) + _t.choice(["", "", "t", "m", " km", "%"]) for _ in range(260)})  # nombres et unités
TEXTES += sorted({"".join(_t.choice("ABCDEFGHIJKLMNOPRSTUVZ") for _ in range(_t.randint(2, 4))) for _ in range(260)})  # sigles


def _texte(s, color, font):
    lines = s.split("|")
    size = (24 if len(s) <= 3 else 17) if len(lines) == 1 else 11 if len(lines) == 2 else 8.5
    return "".join(text(0, (i - (len(lines) - 1) / 2) * size * 1.15 + size * 0.36, t, size, color, font, sx=0.88) for i, t in enumerate(lines))


def _pictos():
    """Pictogrammes : fonction (couleur, couleur de fond) -> SVG en coordonnées centrées."""
    out = [
        lambda c, w: pedestrian(c),
        lambda c, w: bicycle(c),
        lambda c, w: cyclist(c),
        lambda c, w: G(car_rear(c, w), 0, 0, 1.2),
        lambda c, w: G(truck(c, w), 0, 0, 1.1),
        lambda c, w: deer(c),
        lambda c, w: locomotive(c, w),
        lambda c, w: tractor(c, w),
        lambda c, w: bus(c, w),
        lambda c, w: moped(c),
        lambda c, w: fence(c),
        lambda c, w: roundabout_arrows(c),
    ]
    out += [lambda c, w, a=a: arrow(-16 * math.cos(a), 16 * math.sin(a), 16 * math.cos(a), -16 * math.sin(a), c, 6, 15, 12) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
    out += [lambda c, w, s=s: G(_blob(random.Random(s), c), 0, 0, 1.25) for s in range(600)]
    return out


def identites():
    """Liste de (nom, fonction rng -> SVG). La palette et la police sont tirées à chaque vignette."""
    ids = [(f"k_{code}", lambda rng, code=code: build(code, rng)) for code in SIGN_CODES]
    formes = {
        "int": lambda body, p: prohibition(body(p["black"], p["white"]), p),
        "obl": lambda body, p: obligation(body(p["white"], p["blue"]), p),
        "dan": lambda body, p: danger(G(body(p["black"], p["white"]), 0, 0, 0.8), p),
        "car": lambda body, p: blue_square(G(body(p["white"], p["blue"]), 50, 50), p),
        "bla": lambda body, p: svg(100, 70, rect(1, 1, 98, 68, p["white"], rx=6, stroke=p["black"], sw=3) + G(body(p["black"], p["white"]), 50, 35, 1.1)),
    }
    contenus = [(f"t{i}", lambda rng, s=s: lambda c, w: _texte(s, c, _font(rng))) for i, s in enumerate(TEXTES)]
    pictos = _pictos()
    contenus += [(f"p{i}", lambda rng, f=f: f) for i, f in enumerate(pictos)]
    duo = random.Random(7)
    for i in range(400):  # deux pictogrammes côte à côte
        a, b = duo.sample(pictos[:12], 2)
        contenus.append((f"d{i}", lambda rng, a=a, b=b: lambda c, w: G(a(c, w), -13, 0, 0.62) + G(b(c, w), 13, 0, 0.62)))
    for fname, forme in formes.items():
        for cname, contenu in contenus:
            ids.append((f"{fname}_{cname}", lambda rng, forme=forme, contenu=contenu: forme(contenu(rng), palette(rng))))
    ids.append(("feu", lambda rng: obligation(G(_lights(palette(rng)), 0, 0, 1.4), palette(rng))))
    return ids


IDS = identites()


def make(job):
    k, j, seed, split, fonds, names, out = job
    rng, nrng = random.Random(seed), np.random.default_rng(seed)
    img = crop_image(IDS[k][1](rng), rng, nrng, fonds, names, low_min=24, clean=split == "val" and j == 0)
    cv2.imwrite(f"{out}/{split}/{IDS[k][0]}/{j:03d}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(60, 95)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonds", default="datasets_src/fonds")
    ap.add_argument("--out", default="datasets/empreintes")
    ap.add_argument("--par-identite", type=int, default=12)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    a = ap.parse_args()
    meta = json.load(open(f"{a.fonds}/meta.json"))
    names = sorted(n for n in meta if not meta[n].get("exclude"))
    jobs = []
    for k, (name, _) in enumerate(IDS):
        split = "val" if k % 10 == 9 else "train"
        os.makedirs(f"{a.out}/{split}/{name}", exist_ok=True)
        jobs += [(k, j, k * 1009 + j * 7919 + 13, split, a.fonds, names, a.out) for j in range(a.par_identite)]
    random.Random(0).shuffle(jobs)
    with ProcessPoolExecutor(a.workers) as ex:
        for i, _ in enumerate(ex.map(make, jobs, chunksize=64)):
            if i % 10000 == 0:
                print(f"{i}/{len(jobs)}", flush=True)
    print(f"Terminé : {len(IDS)} identités, {len(jobs)} vignettes")


if __name__ == "__main__":
    main()
