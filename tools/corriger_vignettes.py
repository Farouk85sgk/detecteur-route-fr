"""Applique aux vignettes réelles les corrections d'étiquettes faites à la main (data/panoramax_corrections.txt).

Les annotations d'origine des photos Panoramax viennent d'un modèle automatique : dans quelques classes, il prend des
logos ou d'autres panneaux pour le panneau cherché (le logo « ici » pour une limitation à 100, un schéma de giratoire
pour une fin de zone...). Chaque ligne du fichier de corrections donne la classe d'origine, la vignette (identifiant de
la photo et numéro de l'annotation) et la décision :
  autre    ce n'est pas un panneau du catalogue : la vignette passe dans la classe « autre » ;
  ecarter  panneau d'un autre type ou cas ambigu : la vignette est retirée de l'entraînement (dossier _ecartes).

    python tools/corriger_vignettes.py --data datasets/vignettes

Deux panneaux symétriques et rares (voie de détresse à droite C26a, à gauche C26b) reçoivent ensuite chacun le miroir
des vignettes d'entraînement de l'autre (fichiers miroir_*.jpg, refaits à chaque passage).

À lancer après tools/panoramax_dataset.py ; sans effet sur les vignettes déjà corrigées.
"""

import argparse
import collections
import shutil
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
MIROIRS = {"C26a": "C26b", "C26b": "C26a"}  # classe -> classe dont elle reçoit les vignettes retournées


def miroirs(data):
    """Refait les vignettes miroir des classes symétriques (jeu d'entraînement seulement)."""
    for cible, source in MIROIRS.items():
        dossier = data / "train" / cible
        dossier.mkdir(parents=True, exist_ok=True)
        for f in dossier.glob("miroir_*.jpg"):
            f.unlink()
        n = 0
        for f in sorted((data / "train" / source).glob("*.jpg")):
            if f.name.startswith("miroir_"):
                continue
            *debut, x1, y1, x2, y2 = f.stem.split("_")
            cv2.imwrite(str(dossier / f"miroir_{'_'.join(debut)}_{1000 - int(x2)}_{y1}_{1000 - int(x1)}_{y2}.jpg"), cv2.flip(cv2.imread(str(f)), 1), [cv2.IMWRITE_JPEG_QUALITY, 92])
            n += 1
        print(f"{cible:10s} miroirs  {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "datasets" / "vignettes"))
    ap.add_argument("--corrections", default=str(ROOT / "data" / "panoramax_corrections.txt"))
    a = ap.parse_args()
    data = Path(a.data)
    faits = collections.Counter()
    for ligne in Path(a.corrections).read_text(encoding="utf-8").split("\n"):
        if not ligne.strip() or ligne.startswith("#"):
            continue
        classe, cle, decision = ligne.split()
        for split in ("train", "val"):
            for f in (data / split / classe).glob(f"{cle}_*.jpg"):
                cible = data / split / "autre" if decision == "autre" else data / "_ecartes" / split / classe
                cible.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(cible / f.name))
                faits[(classe, decision)] += 1
    for (classe, decision), n in sorted(faits.items()):
        print(f"{classe:10s} {decision:8s} {n}")
    print(f"{sum(faits.values())} vignettes corrigées")
    miroirs(data)


if __name__ == "__main__":
    main()
