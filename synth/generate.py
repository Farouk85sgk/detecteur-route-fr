"""Génère le jeu de données YOLO : panneaux et marquages français incrustés dans des scènes routières réelles.

- Fonds : images comma10k préparées par prepare_backgrounds.py (lignes américaines effacées, horizon estimé).
- Marquages : dessinés dans le repère de la route puis projetés (perspective, usure, éclairage, occultations).
- Panneaux : gabarits SVG (route_fr/signs_svg.py) placés en 3D au bord de la route, sur poteau, avec leurres.

Usage : python synth/generate.py --fonds datasets_src/fonds --out datasets/route_fr --train 20000 --val 1500
"""

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cairosvg
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import BY_CODE, MARKING_CODES, NAMES, SIGN_CODES  # noqa: E402
from route_fr.signs_svg import DECOY_KINDS, build, decoy  # noqa: E402
from synth.markings import Camera, longitudinal, make_local, render_alpha  # noqa: E402

ROAD, MOVABLE, MYCAR = 1, 4, 5
OUT = 416  # taille des images générées (échelle d'une inférence en 640 sur une image 16:9)
LOCAL_MARKINGS = [c for c in MARKING_CODES if c not in ("M_ligne_continue", "M_ligne_discontinue", "M_ligne_mixte")]

# dimensions réelles (largeur en m) : gammes miniature / petite / normale / grande
SIGN_WIDTHS = {
    "triangle": ([0.7, 1.0, 1.25], [0.35, 0.5, 0.15]),
    "circle": ([0.45, 0.65, 0.85, 1.05], [0.1, 0.35, 0.45, 0.1]),
    "octagon": ([0.6, 0.8, 0.9], [0.3, 0.5, 0.2]),
    "diamond": ([0.5, 0.7, 0.9], [0.3, 0.5, 0.2]),
    "square": ([0.5, 0.7, 0.9], [0.3, 0.5, 0.2]),
    "zone": ([0.6, 0.8], [0.6, 0.4]),
    "town_h": ([0.35, 0.45, 0.55], [0.3, 0.5, 0.2]),
}


def sign_shape(code):
    if code[0] == "A" or code in ("AB1", "AB2", "AB25", "AB3a"):
        return "triangle"
    if code == "AB4":
        return "octagon"
    if code in ("AB6", "AB7"):
        return "diamond"
    if code[0] == "C":
        return "square"
    if code in ("B30", "B51"):
        return "zone"
    if code in ("EB10", "EB20"):
        return "town_h"
    return "circle"


def rasterize(svg, max_px):
    """SVG -> RGBA float32 (alpha prémultiplié), plus grande dimension ≈ max_px."""
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    w, h = vb[2], vb[3]
    s = max_px / max(w, h)
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=max(4, round(w * s)), output_height=max(4, round(h * s)))
    im = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0
    if im.shape[2] == 3:
        im = np.dstack([im, np.ones(im.shape[:2], np.float32)])
    im[..., :3] *= im[..., 3:4]
    return im, w / h


