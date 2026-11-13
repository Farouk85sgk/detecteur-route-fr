"""Évalue la chaîne complète (détecteur puis classifieur) sur les vraies photos de validation, comme dans l'appli :
pour chaque panneau annoté, a-t-il été trouvé, et avec le bon type ?

- trouvé et bien nommé : bonne réponse ;
- trouvé mais mal nommé : confusion ;
- non trouvé ou rejeté par le classifieur : oubli ;
- annonce là où il n'y a aucun panneau annoté : fausse annonce. Les annonces qui tombent sur un objet que les
  annotations n'identifient pas (zone ignorée, panneau de type inconnu) sont comptées à part : on ne peut pas les juger.

Un tableau donne ensuite les mêmes nombres pour d'autres seuils de confiance, pour choisir le réglage de l'appli
(seuil des panneaux = sign_factor x conf dans route_fr/detector.py, SEUIL_PANNEAU dans docs/js/moteur.js).

    python tools/evaluer_chaine.py --poids weights/route_fr_yolov5n.pt --classifieur weights/panneaux_cls.pt
"""

import argparse
import json
import collections
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import CLASSES, DET_IGNORER  # noqa: E402
from route_fr.detector import Detector  # noqa: E402


def iou_1n(b, B):
    x1, y1, x2, y2 = np.maximum(b[0], B[:, 0]), np.maximum(b[1], B[:, 1]), np.minimum(b[2], B[:, 2]), np.minimum(b[3], B[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    return inter / ((b[2] - b[0]) * (b[3] - b[1]) + (B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1]) - inter + 1e-9), inter


def boites(fichier, W, H, classe=None):
    out = []
    if fichier.exists():
        for l in fichier.read_text().split("\n"):
            if l.strip():
                k, x, y, w, h = l.split()
                if classe is None or int(k) == classe:
                    out.append((k, [(float(x) - float(w) / 2) * W, (float(y) - float(h) / 2) * H, (float(x) + float(w) / 2) * W, (float(y) + float(h) / 2) * H]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poids", default=str(ROOT / "weights" / "route_fr_yolov5n.pt"))
    ap.add_argument("--classifieur", default=str(ROOT / "weights" / "panneaux_cls.pt"))
    ap.add_argument("--images", default=str(ROOT / "datasets" / "reel" / "images" / "val"))
    ap.add_argument("--taille", type=int, default=416)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--facteur", type=float, default=None, help="seuil des panneaux = facteur x conf (défaut : celui du détecteur)")
    ap.add_argument("--max", type=int, default=0, help="nombre d'images (0 : toutes)")
    ap.add_argument("--annonces", default="", help="fichier JSON où écrire toutes les annonces (score, nature, vrai type, type annoncé)")
    ap.add_argument("--sans-seuils", action="store_true", help="ignorer les seuils propres à certains panneaux (SEUILS de route_fr/classes.py)")
    a = ap.parse_args()
    det = Detector(a.poids, a.taille, a.conf, classifier=a.classifieur)
    if a.facteur is not None:
        det.sign_factor = a.facteur
    if a.sans_seuils:
        det.seuils[:] = 0
    seuil = det.sign_factor * det.conf  # seuil de l'appli ; on récolte les annonces plus bas pour le tableau des seuils
    det.sign_factor = min(det.sign_factor, 0.2 / det.conf)
    dossier = Path(a.images)
    total = collections.Counter()
    tailles = collections.defaultdict(lambda: [0, 0])
    confusions, par_classe = collections.Counter(), collections.defaultdict(lambda: [0, 0])
    annonces = []  # (score, nature, vrai type, type annoncé, tranche de taille)
    for f in sorted(dossier.glob("*.jpg"))[: a.max or None]:
        img = cv2.imread(str(f))
        H, W = img.shape[:2]
        gt = boites(Path(str(f).replace("/images/", "/codes/")).with_suffix(".txt"), W, H)
        ign = np.array([b for _, b in boites(Path(str(f).replace("/images/", "/labels_complets/")).with_suffix(".txt"), W, H, DET_IGNORER)], np.float32).reshape(-1, 4)
        d = det(img)
        d = d[[CLASSES[int(c)].categorie != "marquage" for c in d[:, 5]]] if len(d) else d
        G = np.array([b for _, b in gt], np.float32).reshape(-1, 4)
        pris = np.zeros(len(gt), bool)
        for x1, y1, x2, y2, score, c in d[np.argsort(-d[:, 4])] if len(d) else []:
            code, b = CLASSES[int(c)].code, np.array([x1, y1, x2, y2])
            j, vrai, t = -1, None, None
            if len(G):
                ious, _ = iou_1n(b, G)
                ious[pris] = 0
                j = int(ious.argmax()) if ious.max() >= 0.4 else -1
            if j >= 0:
                pris[j] = True
                vrai = gt[j][0]
                cote = max(G[j][2] - G[j][0], G[j][3] - G[j][1])
                t = "moins de 12 px" if cote < 12 else "12 à 24 px" if cote < 24 else "plus de 24 px"
                nature = "sur un panneau de type inconnu" if vrai == "?" else "bonnes réponses" if vrai == code else "confusions"
            elif len(ign) and iou_1n(b, ign)[1].max() >= 0.4 * (x2 - x1) * (y2 - y1):
                nature = "sur un objet non identifié"
            else:
                nature = "fausses annonces"
            annonces.append((float(score), nature, vrai, code, t))
        for (vrai, b) in gt:
            if vrai not in ("?", "autre"):
                cote = max(b[2] - b[0], b[3] - b[1])
                tailles["moins de 12 px" if cote < 12 else "12 à 24 px" if cote < 24 else "plus de 24 px"][0] += 1
                par_classe[vrai][0] += 1
                total["panneaux du catalogue"] += 1
        total["images"] += 1
    if a.annonces:
        Path(a.annonces).write_text(json.dumps(annonces), encoding="utf-8")
    for score, nature, vrai, code, t in annonces:  # bilan au seuil de l'appli
        if score < seuil:
            continue
        total[nature] += 1
        if nature == "bonnes réponses":
            tailles[t][1] += 1
            par_classe[vrai][1] += 1
        elif nature == "confusions":
            confusions[(vrai, code)] += 1
    n, ok = total["panneaux du catalogue"], total["bonnes réponses"]
    nb_annonces = ok + total["confusions"] + total["fausses annonces"]
    print(f"{total['images']} images, {n} panneaux du catalogue annotés")
    print(f"trouvés et bien nommés : {ok} ({ok / max(n, 1):.1%})   confusions : {total['confusions']}   fausses annonces : {total['fausses annonces']}"
          f"   (sur un objet non identifié : {total['sur un objet non identifié']}, sur un panneau de type inconnu : {total['sur un panneau de type inconnu']})")
    print(f"exactitude des annonces : {ok / max(nb_annonces, 1):.1%}")
    print("rappel par taille : " + ", ".join(f"{k} : {v[1] / max(v[0], 1):.0%} ({v[0]})" for k, v in sorted(tailles.items())))
    faibles = sorted(((c, v[1] / v[0], v[0]) for c, v in par_classe.items() if v[0] >= 4), key=lambda t: t[1])[:20]
    print("panneaux les moins bien reconnus : " + ", ".join(f"{c} {r:.0%} ({k})" for c, r, k in faibles))
    print("confusions les plus fréquentes : " + ", ".join(f"{a}→{b} ×{k}" for (a, b), k in confusions.most_common(15)))
    # annonces fausses par panneau annoncé : confusions, annonces sur un objet ou sur un panneau d'un autre type
    faux, justes = collections.Counter(), collections.Counter()
    for score, nature, vrai, code, t in annonces:
        if score >= seuil:
            (justes if nature == "bonnes réponses" else faux)[code] += 1
    pires = sorted(faux, key=lambda c: (-faux[c], c))[:25]
    print("panneaux le plus souvent annoncés à tort (à tort / à raison) : " + ", ".join(f"{c} {faux[c]}/{justes[c]}" for c in pires))
    print(f"\nselon le seuil des panneaux (celui de l'appli : {seuil:.3f})")
    print(f"{'seuil':>6s} {'bien nommés':>12s} {'confusions':>11s} {'fausses annonces':>17s} {'exactitude':>11s}")
    for s in sorted({0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, round(seuil, 3)}):
        c = collections.Counter(nature for score, nature, *_ in annonces if score >= s)
        bon, conf, faux = c["bonnes réponses"], c["confusions"], c["fausses annonces"]
        print(f"{s:6.3f} {bon / max(n, 1):12.1%} {conf:11d} {faux:17d} {bon / max(bon + conf + faux, 1):11.1%}")


if __name__ == "__main__":
    main()
