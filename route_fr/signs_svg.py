"""Gabarits vectoriels (SVG) des panneaux français, d'après l'IISR et les affiches ENPC.

Chaque constructeur renvoie un document SVG. Avec `rng`, les couleurs, polices et variantes sont tirées au hasard
(génération du jeu de données) ; sans `rng`, on obtient le rendu de référence (icônes de l'application).
Les pictogrammes sont dessinés dans un repère local centré en (0, 0), d'environ ±18 unités.
"""

from __future__ import annotations

import colorsys
import math

FONTS = ["DejaVu Sans", "Liberation Sans", "FreeSans", "Inter", "Carlito"]
BASE_COLORS = {
    "red": "#D52B1E",
    "blue": "#0A5BAA",
    "yellow": "#FFC72C",
    "black": "#1B1B1B",
    "white": "#FFFFFF",
    "grey": "#8C8C8C",
    "green": "#1E7B3A",
    "amber": "#F5A100",
    "lightgreen": "#19A04A",
}


# ----------------------------------------------------------------------------- couleurs et primitives
def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(max(0, min(255, round(v * 255)))) for v in rgb)


def _jitter(color, rng, dh=0.015, ds=0.12, dv=0.12, fade=0.0):
    r, g, b = (int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + rng.uniform(-dh, dh)) % 1
    s = min(1, max(0, s * (1 + rng.uniform(-ds, ds)) * (1 - fade)))
    v = min(1, max(0, v * (1 + rng.uniform(-dv, dv)) + fade * (1 - v) * 0.6))
    return _hex(colorsys.hsv_to_rgb(h, s, v))


def palette(rng=None):
    """Couleurs du panneau ; aléatoires (vieillissement, décoloration) si rng est fourni."""
    if rng is None:
        return dict(BASE_COLORS)
    fade = rng.uniform(0, 0.45) if rng.random() < 0.3 else rng.uniform(0, 0.1)
    p = {k: _jitter(c, rng, fade=fade) for k, c in BASE_COLORS.items()}
    p["white"] = _jitter("#F4F4F0", rng, dh=0.08, ds=1.0, dv=0.06)
    p["black"] = _jitter("#202020", rng, ds=0.5, dv=0.35)
    return p


def _font(rng):
    return FONTS[0] if rng is None else rng.choice(FONTS)


def _pts(points):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def P(d, c, w, cap="butt", join="round"):
    """Tracé (trait) SVG."""
    return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="{cap}" stroke-linejoin="{join}"/>'


def F(d, c):
    """Forme pleine SVG."""
    return f'<path d="{d}" fill="{c}"/>'


def poly(points, c, stroke=None, sw=0, join="round"):
    s = f' stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="{join}"' if stroke else ""
    return f'<polygon points="{_pts(points)}" fill="{c}"{s}/>'


def circ(x, y, r, c, stroke=None, sw=0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{c}"{s}/>'


def rect(x, y, w, h, c, rx=0, stroke=None, sw=0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx:.2f}" fill="{c}"{s}/>'


def text(x, y, s, size, c, font, weight="bold", sx=1.0, anchor="middle", spacing=0.0):
    """Texte centré en x ; sx < 1 condense horizontalement."""
    s = s.replace("&", "&amp;")
    t = (
        f'<text x="0" y="0" font-family="{font}" font-weight="{weight}" font-size="{size:.2f}" fill="{c}" '
        f'text-anchor="{anchor}" letter-spacing="{spacing:.2f}">{s}</text>'
    )
    return f'<g transform="translate({x:.2f} {y:.2f}) scale({sx:.3f} 1)">{t}</g>'


def G(content, tx=0.0, ty=0.0, s=1.0, sx=None, rot=0.0):
    sx = s if sx is None else sx
    return f'<g transform="translate({tx:.2f} {ty:.2f}) rotate({rot:.2f}) scale({sx:.3f} {s:.3f})">{content}</g>'


def head(tip, direction, w, length, c):
    """Pointe de flèche triangulaire de sommet `tip`, orientée selon `direction` (dx, dy)."""
    dx, dy = direction
    n = math.hypot(dx, dy)
    dx, dy = dx / n, dy / n
    bx, by = tip[0] - dx * length, tip[1] - dy * length
    return poly([tip, (bx - dy * w / 2, by + dx * w / 2), (bx + dy * w / 2, by - dx * w / 2)], c)


def arrow(x0, y0, x1, y1, c, w, hw, hl):
    """Flèche droite de (x0, y0) vers la pointe (x1, y1)."""
    d = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / d, (y1 - y0) / d
    bx, by = x1 - ux * (hl - 0.5), y1 - uy * (hl - 0.5)
    return P(f"M {x0:.2f} {y0:.2f} L {bx:.2f} {by:.2f}", c, w) + head((x1, y1), (ux, uy), hw, hl, c)


def svg(w, h, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w * 4}" height="{h * 4}">{body}</svg>'
    )


# ----------------------------------------------------------------------------- pictogrammes (repère local)
def pedestrian(c, w=1.0):
    """Piéton marchant vers la droite, pieds en y=17, tête vers y=-18."""
    return (
        circ(1.6, -14.4, 3.4, c)
        + P("M 1.1 -9.6 L -0.4 2", c, 5.4 * w, cap="round")
        + P("M -0.4 2 L 4.2 9 L 6.2 16.4", c, 3.7 * w, cap="round")
        + P("M -0.4 2 L -3.6 9.6 L -7.6 15.4", c, 3.7 * w, cap="round")
        + P("M 0.9 -8 L 4.6 -2.6 L 6.8 1.4", c, 2.8 * w, cap="round")
        + P("M 0.9 -8 L -3.1 -3 L -5.6 0.6", c, 2.8 * w, cap="round")
    )


