"""Vignettes de panneaux pour le classifieur de second étage (YOLOv5-cls), au format ImageFolder :
<out>/<train|val>/<classe>/*.jpg, avec une classe « fond » pour rejeter les fausses détections.

Chaque vignette imite un recadrage autour d'une détection : panneau en perspective sur un fond routier réel,
cadrage imprécis, éclairage, flou, bruit et basse résolution (panneaux lointains agrandis).

Usage : python synth/generate_crops.py --fonds datasets_src/fonds --out datasets/panneaux_cls --par-classe 1500
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
from route_fr.signs_svg import DECOY_KINDS, build, decoy, other_sign  # noqa: E402
from synth.generate import foliage, rasterize, warp_rgba  # noqa: E402

SIZE = 64  # taille des vignettes (entrée du classifieur)
CANVAS = 128  # rendu à 2x puis réduction
CLASSES = SIGN_CODES + ["autre", "fond"]  # autre : panneau hors liste ; fond : pas un panneau


def perspective_quad(rng, w, h, cx, cy, size):
    """Coins d'un panneau (rapport w/h) tourné en 3D (lacet, tangage, roulis) puis projeté."""
    yaw, pitch, roll = (math.radians(rng.uniform(-a, a)) for a in (40, 12, 6))
    s = size / max(w, h)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        x, y = dx * math.cos(roll) - dy * math.sin(roll), dx * math.sin(roll) + dy * math.cos(roll)
        x, z = x * math.cos(yaw), x * math.sin(yaw)
        y, z = y * math.cos(pitch) - z * math.sin(pitch), y * math.sin(pitch) + z * math.cos(pitch)
        f = 4.0 * max(w, h)  # focale relative : perspective modérée
        pts.append((cx + s * x * f / (f + z), cy + s * y * f / (f + z)))
    return np.array(pts, np.float32)


def background(rng, fonds, names):
    img = cv2.imread(f"{fonds}/img/{rng.choice(names)}.jpg")
    H, W = img.shape[:2]
    p = int(rng.uniform(20, 200))
    x, y = rng.randint(0, W - p), rng.randint(0, int(H * 0.75) - p)
    return cv2.resize(img[y : y + p, x : x + p], (CANVAS, CANVAS), interpolation=cv2.INTER_LINEAR).astype(np.float32)


def crop_image(svg, rng, nrng, fonds, names, low_min=10, clean=False):
    """Vignette 64 x 64 : `svg` (ou rien, pour une vignette de fond) en perspective sur un fond routier réel.
    `low_min` : résolution minimale simulée (px) ; `clean` : vignette nette (sans voile, flou ni bruit)."""
    canvas = background(rng, fonds, names)
    if svg is not None:
        rgba, aspect = rasterize(svg, 160)
        w, h = (aspect, 1.0) if aspect >= 1 else (1.0, 1 / aspect)
        size = rng.uniform(0.72, 0.98) * CANVAS  # grand côté du panneau : recadrage carré autour de la détection
        c = CANVAS / 2 + nrng.normal(0, 0.05 * CANVAS, 2)
        quad = perspective_quad(rng, w, h, c[0], c[1], size)
        out_w = warp_rgba(rgba, quad)
        if out_w is not None:
            x0, y0, layer = out_w
            lum = canvas.mean()
            gain = rng.uniform(0.45, 1.3) * float(np.clip((lum / 120) ** 0.4, 0.5, 1.2))
            tint = (canvas.reshape(-1, 3).mean(0) / max(lum, 1)) ** rng.uniform(0.1, 0.4)
            layer[..., :3] *= gain * tint
            hh, ww = layer.shape[:2]
            ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + ww, CANVAS), min(y0 + hh, CANVAS)
            sub = layer[ay0 - y0 : ay1 - y0, ax0 - x0 : ax1 - x0]
            a = sub[..., 3:4]
            canvas[ay0:ay1, ax0:ax1] = canvas[ay0:ay1, ax0:ax1] * (1 - a) + sub[..., :3] * 255
            if rng.random() < 0.08:
                alpha, color = foliage(canvas.shape, (ax0, ay0, ax1, ay1), rng, nrng)
                alpha = alpha[..., None] * 0.8
                canvas = canvas * (1 - alpha) + color * alpha
    if not clean and rng.random() < 0.25:  # voile / reflet : couleurs pâlies et désaturées (vitre, soleil, affiche brillante)
        veil = rng.uniform(0.1, 0.45)
        grey = canvas.mean(2, keepdims=True)
        canvas = (canvas * (1 - veil) + 255 * veil) * 0.7 + grey * 0.3 * (1 - veil) + 255 * 0.3 * veil
    img = np.clip(canvas, 0, 255).astype(np.uint8)
    # basse résolution : un panneau lointain occupe peu de pixels avant agrandissement
    low = SIZE if clean else int(np.clip(math.exp(rng.uniform(math.log(low_min), math.log(72))), low_min, SIZE))
    img = cv2.resize(img, (low, low), interpolation=cv2.INTER_AREA)
    if not clean and rng.random() < 0.3:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.3, 0.9))
    if not clean and rng.random() < 0.5:
        img = np.clip(img + nrng.normal(0, rng.uniform(1, 7), img.shape), 0, 255).astype(np.uint8)
    return cv2.resize(img, (SIZE, SIZE), interpolation=cv2.INTER_LINEAR)


def make(job):
    idx, seed, split, cls, fonds, names, out = job
    rng, nrng = random.Random(seed), np.random.default_rng(seed)
    kind = cls
    if cls == "fond":
        kind = rng.choice(DECOY_KINDS + ["patch", "patch", "patch"])
    svg = None
    if kind != "patch":
        svg = other_sign(rng) if cls == "autre" else decoy(kind, rng) if cls == "fond" else build(kind, rng)
    img = crop_image(svg, rng, nrng, fonds, names)
    cv2.imwrite(f"{out}/{split}/{cls}/{idx:06d}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(55, 95)])
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonds", default="datasets_src/fonds")
    ap.add_argument("--out", default="datasets/panneaux_cls")
    ap.add_argument("--par-classe", type=int, default=1500)
    ap.add_argument("--val-par-classe", type=int, default=100)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--seulement", nargs="+", default=None, help="ne générer que ces classes")
    a = ap.parse_args()
    meta = json.load(open(f"{a.fonds}/meta.json"))
    names = sorted(n for n in meta if not meta[n].get("exclude"))
    jobs = []
    for split, n in (("train", a.par_classe), ("val", a.val_par_classe)):
        for k, cls in enumerate(CLASSES):
            if a.seulement and cls not in a.seulement:
                continue
            os.makedirs(f"{a.out}/{split}/{cls}", exist_ok=True)
            count = n * 3 if cls == "fond" else n * 4 if cls == "autre" else n
            jobs += [(i, (k * 1_000_003 + i) * (7 if split == "val" else 1), split, cls, a.fonds, names, a.out) for i in range(count)]
    random.Random(0).shuffle(jobs)
    with ProcessPoolExecutor(a.workers) as ex:
        for i, _ in enumerate(ex.map(make, jobs, chunksize=64)):
            if i % 10000 == 0:
                print(f"{i}/{len(jobs)}", flush=True)
    print(f"Terminé : {len(jobs)} vignettes, {len(CLASSES)} classes")


if __name__ == "__main__":
    main()
