"""Nettoie les vignettes réelles du classifieur avec le classifieur lui-même, avant un second tour d'entraînement.

Les étiquettes des vraies photos viennent de modèles automatiques et quelques-unes sont fausses. Une vignette dont
le classifieur rejette nettement l'étiquette (probabilité inférieure à 5 %) tout en reconnaissant autre chose avec
assurance (plus de 80 %) est écartée : son nom est écrit dans <data>/exclus.txt, que l'entraînement respecte.
Les objets non identifiés par les annotations (dossier _inconnu) que le classifieur ne reconnaît pas non plus
(moins de 50 % pour tout panneau du catalogue) sont copiés dans la classe « autre ».

    python tools/nettoyer_vignettes.py --classifieur weights/panneaux_cls.pt --data datasets/vignettes
"""

import argparse
import collections
import shutil
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "yolov5"))

from train_classifieur import CLASSES, Vignettes, predire  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--classifieur", default=str(ROOT / "weights" / "panneaux_cls.pt"))
    ap.add_argument("--data", default=str(ROOT / "datasets" / "vignettes"))
    a = ap.parse_args()
    data = Path(a.data)
    (data / "exclus.txt").unlink(missing_ok=True)
    model = torch.load(a.classifieur, map_location="cpu", weights_only=False)["model"].float().eval()
    n_cat = len(CLASSES) - 2  # « autre » et « fond » sont les deux dernières classes
    exclus, par_classe = [], collections.Counter()
    for split in ("train", "val"):
        ds = Vignettes([data], split, False)
        p = predire(model, ds)
        k = p.argmax(1)
        for i in np.where((ds.y < n_cat) & (p[np.arange(len(k)), ds.y] < 0.05) & (p.max(1) > 0.8))[0]:
            f = ds.fichiers[i]
            exclus.append(f"{split}/{CLASSES[ds.y[i]]}/{f.name}")
            par_classe[CLASSES[ds.y[i]]] += 1
        print(f"{split} : {len(ds)} vignettes examinées", flush=True)
    (data / "exclus.txt").write_text("\n".join(exclus), encoding="utf-8")
    print(f"{len(exclus)} vignettes écartées ; classes les plus touchées : " + ", ".join(f"{c} {n}" for c, n in par_classe.most_common(15)))
    autre = data / "train" / "autre"
    for f in autre.glob("inconnu_*.jpg"):
        f.unlink()
    if (data / "train" / "_inconnu").exists():
        ds = Vignettes([data], "train", False, classes=["_inconnu"])
        p = predire(model, ds)
        garde = np.where(p[:, :n_cat].max(1) < 0.5)[0]
        for i in garde:
            shutil.copy(ds.fichiers[i], autre / f"inconnu_{ds.fichiers[i].name}")
        print(f"{len(garde)} objets non identifiés sur {len(ds)} ajoutés à la classe « autre »")


if __name__ == "__main__":
    main()