def bicycle(c, w=2.1):
    """Bicyclette de profil (vers la droite), roues centrées en y=6."""
    return (
        circ(-10.5, 6, 6.8, "none", c, w)
        + circ(10.5, 6, 6.8, "none", c, w)
        + P("M -10.5 6 L -1 6 L -4.5 -5 Z M -1 6 L 6.5 -5 L -4.5 -5 M 10.5 6 L 6.5 -5 L 5.8 -9", c, w)
        + P("M 3.2 -9 L 8.6 -9 M -7.3 -7.3 L -1.8 -7.3 M -4.5 -5 L -4.5 -7.3", c, w * 1.1, cap="round")
    )


def cyclist(c):
    return (
        bicycle(c)
        + circ(4.6, -19.6, 3.0, c)
        + P("M -4 -8 L 2.8 -15.2", c, 4.4, cap="round")
        + P("M 2.6 -14.6 L 6.4 -9.6", c, 2.6, cap="round")
        + P("M -4 -8 L 2.6 -1.6 L 0.4 6.4", c, 3.0, cap="round")
    )


def car_rear(c, window):
    """Voiture vue de l'arrière (panneaux B3, B34)."""
    return (
        F("M -7.6 -1.6 Q -7.6 -2.6 -6.2 -2.6 L 6.2 -2.6 Q 7.6 -2.6 7.6 -1.6 L 7.6 5.4 L -7.6 5.4 Z", c)
        + poly([(-6.1, -2.4), (-4.5, -7.8), (4.5, -7.8), (6.1, -2.4)], c)
        + poly([(-4.7, -3.0), (-3.6, -6.7), (3.6, -6.7), (4.7, -3.0)], window)
        + rect(-7.4, 5.0, 3.2, 3.4, c)
        + rect(4.2, 5.0, 3.2, 3.4, c)
    )


def truck(c, window):
    """Camion de profil, cabine à gauche (B8)."""
    return (
        poly([(-17, 6), (-17, -4), (-14, -9), (-7, -9), (-7, 6)], c)
        + poly([(-15.5, -3.6), (-13.2, -7.6), (-8.6, -7.6), (-8.6, -3.6)], window)
        + rect(-6, -12, 23, 18, c)
        + rect(-17, 5.5, 34, 2.6, c)
        + "".join(circ(x, 9, 3.3, c) + circ(x, 9, 1.1, window) for x in (-12, 7, 13.2))
    )


def deer(c):
    """Cerf bondissant vers la gauche (A15b)."""
    return (
        f'<ellipse cx="2" cy="0" rx="9.5" ry="4.6" transform="rotate(-14 2 0)" fill="{c}"/>'
        + P("M -5 -1.5 L -10.5 -8.5", c, 4.2, cap="round")
        + f'<ellipse cx="-12.5" cy="-9.8" rx="3.8" ry="2.3" transform="rotate(22 -12.5 -9.8)" fill="{c}"/>'
        + P("M -11.6 -11.6 L -10.2 -17.5 M -10.8 -14.6 L -7.6 -16.6 M -12.8 -12 L -15.2 -16.8", c, 1.3, cap="round")
        + P("M -5.5 1.5 L -11.5 4.2 L -17.2 2.6", c, 2.2, cap="round")
        + P("M -4 2.6 L -8.6 7.6 L -14 8.6", c, 2.2, cap="round")
        + P("M 8.4 1.5 L 13.6 6.4 L 19 10.2", c, 2.4, cap="round")
        + P("M 9.6 2.6 L 12.6 8.6 L 16.6 13.6", c, 2.4, cap="round")
        + P("M 11 -3 L 13.4 -5.2", c, 1.6, cap="round")
    )


def locomotive(c, window):
    """Locomotive à vapeur tournée vers la gauche (A8)."""
    return (
        rect(-14, -4, 18.5, 8.5, c, rx=2)
        + rect(4, -12, 10.5, 16.5, c)
        + rect(6, -10, 6.5, 4.6, window)
        + rect(2.8, -13.6, 13, 2.2, c)
        + rect(-12.2, -10.5, 4, 7, c)
        + rect(-13.2, -12, 6, 2, c)
        + circ(-8.4, -15.4, 2.4, c)
        + circ(-3.4, -17.2, 3.0, c)
        + circ(2.8, -18.6, 3.4, c)
        + rect(-16.5, 4, 33, 2.4, c)
        + poly([(-16.5, 4), (-19.5, 9.5), (-14.5, 9.5)], c)
        + "".join(circ(x, 7.6, r, c) for x, r in ((-10, 3.0), (-3.2, 3.0), (4.4, 3.6), (11.2, 3.6)))
        + rect(-19.5, 11, 39, 1.4, c)
    )


def fence(c):
    """Barrière de passage à niveau (A7)."""
    return rect(-15, -8.5, 30, 3.2, c) + rect(-15, 3.0, 30, 3.2, c) + "".join(rect(x - 1.3, -11, 2.6, 21, c) for x in (-12.5, -7.5, -2.5, 2.5, 7.5, 12.5))


def roundabout_arrows(c, r=11.0, w=3.6):
    out = []
    for i in range(3):
        a0 = math.radians(100 + 120 * i)
        a1 = a0 + math.radians(68)
        x0, y0 = r * math.cos(a0), -r * math.sin(a0)
        x1, y1 = r * math.cos(a1), -r * math.sin(a1)
        out.append(P(f"M {x0:.2f} {y0 + 1:.2f} A {r} {r} 0 0 0 {x1:.2f} {y1 + 1:.2f}", c, w))
        tx, ty = -math.sin(a1), -math.cos(a1)
        out.append(head((x1 + tx * 4.5, y1 + ty * 4.5 + 1), (tx, ty), 8.5, 7, c))
    return "".join(out)


# ----------------------------------------------------------------------------- formes de panneaux
TRI_SIDE, TRI_BAND = 94.0, 10.2


def _tri(cx, cy, side, up=True):
    r, R = side / (2 * math.sqrt(3)), side / math.sqrt(3)
    if up:
        return [(cx, cy - R), (cx - side / 2, cy + r), (cx + side / 2, cy + r)]
    return [(cx - side / 2, cy - r), (cx + side / 2, cy - r), (cx, cy + R)]