def warp_rgba(rgba, quad, ss=2):
    """Déforme un RGBA prémultiplié vers le quadrilatère `quad` (TL, TR, BR, BL). Fenêtre non bornée."""
    x0, y0 = np.floor(quad.min(0)).astype(int) - 2
    x1, y1 = np.ceil(quad.max(0)).astype(int) + 2
    if x1 - x0 > 900 or y1 - y0 > 900:
        return None
    h, w = rgba.shape[:2]
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
    dst = ((quad - [x0, y0]) * ss).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(rgba, M, ((x1 - x0) * ss, (y1 - y0) * ss), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return x0, y0, cv2.resize(out, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)


def visible_part(shape, x0, y0, layer, occ=None):
    """Partie visible d'un calque (bornes de l'image et occultants) : (alpha total, alpha visible, fenêtre, calque)."""
    H, W = shape[:2]
    h, w = layer.shape[:2]
    ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    total = float(layer[..., 3].sum())
    if ax1 <= ax0 or ay1 <= ay0 or total <= 0:
        return total, 0.0, None, None
    sub = layer[ay0 - y0 : ay1 - y0, ax0 - x0 : ax1 - x0].copy()
    if occ is not None:
        sub *= 1.0 - occ[ay0:ay1, ax0:ax1, None]
    return total, float(sub[..., 3].sum()), (ax0, ay0, ax1, ay1), sub


def paste(img, x0, y0, layer, occ=None):
    """Compose un calque RGBA prémultiplié ; renvoie la boîte (x0, y0, x1, y1) de sa partie visible ou None."""
    total, vis, win, sub = visible_part(img.shape, x0, y0, layer, occ)
    if win is None:
        return None
    ax0, ay0, ax1, ay1 = win
    a = sub[..., 3:4]
    region = img[ay0:ay1, ax0:ax1].astype(np.float32)
    img[ay0:ay1, ax0:ax1] = np.clip(region * (1 - a) + sub[..., :3] * 255.0, 0, 255).astype(np.uint8)
    box = bbox_of(sub[..., 3], 0.5)
    return None if box is None else (box[0] + ax0, box[1] + ay0, box[2] + ax0, box[3] + ay0)


def bbox_of(alpha, thr=0.5):
    ys, xs = np.nonzero(alpha > thr)
    if len(xs) == 0:
        return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


class Scene:
    """Fond recadré + géométrie caméra + occultants."""

    def __init__(self, img, mask, meta, rng):
        k = rng.uniform(0.55, 1.0)
        img = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        H, W = mask.shape
        f, (u0, v0) = meta["f"] * k, (meta["vp"][0] * k, meta["vp"][1] * k)
        hood = meta["hood"] * k
        cw = min(OUT, W)
        y1 = int(min(H, hood + rng.uniform(-0.02, 0.07) * H))
        y0 = max(0, y1 - OUT)
        # garder l'horizon entre 20 % et 62 % de la hauteur du recadrage
        lo, hi = v0 - 0.62 * (y1 - y0), v0 - 0.20 * (y1 - y0)
        y0 = int(np.clip(y0, max(0, lo), max(0, hi)))
        y1 = min(H, y0 + OUT)
        x0 = rng.randint(0, max(0, W - cw))
        self.img = np.ascontiguousarray(img[y0:y1, x0 : x0 + cw])
        self.mask = np.ascontiguousarray(mask[y0:y1, x0 : x0 + cw])
        self.cam = Camera(f, u0 - x0, v0 - y0, self.img.shape[1], self.img.shape[0])
        # vrais panneaux STOP du fond (identiques au AB4 français), repérés par find_real_stops.py
        self.real = []
        ch = self.img.shape[0]
        for bx0, by0, bx1, by1, _ in meta.get("stops", []):
            b = np.array([bx0 * k - x0, by0 * k - y0, bx1 * k - x0, by1 * k - y0])
            c = np.clip(b, 0, [cw, ch, cw, ch])
            full, inside = (b[2] - b[0]) * (b[3] - b[1]), max(0, c[2] - c[0]) * max(0, c[3] - c[1])
            if full > 0 and inside / full >= 0.6 and min(c[2] - c[0], c[3] - c[1]) >= 8:
                self.real.append((BY_CODE["AB4"], *c))
        self.xl = meta["xl"]
        self.xr = meta["xr"]
        lane_w = (self.xr - self.xl) if (self.xl is not None and self.xr is not None) else rng.uniform(3.0, 3.7)
        self.lane_w = float(np.clip(lane_w, 2.6, 4.3))
        if self.xl is None and self.xr is None:
            c = rng.uniform(-0.3, 0.3)
            self.xl, self.xr = c - self.lane_w / 2, c + self.lane_w / 2
        elif self.xl is None:
            self.xl = self.xr - self.lane_w
        elif self.xr is None:
            self.xr = self.xl + self.lane_w
        # objets mobiles : profondeur estimée par leur point le plus bas
        n, lab, stats, _ = cv2.connectedComponentsWithStats((self.mask == MOVABLE).astype(np.uint8))
        self.movers = []
        for i in range(1, n):
            vb = stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT]
            z = self.cam.z_at_v(vb) if vb > self.cam.v0 + 1 else 1e9
            self.movers.append((z, lab == i))
        self.hood = (self.mask == MYCAR).astype(np.float32)
        self.night = float(cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY).mean()) < 55

    def occluder(self, z):
        occ = self.hood.copy()
        for zm, m in self.movers:
            if zm < z - 0.5:
                occ[m] = 1.0
        return occ


