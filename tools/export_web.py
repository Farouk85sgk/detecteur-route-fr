"""Prépare la version web (dossier docs/, publié par GitHub Pages) :
- detecteur.onnx : détecteur de panneaux (une classe) et de marquages au sol (YOLOv5n, taille dynamique) ;
- usagers.onnx : YOLOv5n COCO d'origine réduit aux piétons, vélos, motos et feux tricolores ;
- catalogue.json : tous les éléments connus (route_fr/classes.py) et les classes du détecteur ;
- icônes et page de crédits.
(panneaux.onnx, le classifieur de panneaux, est produit par tools/train_classifieur.py ; empreinte.onnx, pour
« Mes panneaux », par tools/train_empreinte.py ; series/banque.json par tools/construire_series.py.)

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

from route_fr.classes import CLASSES, CODE_AFFICHE, DETECTEUR, FICHES_SEULES, MARQUAGES_FICHES  # noqa: E402

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


def credits_html(md):
    """Page de crédits des icônes (docs/credits.html) à partir de route_fr/icones/CREDITS.md."""
    import html
    import re

    lien = lambda t: re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}" rel="noopener">{html.escape(m.group(1))}</a>', t)  # noqa: E731
    lignes = md.split("\n")
    intro = " ".join(l for l in lignes[1:] if l and not l.startswith("|"))
    rangs = [[c.strip() for c in l.strip("|").split("|")] for l in lignes if l.startswith("|") and not l.startswith("|---")]
    table = "".join("<tr>" + "".join(f"<{'th' if i == 0 else 'td'}>{lien(c)}</{'th' if i == 0 else 'td'}>" for c in r) + "</tr>" for i, r in enumerate(rangs))
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crédits des icônes</title>'
        "<style>body{font:16px/1.5 system-ui,sans-serif;margin:24px auto;max-width:900px;padding:0 16px;color:#1b1f3a}table{border-collapse:collapse;width:100%;font-size:14px}"
        "td,th{border-bottom:1px solid #d5d8e6;padding:6px 8px;text-align:left}a{color:#2453d6}</style></head><body>"
        f'<p><a href="./">Retour à l\'appli</a></p><h1>Crédits des icônes de panneaux</h1><p>{lien(html.escape(intro, quote=False))}</p><table>{table}</table></body></html>'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poids", default=str(ROOT / "weights" / "route_fr_yolov5n.pt"))
    ap.add_argument("--usagers", default=str(ROOT / "yolov5" / "yolov5n.pt"), help="YOLOv5 COCO (téléchargé s'il manque)")
    ap.add_argument("--sans-modeles", action="store_true", help="ne refaire que le catalogue, les icônes et les crédits")
    a = ap.parse_args()
    web = ROOT / "docs"
    if not a.sans_modeles:
        export_onnx(a.poids, web / "detecteur.onnx", 640)
        shutil.copy(web / "detecteur.onnx", Path(a.poids).with_suffix(".onnx"))  # même fichier pour l'application de bureau
        export_usagers(a.usagers, web / "usagers.onnx")
    items = [dict(dataclasses.asdict(c), affiche=CODE_AFFICHE.get(c.code, c.code), detecte=c.code not in FICHES_SEULES | MARQUAGES_FICHES) for c in CLASSES]
    (web / "catalogue.json").write_text(json.dumps({"detecteur": DETECTEUR, "items": items}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    shutil.rmtree(web / "icones", ignore_errors=True)
    shutil.copytree(ROOT / "route_fr" / "icones", web / "icones", ignore=shutil.ignore_patterns("*.md"))
    (web / "credits.html").write_text(credits_html((ROOT / "route_fr" / "icones" / "CREDITS.md").read_text(encoding="utf-8")), encoding="utf-8")
    for ancien in ("modele.onnx", "classifieur.onnx", "classifieur.json", "classes.json"):  # fichiers des versions 1 et 2
        (web / ancien).unlink(missing_ok=True)
    print(f"Version web prête dans {web}")


if __name__ == "__main__":
    main()