def danger(picto, p, s=1.0, ty=59.0):
    """Panneau de danger : triangle pointe en haut, bordure rouge, fond blanc. viewBox 100 x 90."""
    cy = 88 - 2.5 - TRI_SIDE / (2 * math.sqrt(3))
    inner = TRI_SIDE - 2 * math.sqrt(3) * TRI_BAND
    body = (
        poly(_tri(50, cy, TRI_SIDE), p["white"], p["white"], 5)
        + poly(_tri(50, cy, TRI_SIDE), p["red"], p["red"], 2)
        + poly(_tri(50, cy, inner), p["white"], p["white"], 1.5)
        + G(picto, 50, ty, s)
    )
    return svg(100, 90, body)


def yield_sign(p):
    """AB3a : triangle pointe en bas. viewBox 100 x 90."""
    cy = 2.5 + TRI_SIDE / (2 * math.sqrt(3))
    inner = TRI_SIDE - 2 * math.sqrt(3) * 12.0
    body = (
        poly(_tri(50, cy, TRI_SIDE, False), p["white"], p["white"], 5)
        + poly(_tri(50, cy, TRI_SIDE, False), p["red"], p["red"], 2)
        + poly(_tri(50, cy, inner, False), p["white"], p["white"], 1.5)
    )
    return svg(100, 90, body)


def prohibition(content, p, inner_color=None):
    """Disque à bordure rouge (B). viewBox 100 x 100 ; `content` en coordonnées centrées."""
    body = circ(50, 50, 49.6, p["white"]) + circ(50, 50, 48.2, p["red"]) + circ(50, 50, 37.6, inner_color or p["white"])
    return svg(100, 100, body + G(content, 50, 50))


def red_bar(p, w=7.6, r=37.6):
    a = r * math.cos(math.radians(45)) + 0.6
    return P(f"M {-a:.2f} {-a:.2f} L {a:.2f} {a:.2f}", p["red"], w)


def obligation(content, p):
    """Disque bleu à pictogramme blanc. viewBox 100 x 100."""
    return svg(100, 100, circ(50, 50, 49.6, p["white"]) + circ(50, 50, 48.2, p["blue"]) + G(content, 50, 50))


def end_band(p, rng, r=48.0, w=12.0, hatched=None):
    """Bande diagonale « / » des panneaux de fin (B31, B33, B34)."""
    a = r * math.cos(math.radians(45))
    band = P(f"M {-a:.2f} {a:.2f} L {a:.2f} {-a:.2f}", p["black"], w)
    hatched = (rng is not None and rng.random() < 0.4) if hatched is None else hatched
    if hatched:
        for k in (-0.25, 0.0, 0.25):
            o = k * w / math.sqrt(2) * math.sqrt(2)
            band += P(f"M {-a + o:.2f} {a + o:.2f} L {a + o:.2f} {-a + o:.2f}", p["white"], 0.8)
    return band


def end_sign(content, p, rng, band_w=12.0):
    clip = '<clipPath id="disc"><circle cx="0" cy="0" r="47.5"/></clipPath>'
    body = circ(0, 0, 49.6, p["white"], "#9A9A9A", 0.8) + content + f'<g clip-path="url(#disc)">{end_band(p, rng, w=band_w)}</g>'
    return svg(100, 100, f"<defs>{clip}</defs>" + G(body, 50, 50))


def blue_square(content, p, w=100, h=100):
    return svg(w, h, rect(0.5, 0.5, w - 1, h - 1, p["white"], rx=7) + rect(3.2, 3.2, w - 6.4, h - 6.4, p["blue"], rx=5.5) + content)


def number(n, p, rng, size=None, color=None, y=0.0):
    s = str(n)
    size = size or (45 if len(s) <= 2 else 37)
    sx = 0.86 if len(s) <= 2 else 0.74
    if rng is not None:
        sx *= rng.uniform(0.93, 1.06)
    return text(0, y + size * 0.36, s, size, color or p["black"], _font(rng), sx=sx, spacing=-0.5)


# ----------------------------------------------------------------------------- villes (EB10/EB20)
_PREFIX = ["SAINT-", "SAINTE-", "LE ", "LA ", "LES ", "", "", "", "", "", "", ""]
_ROOTS = [
    "MARTIN", "LUCILLE", "BEAUMONT", "VILLENEUVE", "MONTREUIL", "CHATEAUNEUF", "FONTAINE", "BOURGNEUF", "VILLIERS",
    "NEUVILLE", "BELLEVUE", "ROCHEFORT", "MONTFORT", "PLESSIS", "CHAMPAGNE", "ESCOUBLAC", "SAUMUR", "CHOLET", "LAVAL",
    "VANNES", "ANGERS", "NANTES", "TOURS", "DIJON", "BREST", "PAU", "METZ", "LILLE", "LYON", "NIORT", "BLOIS", "ALBI",
    "AUXERRE", "CHARTRES", "EVREUX", "MELUN", "MEAUX", "SENLIS", "VERNON", "GIEN", "DOLE", "AGEN", "DAX", "RODEZ",
    "QUIMPER", "LORIENT", "PLOERMEL", "REDON", "ANCENIS", "CLISSON", "PORNIC", "GUERANDE", "SAVENAY", "MACHECOUL",
    "BOUAYE", "VERTOU", "REZE", "ORVAULT", "CARQUEFOU", "BLAIN", "NORT", "TREILLIERES", "SUCE", "LIGNE", "MOUZEIL",
    "VALLET", "AIGREFEUILLE", "GETIGNE", "MONTAIGU", "CHALLANS", "LUCON", "FONTENAY", "PARTHENAY", "THOUARS",
]
_SUFFIX = ["", "", "", "", "-SUR-LOIRE", "-EN-BRIE", "-LES-BAINS", "-SUR-MER", "-DE-BRETAGNE", "-LA-FORET", "-LE-ROI"]


def town_name(rng):
    if rng is None:
        return "VILLE"  # icônes : nom générique
    name = rng.choice(_PREFIX) + rng.choice(_ROOTS) + rng.choice(_SUFFIX)
    return name.replace("SAINT-", "ST ").replace("SAINTE-", "STE ") if rng.random() < 0.3 else name