# ----------------------------------------------------------------------------- marquages
def plan_markings(sc, rng):
    """Choisit les marquages de la scène (lignes de la voie + marquages ponctuels)."""
    cam, xl, xr, lw = sc.cam, sc.xl, sc.xr, sc.lane_w
    xc = (xl + xr) / 2
    zb = max(sc.cam.z_bottom, 2.0)
    items = []
    z_end = rng.uniform(70, 160)
    # carrefour : ligne d'effet + annonces, les lignes longitudinales s'arrêtent avant
    if rng.random() < 0.38:
        zi = rng.uniform(zb + 6, 34)
        kind = rng.choice(["stop", "cedez", "feux"])
        if kind == "stop":
            items.append(make_local("M_ligne_stop", xc, zi, lw, rng, cam))
            if rng.random() < 0.6:
                items.append(make_local("M_stop_sol", xc, zi - rng.uniform(3, 7), lw, rng, cam))
        elif kind == "cedez":
            items.append(make_local("M_ligne_cedez", xc, zi, lw, rng, cam))
            if rng.random() < 0.55:
                items.append(make_local("M_triangle_cedez", xc, zi - rng.uniform(4, 9), lw, rng, cam))
        if rng.random() < (0.75 if kind == "feux" else 0.35):
            zp = zi + (rng.uniform(1.2, 3) if kind != "feux" else 0)
            items.append(make_local("M_passage_pietons", xc + rng.uniform(-0.5, 0.5), zp + 2, lw, rng, cam))
            if rng.random() < 0.25:
                items.append(make_local("M_damier", xc, zp + 6.5, lw, rng, cam))
        if rng.random() < 0.4:
            code = rng.choice(["M_fleche_tout_droit", "M_fleche_droite", "M_fleche_gauche", "M_fleche_tout_droit_droite", "M_fleche_tout_droit_gauche"])
            items.append(make_local(code, xc + rng.uniform(-0.2, 0.2), zi - rng.uniform(9, 20), lw, rng, cam))
        z_end = zi - 0.4
    # marquages ponctuels supplémentaires, classes tirées uniformément
    for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
        code = rng.choice(LOCAL_MARKINGS)
        z = rng.uniform(zb + 3, min(z_end - 2, 40)) if z_end > zb + 6 else rng.uniform(zb + 3, 30)
        x = xc + rng.uniform(-0.25, 0.25)
        if code == "M_zigzag":
            x = xr - 0.1
        elif code == "M_velo" and rng.random() < 0.5:
            x = xr - rng.uniform(0.6, 0.9)
        elif code == "M_zebras":
            x = xl - rng.uniform(0.6, 1.6)
        elif code == "M_fleche_rabattement":
            x = xl + rng.uniform(0.6, 1.2) if rng.random() < 0.5 else xc - 0.3
        elif code in ("M_ligne_stop", "M_ligne_cedez", "M_passage_pietons", "M_damier"):
            z_end = min(z_end, z - 0.4)
        items.append(make_local(code, x, z, lw, rng, cam))
    # lignes longitudinales
    if rng.random() < 0.85:
        z0 = 1.5
        style = rng.choices(["M_ligne_continue", "M_ligne_discontinue", "M_ligne_mixte", None], [0.35, 0.4, 0.2, 0.05])[0]
        if style:
            items.append(longitudinal(style, xl, z0, z_end, rng))
        style = rng.choices(["M_ligne_continue", "M_ligne_discontinue", None], [0.3, 0.45, 0.25])[0]
        if style:
            items.append(longitudinal(style, xr, z0, z_end, rng))
        if rng.random() < 0.3:
            items.append(longitudinal(rng.choice(["M_ligne_continue", "M_ligne_discontinue"]), xr + lw, z0, z_end, rng))
        if rng.random() < 0.25:
            items.append(longitudinal(rng.choice(["M_ligne_continue", "M_ligne_discontinue"]), xl - lw, z0, z_end, rng))
    return [m for m in items if m is not None]


