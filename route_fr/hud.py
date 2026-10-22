"""Affichage : cadres sur la vidéo, panneau latéral (limitation en cours, derniers panneaux, explications)."""

import textwrap
import time
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .classes import CATEGORIES, CLASSES, CODE_AFFICHE

HERE = Path(__file__).resolve().parent
FONT = HERE / "fonts" / "DejaVuSans.ttf"
FONT_BOLD = HERE / "fonts" / "DejaVuSans-Bold.ttf"
PANEL_W = 380


@lru_cache(maxsize=2048)
def _text_image(text, size, color, bold):
    """Texte (accents compris, contrairement à cv2.putText) rendu en BGRA, mis en cache."""
    font = ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)
    x0, y0, x1, y1 = font.getbbox(text)
    im = Image.new("RGBA", (max(1, x1 - x0 + 2), max(1, y1 - y0 + 2)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((1 - x0, 1 - y0), text, font=font, fill=(color[2], color[1], color[0], 255))
    return np.array(im)[..., [2, 1, 0, 3]]


def put_text(img, text, org, size=16, color=(255, 255, 255), bold=False, bg=None, pad=3):
    """Écrit `text` avec son coin haut-gauche en `org` ; renvoie la largeur et la hauteur occupées."""
    t = _text_image(text, size, tuple(int(c) for c in color), bold)
    h, w = t.shape[:2]
    x, y = int(org[0]), int(org[1])
    if bg is not None:
        cv2.rectangle(img, (x - pad, y - pad), (x + w + pad, y + h + pad), bg, -1)
    blit(img, t, x, y)
    return w, h


def blit(img, rgba, x, y):
    H, W = img.shape[:2]
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    sub = rgba[y0 - y : y1 - y, x0 - x : x1 - x].astype(np.float32)
    a = sub[..., 3:4] / 255.0
    img[y0:y1, x0:x1] = (img[y0:y1, x0:x1] * (1 - a) + sub[..., :3] * a).astype(np.uint8)


@lru_cache(maxsize=256)
def icon(code, size):
    path = HERE / "icones" / f"{code}.png"
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.shape[2] == 3:
        im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    s = size / max(im.shape[:2])
    return cv2.resize(im, (max(1, round(im.shape[1] * s)), max(1, round(im.shape[0] * s))), interpolation=cv2.INTER_AREA)


def speed_icon(img, value, cx, cy, r):
    """Panneau B14 dessiné avec la vitesse en cours."""
    cv2.circle(img, (cx, cy), r, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), int(r * 0.97), (30, 40, 213), -1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), int(r * 0.76), (255, 255, 255), -1, cv2.LINE_AA)
    txt = str(value)
    size = int(r * (0.95 if len(txt) <= 2 else 0.75))
    t = _text_image(txt, size, (25, 25, 25), True)
    blit(img, t, cx - t.shape[1] // 2, cy - t.shape[0] // 2)


class Hud:
    def __init__(self, show_panel=True, show_markings=True):
        self.show_panel, self.show_markings = show_panel, show_markings
        self.speed, self.speed_code, self.speed_time = None, None, 0.0
        self.events = []  # (instant, indice de classe)

    def on_new(self, cls_idx):
        """Nouvel objet confirmé : ajout à l'historique."""
        now = time.time()
        if not self.events or self.events[-1][1] != cls_idx or now - self.events[-1][0] > 5:
            self.events.append((now, cls_idx))
            self.events = self.events[-40:]

    def update_speed(self, tracks, scale):
        """Mémoire de la vitesse maximale : panneau de vitesse le plus proche, lu avec assez de certitude."""
        best = None
        for t in tracks:
            c = CLASSES[t.cls]
            if (c.vitesse is not None or c.code in ("B33", "B31")) and t.conf >= 0.4 and t.size * scale >= 20:
                best = t if best is None or t.size > best.size else best
        if best is not None:
            c = CLASSES[best.cls]
            if (c.vitesse, c.code) != (self.speed, self.speed_code):
                self.speed, self.speed_code, self.speed_time = c.vitesse, c.code, time.time()

    def draw_tracks(self, img, tracks, scale=1.0):
        for t in tracks:
            c = CLASSES[t.cls]
            if c.categorie == "marquage" and not self.show_markings:
                continue
            color = CATEGORIES[c.categorie][0]
            x1, y1, x2, y2 = (int(v * scale) for v in t.box)
            marking = c.categorie == "marquage"
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 1 if marking else 2, cv2.LINE_AA)
            label = c.nom if marking else f"{c.nom}  {t.conf:.0%}"  # étiquettes compactes pour les marquages
            text_color = (20, 20, 20) if c.categorie in ("zone", "priorite", "marquage") else (255, 255, 255)
            t_img = _text_image(label, 12 if marking else 15, text_color, True)
            ty = y1 - t_img.shape[0] - 6 if y1 - t_img.shape[0] - 6 > 0 else y2 + 4
            cv2.rectangle(img, (x1, ty - 2), (x1 + t_img.shape[1] + 6, ty + t_img.shape[0] + 3), color, -1)
            blit(img, t_img, x1 + 3, ty)

    def panel(self, height, fps, infer_ms, n_tracks, conf, recording):
        p = np.full((height, PANEL_W, 3), (32, 30, 28), np.uint8)
        y = 14
        put_text(p, "Vitesse maximale", (16, y), 18, (230, 230, 230), True)
        y += 34
        if self.speed is not None:
            speed_icon(p, self.speed, 70, y + 52, 52)
            src = next(c for c in CLASSES if c.code == self.speed_code)
            put_text(p, src.nom, (140, y + 22), 15, (210, 210, 210), True)
            put_text(p, f"vu il y a {int(time.time() - self.speed_time)} s", (140, y + 48), 14, (160, 160, 160))
        else:
            cv2.circle(p, (70, y + 52), 52, (90, 90, 90), 2, cv2.LINE_AA)
            put_text(p, "?", (58, y + 30), 40, (120, 120, 120), True)
            msg = "Fin de limitation" if self.speed_code in ("B33", "B31") else "Aucune limitation lue"
            put_text(p, msg, (140, y + 36), 15, (180, 180, 180))
        y += 122
        cv2.line(p, (12, y), (PANEL_W - 12, y), (70, 70, 70), 1)
        y += 12
        put_text(p, "Derniers panneaux et marquages", (16, y), 17, (230, 230, 230), True)
        y += 32
        recent, seen = [], set()
        for t_ev, k in reversed(self.events):
            if k not in seen:
                recent.append((t_ev, k))
                seen.add(k)
        for i, (t_ev, k) in enumerate(recent):
            c = CLASSES[k]
            lines = textwrap.wrap(c.explication, 36) if i == 0 else []
            need = 58 + 19 * len(lines)
            if y + need > height - 92:
                break
            ic = icon(c.code, 50)
            if ic is not None:
                blit(p, ic, 16 + (50 - ic.shape[1]) // 2, y + (50 - ic.shape[0]) // 2)
            color = CATEGORIES[c.categorie][0]
            put_text(p, c.nom, (78, y + 2), 16, (255, 255, 255), True)
            put_text(p, f"{CODE_AFFICHE.get(c.code, c.code)}  ·  {int(time.time() - t_ev)} s", (78, y + 26), 13, color)
            for j, line in enumerate(lines):
                put_text(p, line, (78, y + 50 + 19 * j), 14, (205, 205, 205))
            y += need
        y = height - 84
        cv2.line(p, (12, y), (PANEL_W - 12, y), (70, 70, 70), 1)
        put_text(p, f"{fps:4.1f} img/s   inférence {infer_ms:4.0f} ms   objets {n_tracks}", (16, y + 10), 14, (170, 220, 170))
        put_text(p, f"seuil {conf:.2f}" + ("   ● ENREGISTREMENT" if recording else ""), (16, y + 32), 14, (120, 120, 255) if recording else (170, 170, 170))
        put_text(p, "Q quitter  Espace pause  S capture  R enreg.  M marquages  +/- seuil", (16, y + 56), 12, (140, 140, 140))
        return p

    def compose(self, frame, tracks, scale, fps, infer_ms, conf, recording):
        """Image affichée : vidéo (déjà mise à l'échelle `scale`) annotée + panneau latéral."""
        img = frame.copy()
        self.draw_tracks(img, tracks, scale)
        if not self.show_panel:
            put_text(img, f"{fps:.1f} img/s", (10, 10), 16, (255, 255, 255), True, bg=(0, 0, 0))
            return img
        return np.concatenate([img, self.panel(img.shape[0], fps, infer_ms, len(tracks), conf, recording)], 1)
