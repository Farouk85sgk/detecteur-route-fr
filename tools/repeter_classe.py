"""Répète les images d'un jeu de données YOLO qui contiennent une classe rare.

Le script crée des dossiers de liens (images/<classe>_1, labels/<classe>_1, ...) à ajouter à la liste « train » du
fichier de données : pendant l'entraînement, le réseau revoit ces images plus souvent, sans qu'il faille en générer
d'autres. Il a servi à réapprendre les dents de requin (3 % des images synthétiques) après la correction de leur dessin.

    python tools/repeter_classe.py --jeu datasets/route_fr --classe M_dents_requin --fois 5
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import DETECTEUR  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", required=True, help="dossier du jeu de données (avec images/train et labels/train)")
    ap.add_argument("--classe", required=True, help="classe du détecteur à répéter, par exemple M_dents_requin")
    ap.add_argument("--fois", type=int, default=2, help="nombre de reprises en plus de l'original")
    a = ap.parse_args()
    jeu, k = Path(a.jeu).resolve(), str(DETECTEUR.index(a.classe))
    avec = [f for f in sorted((jeu / "labels" / "train").glob("*.txt")) if any(ligne.split()[:1] == [k] for ligne in f.read_text().splitlines())]
    for n in range(1, a.fois + 1):
        for dossier in (jeu / "images" / f"{a.classe}_{n}", jeu / "labels" / f"{a.classe}_{n}"):
            dossier.mkdir(exist_ok=True)
            for ancien in dossier.iterdir():
                ancien.unlink()
        for f in avec:
            os.symlink(jeu / "images" / "train" / f"{f.stem}.jpg", jeu / "images" / f"{a.classe}_{n}" / f"{f.stem}.jpg")
            os.symlink(f, jeu / "labels" / f"{a.classe}_{n}" / f.name)
    dossiers = ", ".join(f"{jeu.name}/images/{a.classe}_{n}" for n in range(1, a.fois + 1))
    print(f"{len(avec)} images contiennent « {a.classe} ». À ajouter à « train » dans le fichier de données : {dossiers}")


if __name__ == "__main__":
    main()