def smooth_noise(shape, rng, scale):
    small = rng.random((max(2, shape[0] // scale), max(2, shape[1] // scale))).astype(np.float32)
    return cv2.resize(small, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)


def paint_markings(sc, rng, nrng):
    cam = sc.cam
    road = (sc.mask == ROAD).astype(np.float32)
    road = cv2.GaussianBlur(road, (3, 3), 0.6)
    img = sc.img.astype(np.float32)
    # éclairage local de la chaussée -> teinte de la peinture
    rb = cv2.GaussianBlur(road, (0, 0), 7) + 1e-3
    illum = cv2.GaussianBlur(img * road[..., None], (0, 0), 7) / rb[..., None]
    ratio = rng.uniform(1.7, 3.2) if not sc.night else rng.uniform(1.5, 3.5)
    white = np.clip(illum * ratio + rng.uniform(0, 25), 0, 250)
    yellow = np.clip(illum * ratio * np.array([0.35, 0.85, 1.05]), 0, 250)
    wear_field = smooth_noise(road.shape, nrng, 24) * 0.6 + smooth_noise(road.shape, nrng, 3) * 0.4
    labels = []
    for mk in plan_markings(sc, rng):
        a = render_alpha(cam, mk)
        total = a.sum()
        if total < 4:
            continue
        wear = rng.uniform(0, 0.75) if rng.random() < 0.6 else 0.0
        opacity = rng.uniform(0.7, 0.97)
        av = a * road * opacity * np.clip(1 - wear * wear_field, 0.15, 1)
        if av.sum() / (total * opacity) < 0.35:
            continue
        lab = av.copy()
        if mk.label_zmax:
            vmax = int(cam.v0 + cam.f * cam.h / mk.label_zmax)
            lab[: max(vmax, 0)] = 0
        box = bbox_of(lab, 0.2)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        bw, bh = x1 - x0, y1 - y0
        if mk.label_zmax:  # ligne longitudinale
            too_small = bw < 6 or bh < 8
        elif mk.code in ("M_ligne_stop", "M_ligne_cedez"):
            too_small = bw < 20 or bh < 3
        else:  # trop loin pour être lisible : ni peint ni annoté
            too_small = bw < 10 or bh < 5 or bw * bh < 80
        if too_small:
            continue
        paint = yellow if mk.color == "yellow" else white
        img = img * (1 - av[..., None]) + paint * av[..., None]
        labels.append((BY_CODE[mk.code], x0, y0, x1, y1))
    sc.img = np.clip(img, 0, 255).astype(np.uint8)
    return labels


# ----------------------------------------------------------------------------- panneaux
def sign_corners(cam, X, Yc, Z, wm, hm, yaw, roll):
    out = []
    for dx, dy in ((-wm / 2, hm / 2), (wm / 2, hm / 2), (wm / 2, -hm / 2), (-wm / 2, -hm / 2)):
        rx = dx * math.cos(roll) - dy * math.sin(roll)
        ry = dx * math.sin(roll) + dy * math.cos(roll)
        Xp, Zp, Yp = X + rx * math.cos(yaw), Z + rx * math.sin(yaw), Yc + ry
        out.append((cam.u0 + cam.f * Xp / Zp, cam.v0 + cam.f * (cam.h - Yp) / Zp))
    return np.array(out, np.float32)


def photometric(rgba, sc, rng, region_mean):
    """Accorde l'éclairage et la balance des blancs du panneau à la scène."""
    lum = float(region_mean.mean())
    if sc.night:
        gain = rng.uniform(0.45, 1.35)
    else:
        gain = rng.uniform(0.7, 1.12) * float(np.clip((lum / 120.0) ** 0.5, 0.5, 1.25))
    tint = (region_mean / max(region_mean.mean(), 1e-3)) ** rng.uniform(0.1, 0.4)
    out = rgba.copy()
    out[..., :3] = out[..., :3] * gain * tint[None, None, :]
    if rng.random() < 0.15:  # reflet / éblouissement
        h, w = out.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.3, 0.8) * max(w, h)
        glow = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)) * rng.uniform(0.15, 0.5)
        out[..., :3] += glow[..., None] * out[..., 3:4]
    return np.clip(out, 0, None)


