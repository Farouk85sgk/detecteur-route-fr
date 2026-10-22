"""Marquages au sol français dessinés dans le repère de la route puis projetés dans l'image.

Repère route : X latéral (m, positif à droite), Z distance devant la caméra (m), sol plat.
Projection (caméra sans roulis) : u = u0 + f X / Z ; v = v0 + f h / Z, (u0, v0) étant le point de fuite.
Les formes locales sont définies en (x, z) mètres, z vers l'avant ; les pointes de flèche visent +z.
"""

import math
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_FILES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


@dataclass
class Camera:
    f: float
    u0: float
    v0: float
    w: int
    h_img: int
    h: float = 1.25  # hauteur de la caméra (m)

    def project(self, X, Z):
        X, Z = np.asarray(X, float), np.asarray(Z, float)
        return self.u0 + self.f * X / Z, self.v0 + self.f * self.h / Z

    def z_at_v(self, v):
        return self.f * self.h / max(v - self.v0, 1e-3)

    @property
    def z_bottom(self):
        """Distance au sol de la dernière ligne de l'image."""
        return self.z_at_v(self.h_img)


@dataclass
class Marking:
    code: str
    polys: list = field(default_factory=list)  # polygones (N, 2) en coordonnées route (X, Z)
    rasters: list = field(default_factory=list)  # (alpha uint8, coins route TL, TR, BR, BL)
    color: str = "white"
    label_zmax: float = 0.0  # lignes longitudinales : on n'annote que la partie Z < label_zmax


# ----------------------------------------------------------------------------- géométrie
def clip_z(poly, zmin):
    """Découpe un polygone (N, 2) par le demi-plan Z >= zmin (Sutherland-Hodgman)."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ina, inb = a[1] >= zmin, b[1] >= zmin
        if ina:
            out.append(a)
        if ina != inb:
            t = (zmin - a[1]) / (b[1] - a[1])
            out.append(a + t * (b - a))
    return np.array(out) if len(out) >= 3 else None


def clip_convex(poly, region):
    """Intersection d'un polygone avec une région convexe (orientation quelconque)."""
    reg = np.asarray(region, float)
    area = np.sum(reg[:, 0] * np.roll(reg[:, 1], -1) - np.roll(reg[:, 0], -1) * reg[:, 1])
    sign = 1 if area > 0 else -1
    out = np.asarray(poly, float)
    for i in range(len(reg)):
        a, b = reg[i], reg[(i + 1) % len(reg)]
        if len(out) < 3:
            return None
        res = []
        for j in range(len(out)):
            p, q = out[j], out[(j + 1) % len(out)]
            sp = sign * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))
            sq = sign * ((b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0]))
            if sp >= 0:
                res.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                res.append(p + t * (q - p))
        out = np.array(res)
    return out if len(out) >= 3 else None


