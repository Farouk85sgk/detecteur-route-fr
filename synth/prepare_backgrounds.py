"""Prépare les images routières comma10k (licence MIT) comme fonds pour le jeu de données synthétique.

Pour chaque image : estimation du point de fuite (horizon) à partir des marquages américains, position des lignes
de la voie empruntée, effacement des marquages (inpainting), rejet des images contenant d'autres peintures au sol
non annotées (passages piétons, flèches...). Résultat : <out>/img/*.jpg, <out>/mask/*.png et <out>/meta.json.

Usage : python synth/prepare_backgrounds.py --src datasets_src/c10k --out datasets_src/fonds
"""

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

# classes des masques comma10k (convertis en indices)
ROAD, LANE, UNDRIVABLE, MOVABLE, MYCAR = 1, 2, 3, 4, 5
F_1164 = 910.0  # focale de la caméra EON (images 1164 x 874)
CAM_H = 1.25  # hauteur supposée de la caméra (m)


def lane_lines(mask):
    """Segments de marquages longitudinaux : liste de (point, direction unitaire, longueur)."""
    m = (mask == LANE).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    lines = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 25:
            continue
        ys, xs = np.nonzero(lab == i)
        pts = np.stack([xs, ys], 1).astype(np.float32)
        mean = pts.mean(0)
        cov = np.cov((pts - mean).T)
        evals, evecs = np.linalg.eigh(cov)
        if evals[1] < 1e-6 or evals[1] / max(evals[0], 1e-3) < 9:  # pas assez allongé
            continue
        d = evecs[:, 1]
        length = 4 * np.sqrt(evals[1])
        if abs(d[1]) < 0.12 or length < 15:  # quasi horizontal ou trop court
            continue
        lines.append((mean, d / np.linalg.norm(d), length))
    return lines


def vanishing_point(lines, w, h):
    """Intersection robuste des droites (moindres carrés pondérés après filtrage médian)."""
    if len(lines) < 2:
        return None
    inter = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            p1, d1, l1 = lines[i]
            p2, d2, l2 = lines[j]
            cross = d1[0] * d2[1] - d1[1] * d2[0]
            if abs(cross) < 0.08:  # droites presque parallèles
                continue
            t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / cross
            inter.append(p1 + t * d1)
    if not inter:
        return None
    vp = np.median(np.array(inter), 0)
    for _ in range(2):  # raffinement sur les droites cohérentes
        A, b = np.zeros((2, 2)), np.zeros(2)
        used = 0
        for p, d, length in lines:
            nrm = np.array([-d[1], d[0]])
            if abs(nrm @ (vp - p)) > 0.02 * w:
                continue
            A += length * np.outer(nrm, nrm)
            b += length * nrm * (nrm @ p)
            used += 1
        if used < 2 or abs(np.linalg.det(A)) < 1e-6:
            break
        vp = np.linalg.solve(A, b)
    if not (0.25 * w < vp[0] < 0.75 * w and 0.30 * h < vp[1] < 0.62 * h):
        return None
    return vp


def horizon_from_road(mask, h):
    rows = np.nonzero(((mask == ROAD) | (mask == LANE)).sum(1) > 4)[0]
    if len(rows) == 0:
        return None
    top = rows.min()
    xs = np.nonzero((mask[top : top + 6] == ROAD) | (mask[top : top + 6] == LANE))[1]
    return np.array([xs.mean(), top + 0.004 * h])


def lane_bounds(mask, vp, f):
    """Positions latérales (m) des lignes gauche et droite de la voie, à partir des pixels de marquage proches."""
    ys, xs = np.nonzero(mask == LANE)
    keep = ys > vp[1] + 6
    ys, xs = ys[keep], xs[keep]
    if len(xs) < 30:
        return None, None
    Z = f * CAM_H / (ys - vp[1])
    X = (xs - vp[0]) * Z / f
    near = (Z > 4) & (Z < 22)
    X = X[near]
    left = X[(X < -0.9) & (X > -3.2)]
    right = X[(X > 0.9) & (X < 3.2)]
    xl = float(np.median(left)) if len(left) > 15 else None
    xr = float(np.median(right)) if len(right) > 15 else None
    return xl, xr


def residual_paint(img, mask):
    """Fraction de la chaussée couverte de peinture claire non annotée après effacement des lignes."""
    road = (mask == ROAD).astype(np.uint8)
    if road.sum() < 2000:
        return 1.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    v = hsv[..., 2].astype(np.float32)
    local = cv2.blur(v * road, (41, 41)) / np.maximum(cv2.blur(road.astype(np.float32), (41, 41)), 1e-3)
    bright = (v > local + 45) & (hsv[..., 1] < 70) & (road > 0)
    yellow = (hsv[..., 0] > 15) & (hsv[..., 0] < 35) & (hsv[..., 1] > 90) & (v > local + 20) & (road > 0)
    paint = cv2.morphologyEx((bright | yellow).astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return float(paint.sum()) / float(road.sum())


def process(args):
    img_path, mask_path, out = args
    name = Path(img_path).stem
    img = cv2.imread(img_path)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if img is None or mask is None:
        return None
    h, w = mask.shape
    f = F_1164 * w / 1164.0
    lines = lane_lines(mask)
    vp = vanishing_point(lines, w, h)
    source = "lines"
    if vp is None:
        vp = horizon_from_road(mask, h)
        source = "road"
    if vp is None or not (0.3 * h < vp[1] < 0.62 * h):
        return None
    xl, xr = lane_bounds(mask, vp, f)
    lane = cv2.dilate((mask == LANE).astype(np.uint8), np.ones((5, 5), np.uint8))
    clean = cv2.inpaint(img, lane, 4, cv2.INPAINT_TELEA)
    mask_clean = mask.copy()
    mask_clean[mask == LANE] = ROAD
    paint = residual_paint(clean, mask_clean)
    if paint > 0.004:
        return None
    rows = np.nonzero((mask == MYCAR).sum(1) > 0.3 * w)[0]
    hood = int(rows.min()) if len(rows) else h
    cv2.imwrite(f"{out}/img/{name}.jpg", clean, [cv2.IMWRITE_JPEG_QUALITY, 94])
    cv2.imwrite(f"{out}/mask/{name}.png", mask_clean)
    return name, dict(vp=[round(float(vp[0]), 1), round(float(vp[1]), 1)], f=round(f, 1), xl=xl, xr=xr, hood=hood, vp_source=source, paint=round(paint, 5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="datasets_src/c10k")
    ap.add_argument("--out", default="datasets_src/fonds")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(f"{a.out}/img", exist_ok=True)
    os.makedirs(f"{a.out}/mask", exist_ok=True)
    imgs = sorted(Path(a.src, "jpg").glob("*.jpg"))
    if a.limit:
        imgs = imgs[: a.limit]
    jobs = [(str(p), str(Path(a.src, "mask", p.stem + ".png")), a.out) for p in imgs]
    meta = {}
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(process, jobs, chunksize=8)):
            if r:
                meta[r[0]] = r[1]
            if i % 1000 == 0:
                print(f"{i}/{len(jobs)} conservées: {len(meta)}", flush=True)
    json.dump(meta, open(f"{a.out}/meta.json", "w"))
    print(f"{len(meta)} fonds conservés sur {len(jobs)}")


if __name__ == "__main__":
    main()
