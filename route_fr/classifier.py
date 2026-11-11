"""Second étage : le classifieur dit quel panneau se trouve dans chaque boîte « panneau » du détecteur, ou la rejette
(« autre » : panneau hors catalogue ; « fond » : dos de panneau, publicité, fausse détection...).

Il regarde un carré centré sur la boîte, prolongé vers le bas d'une demi-hauteur : le panonceau placé sous un panneau
en change souvent le sens (sens interdit « sauf vélos », cédez-le-passage « à 150 m »...)."""

import cv2
import numpy as np
import torch

from .classes import BY_CODE
from .detector import DetectMultiBackend  # chemin yolov5 déjà configuré par detector.py

MEAN = np.array([0.485, 0.456, 0.406], np.float32)  # normalisation ImageNet de YOLOv5-cls
STD = np.array([0.229, 0.224, 0.225], np.float32)
W_CLS, H_CLS = 64, 96  # entrée du classifieur (largeur, hauteur)


def fenetre(box, marge=1.15):
    """Zone vue par le classifieur pour une boîte (x1, y1, x2, y2) : carré de côté s (grand côté x marge) centré sur la
    boîte, prolongé de s / 2 vers le bas. Renvoie (x, y, largeur, hauteur)."""
    x1, y1, x2, y2 = box
    s = max(x2 - x1, y2 - y1) * marge
    return (x1 + x2) / 2 - s / 2, (y1 + y2) / 2 - s / 2, s, 1.5 * s


def crops(frame, boxes):
    """Vignettes 64 x 96 des boîtes, comme à l'entraînement (bords de l'image répétés si la zone en sort)."""
    H, W = frame.shape[:2]
    out = np.zeros((len(boxes), H_CLS, W_CLS, 3), np.uint8)
    for i, box in enumerate(boxes):
        x, y, w, h = fenetre(box)
        a, b, c, d = int(round(x)), int(round(y)), int(round(x + w)), int(round(y + h))
        c, d = max(c, a + 2), max(d, b + 3)
        pad = cv2.copyMakeBorder(frame[max(b, 0) : min(d, H), max(a, 0) : min(c, W)], max(0, -b), max(0, d - H), max(0, -a), max(0, c - W), cv2.BORDER_REPLICATE)
        out[i] = cv2.resize(pad, (W_CLS, H_CLS), interpolation=cv2.INTER_AREA if c - a > W_CLS else cv2.INTER_LINEAR)
    return out


class SignClassifier:
    def __init__(self, weights, device):
        self.model = DetectMultiBackend(weights, device=device)
        self.device = device
        names = self.model.names
        names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
        self.map = np.array([BY_CODE.get(n, -1) for n in names])  # indice classifieur -> indice du catalogue (-1 = rejet)

    @torch.inference_mode()
    def __call__(self, frame, boxes):
        """Renvoie (classes du catalogue, probabilités) pour chaque boîte ; classe -1 = à rejeter."""
        if len(boxes) == 0:
            return np.zeros(0, int), np.zeros(0, np.float32)
        x = crops(frame, boxes)[..., ::-1].astype(np.float32) / 255.0
        x = torch.from_numpy(np.ascontiguousarray(((x - MEAN) / STD).transpose(0, 3, 1, 2))).to(self.device)
        logits = self.model(x)
        logits = logits[0] if isinstance(logits, (list, tuple)) else logits
        p = torch.softmax(torch.as_tensor(logits).float(), 1).cpu().numpy()
        k = p.argmax(1)
        return self.map[k], p[np.arange(len(k)), k]