def pole(sc, X, Z, y_top, rng, color, gain):
    cam = sc.cam
    pw = rng.uniform(0.05, 0.09)
    quad = np.array([[X - pw / 2, y_top], [X + pw / 2, y_top], [X + pw / 2, 0.0], [X - pw / 2, 0.0]])
    pts = np.array([(cam.u0 + cam.f * x / Z, cam.v0 + cam.f * (cam.h - y) / Z) for x, y in quad], np.float32)
    w = max(2, int(pts[:, 0].max() - pts[:, 0].min() + 4))
    h = max(2, int(pts[:, 1].max() - pts[:, 1].min() + 4))
    if h > 2000:
        return
    layer = np.zeros((h * 2, w * 2, 4), np.uint8)
    o = pts.min(0) - 2
    cv2.fillPoly(layer, [np.round((pts - o) * 2 * 16).astype(np.int32)], (*[min(255, int(c * gain)) for c in color], 255), cv2.LINE_AA, shift=4)
    layer = cv2.resize(layer, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0  # RGBA prémultiplié
    paste(sc.img, int(o[0]), int(o[1]), layer, sc.occluder(Z))


def foliage(shape, box, rng, nrng):
    """Grappes de feuilles près d'un bord du panneau : (alpha HxW, couleur HxWx3)."""
    H, W = shape[:2]
    x0, y0, x1, y1 = box
    size = max(x1 - x0, y1 - y0)
    alpha = np.zeros((H, W), np.float32)
    side = rng.choice(["left", "right", "top", "bottom"])
    for _ in range(rng.randint(3, 8)):
        cx = {"left": x0, "right": x1}.get(side, rng.uniform(x0, x1)) + rng.gauss(0, 0.15) * size
        cy = {"top": y0, "bottom": y1}.get(side, rng.uniform(y0, y1)) + rng.gauss(0, 0.15) * size
        ax, ay = rng.uniform(0.12, 0.35) * size, rng.uniform(0.12, 0.35) * size
        cv2.ellipse(alpha, (int(cx), int(cy)), (max(1, int(ax)), max(1, int(ay))), rng.uniform(0, 180), 0, 360, 1.0, -1, cv2.LINE_AA)
    alpha *= (nrng.random((H, W)) > rng.uniform(0.1, 0.35)).astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.7)
    base = np.array(rng.choice([(30, 70, 40), (25, 55, 35), (40, 90, 60), (35, 60, 70)]), np.float32)
    color = np.clip(base[None, None, :] * nrng.uniform(0.5, 1.5, (H, W, 1)), 0, 255)
    return alpha, color


