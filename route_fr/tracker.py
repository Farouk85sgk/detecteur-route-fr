"""Stabilisation temporelle des détections : suivi par recouvrement (IoU), vote de classe, lissage des boîtes.

Supprime le scintillement image par image et les fausses détections isolées : un objet n'est confirmé
qu'après `min_hits` détections et reste affiché `max_misses` images après sa dernière détection.
"""

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np


def iou_matrix(a, b):
    """IoU entre deux ensembles de boîtes (x1, y1, x2, y2)."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:4], b[None, :, 2:4])
    inter = np.prod(np.clip(br - tl, 0, None), axis=2)
    area = lambda x: (x[:, 2] - x[:, 0]) * (x[:, 3] - x[:, 1])  # noqa: E731
    return inter / (area(a)[:, None] + area(b)[None, :] - inter + 1e-9)


@dataclass
class Track:
    id: int
    box: np.ndarray
    group: bool  # True = marquage au sol, False = panneau
    scores: dict = field(default_factory=lambda: defaultdict(float))
    conf: float = 0.0
    hits: int = 0
    misses: int = 0
    confirmed: bool = False

    @property
    def cls(self):
        return max(self.scores, key=self.scores.get)

    @property
    def size(self):
        return float(max(self.box[2] - self.box[0], self.box[3] - self.box[1]))


class Stabilizer:
    def __init__(self, is_marking, min_hits=2, max_misses=6, iou_thr=0.25, smooth=0.55, min_sign_px=18):
        self.is_marking = is_marking  # fonction classe -> bool
        self.min_hits, self.max_misses, self.iou_thr, self.smooth = min_hits, max_misses, iou_thr, smooth
        self.min_sign_px = min_sign_px  # un panneau plus petit est trop lointain pour être lu de façon fiable
        self.scale = 1.0  # pixels de l'image -> pixels à l'échelle d'inférence (640)
        self.tracks, self.next_id = [], 1

    def update(self, dets, scale=1.0):
        """dets : (n, 6) x1, y1, x2, y2, conf, cls ; scale : 640 / plus grand côté de l'image.
        Renvoie (pistes confirmées visibles, pistes nouvellement confirmées)."""
        self.scale = scale
        dets = np.asarray(dets, dtype=np.float32).reshape(-1, 6)
        groups = np.array([self.is_marking(int(c)) for c in dets[:, 5]], bool)
        boxes = np.array([t.box for t in self.tracks]).reshape(-1, 4)
        ious = iou_matrix(boxes, dets[:, :4])
        for i, t in enumerate(self.tracks):  # pas d'association entre panneaux et marquages
            ious[i, groups != t.group] = 0
        matched_t, matched_d = set(), set()
        for flat in np.argsort(-ious, axis=None):
            i, j = divmod(int(flat), max(len(dets), 1))
            if ious[i, j] < self.iou_thr:
                break
            if i in matched_t or j in matched_d:
                continue
            matched_t.add(i)
            matched_d.add(j)
            self._hit(self.tracks[i], dets[j])
        for j in range(len(dets)):
            if j not in matched_d:
                t = Track(self.next_id, dets[j, :4].copy(), bool(groups[j]))
                self.next_id += 1
                self._hit(t, dets[j])
                self.tracks.append(t)
                matched_t.add(len(self.tracks) - 1)
        new = []
        for i, t in enumerate(self.tracks):
            if i not in matched_t:
                t.misses += 1
                for c in t.scores:  # oubli progressif des votes
                    t.scores[c] *= 0.9
            elif not t.confirmed and (t.hits >= self.min_hits or t.conf > 0.85) and (t.group or t.size * self.scale >= self.min_sign_px):
                t.confirmed = True
                new.append(t)
        self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]
        return [t for t in self.tracks if t.confirmed], new

    def _hit(self, t, det):
        a = self.smooth if t.hits else 1.0
        t.box = a * det[:4] + (1 - a) * t.box
        t.conf = a * float(det[4]) + (1 - a) * t.conf
        t.scores[int(det[5])] += float(det[4]) * min(1.0, t.size * self.scale / 32)  # les vues lointaines votent moins
        t.hits += 1
        t.misses = 0