def town_sign(p, rng, exit_sign=False):
    name = town_name(rng)
    font = _font(rng)
    sub = None
    if rng is not None and rng.random() < 0.3:
        sub = "Commune de " + rng.choice(_ROOTS).title()
    h = 30 if sub is None else 38
    w = max(70.0, 9.0 * len(name) + 22)
    border = p["red"] if (rng is None or rng.random() < 0.9) else p["black"]
    body = rect(0.5, 0.5, w - 1, h - 1, p["white"], rx=3.5) + rect(2.2, 2.2, w - 4.4, h - 4.4, "none", rx=2.5, stroke=border, sw=2.6)
    body += text(w / 2, 20.5, name, 13.5, p["black"], font, sx=0.95)
    if sub:
        body += text(w / 2, 31, sub, 6.5, p["black"], font, weight="normal")
    if exit_sign:
        body += P(f"M 6 {h - 5} L {w - 6} 5", p["red"], 2.8)
    return svg(round(w), h, body)


# ----------------------------------------------------------------------------- constructeurs par classe
def _curve(p):
    return P("M -6 17 L -6 1 A 13 13 0 0 1 7 -12 L 12.5 -12", p["black"], 6.2)


def _double_curve(p):
    return P("M -8.5 17 L -8.5 -5.5 L 8.5 7.5 L 8.5 -16", p["black"], 5.8)


def _narrow(p, rng, variant=None):
    c = p["black"]
    variant = variant or ("A3" if rng is None else rng.choice(["A3", "A3", "A3a", "A3b"]))
    left_bend = P("M -10.5 17 L -10.5 6 L -4.5 -2 L -4.5 -16", c, 4.4)
    right_bend = P("M 10.5 17 L 10.5 6 L 4.5 -2 L 4.5 -16", c, 4.4)
    if variant == "A3":
        return left_bend + right_bend
    if variant == "A3a":  # rétrécie par la droite
        return P("M -6.5 17 L -6.5 -16", c, 4.4) + P("M 10.5 17 L 10.5 6 L 2.5 -2 L 2.5 -16", c, 4.4)
    return P("M 6.5 17 L 6.5 -16", c, 4.4) + P("M -10.5 17 L -10.5 6 L -2.5 -2 L -2.5 -16", c, 4.4)


def _slippery(p):
    c = p["black"]
    car = (
        F("M -8.2 -10.5 Q -8.2 -12 -6.6 -12 L 6.6 -12 Q 8.2 -12 8.2 -10.5 L 8.2 -4.5 L -8.2 -4.5 Z", c)
        + poly([(-6.4, -11.8), (-4.6, -17.4), (4.6, -17.4), (6.4, -11.8)], c)
        + poly([(-4.8, -12.4), (-3.6, -16.2), (3.6, -16.2), (4.8, -12.4)], p["white"])
        + rect(-8, -5, 3.4, 3.4, c)
        + rect(4.6, -5, 3.4, 3.4, c)
    )
    tracks = P("M -4.5 -0.5 C -10 5, 1.5 8.5, -4.5 17", c, 2.3) + P("M 4.5 -0.5 C -1 5, 10.5 8.5, 4.5 17", c, 2.3)
    return G(car, 0, 0, 1.0, rot=-10) + tracks


def _children(p):
    c = p["black"]
    big = G(pedestrian(c), -5.5, 17 * (1 - 0.86), 0.86, sx=-0.86)
    small = G(pedestrian(c), 8.5, 17 * (1 - 0.66), 0.66, sx=-0.66)
    return big + small + P("M -1.2 2.8 L 4.4 5.6", c, 1.8, cap="round")


def _crossing(p):
    c = p["black"]
    stripes = "".join(poly([(x, 17), (x + 4.2, 17), (x + 6.4, 10.5), (x + 2.2, 10.5)], c) for x in (-18, -10.8, -3.6, 3.6, 10.8))
    return G(pedestrian(c), 0.5, 10.5 - 17 * 0.78, 0.78) + stripes


def _exclamation(p):
    c = p["black"]
    return poly([(-3.3, -17.5), (3.3, -17.5), (1.9, 7.5), (-1.9, 7.5)], c, c, 1.2) + circ(0, 13.5, 3.2, c)


def _lights(p):
    return (
        rect(-6.8, -18.5, 13.6, 37, p["black"], rx=3.2)
        + circ(0, -10.6, 4.2, p["red"])
        + circ(0, 0, 4.2, p["amber"])
        + circ(0, 10.6, 4.2, p["lightgreen"])
    )


def _two_way(p):
    c = p["black"]
    return arrow(-5.5, -17, -5.5, 17.5, c, 3.8, 10, 9) + arrow(5.5, 17, 5.5, -17.5, c, 3.8, 10, 9)


def _descent(p, rng):
    c = p["black"]
    pct = "10%" if rng is None else rng.choice(["7%", "8%", "10%", "10%", "12%", "15%"])
    ang = math.degrees(math.atan2(20, 34))
    return poly([(-17.5, -9), (17.5, 13), (-17.5, 13)], c) + G(text(0, 0, pct, 10.5, p["white"], _font(rng)), -4.5, 6.4, 1.0, rot=ang)


def _ab2(p):
    c = p["black"]
    return poly([(-3.6, 17), (3.6, 17), (3.6, -8), (6.6, -8), (0, -17.5), (-6.6, -8), (-3.6, -8)], c) + rect(-13, -1.6, 26, 3.2, c)


def _ab6(p, end=False):
    body = poly([(50, 1.5), (98.5, 50), (50, 98.5), (1.5, 50)], p["white"], "#3A3A3A", 0.9) + poly(
        [(50, 15.5), (84.5, 50), (50, 84.5), (15.5, 50)], p["yellow"]
    )
    if end:
        a = 21.5
        body += P(f"M {50 - a} {50 + a} L {50 + a} {50 - a}", p["white"], 13) + P(f"M {50 - a} {50 + a} L {50 + a} {50 - a}", p["black"], 10)
    return svg(100, 100, body)