def place_objects(sc, rng, nrng):
    """Panneaux annotés et leurres (dos de panneaux, panonceaux, directions...)."""
    cam = sc.cam
    labels = []
    n_signs = rng.choices([0, 1, 2, 3, 4, 5], [0.06, 0.2, 0.3, 0.24, 0.12, 0.08])[0]
    n_decoys = rng.choices([0, 1, 2, 3], [0.35, 0.35, 0.2, 0.1])[0]
    jobs = [("sign", rng.choice(SIGN_CODES)) for _ in range(n_signs)] + [("decoy", rng.choice(DECOY_KINDS)) for _ in range(n_decoys)]
    placed = [tuple(r[1:]) for r in sc.real]
    for kind, what in jobs:
        for _ in range(12):
            if kind == "sign":
                svg = build(what, rng)
                shape = sign_shape(what)
                widths, probs = SIGN_WIDTHS[shape]
                wm = rng.choices(widths, probs)[0] * rng.uniform(0.95, 1.05)
            else:
                svg = decoy(what, rng)
                wm = rng.uniform(0.5, 1.0) if what == "back" else rng.uniform(0.4, 2.2)
            px = math.exp(rng.uniform(math.log(11), math.log(120)))
            vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
            aspect = vb[2] / vb[3]
            if kind == "sign" and what in ("EB10", "EB20"):
                hm = rng.choices(*SIGN_WIDTHS["town_h"])[0]
                wm = hm * aspect
                px = max(px, 14) * aspect
            else:
                hm = wm / aspect
            Z = cam.f * wm / px
            if Z < 3 or Z > 90:
                continue
            side = rng.random()
            if side < 0.72:
                X = sc.xr + rng.uniform(0.6, 3.5)
            elif side < 0.95:
                X = sc.xl - rng.uniform(0.6, 3.5)
            else:
                X = rng.uniform(sc.xl, sc.xr)
            overhead = side >= 0.95
            Yc = rng.uniform(4.8, 6.0) if overhead else rng.uniform(1.4, 2.9) + hm / 2
            yaw = math.radians(rng.gauss(0, 12))
            if kind == "decoy" and what == "back":
                yaw += math.radians(rng.uniform(-20, 20))
            quad = sign_corners(cam, X, Yc, Z, wm, hm, yaw, math.radians(rng.gauss(0, 2)))
            x0, y0 = quad.min(0)
            x1, y1 = quad.max(0)
            if x1 < 4 or y1 < 4 or x0 > cam.w - 4 or y0 > cam.h_img - 4:
                continue
            if any(not (x1 < bx0 - 2 or x0 > bx1 + 2 or y1 < by0 - 2 or y0 > by1 + 2) for bx0, by0, bx1, by1 in placed):
                continue
            placed.append((x0, y0, x1, y1))
            break
        else:
            continue
        size_px = max(quad[:, 0].max() - quad[:, 0].min(), quad[:, 1].max() - quad[:, 1].min())
        rgba, _ = rasterize(svg, int(np.clip(size_px * 2, 32, 360)))
        xa, ya = int(max(0, x0 - 10)), int(max(0, y0 - 10))
        xb, yb = int(min(cam.w, x1 + 10)), int(min(cam.h_img, y1 + 10))
        region = sc.img[ya:yb, xa:xb].reshape(-1, 3).astype(np.float32)
        region_mean = region.mean(0) if len(region) else np.array([120.0, 120.0, 120.0])
        rgba = photometric(rgba, sc, rng, region_mean)
        out = warp_rgba(rgba, quad)
        if out is None:
            continue
        wx, wy, layer = out
        sigma = rng.uniform(0.0, 0.9) + (0.6 if sc.night else 0)
        if sigma > 0.25:
            layer = cv2.GaussianBlur(layer, (0, 0), sigma)
        if rng.random() < 0.4:
            noise = nrng.normal(0, rng.uniform(0.005, 0.03), layer.shape[:2] + (3,)).astype(np.float32)
            layer[..., :3] += noise * layer[..., 3:4]
        occ = sc.occluder(Z)
        leaves = None
        if kind == "sign" and rng.random() < 0.1:  # feuillage masquant une partie du panneau
            leaves = foliage(sc.img.shape, (x0, y0, x1, y1), rng, nrng)
            occ = np.maximum(occ, leaves[0])
        if kind == "sign":  # panneau trop caché ou trop petit : on ne le dessine pas (pas de faux négatif)
            total, vis, win, sub = visible_part(sc.img.shape, wx, wy, layer, occ)
            box = None if win is None else bbox_of(sub[..., 3], 0.5)
            if box is None or vis / total < 0.55 or box[2] - box[0] < 8 or box[3] - box[1] < 8:
                continue
        # poteau puis panneau
        if not overhead and rng.random() < 0.75:
            col = rng.choice([(150, 150, 150), (175, 175, 170), (110, 112, 110), (60, 75, 60), (40, 40, 40)])
            gain = rng.uniform(0.7, 1.15) * float(np.clip(region_mean.mean() / 120.0, 0.3, 1.1))
            pole(sc, X, Z, Yc - hm / 2, rng, col, gain)
        box = paste(sc.img, wx, wy, layer, occ)
        if leaves is not None:
            la = leaves[0][..., None]
            sc.img = (sc.img * (1 - la) + leaves[1] * la).astype(np.uint8)
        if kind == "sign" and box is not None:
            labels.append((BY_CODE[what], *box))
        if kind == "sign" and not overhead and rng.random() < 0.18:  # panonceau sous le panneau
            psvg = decoy("panonceau", rng)
            pvb = [float(x) for x in re.search(r'viewBox="([^"]+)"', psvg).group(1).split()]
            pw = wm * rng.uniform(0.7, 1.0)
            ph = pw * pvb[3] / pvb[2]
            pquad = sign_corners(cam, X, Yc - hm / 2 - 0.04 - ph / 2, Z, pw, ph, yaw, 0)
            prgba, _ = rasterize(psvg, int(np.clip(2 * (pquad[:, 0].max() - pquad[:, 0].min()), 24, 300)))
            pout = warp_rgba(photometric(prgba, sc, rng, region_mean), pquad)
            if pout is not None:
                paste(sc.img, pout[0], pout[1], pout[2], occ)
    return labels


