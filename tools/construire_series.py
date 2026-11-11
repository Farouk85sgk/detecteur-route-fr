"""Compile la banque de questions du code (data/series/questions/*.txt) en docs/series/banque.json pour l'appli.

Les questions sont écrites dans des fichiers texte faciles à relire et à corriger, un fichier par lot (L01.txt...).
La lettre du nom donne le thème officiel de l'examen (L, C, R, U, D, A, P, M, S, E). Format :

    # Titre du lot (affiché dans l'appli)
    ? Texte de la question
    - mauvaise réponse
    + bonne réponse (plusieurs lignes « + » si plusieurs bonnes réponses)
    ! Explication affichée après la réponse
    @ sous-thème | difficulté de 1 à 3 | code d'un panneau à afficher (facultatif)

Une ligne vide sépare les questions. Le script vérifie chaque question (2 à 4 réponses, au moins une bonne et une
mauvaise, explication présente, panneau connu) et refuse de produire la banque s'il trouve une erreur.

    python tools/construire_series.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import BY_CODE  # noqa: E402

THEMES = [  # les dix thèmes de l'épreuve théorique générale, et le nombre de questions de chacun dans un examen de 40 questions
    ("L", "Circulation routière", "Signalisation, priorités, vitesses, dépassement, stationnement", 4),
    ("C", "Le conducteur", "Alcool, fatigue, distractions, comportement", 10),
    ("R", "La route", "Nuit, intempéries, distances, zones dangereuses", 4),
    ("U", "Les autres usagers", "Piétons, cyclistes, deux-roues, poids lourds, partage de la route", 5),
    ("D", "Notions diverses", "Permis à points, documents, infractions, chargement", 3),
    ("A", "Premiers secours", "Protéger, alerter, secourir", 1),
    ("P", "Prendre et quitter son véhicule", "S'installer, se garer, descendre en sécurité", 3),
    ("M", "Mécanique et équipements", "Pneus, voyants, freins, entretien", 4),
    ("S", "Sécurité du passager et du véhicule", "Ceinture, airbags, sièges enfants, aides à la conduite", 3),
    ("E", "Environnement", "Écoconduite, pollution, mobilités", 3),
]


def lire(fichier):
    lot, titre, questions, q = fichier.stem, "", [], None
    for n, ligne in enumerate(fichier.read_text(encoding="utf-8").split("\n") + [""], 1):
        ligne = ligne.strip()
        if not ligne:
            if q:
                questions.append(q)
            q = None
            continue
        marque, texte = ligne[0], ligne[1:].strip()
        if marque == "#":
            titre = titre or texte
        elif marque == "?":
            if q:
                raise ValueError(f"{fichier.name}:{n} : ligne vide manquante avant cette question")
            q = {"q": texte, "c": [], "b": [], "e": "", "s": "", "d": 2}
        elif q is None:
            raise ValueError(f"{fichier.name}:{n} : ligne hors question : {ligne[:50]}")
        elif marque in "+-":
            if marque == "+":
                q["b"].append(len(q["c"]))
            q["c"].append(texte)
        elif marque == "!":
            q["e"] = (q["e"] + " " + texte).strip()
        elif marque == "@":
            parts = [p.strip() for p in texte.split("|")]
            q["s"] = parts[0]
            if len(parts) > 1 and parts[1]:
                q["d"] = int(parts[1])
            if len(parts) > 2 and parts[2]:
                q["p"] = parts[2]
        else:
            raise ValueError(f"{fichier.name}:{n} : ligne non comprise : {ligne[:50]}")
    for i, q in enumerate(questions, 1):
        ou = f"{fichier.name}, question {i} ({q['q'][:40]}...)"
        if not 2 <= len(q["c"]) <= 4:
            raise ValueError(f"{ou} : {len(q['c'])} réponses (il en faut 2 à 4)")
        if not q["b"] or len(q["b"]) == len(q["c"]):
            raise ValueError(f"{ou} : il faut au moins une bonne et une mauvaise réponse")
        if len(set(q["c"])) != len(q["c"]):
            raise ValueError(f"{ou} : deux réponses identiques")
        if not q["e"] or not q["s"] or q["d"] not in (1, 2, 3):
            raise ValueError(f"{ou} : explication, sous-thème ou difficulté manquant")
        if "p" in q and q["p"] not in BY_CODE:
            raise ValueError(f"{ou} : panneau inconnu {q['p']}")
        q["id"] = f"{lot}-{i:02d}"
    return {"id": lot, "theme": lot[0], "titre": titre, "questions": questions}


def main():
    src = ROOT / "data" / "series" / "questions"
    lots = [lire(f) for f in sorted(src.glob("*.txt"))]
    connus = {t[0] for t in THEMES}
    for lot in lots:
        if lot["theme"] not in connus or not lot["titre"]:
            raise ValueError(f"{lot['id']} : thème inconnu ou titre manquant")
    textes = {}
    for lot in lots:
        for q in lot["questions"]:
            cle = (q["q"], q.get("p"))
            if cle in textes:
                raise ValueError(f"question en double : {q['id']} et {textes[cle]}")
            textes[cle] = q["id"]
    banque = {
        "themes": [{"id": t, "nom": nom, "detail": detail, "examen": n} for t, nom, detail, n in THEMES],
        "lots": [{"id": lot["id"], "theme": lot["theme"], "titre": lot["titre"], "questions": lot["questions"]} for lot in lots],
    }
    out = ROOT / "docs" / "series"
    out.mkdir(exist_ok=True)
    (out / "banque.json").write_text(json.dumps(banque, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    par = {t[0]: sum(len(lot["questions"]) for lot in lots if lot["theme"] == t[0]) for t in THEMES}
    print(f"{sum(par.values())} questions dans {len(lots)} lots -> {out / 'banque.json'}")
    print("  " + ", ".join(f"{t} : {n}" for t, n in par.items()))


if __name__ == "__main__":
    main()
