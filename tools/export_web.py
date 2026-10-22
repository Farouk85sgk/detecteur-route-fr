"""Prépare la version web (dossier docs/, publié par GitHub Pages) :
- modele.onnx : détecteur panneaux + marquages (YOLOv5n, taille dynamique) ;
- classifieur.onnx : classifieur de panneaux (second étage) ;
- usagers.onnx : YOLOv5n COCO d'origine réduit aux piétons, vélos, motos et feux tricolores ;
- classes.json, classifieur.json et icônes.
(empreinte.onnx, pour « Mes panneaux », est produit par tools/train_empreinte.py.)

    python tools/export_web.py

Puis envoyer sur GitHub (la page se met à jour toute seule, voir README) ou tester en local :
    python -m http.server --directory docs 8000   ->  http://localhost:8000
"""

import argparse
import dataclasses
import json
import shutil
import subprocess
import sys
from pathlib import Path

import onnx
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "yolov5"))  # classes YOLOv5 nécessaires pour relire les poids .pt

from models.experimental import attempt_load  # noqa: E402
from models.yolo import Detect  # noqa: E402
from ultralytics.utils.export import torch2onnx  # noqa: E402

from route_fr.classes import CLASSES, CODE_AFFICHE  # noqa: E402

USAGERS = [0, 1, 3, 9]  # classes COCO gardées : personne, vélo, moto, feu tricolore


def export_onnx(weights, out, img):
    tmp = out.with_suffix(".pt")
    shutil.copy(weights, tmp)
    subprocess.run([sys.executable, str(ROOT / "yolov5" / "export.py"), "--weights", str(tmp), "--include", "onnx", "--dynamic", "--simplify", "--img", str(img)], check=True)
    tmp.unlink()


def slim(path):
    try:
        import onnxslim

        onnx.save(onnxslim.slim(onnx.load(path)), path)
    except ImportError:
        pass


class UsagersWeb(torch.nn.Module):
    """YOLOv5 COCO dont la sortie ne garde que les 4 classes utiles (moins de calculs dans le navigateur)."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        y = self.model(x)[0]
        return torch.cat([y[..., :5], y[..., [5 + k for k in USAGERS]]], -1)


def export_usagers(weights, out):
    model = attempt_load(weights, device=torch.device("cpu"), fuse=True).eval()
    for m in model.modules():
        if isinstance(m, Detect):
            m.inplace, m.dynamic, m.export = False, True, True
    dyn = {"images": {0: "batch", 2: "height", 3: "width"}, "output0": {0: "batch", 1: "anchors"}}
    torch2onnx(UsagersWeb(model), torch.zeros(1, 3, 640, 640), out, opset=17, dynamic=dyn)
    slim(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poids", default=str(ROOT / "weights" / "route_fr_yolov5n.pt"))
    ap.add_argument("--classifieur", default=str(ROOT / "weights" / "panneaux_cls.pt"))
    ap.add_argument("--usagers", default=str(ROOT / "yolov5" / "yolov5n.pt"), help="YOLOv5 COCO (téléchargé s'il manque)")
    a = ap.parse_args()
    web = ROOT / "docs"
    export_onnx(a.poids, web / "modele.onnx", 640)
    if Path(a.classifieur).exists():
        export_onnx(a.classifieur, web / "classifieur.onnx", 64)
        names = torch.load(a.classifieur, map_location="cpu", weights_only=False)["model"].names
        names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
        (web / "classifieur.json").write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    export_usagers(a.usagers, web / "usagers.onnx")
    classes = [dict(dataclasses.asdict(c), affiche=CODE_AFFICHE.get(c.code, c.code)) for c in CLASSES]
    (web / "classes.json").write_text(json.dumps(classes, ensure_ascii=False), encoding="utf-8")
    shutil.copytree(ROOT / "route_fr" / "icones", web / "icones", dirs_exist_ok=True)
    print(f"Version web prête dans {web}")


if __name__ == "__main__":
    main()
