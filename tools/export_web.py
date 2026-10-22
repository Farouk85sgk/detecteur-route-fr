"""Prépare la version web (dossier docs/, publié par GitHub Pages) : détecteur ONNX à taille dynamique, classifieur de panneaux (s'il existe),
classes.json et icônes.

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

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "yolov5"))  # classes YOLOv5 nécessaires pour relire les poids .pt

from route_fr.classes import CLASSES  # noqa: E402


def export_onnx(weights, out, img):
    tmp = out.with_suffix(".pt")
    shutil.copy(weights, tmp)
    subprocess.run([sys.executable, str(ROOT / "yolov5" / "export.py"), "--weights", str(tmp), "--include", "onnx", "--dynamic", "--simplify", "--img", str(img)], check=True)
    tmp.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poids", default=str(ROOT / "weights" / "route_fr_yolov5n.pt"))
    ap.add_argument("--classifieur", default=str(ROOT / "weights" / "panneaux_cls.pt"))
    a = ap.parse_args()
    web = ROOT / "docs"
    export_onnx(a.poids, web / "modele.onnx", 640)
    if Path(a.classifieur).exists():
        export_onnx(a.classifieur, web / "classifieur.onnx", 64)
        names = torch.load(a.classifieur, map_location="cpu", weights_only=False)["model"].names
        names = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)
        (web / "classifieur.json").write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    (web / "classes.json").write_text(json.dumps([dataclasses.asdict(c) for c in CLASSES], ensure_ascii=False), encoding="utf-8")
    shutil.copytree(ROOT / "route_fr" / "icones", web / "icones", dirs_exist_ok=True)
    print(f"Version web prête dans {web}")


if __name__ == "__main__":
    main()