# ----------------------------------------------------------------------------- image complète
def augment(img, rng, nrng):
    if rng.random() < 0.25:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.3, 0.9))
    if rng.random() < 0.12:
        k = rng.choice([3, 5, 7])
        ker = np.zeros((k, k), np.float32)
        ker[k // 2, :] = 1.0 / k
        M = cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), rng.uniform(0, 180), 1)
        img = cv2.filter2D(img, -1, cv2.warpAffine(ker, M, (k, k)))
    if rng.random() < 0.5:
        img = np.clip(img.astype(np.float32) + nrng.normal(0, rng.uniform(1, 6), img.shape), 0, 255).astype(np.uint8)
    if rng.random() < 0.3:
        g = rng.uniform(0.75, 1.35)
        img = (255 * (img / 255.0) ** g).astype(np.uint8)
    return img


def make_sample(job):
    idx, seed, split, names, fonds, out = job
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    meta_all = make_sample.meta
    for _ in range(5):
        name = rng.choice(names)
        img = cv2.imread(f"{fonds}/img/{name}.jpg")
        mask = cv2.imread(f"{fonds}/mask/{name}.png", cv2.IMREAD_GRAYSCALE)
        if img is not None and mask is not None:
            break
    sc = Scene(img, mask, meta_all[name], rng)
    labels = paint_markings(sc, rng, nrng)
    labels += place_objects(sc, rng, nrng)
    labels += sc.real
    final = augment(sc.img, rng, nrng)
    stem = f"{split}_{idx:06d}"
    cv2.imwrite(f"{out}/images/{split}/{stem}.jpg", final, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(60, 95)])
    H, W = final.shape[:2]
    with open(f"{out}/labels/{split}/{stem}.txt", "w") as fh:
        for c, x0, y0, x1, y1 in labels:
            x0, x1 = np.clip([x0, x1], 0, W)
            y0, y1 = np.clip([y0, y1], 0, H)
            if x1 - x0 < 2 or y1 - y0 < 2:
                continue
            fh.write(f"{c} {(x0 + x1) / 2 / W:.6f} {(y0 + y1) / 2 / H:.6f} {(x1 - x0) / W:.6f} {(y1 - y0) / H:.6f}\n")
    return len(labels)


def _init(meta):
    make_sample.meta = meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonds", default="datasets_src/fonds")
    ap.add_argument("--out", default="datasets/route_fr")
    ap.add_argument("--train", type=int, default=20000)
    ap.add_argument("--val", type=int, default=1500)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-peinture", type=float, default=0.001, help="part maximale de peinture résiduelle sur la chaussée")
    a = ap.parse_args()
    meta = json.load(open(f"{a.fonds}/meta.json"))
    # fonds sans STOP douteux et sans peinture résiduelle (passages piétons, textes américains non annotés)
    names = sorted(n for n in meta if not meta[n].get("exclude") and meta[n]["paint"] <= a.max_peinture)
    print(f"{len(names)} fonds utilisables sur {len(meta)}")
    # séparation des fonds train / val (5 % des fonds réservés à la validation)
    is_val = {n: int(hashlib.md5(n.encode()).hexdigest(), 16) % 100 < 5 for n in names}
    split_names = {"train": [n for n in names if not is_val[n]], "val": [n for n in names if is_val[n]]}
    jobs = []
    for split, count in (("train", a.train), ("val", a.val)):
        os.makedirs(f"{a.out}/images/{split}", exist_ok=True)
        os.makedirs(f"{a.out}/labels/{split}", exist_ok=True)
        jobs += [(i, a.seed * 10_000_000 + (0 if split == "train" else 5_000_000) + i, split, split_names[split], a.fonds, a.out) for i in range(count)]
    with open(ROOT / "data" / "route_fr.yaml", "w") as fh:
        fh.write("# Jeu de données synthétique : panneaux et marquages au sol français (généré par synth/generate.py)\n")
        fh.write(f"path: {Path(a.out).resolve()}\ntrain: images/train\nval: images/val\n\nnames:\n")
        fh.writelines(f"  {i}: {n}\n" for i, n in enumerate(NAMES))
    n_obj = 0
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(meta,)) as ex:
        for i, n in enumerate(ex.map(make_sample, jobs, chunksize=16)):
            n_obj += n
            if i % 1000 == 0:
                print(f"{i}/{len(jobs)} images, {n_obj} objets", flush=True)
    print(f"Terminé : {len(jobs)} images, {n_obj} objets annotés")


if __name__ == "__main__":
    main()
