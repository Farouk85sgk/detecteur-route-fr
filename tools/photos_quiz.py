"""Choisit de vraies photos de routes françaises pour le quiz « En situation réelle » de l'appli web.

Dans les vues Panoramax téléchargées (tools/panoramax_telecharge.py), garde pour chaque panneau du catalogue une ou
deux photos où il est grand, net et identifié avec certitude (par le modèle d'origine et, si on le donne, par le
classifieur du projet), recadre la scène en 4:3 autour de lui et l'entoure d'un cadre jaune.

Sorties : docs/series/photos/<n>.jpg et docs/series/photos.json (panneau, auteur, date et lien de chaque photo :
elles sont sous Licence Ouverte 2.0, qui demande de citer la source).

    python tools/photos_quiz.py --vues datasets_src/panoramax --classifieur weights/panneaux_cls.pt
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.panoramax import code_catalogue  # noqa: E402

L, H = 560, 420  # taille des photos du quiz
# Panneaux dont la photo retenue a été jugée fausse ou trop peu lisible à la relecture : pas de question sur eux.
SAUF = "A16,A23,A24,A3b,AK30,B14_100,B13,B16,B17,B1j,B2b,B41,B57,C1a_M4c,C4a,CE14,CE23,CE28,CE52,J13,M6h"


def candidats(vues):
    """(code, fichier json, indice de l'annotation, grand côté) des panneaux grands et sûrs, loin des bords."""
    out = collections.defaultdict(list)
    for fj in sorted((vues / "vues").glob("*.json")):
        m = json.loads(fj.read_text(encoding="utf-8"))
        for i, a in enumerate(m["annots"]):
            nature, code = code_catalogue(a["code"])
            x1, y1, x2, y2 = a["box"]
            c = max(x2 - x1, y2 - y1)
            if nature != "classe" or (a["cls"] or 0) < 0.98 or (a["det"] or 0) < 0.75 or not 64 <= c <= 300:
                continue
            if x1 < 1.2 * c or y1 < 0.8 * c or x2 > m["w"] - 1.2 * c or y2 > m["h"] - 0.8 * c:
                continue
            out[code].append((str(fj), i, c, m["producteur"], m["sequence"]))
    return out


def cadrer(m, img, i, rng):
    """Scène 4:3 autour du panneau i (il occupe 12 à 20 % de la largeur), panneau entouré de jaune."""
    x1, y1, x2, y2 = m["annots"][i]["box"]
    c = max(x2 - x1, y2 - y1)
    w = min(c * rng.uniform(5.0, 7.5), m["w"], m["h"] * 4 / 3)
    h = w * 3 / 4
    cx, cy = (x1 + x2) / 2 + rng.uniform(-0.18, 0.18) * w, (y1 + y2) / 2 + rng.uniform(-0.05, 0.2) * h
    X = int(np.clip(cx - w / 2, 0, m["w"] - w))
    Y = int(np.clip(cy - h / 2, 0, m["h"] - h))
    e = L / w
    out = cv2.resize(img[Y : Y + int(h), X : X + int(w)], (L, H), interpolation=cv2.INTER_AREA)
    marge = 0.12 * c
    p1 = (int((x1 - marge - X) * e), int((y1 - marge - Y) * e))
    p2 = (int((x2 + marge - X) * e), int((y2 + marge - Y) * e))
    cv2.rectangle(out, p1, p2, (20, 20, 20), 5, cv2.LINE_AA)
    cv2.rectangle(out, p1, p2, (30, 198, 255), 3, cv2.LINE_AA)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vues", default=str(ROOT / "datasets_src" / "panoramax"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "series"))
    ap.add_argument("--par-code", type=int, default=1)
    ap.add_argument("--classifieur", default="", help="poids du classifieur : ne garder que les panneaux qu'il reconnaît aussi")
    ap.add_argument("--sauf", default=SAUF, help="codes à laisser de côté, séparés par des virgules")
    ap.add_argument("--graine", type=int, default=3)
    a = ap.parse_args()
    rng = random.Random(a.graine)
    sauf = set(a.sauf.split(","))
    cls = None
    if a.classifieur:
        import torch

        from route_fr.classifier import SignClassifier
        from route_fr.classes import BY_CODE

        cls = SignClassifier(a.classifieur, torch.device("cpu"))
    out = Path(a.out)
    (out / "photos").mkdir(parents=True, exist_ok=True)
    for f in (out / "photos").glob("*.jpg"):
        f.unlink()
    photos = []
    for code, liste in sorted(candidats(Path(a.vues)).items()):
        rng.shuffle(liste)
        liste.sort(key=lambda t: -min(t[2], 140))  # les plus grands d'abord (au-delà de 140 px, peu importe)
        pris, sequences = 0, set()
        for fj, i, _, prod, seq in liste:
            if pris >= a.par_code:
                break
            if seq in sequences:
                continue
            m = json.loads(Path(fj).read_text(encoding="utf-8"))
            img = cv2.imread(fj[:-5] + ".jpg")
            if img is None:
                continue
            m["h"], m["w"] = img.shape[:2]
            if cls is not None:
                k, p = cls(img, np.array([m["annots"][i]["box"]], np.float32))
                if k[0] != BY_CODE[code] or p[0] < 0.9:
                    continue
            scene = cadrer(m, img, i, rng)  # toujours calculée : le tirage reste le même quels que soient les codes écartés
            sequences.add(seq)
            pris += 1
            if code in sauf:
                continue
            nom = f"{len(photos) + 1:03d}.jpg"
            cv2.imwrite(str(out / "photos" / nom), scene, [cv2.IMWRITE_JPEG_QUALITY, 72])
            photos.append({"f": nom, "code": code, "auteur": m["producteur"], "date": m["date"], "source": m["source"]})
    (out / "photos.json").write_text(json.dumps({"licence": "Licence Ouverte 2.0 (Etalab)", "origine": "Panoramax, instance IGN", "photos": photos}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    taille = sum(f.stat().st_size for f in (out / "photos").glob("*.jpg")) // 1024
    print(f"{len(photos)} photos de {len({p['code'] for p in photos})} panneaux différents ({taille} Ko) -> {out / 'photos'}")


if __name__ == "__main__":
    main()