def _stop(p, rng):
    pts = [(50 + 48.5 * math.cos(math.radians(22.5 + 45 * k)), 50 + 48.5 * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
    inner = [(50 + 44.2 * math.cos(math.radians(22.5 + 45 * k)), 50 + 44.2 * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
    sx = 0.9 if rng is None else rng.uniform(0.82, 0.98)
    body = (
        poly(pts, p["white"], p["white"], 2.4)
        + poly(pts, p["red"])
        + poly(inner, "none", p["white"], 2.2)
        + text(50, 61.5, "STOP", 30, p["white"], _font(rng), sx=sx, spacing=-0.4)
    )
    return svg(100, 100, body)


def _turn_arrow(c, w=5.0, left=True):
    """Flèche montant puis tournant (B2a/B2b), repère du disque."""
    path = P("M 3 21 L 3 1 A 9 9 0 0 0 -6 -8 L -9.5 -8", c, w)
    g = path + head((-19, -8), (-1, 0), 12.5, 10, c)
    return g if left else G(g, sx=-1)


def _uturn(c, w=5.0):
    return P("M 7 21 L 7 -3 A 7.5 7.5 0 0 0 -8 -3 L -8 5", c, w) + head((-8, 15), (0, 1), 12.5, 10.5, c)


def _parking_bans(p, rng, cross=False):
    bar = red_bar(p, 7.4, 37.6)
    content = bar if not cross else bar + G(bar, sx=-1)
    if not cross and rng is not None and rng.random() < 0.25:
        content += text(-8, 2, rng.choice(["1-15", "16-31"]), 9, p["white"], _font(rng), sx=0.9)
    return svg(100, 100, circ(50, 50, 49.6, p["white"]) + circ(50, 50, 48.2, p["red"]) + circ(50, 50, 37.6, p["blue"]) + G(content, 50, 50))


def _b15(p):
    return arrow(-7.5, -21, -7.5, 22, p["black"], 5, 13, 11) + arrow(7.5, 21, 7.5, -22, p["red"], 5, 13, 11)


# flèches blanches des panneaux d'obligation (repère du disque, rayon 48)
def _ob_straight(c, angle=0.0):
    return G(arrow(0, 25, 0, -27, c, 7.4, 21, 15), rot=angle)


def _ob_bent(c, right=True):
    g = P("M -6 26 L -6 0 A 10 10 0 0 1 4 -10 L 9 -10", c, 7.4) + head((25, -10), (1, 0), 21, 15, c)
    return g if right else G(g, sx=-1)


def _ob_straight_or(c, right=True):
    g = arrow(-8, 26, -8, -26, c, 7.2, 19, 14) + P("M -8 10 A 12 12 0 0 1 4 -2 L 9 -2", c, 7.2) + head((25, -2), (1, 0), 19, 14, c)
    return g if right else G(g, sx=-1)


def _ob_left_or_right(c):
    g = P("M 0 26 L 0 4 A 10 10 0 0 1 10 -6 L 12 -6", c, 7.2) + head((26, -6), (1, 0), 18, 13.5, c)
    g += P("M 0 4 A 10 10 0 0 0 -10 -6 L -12 -6", c, 7.2) + head((-26, -6), (-1, 0), 18, 13.5, c)
    return g


def _adult_child(c):
    adult = (
        circ(-6, -15.5, 3.6, c)
        + F("M -10 -11 L -2 -11 L -1.6 3 L -10.4 3 Z", c)
        + rect(-9.8, 2, 3.0, 16, c)
        + rect(-5.2, 2, 3.0, 16, c)
        + P("M -10.6 -10 L -12 2", c, 2.4, cap="round")
    )
    child = circ(7, -4.5, 2.8, c) + F("M 4 -1.5 L 10 -1.5 L 10.3 8 L 3.7 8 Z", c) + rect(4.3, 7.5, 2.4, 10.5, c) + rect(7.3, 7.5, 2.4, 10.5, c)
    return adult + child + P("M -2 -9 L 3.8 0", c, 2.2, cap="round")


def _zone30(p, rng, end=False):
    font = _font(rng)
    w, h = 80, 100
    if not end:
        inner = circ(40, 62, 29.5, p["red"]) + circ(40, 62, 22.8, p["white"]) + G(number(30, p, rng, size=27), 40, 62)
        body = rect(0.5, 0.5, w - 1, h - 1, p["white"], rx=4, stroke="#B03030" if rng is None else p["red"], sw=1.6)
        body += text(40, 24, "ZONE", 15.5, p["black"], font, spacing=2.5) + inner
        return svg(w, h, body)
    clip = f'<clipPath id="c"><rect x="3" y="28" width="{w - 6}" height="{h - 31}"/></clipPath>'
    band = f'<g clip-path="url(#c)">{P(f"M 0 {h} L {w} 0", p["black"], 13)}</g>'
    body = f"<defs>{clip}</defs>" + rect(0.5, 0.5, w - 1, h - 1, p["white"], rx=4, stroke=p["black"], sw=2.2) + band
    body += circ(40, 62, 31.5, p["white"]) + circ(40, 62, 29.5, p["grey"]) + circ(40, 62, 23, p["white"]) + G(number(30, p, rng, size=27), 40, 62)
    body += text(40, 22, "FIN DE ZONE", 10, p["black"], font, sx=0.9, spacing=0.8)
    return svg(w, h, body)


def _impasse(p):
    return blue_square(rect(41.5, 38, 17, 54, p["white"]) + rect(22, 15, 56, 22, p["red"], stroke=p["white"], sw=3.2), p)


def _c18(p):
    return blue_square(arrow(35, 16, 35, 86, p["red"], 9, 22, 17) + arrow(65, 84, 65, 14, p["white"], 9, 22, 17), p)


def _c20a(p):
    c = p["black"]
    stripes = "".join(poly([(x, 80), (x + 4.4, 80), (x + 7, 72), (x + 2.6, 72)], c) for x in (27, 35.5, 44, 52.5, 61))
    body = poly([(50, 9), (91, 84), (9, 84)], p["white"], p["white"], 3) + stripes + G(pedestrian(c), 51, 72 - 17 * 0.92, 0.92)
    return blue_square(body, p)


def _c107(p):
    w = p["white"]
    car = (
        rect(22, 48, 56, 25, w, rx=6)
        + poly([(29, 49), (36, 29), (64, 29), (71, 49)], w)
        + poly([(34, 46.5), (39.4, 33), (60.6, 33), (66, 46.5)], p["blue"])
        + rect(25, 70, 12, 13, w, rx=2)
        + rect(63, 70, 12, 13, w, rx=2)
        + circ(32, 58.5, 4.2, p["blue"])
        + circ(68, 58.5, 4.2, p["blue"])
        + rect(42, 56, 16, 6, p["blue"], rx=1)
    )
    return blue_square(car, p)


def _c207(p):
    w = p["white"]
    body = (
        rect(13, 20, 74, 12, w)
        + rect(13, 32, 7, 10, w)
        + rect(80, 32, 7, 10, w)
        + poly([(15, 90), (46, 90), (47.6, 36), (42, 36)], w)
        + poly([(54, 90), (85, 90), (58, 36), (52.4, 36)], w)
    )
    return blue_square(body, p)


def build(code: str, rng=None) -> str:
    """Document SVG du panneau `code` (voir classes.py)."""
    p = palette(rng)
    c = p["black"]
    if code.startswith("B14_"):
        return prohibition(number(int(code[4:]), p, rng), p)
    simple_danger = {
        "A1a": lambda: _curve(p),
        "A1b": lambda: G(_curve(p), sx=-1),
        "A1c": lambda: _double_curve(p),
        "A1d": lambda: G(_double_curve(p), sx=-1),
        "A2b": lambda: G(F("M -17.5 10 L -11.5 10 C -7.5 10 -6.5 -1 0 -1 C 6.5 -1 7.5 10 11.5 10 L 17.5 10 L 17.5 13.5 L -17.5 13.5 Z", c), 0, 1, 1.05),
        "A3": lambda: _narrow(p, rng),
        "A4": lambda: G(_slippery(p), 0, 0, 1.1),
        "A7": lambda: G(fence(c), 0, 3, 1.1),
        "A8": lambda: G(locomotive(c, p["white"]), 0, 2, 1.0),
        "A13a": lambda: G(_children(p), 0, 0, 1.1),
        "A13b": lambda: G(_crossing(p), 0, 0, 1.1),
        "A14": lambda: _exclamation(p),
        "A15b": lambda: G(deer(c), 0, 1, 1.05),
        "A16": lambda: _descent(p, rng),
        "A17": lambda: _lights(p),
        "A18": lambda: _two_way(p),
        "A21": lambda: G(cyclist(c), 0, 3, 1.05),
        "AB1": lambda: P("M -12 -11.5 L 12 12.5 M -12 12.5 L 12 -11.5", c, 6.6),
        "AB2": lambda: _ab2(p),
        "AB25": lambda: G(roundabout_arrows(c, 12.5, 4.2), 0, 1, 1.0),
    }
    if code in simple_danger:
        return danger(simple_danger[code](), p)
    if code == "AB3a":
        return yield_sign(p)
    if code == "AB4":
        return _stop(p, rng)
    if code in ("AB6", "AB7"):
        return _ab6(p, end=code == "AB7")
    prohibitions = {
        "B0": lambda: "",
        "B2a": lambda: _turn_arrow(c) + red_bar(p),
        "B2b": lambda: _turn_arrow(c, left=False) + red_bar(p),
        "B2c": lambda: _uturn(c) + red_bar(p),
        "B3": lambda: G(car_rear(p["red"], p["white"]), -11.5, 1, 1.45) + G(car_rear(c, p["white"]), 11.5, 1, 1.45),
        "B8": lambda: G(truck(c, p["white"]), 0, 0, 1.4),
        "B9a": lambda: G(pedestrian(c), 0, 0, 1.5),
        "B9b": lambda: G(bicycle(c, 2.4), 0, -1, 1.45),
        "B15": lambda: _b15(p),
    }
    if code in prohibitions:
        return prohibition(prohibitions[code](), p)
    if code == "B1":
        return svg(100, 100, circ(50, 50, 49.6, p["white"]) + circ(50, 50, 48.2, p["red"]) + rect(19, 42, 62, 16, p["white"]))
    if code in ("B6a1", "B6d"):
        return _parking_bans(p, rng, cross=code == "B6d")
    if code == "B31":
        return end_sign("", p, rng)
    if code == "B33":
        n = 50 if rng is None else rng.choice([30, 40, 50, 60, 70, 80, 90, 110])
        return end_sign(number(n, p, rng, color=p["black"]), p, rng, 7.5)
    if code == "B34":
        return end_sign(G(car_rear(p["grey"], p["white"]), -11.5, 1, 1.45) + G(car_rear(p["grey"], p["white"]), 11.5, 1, 1.45), p, rng, 7.5)
    w = p["white"]
    obligations = {
        "B21b": lambda: _ob_straight(w),
        "B21d1": lambda: _ob_bent(w) if rng is None or rng.random() < 0.5 else _ob_straight(w, 90),
        "B21d2": lambda: _ob_bent(w, False) if rng is None or rng.random() < 0.5 else _ob_straight(w, -90),
        "B21c1": lambda: _ob_straight_or(w),
        "B21c2": lambda: _ob_straight_or(w, False),
        "B21e": lambda: _ob_left_or_right(w),
        "B21a1": lambda: _ob_straight(w, 135),
        "B21a2": lambda: _ob_straight(w, -135),
        "B22a": lambda: G(bicycle(w, 2.6), 0, -1, 1.45),
        "B22b": lambda: G(_adult_child(w), 0, 0, 1.45),
    }
    if code in obligations:
        return obligation(obligations[code](), p)
    if code in ("B30", "B51"):
        return _zone30(p, rng, end=code == "B51")
    if code in ("EB10", "EB20"):
        return town_sign(p, rng, exit_sign=code == "EB20")
    if code == "C1a":
        return blue_square(text(50, 76, "P", 76, w, _font(rng)), p)
    if code == "C12":
        return blue_square(poly([(50, 9), (82, 47), (60, 47), (60, 91), (40, 91), (40, 47), (18, 47)], w), p)
    if code == "C13a":
        return _impasse(p)
    if code == "C18":
        return _c18(p)
    if code == "C20a":
        return _c20a(p)
    if code == "C107":
        return _c107(p)
    if code == "C207":
        return _c207(p)
    raise KeyError(code)


# ----------------------------------------------------------------------------- leurres (non annotés)
_PANONCEAUX = ["150 m", "50 m", "300 m", "SAUF RIVERAINS", "SAUF BUS", "RAPPEL", "DÉBUT", "SAUF LIVRAISONS", "STOP 150 m", "CÉDEZ LE PASSAGE", "SORTIE DE CAMIONS", "ÉCOLE", "ACCOTEMENT MEUBLE", "AQUAPLANAGE", "2 km", "SAUF CYCLES", "VOUS N'AVEZ PAS LA PRIORITÉ"]


def decoy(kind: str, rng) -> str:
    """Objets ressemblants à ne pas détecter : dos de panneaux, panonceaux, directions, plaques de rue, publicités."""
    p = palette(rng)
    font = _font(rng)
    if kind == "back":
        grey = _jitter("#A8A8A8", rng, ds=0.5, dv=0.2)
        rim = _jitter("#7A7A7A", rng, ds=0.5, dv=0.2)
        shape = rng.choice(["circle", "triangle", "octagon", "square", "itriangle"])
        if shape == "circle":
            body = circ(50, 50, 48, grey, rim, 2.5)
        elif shape == "square":
            body = rect(2, 2, 96, 96, grey, rx=6, stroke=rim, sw=2.5)
        elif shape == "octagon":
            pts = [(50 + 47 * math.cos(math.radians(22.5 + 45 * k)), 50 + 47 * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
            body = poly(pts, grey, rim, 2.5)
        else:
            body = poly(_tri(50, 56 if shape == "triangle" else 33, 92, shape == "triangle"), grey, rim, 3)
        body += rect(44, 30, 12, 40, rim) + rect(30, 34, 40, 5, rim) + rect(30, 61, 40, 5, rim)
        return svg(100, 100, body)
    if kind == "panonceau":
        t = rng.choice(_PANONCEAUX)
        w = max(40.0, 5.6 * len(t) + 10)
        two = len(t) > 14 and " " in t
        h = 24 if two else 16
        body = rect(0.5, 0.5, w - 1, h - 1, p["white"], rx=2, stroke=p["black"], sw=1.2)
        if two:
            a, b = t.split(" ", 1)
            body += text(w / 2, 10.5, a, 7.5, p["black"], font) + text(w / 2, 20, b, 7.5, p["black"], font)
        else:
            body += text(w / 2, 11.5, t, 8.5, p["black"], font)
        return svg(round(w), h, body)
    if kind == "direction":
        bg, fg = rng.choice([(p["white"], p["black"]), (p["green"], p["white"]), (p["blue"], p["white"]), (p["white"], p["black"])])
        lines = [town_name(rng).title() for _ in range(rng.randint(1, 3))]
        w = max(60.0, 6.2 * max(len(s) for s in lines) + 24)
        h = 8 + 13 * len(lines)
        tip = rng.random() < 0.5
        body = (
            poly([(1, 1), (w - 14, 1), (w - 1, h / 2), (w - 14, h - 1), (1, h - 1)], bg, fg, 1.4)
            if tip
            else rect(1, 1, w - 2, h - 2, bg, rx=3, stroke=fg, sw=1.4)
        )
        for i, s in enumerate(lines):
            body += text(8, 15 + 13 * i, s, 10, fg, font, anchor="start")
            if rng.random() < 0.5:
                body += text(w - 18, 15 + 13 * i, f"{rng.randint(1, 60)}", 9, fg, font)
        return svg(round(w), round(h), body)
    if kind == "street":
        t = "RUE " + rng.choice(["DE LA PAIX", "VICTOR HUGO", "JEAN JAURÈS", "DU MOULIN", "DES ÉCOLES", "PASTEUR", "DE LA GARE"])
        w = 5.8 * len(t) + 14
        body = rect(0.5, 0.5, w - 1, 21, p["blue"], rx=2, stroke=p["white"], sw=1.6) + text(w / 2, 14.5, t, 9, p["white"], font)
        return svg(round(w), 22, body)
    if kind == "cartouche":
        t, bg, fg = rng.choice([("N " + str(rng.randint(1, 165)), p["red"], p["white"]), ("D " + str(rng.randint(1, 999)), p["yellow"], p["black"]), ("A " + str(rng.randint(1, 89)), p["red"], p["white"]), ("E " + str(rng.randint(1, 80)), p["green"], p["white"])])
        return svg(44, 20, rect(0.5, 0.5, 43, 19, bg, rx=2.5) + text(22, 14.5, t, 12, fg, font))
    # publicité / enseigne
    bg = _jitter(rng.choice(["#E63946", "#F1FAEE", "#2A9D8F", "#E9C46A", "#264653", "#F4A261", "#6A4C93"]), rng)
    w, h = rng.uniform(60, 140), rng.uniform(30, 80)
    body = rect(0, 0, w, h, bg, rx=rng.uniform(0, 6))
    body += text(w / 2, h / 2 + 5, rng.choice(["PROMO", "BOULANGERIE", "PHARMACIE", "GARAGE", "SOLDES", "HOTEL", "TABAC"]), 13, rng.choice(["#FFFFFF", "#111111", "#FFD700"]), font)
    return svg(round(w), round(h), body)


DECOY_KINDS = ["back", "back", "panonceau", "direction", "street", "cartouche", "ad"]


# ----------------------------------------------------------------------------- panneaux hors liste (classe « autre »)
_OTHER_TEXTS = ["HALTE|POLICE", "DOUANE|ZOLL", "PÉAGE", "INTERDIT|AUX|TROUPEAUX", "ALLUMEZ|VOS|FEUX", "FIN", "SAUF|RIVERAINS", "ZONE|BLEUE"]


def _blob(rng, c, r=15.0):
    """Silhouette aléatoire lisse (pictogramme inconnu)."""
    k = [(rng.uniform(0.05, 0.3), rng.uniform(0, 6.28)) for _ in range(4)]
    sx = rng.uniform(0.8, 1.5)
    pts = []
    for i in range(48):
        t = 6.283 * i / 48
        rr = r * (1 + sum(a * math.sin((j + 2) * t + ph) for j, (a, ph) in enumerate(k)))
        pts.append((sx * rr * math.cos(t), rr * math.sin(t)))
    return poly(pts, c)


def tractor(c, hole):
    """Tracteur de profil (B9e)."""
    return (
        circ(-8, 5, 8.5, c) + circ(-8, 5, 3.2, hole) + circ(11, 8.5, 5, c) + circ(11, 8.5, 1.8, hole)
        + rect(-4, -3, 19, 7, c) + P("M -13 -2 L -13 -13 L -3 -13 L -3 -2", c, 2.4) + P("M 8 -3 L 8 -10", c, 2)
    )


def bus(c, window):
    """Autocar de profil (B9f)."""
    return rect(-18, -9, 36, 15, c, rx=2.5) + "".join(rect(x, -6.5, 5.5, 5, window) for x in (-15, -8.5, -2, 4.5)) + circ(-10, 7, 3.4, c) + circ(11, 7, 3.4, c)


def moped(c):
    """Cyclomoteur (B9g)."""
    return bicycle(c) + rect(-6, 0, 9, 5.5, c, rx=1.5) + rect(-9, -9.5, 7, 2.5, c)


def other_sign(rng) -> str:
    """Panneau français absent de la liste (gabarit, poids, vitesse minimale, textes, pictogrammes inconnus).
    Sert à apprendre au classifieur à ne pas forcer ces panneaux dans une classe connue."""
    p = palette(rng)
    c, w, font = p["black"], p["white"], _font(rng)
    kind = rng.choice(["unit", "unit", "text", "text_band", "text_band", "vehicle", "vehicle", "combo", "blob", "blob", "blue_number", "square_number", "misplaced"])
    if kind == "text_band":  # B4, B5a : deux mots séparés par une barre noire
        top, bottom = rng.choice([("HALTE", "POLICE"), ("DOUANE", "ZOLL"), ("HALTE", "GENDARMERIE"), ("DOUANE", "DOGANA"), ("PÉAGE", "STOP")])
        body = text(0, -8, top, 11, c, font, sx=0.9) + rect(-26, -3, 52, 6, c, rx=3) + text(0, 17, bottom, 11, c, font, sx=0.85)
        return prohibition(body, p)
    if kind == "vehicle":  # B9d à B9g... : autres catégories de véhicules
        body = rng.choice([tractor(c, w), bus(c, w), moped(c), G(car_rear(c, w), 0, -6, 1.1) + G(moped(c), 0, 9, 0.55)])
        return prohibition(G(body, 0, 0, rng.uniform(1.0, 1.3)), p)
    if kind == "unit":  # B10a à B13a, B17 : longueur, largeur, hauteur, poids, distance
        val = rng.choice(["2", "2,5", "3", "3,5", "4,3", "5,5", "7,5", "10", "12", "19", "26"]) + rng.choice(["t", "m", " t", " m"])
        if rng.random() < 0.2:
            val = f"{rng.choice([50, 70, 100, 150])}m"
        body = text(0, 8, val, 25 if len(val) <= 3 else 19, c, font, sx=0.85)
        if rng.random() < 0.35:  # flèches de gabarit
            body += head((-34, 0), (-1, 0), 9, 7, c) + head((34, 0), (1, 0), 9, 7, c) if rng.random() < 0.5 else head((0, -34), (0, -1), 9, 7, c) + head((0, 34), (0, 1), 9, 7, c)
        return prohibition(body, p)
    if kind == "text":
        lines = rng.choice(_OTHER_TEXTS).split("|")
        size = 15 if len(lines) == 1 else 11 if len(lines) == 2 else 8.5
        body = "".join(text(0, (i - (len(lines) - 1) / 2) * size * 1.15 + size * 0.36, s, size, c, font, sx=0.9) for i, s in enumerate(lines))
        return prohibition(body, p) if rng.random() < 0.7 else obligation(body.replace(f'fill="{c}"', f'fill="{w}"'), p)
    if kind == "combo":  # B3a, B7b... : deux véhicules
        left = rng.choice([truck(p["red"], w), car_rear(p["red"], w), bicycle(c)])
        right = rng.choice([car_rear(c, w), truck(c, w), pedestrian(c)])
        return prohibition(G(left, -12, 1, 0.75) + G(right, 12, 1, 0.75), p)
    if kind == "blob":
        body = _blob(rng, c)
        if rng.random() < 0.6:
            return danger(body, p) if rng.random() < 0.5 else prohibition(G(body, s=1.3), p)
        return obligation(G(_blob(rng, w), s=1.3), p)
    if kind == "blue_number":  # B25 vitesse minimale
        return obligation(number(rng.choice([30, 40, 50, 60, 80, 90]), p, rng, color=w), p)
    if kind == "square_number":  # C4a / C4b vitesse conseillée
        body = G(number(rng.choice([30, 40, 50, 70]), p, rng, size=55, color=w), 50, 50)
        if rng.random() < 0.4:
            body += P("M 12 88 L 88 12", p["red"], 8)
        return blue_square(body, p)
    misplaced = [
        lambda: prohibition(G(deer(c), s=1.2), p),
        lambda: prohibition(G(locomotive(c, w), s=1.1), p),
        lambda: prohibition(G(_lights(p), s=0.9), p),
        lambda: prohibition(G(fence(c), s=1.2), p),
        lambda: danger(G(truck(c, w), 0, 2, 0.8), p),
        lambda: obligation(G(deer(w), s=1.2), p),
        lambda: obligation(G(truck(w, p["blue"]), s=1.2), p),
    ]
    return rng.choice(misplaced)()
