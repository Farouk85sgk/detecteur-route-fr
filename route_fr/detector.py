"""Détecteur YOLOv5 (code du dépôt ultralytics/yolov5) : PyTorch, ONNX, OpenVINO, TensorRT, CoreML...

Optionnellement suivi d'un classifieur de panneaux (second étage, voir classifier.py) qui affine la classe exacte
de chaque panneau détecté et écarte les fausses détections.
"""

import sys
from pathlib import Path

import numpy as np
import torch

YOLOV5_DIR = Path(__file__).resolve().parents[1] / "yolov5"
if str(YOLOV5_DIR) not in sys.path:
    sys.path.insert(0, str(YOLOV5_DIR))

from models.common import DetectMultiBackend  # noqa: E402
from utils.augmentations import letterbox  # noqa: E402
from utils.general import check_img_size, non_max_suppression, scale_boxes  # noqa: E402
from utils.torch_utils import select_device  # noqa: E402

from .classes import CLASSES  # noqa: E402

IS_SIGN = np.array([c.categorie != "marquage" for c in CLASSES])
SIGN_VEC = torch.from_numpy(IS_SIGN.astype(np.float32))
SIGN0 = int(np.argmax(IS_SIGN))  # colonne qui porte la pseudo-classe « panneau »


def nms_agnostic(d, iou=0.5):
    """Suppression des doublons toutes classes confondues (panneaux reclassés par le second étage)."""
    order, keep = np.argsort(-d[:, 4]), []
    while len(order):
        i, order = order[0], order[1:]
        keep.append(i)
        tl = np.maximum(d[i, :2], d[order, :2])
        br = np.minimum(d[i, 2:4], d[order, 2:4])
        inter = np.prod(np.clip(br - tl, 0, None), 1)
        area = lambda b: (b[..., 2] - b[..., 0]) * (b[..., 3] - b[..., 1])  # noqa: E731
        order = order[inter / (area(d[i]) + area(d[order]) - inter + 1e-9) <= iou]
    return d[keep]


class Detector:
    """Détection sur une image BGR ; renvoie un tableau (n, 6) : x1, y1, x2, y2, confiance, classe."""

    def __init__(self, weights, imgsz=640, conf=0.35, iou=0.45, device="", half=False, max_det=300, classifier=None, conf_signs=0.15):
        self.device = select_device(device)
        self.model = DetectMultiBackend(weights, device=self.device, fp16=half and self.device.type != "cpu")
        if not self.model.pt and self.device.type == "cpu":
            torch.set_num_threads(1)  # PyTorch ne fait plus que pré/post-traitement : laisser les cœurs au moteur ONNX/OpenVINO
        self.names = self.model.names
        self.stride = self.model.stride
        imgsz = [imgsz] if isinstance(imgsz, int) else list(imgsz)
        fixed = self._fixed_shape()
        if fixed:  # ONNX exporté à taille fixe
            self.imgsz, self.dynamic = fixed, False
        elif self.model.pt or self.model.onnx:  # cadrage rectangulaire minimal (plus rapide)
            self.imgsz, self.dynamic = check_img_size(max(imgsz), s=self.stride), True
        else:  # OpenVINO, TensorRT... : taille d'export à redonner avec --taille H L
            self.imgsz, self.dynamic = (imgsz * 2)[:2], False
        self.conf, self.iou, self.max_det = conf, iou, max_det
        self.classifier = None
        if classifier:
            from .classifier import SignClassifier

            self.classifier = SignClassifier(classifier, self.device)
        self.conf_signs = conf_signs  # seuil bas pour les panneaux : le classifieur confirme ensuite
        self.sign_factor = 1.3  # seuil final des panneaux (score combiné) = sign_factor x conf, calé sur la validation
        size = self.imgsz if isinstance(self.imgsz, list) else [self.imgsz, self.imgsz]
        self.model.warmup(imgsz=(1, 3, *size))

    def _fixed_shape(self):
        """Taille d'entrée figée d'un modèle exporté (ONNX), si connue."""
        session = getattr(self.model, "session", None)
        if session is not None:
            shape = session.get_inputs()[0].shape
            if all(isinstance(s, int) for s in shape[2:]):
                return list(shape[2:])
        return None

    @torch.inference_mode()
    def __call__(self, frame):
        im = letterbox(frame, self.imgsz, stride=self.stride, auto=self.dynamic)[0]
        im = np.ascontiguousarray(im.transpose((2, 0, 1))[::-1])
        x = torch.from_numpy(im).to(self.device)
        x = (x.half() if self.model.fp16 else x.float())[None] / 255.0
        y = self.model(x)
        y = y[0] if isinstance(y, (list, tuple)) else y
        if self.classifier is None:
            pred = non_max_suppression(y, self.conf, self.iou, max_det=self.max_det)[0]
            pred[:, :4] = scale_boxes(x.shape[2:], pred[:, :4], frame.shape).round()
            return pred.float().cpu().numpy()
        # Les panneaux d'une même famille (ex. 17 triangles de danger) se partagent la probabilité de classe :
        # on regroupe toutes les classes de panneaux en une pseudo-classe « panneau » (somme des probabilités),
        # et le classifieur choisit ensuite la classe exacte.
        # (en place : la colonne de la première classe de panneau reçoit le score « panneau », les autres sont mises à 0)
        y = y.float()
        cls = y[..., 5:]
        sign_score = (cls @ SIGN_VEC.to(y.device)).clamp_(max=1.0)
        cls[..., IS_SIGN] = 0
        cls[..., SIGN0] = sign_score
        pred = non_max_suppression(y, min(self.conf, self.conf_signs), self.iou, max_det=self.max_det)[0]
        pred[:, :4] = scale_boxes(x.shape[2:], pred[:, :4], frame.shape).round()
        d = pred.float().cpu().numpy()
        sign = d[:, 5] == SIGN0
        marks = d[~sign & (d[:, 4] >= self.conf)]
        signs = d[sign]
        if len(signs):
            cls, p = self.classifier(frame, signs[:, :4])
            ok = cls >= 0  # -1 : le classifieur y voit un leurre (dos de panneau, publicité...)
            signs = signs[ok]
            signs[:, 5] = cls[ok]
            signs[:, 4] = np.sqrt(signs[:, 4] * p[ok])  # confiance combinée détecteur x classifieur
            signs = nms_agnostic(signs[signs[:, 4] >= self.sign_factor * self.conf]) if len(signs) else signs
        return np.concatenate([marks, signs.reshape(-1, 6)])
