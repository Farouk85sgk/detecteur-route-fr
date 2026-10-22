"""Second étage : un classifieur YOLOv5-cls reclasse chaque panneau détecté à partir d'une vignette carrée,
et écarte les fausses détections (classe « fond » : dos de panneaux, directions, publicités...)."""

import cv2
import numpy as np
import torch

from .classes import BY_CODE
from .detector import DetectMultiBackend  # chemin yolov5 déjà configuré par detector.py

MEAN = np.array([0.485, 0.456, 0.406], np.float32)  # normalisation ImageNet de YOLOv5-cls
STD = np.array([0.229, 0.224, 0.225], np.float32)


def square_crops(frame, boxes, size=64, margin=1.15):
    """Vignettes carrées centrées sur les boîtes (grand côté x margin), comme à l'entraînement."""
    H, W = frame.shape[:2]
    out = np.zeros((len(boxes), size, size, 3), np.uint8)
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        cx, cy, s = (x1 + x2) / 2, (y1 + y2) / 2, max(x2 - x1, y2 - y1) * margin
        a, b = int(round(cx - s / 2)), int(round(cy - s / 2))
        n = max(2, int(round(s)))
        pad = cv2.copyMakeBorder(frame[max(b, 0) : min(b + n, H), max(a, 0) : min(a + n, W)], max(0, -b), max(0, b + n - H), max(0, -a), max(0, a + n - W), cv2.BORDER_REPLICATE)
        out[i] = cv2.resize(pad, (size, size), interpolation=cv2.INTER_AREA if n > size else cv2.INTER_LINEAR)
    return out


class SignClassifier:
    def __init__(self, weights, device, size=64):
        self.model = DetectMultiBackend(weights, device=device)
        self.size, self.device = size, device
        names = self.model.names
        names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
        self.map = np.array([BY_CODE.get(n, -1) for n in names])  # indice classifieur -> indice global (-1 = fond)

    @torch.inference_mode()
    def __call__(self, frame, boxes):
        """Renvoie (classes globales, probabilités) pour chaque boîte ; classe -1 = fausse détection."""
        if len(boxes) == 0:
            return np.zeros(0, int), np.zeros(0, np.float32)
        crops = square_crops(frame, boxes, self.size)[..., ::-1].astype(np.float32) / 255.0
        x = torch.from_numpy(np.ascontiguousarray(((crops - MEAN) / STD).transpose(0, 3, 1, 2))).to(self.device)
        logits = self.model(x)
        logits = logits[0] if isinstance(logits, (list, tuple)) else logits
        p = torch.softmax(torch.as_tensor(logits).float(), 1).cpu().numpy()
        k = p.argmax(1)
        return self.map[k], p[np.arange(len(k)), k]
