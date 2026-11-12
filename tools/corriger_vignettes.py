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

Avec --reel et --vues, les mêmes corrections sont reportées dans les types de panneaux qui servent à évaluer la chaîne
complète (datasets/reel/codes/val, lus par tools/evaluer_chaine.py) : « autre » pour un faux panneau, « ? » (non jugé)
pour un cas écarté.

    python tools/corriger_vignettes.py --data datasets/vignettes --reel datasets/reel --vues datasets_src/panoramax

À lancer après tools/panoramax_dataset.py ; sans effet sur ce qui est déjà corrigé.
"""

import argparse
import collections
import json
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


def corriger_codes(reel, vues, corrections):
    """Reporte les corrections dans reel/codes/val : la ligne d'un panneau corrigé y est retrouvée par sa position."""
    par_photo = collections.defaultdict(list)
    for classe, cle, decision in corrections:
        photo, i = cle.rsplit("_", 1)
        par_photo[photo].append((classe, int(i), "autre" if decision == "autre" else "?"))
    n = 0
    for ligne in (reel / "sources.jsonl").read_text(encoding="utf-8").split("\n"):
        if not ligne.strip():
            continue
        src = json.loads(ligne)
        if src["split"] != "val" or src["id"] not in par_photo:
            continue
        annots = json.loads((vues / "vues" / f"{src['id']}.json").read_text(encoding="utf-8"))["annots"]
        for nom, (x0, y0, S) in src["fenetres"].items():
            fichier = reel / "codes" / "val" / f"{nom}.txt"
            if not fichier.exists():
                continue
            lignes = [l.split() for l in fichier.read_text().split("\n") if l.strip()]
            for classe, i, nouveau in par_photo[src["id"]]:
                bx1, by1, bx2, by2 = annots[i]["box"]
                cx1, cy1, cx2, cy2 = max(bx1, x0), max(by1, y0), min(bx2, x0 + S), min(by2, y0 + S)
                attendu = [((cx1 + cx2) / 2 - x0) / S, ((cy1 + cy2) / 2 - y0) / S, (cx2 - cx1) / S, (cy2 - cy1) / S]
                for l in lignes:
                    if l[0] == classe and max(abs(float(v) - w) for v, w in zip(l[1:], attendu)) < 2e-4:
                        l[0] = nouveau
                        n += 1
            fichier.write_text("".join(" ".join(l) + "\n" for l in lignes))
    print(f"{n} types de panneaux corrigés dans {reel / 'codes' / 'val'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "datasets" / "vignettes"))
    ap.add_argument("--corrections", default=str(ROOT / "data" / "panoramax_corrections.txt"))
    ap.add_argument("--reel", default="", help="jeu de photos réelles (datasets/reel) : corrige aussi ses types de panneaux de validation")
    ap.add_argument("--vues", default=str(ROOT / "datasets_src" / "panoramax"))
    a = ap.parse_args()
    data = Path(a.data)
    faits = collections.Counter()
    toutes = [l.split() for l in Path(a.corrections).read_text(encoding="utf-8").split("\n") if l.strip() and not l.startswith("#")]
    if a.reel:
        corriger_codes(Path(a.reel), Path(a.vues), toutes)
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