def stroke(points, width):
    """Polygone épaissi autour d'une polyligne (jointures en onglet simplifiées)."""
    pts = np.asarray(points, float)
    d = np.gradient(pts, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([-d[:, 1], d[:, 0]], 1) * width / 2
    return np.concatenate([pts + nrm, (pts - nrm)[::-1]])


def place(poly, xc, zc, mirror=False):
    p = np.asarray(poly, float).copy()
    if mirror:
        p[:, 0] = -p[:, 0]
    p[:, 0] += xc
    p[:, 1] += zc
    return p


def rect_xz(x0, x1, z0, z1):
    return np.array([[x0, z0], [x1, z0], [x1, z1], [x0, z1]], float)


# ----------------------------------------------------------------------------- formes locales (x, z)
def arrow_straight(L, head_w, shaft_w):
    hl = 0.36 * L
    return [rect_xz(-shaft_w / 2, shaft_w / 2, -L / 2, L / 2 - hl + 0.02), np.array([[-head_w / 2, L / 2 - hl], [head_w / 2, L / 2 - hl], [0, L / 2]])]


def _arrow_head(tip, direction, w, length):
    d = np.asarray(direction, float) / np.linalg.norm(direction)
    n = np.array([-d[1], d[0]])
    base = np.asarray(tip) - d * length
    return np.array([tip, base + n * w / 2, base - n * w / 2])


def arrow_turn(L, head_w, shaft_w, right=True, branch=False, rng=None):
    """Flèche tournant à droite ; avec branch=True, flèche tout droit + droite."""
    polys = []
    s = 1 if right else -1
    if branch:
        polys += arrow_straight(L, head_w, shaft_w)
        z0, r = -0.05 * L, 0.18 * L
    else:
        z0, r = 0.10 * L, 0.22 * L
        polys.append(rect_xz(-shaft_w / 2, shaft_w / 2, -L / 2, z0 + 0.01))
    ang = np.linspace(0, math.radians(80), 12)
    arc = np.stack([s * (r - r * np.cos(ang)), z0 + r * np.sin(ang)], 1)
    end = arc[-1]
    d = arc[-1] - arc[-2]
    hl = 0.27 * L
    tip = end + d / np.linalg.norm(d) * hl
    polys.append(stroke(arc, shaft_w))
    polys.append(_arrow_head(tip, d, head_w, hl))
    return polys


def arrow_fold(L, head_w, shaft_w):
    """Flèche de rabattement : longue flèche courbe vers la droite."""
    zs = np.linspace(-L / 2, L / 2 - 0.25 * L, 16)
    t = (zs + L / 2) / (0.75 * L)
    lat = 0.18 * L * t**2
    pts = np.stack([lat, zs], 1)
    d = pts[-1] - pts[-2]
    tip = pts[-1] + d / np.linalg.norm(d) * 0.25 * L
    return [stroke(pts, shaft_w), _arrow_head(tip, d, head_w, 0.25 * L)]


def triangles_row(n, base, height, gap, apex_near=True):
    """Rangée de triangles (dents de requin), pointe vers le conducteur."""
    total = n * base + (n - 1) * gap
    out = []
    for i in range(n):
        x0 = -total / 2 + i * (base + gap)
        if apex_near:
            out.append(np.array([[x0, height / 2], [x0 + base, height / 2], [x0 + base / 2, -height / 2]]))
    return out


# ----------------------------------------------------------------------------- rasters (texte, vélo)
def text_raster(word, rng, w_px, h_px):
    font = ImageFont.truetype(rng.choice(FONT_FILES), 120)
    x0, y0, x1, y1 = font.getbbox(word)
    im = Image.new("L", (x1 - x0 + 20, y1 - y0 + 20), 0)
    ImageDraw.Draw(im).text((10 - x0, 10 - y0), word, fill=255, font=font)
    return cv2.resize(np.array(im), (max(4, int(w_px)), max(4, int(h_px))), interpolation=cv2.INTER_AREA)


def bike_raster(rng, w_px, h_px, rider=True):
    s = 200
    im = np.zeros((s, s), np.uint8)
    t = max(6, s // 28)
    cv2.circle(im, (52, 132), 38, 255, t, cv2.LINE_AA)
    cv2.circle(im, (148, 132), 38, 255, t, cv2.LINE_AA)
    cv2.polylines(im, [np.array([(52, 132), (96, 132), (78, 74), (52, 132)], np.int32)], False, 255, t, cv2.LINE_AA)
    cv2.line(im, (96, 132), (136, 74), 255, t, cv2.LINE_AA)
    cv2.line(im, (78, 74), (136, 74), 255, t, cv2.LINE_AA)
    cv2.line(im, (136, 74), (148, 132), 255, t, cv2.LINE_AA)
    cv2.line(im, (130, 60), (148, 60), 255, t, cv2.LINE_AA)
    cv2.line(im, (136, 74), (136, 60), 255, t, cv2.LINE_AA)
    if rider:
        cv2.circle(im, (124, 18), 14, 255, -1, cv2.LINE_AA)
        cv2.line(im, (76, 62), (114, 34), 255, t + 8, cv2.LINE_AA)
        cv2.line(im, (112, 38), (134, 60), 255, t, cv2.LINE_AA)
        cv2.polylines(im, [np.array([(76, 62), (104, 92), (96, 132)], np.int32)], False, 255, t + 2, cv2.LINE_AA)
    else:
        cv2.line(im, (66, 66), (90, 66), 255, t, cv2.LINE_AA)
    return cv2.resize(im, (max(4, int(w_px)), max(4, int(h_px))), interpolation=cv2.INTER_AREA)


def raster_corners(xc, zc, wm, lm):
    return np.array([[xc - wm / 2, zc + lm / 2], [xc + wm / 2, zc + lm / 2], [xc + wm / 2, zc - lm / 2], [xc - wm / 2, zc - lm / 2]])


def raster_size(cam, xc, zc, wm, lm):
    """Taille de raster adaptée à l'image (≈ 2 px raster par pixel image au plus près)."""
    zn = max(zc - lm / 2, 1.0)
    w_px = 2 * cam.f * wm / zn
    h_px = 2 * cam.f * cam.h * (1 / zn - 1 / (zc + lm / 2))
    return int(np.clip(w_px, 6, 600)), int(np.clip(h_px, 6, 600))


# ----------------------------------------------------------------------------- rendu
def render_alpha(cam, mk, ss=2, zmin=1.2):
    """Couverture (0..1) d'un marquage dans l'image, avec anti-crénelage par sur-échantillonnage."""
    W, H = cam.w * ss, cam.h_img * ss
    canvas = np.zeros((H, W), np.uint8)
    zmin = max(zmin, cam.z_at_v(cam.h_img + 40) if cam.h_img + 40 > cam.v0 else zmin)
    for poly in mk.polys:
        p = clip_z(np.asarray(poly, float), zmin)
        if p is None:
            continue
        u, v = cam.project(p[:, 0], p[:, 1])
        pts = np.stack([u * ss, v * ss], 1)
        if pts[:, 0].max() < -50 or pts[:, 0].min() > W + 50 or pts[:, 1].max() < 0 or pts[:, 1].min() > H + 50:
            continue
        pts = np.clip(pts, -4 * W, 5 * W)
        cv2.fillPoly(canvas, [np.round(pts * 16).astype(np.int32)], 255, cv2.LINE_AA, shift=4)
    for raster, corners in mk.rasters:
        if corners[:, 1].min() < zmin:
            continue
        u, v = cam.project(corners[:, 0], corners[:, 1])
        dst = np.stack([u * ss, v * ss], 1).astype(np.float32)
        h, w = raster.shape
        src = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
        M = cv2.getPerspectiveTransform(src, dst)
        canvas = np.maximum(canvas, cv2.warpPerspective(raster, M, (W, H), flags=cv2.INTER_LINEAR))
    return cv2.resize(canvas, (cam.w, cam.h_img), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


# ----------------------------------------------------------------------------- constructeurs de marquages
LINE_PATTERNS = [(3.0, 10.0), (3.0, 10.0), (1.5, 5.0), (3.0, 3.5), (3.0, 1.33), (20.0, 6.0), (39.0, 13.0), (5.0, 5.0)]


def longitudinal(code, x, z0, z1, rng, width=None):
    """Ligne continue, discontinue ou mixte à la position latérale x, de z0 à z1."""
    width = width or rng.choice([0.10, 0.12, 0.15, 0.15, 0.18, 0.20])
    polys = []

    def dashed(xx, ww, pattern):
        dash, gap = pattern
        z = z0 - rng.uniform(0, dash + gap)
        while z < z1:
            a, b = max(z, z0), min(z + dash, z1)
            if b > a:
                polys.append(rect_xz(xx - ww / 2, xx + ww / 2, a, b))
            z += dash + gap

    if code == "M_ligne_continue":
        polys.append(rect_xz(x - width / 2, x + width / 2, z0, z1))
    elif code == "M_ligne_discontinue":
        dashed(x, width, rng.choice(LINE_PATTERNS))
    else:  # mixte : continue + discontinue côte à côte
        sep = rng.uniform(0.08, 0.16) + width
        side = rng.choice([-1, 1])
        polys.append(rect_xz(x - width / 2, x + width / 2, z0, z1))
        dashed(x + side * sep, width, rng.choice(LINE_PATTERNS[:3]))
    return Marking(code, polys, label_zmax=rng.uniform(38, 46))


def make_local(code, xc, zc, lane_w, rng, cam):
    """Marquage ponctuel centré en (xc, zc) ; retourne un Marking ou None."""
    mk = Marking(code)
    if code.startswith("M_fleche") and code != "M_fleche_rabattement":
        L = rng.uniform(3.5, 7.5)
        hw, sw = rng.uniform(0.55, 0.95), rng.uniform(0.14, 0.24)
        if code == "M_fleche_tout_droit":
            shapes = arrow_straight(L, hw, sw)
        else:
            right = code.endswith("droite")
            shapes = arrow_turn(L, hw, sw, right=right, branch="tout_droit" in code, rng=rng)
        mk.polys = [place(p, xc, zc) for p in shapes]
    elif code == "M_fleche_rabattement":
        L = rng.uniform(6, 10)
        mk.polys = [place(p, xc, zc) for p in arrow_fold(L, rng.uniform(0.6, 0.95), rng.uniform(0.15, 0.24))]
    elif code == "M_triangle_cedez":
        bw, ln = rng.uniform(0.9, 1.5), rng.uniform(2.5, 5.0)
        mk.polys = [place([[-bw / 2, ln / 2], [bw / 2, ln / 2], [0, -ln / 2]], xc, zc)]
    elif code == "M_dents_requin":
        n = rng.randint(3, 7)
        base = min(rng.uniform(0.45, 0.9), (lane_w - 0.3) / n)
        mk.polys = [place(p, xc, zc) for p in triangles_row(n, base, rng.uniform(0.6, 1.4), rng.uniform(0.1, 0.3))]
    elif code == "M_passage_pietons":
        ln = rng.uniform(2.5, 6.0)
        stripe, gap = 0.5, rng.uniform(0.5, 0.8)
        x0, x1 = xc - rng.uniform(0.5, 1.2) * lane_w * 1.5, xc + rng.uniform(0.5, 1.2) * lane_w * 1.5
        x = x0
        while x + stripe < x1:
            mk.polys.append(rect_xz(x, x + stripe, zc - ln / 2, zc + ln / 2))
            x += stripe + gap
    elif code == "M_damier":
        sq = rng.choice([0.5, 0.5, 0.6])
        rows = rng.choice([2, 2, 3])
        n = int(lane_w * rng.uniform(1.0, 2.2) / sq)
        x0 = xc - n * sq / 2
        for r in range(rows):
            for k in range(n):
                if (r + k) % 2 == 0:
                    mk.polys.append(rect_xz(x0 + k * sq, x0 + (k + 1) * sq, zc + r * sq, zc + (r + 1) * sq))
    elif code in ("M_ligne_stop", "M_ligne_cedez"):
        x0, x1 = xc - lane_w / 2, xc + lane_w / 2
        if code == "M_ligne_stop":
            mk.polys.append(rect_xz(x0, x1, zc, zc + 0.5))
        else:
            x = x0 + rng.uniform(0, 0.3)
            while x + 0.5 <= x1:
                mk.polys.append(rect_xz(x, x + 0.5, zc, zc + 0.5))
                x += 1.0
    elif code in ("M_stop_sol", "M_bus"):
        word = "STOP" if code == "M_stop_sol" else "BUS"
        wm = min(lane_w * rng.uniform(0.55, 0.8), 2.6)
        lm = rng.uniform(1.6, 3.2) if word == "STOP" else rng.uniform(1.5, 2.8)
        mk.rasters.append((text_raster(word, rng, *raster_size(cam, xc, zc, wm, lm)), raster_corners(xc, zc, wm, lm)))
    elif code == "M_velo":
        wm = rng.uniform(0.8, 1.4)
        lm = wm * rng.uniform(1.2, 2.2)
        mk.rasters.append((bike_raster(rng, *raster_size(cam, xc, zc, wm, lm), rider=rng.random() < 0.6), raster_corners(xc, zc, wm, lm)))
        if rng.random() < 0.3:  # chevrons d'accompagnement
            for k in range(2):
                z = zc + lm / 2 + 0.4 + 0.5 * k
                mk.polys.append(place(stroke([[-0.35, -0.25], [0, 0.1], [0.35, -0.25]], 0.12), xc, z))
    elif code == "M_zigzag":
        L = rng.uniform(10, 22)
        n = rng.randint(3, 5)
        amp = rng.uniform(0.5, 1.0)
        zs = np.linspace(zc - L / 2, zc + L / 2, 2 * n + 1)
        xs = np.where(np.arange(len(zs)) % 2 == 0, xc, xc - amp)
        for a, b in zip(zip(xs[:-1], zs[:-1]), zip(xs[1:], zs[1:])):
            mk.polys.append(stroke([a, b], 0.13))
        mk.color = "yellow"
    elif code == "M_zebras":
        wz, L = rng.uniform(1.0, 2.8), rng.uniform(10, 28)
        taper = rng.uniform(4, 10)
        region = np.array([[xc - wz / 2, zc - L / 2 + taper], [xc, zc - L / 2], [xc + wz / 2, zc - L / 2 + taper], [xc + wz / 2, zc + L / 2], [xc - wz / 2, zc + L / 2]])
        spacing, sw = rng.uniform(1.0, 2.2), rng.uniform(0.3, 0.5)
        ang = rng.choice([1, -1])
        for z in np.arange(zc - L / 2 - wz, zc + L / 2 + wz, spacing):
            band = np.array([[xc - wz, z - ang * wz], [xc + wz, z + ang * wz], [xc + wz, z + ang * wz + sw], [xc - wz, z - ang * wz + sw]])
            c = clip_convex(band, region)
            if c is not None:
                mk.polys.append(c)
        for a, b in zip(region, np.roll(region, -1, 0)):
            mk.polys.append(stroke([a, b], 0.15))
    else:
        return None
    return mk
