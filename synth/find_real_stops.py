"""Repère les vrais panneaux STOP des fonds comma10k avec YOLOv5 pré-entraîné sur COCO (classe « stop sign »).

Les STOP américains sont identiques au panneau français AB4 : on les annote AB4 au lieu de les laisser comme
faux négatifs. Les fonds avec une détection incertaine sont écartés. Met à jour <fonds>/meta.json.

Usage : python synth/find_real_stops.py --fonds datasets_src/fonds --weights yolov5/yolov5s.pt
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "yolov5"))

from models.common import DetectMultiBackend  # noqa: E402
from utils.augmentations import letterbox  # noqa: E402
from utils.general import non_max_suppression, scale_boxes  # noqa: E402

STOP_SIGN = 11  # indice COCO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonds", default="datasets_src/fonds")
    ap.add_argument("--weights", default=str(ROOT / "yolov5" / "yolov5s.pt"))
    ap.add_argument("--imgsz", type=int, default=832)
    ap.add_argument("--sure", type=float, default=0.45)
    ap.add_argument("--doubt", type=float, default=0.12)
    a = ap.parse_args()
    torch.set_num_threads(4)
    model = DetectMultiBackend(a.weights, device=torch.device("cpu"))
    meta_path = Path(a.fonds, "meta.json")
    meta = json.load(open(meta_path))
    removed = 0
    for i, name in enumerate(sorted(meta)):
        im0 = cv2.imread(f"{a.fonds}/img/{name}.jpg")
        im = letterbox(im0, a.imgsz, stride=model.stride, auto=True)[0]
        x = torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).float()[None] / 255.0
        with torch.inference_mode():
            pred = non_max_suppression(model(x), a.doubt, 0.45, classes=[STOP_SIGN])[0]
            pred[:, :4] = scale_boxes(x.shape[2:], pred[:, :4], im0.shape).round()
        sure = [[*map(float, p[:4]), round(float(p[4]), 3)] for p in pred if p[4] >= a.sure]
        doubtful = any(p[4] < a.sure for p in pred)
        meta[name]["stops"] = sure
        if doubtful:
            meta[name]["exclude"] = True
            removed += 1
        if i % 500 == 0:
            n = sum(len(v.get("stops", [])) for v in meta.values())
            print(f"{i}/{len(meta)} STOP réels: {n}, fonds écartés: {removed}", flush=True)
    json.dump(meta, open(meta_path, "w"))
    print(f"Terminé : {sum(len(v.get('stops', [])) for v in meta.values())} STOP réels, {removed} fonds écartés")


if __name__ == "__main__":
    main()
