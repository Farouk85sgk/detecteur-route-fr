"""Construit, à partir des vues Panoramax téléchargées (tools/panoramax_telecharge.py), les données réelles :

- du détecteur (format YOLO) : <out>/reel/images/<train|val>/*.jpg et labels/ : dans chaque vue, un recadrage carré
  ramené à 416 px, à l'échelle d'un téléphone (environ 9 px par degré) ou plus serré. Les panneaux annotés deviennent des
  exemples de la classe « panneau » ; ce qui est douteux (objet non identifié, panneau minuscule ou coupé) est déclaré
  « _ignorer » : ni exemple ni contre-exemple. Les marquages au sol de ces photos ne sont pas annotés : une zone « _reel »
  (toute l'image, ou seulement sous l'horizon quand il est connu) indique à l'entraînement de n'y tirer aucune
  conclusion sur les marquages. Pour la validation, labels/ ne garde que les panneaux, labels_complets/ garde tout et
  codes/ donne le type de chaque panneau (pour évaluer la chaîne complète, tools/evaluer_chaine.py) ;
- du classifieur (--vignettes) : <out>/vignettes/<train|val>/<classe>/*.jpg, panneaux découpés à pleine définition avec
  leur décor, dans lesquels tools/train_classifieur.py tire ensuite ses recadrages d'entraînement.

La validation regroupe des zones géographiques entières (mailles de 0,2°) : aucune rue commune avec l'entraînement.
Les sources (auteur, lien, licence) et le recadrage de chaque image sont notés dans <out>/reel/sources.jsonl.

    python tools/panoramax_dataset.py --vues datasets_src/panoramax --out datasets
"""

import argparse
import collections
import hashlib
import json
import os
import random
import sys
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_fr.classes import DET_IGNORER, DET_PANNEAU, DET_REEL  # noqa: E402
from route_fr.panoramax import code_catalogue  # noqa: E402

T = 416  # côté des images du détecteur
FOV_DEFAUT = 90  # champ horizontal supposé des photos « plates » qui ne l'indiquent pas (caméras de relevé routier)
PETIT = 6  # en dessous (px, grand côté), un panneau est illisible : zone ignorée


def en_validation(lon, lat):
    maille = f"{int(lon * 5)}_{int(lat * 5)}"
    return int(hashlib.md5(maille.encode()).hexdigest(), 16) % 100 < 6


def fenetre(m, rng, ppd, principal=True):
    """Carré (x0, y0, côté) recadré dans la vue ; contient le panneau principal, placé au hasard, si `principal`."""
    w, h = m["w"], m["h"]
    cible = rng.uniform(8, 13) if rng.random() < 0.6 else rng.uniform(13, 30)  # px par degré une fois ramené à T
    S = int(np.clip(round(T * ppd / cible), 200, min(w, h)))
    a = next((a for a in m["annots"] if a["principal"]), None) if principal else None
    if a is None:
        return rng.randint(0, w - S), rng.randint(0, h - S), S
    x1, y1, x2, y2 = a["box"]
    pos = []
    for lo, hi, taille in ((x1, x2, w), (y1, y2, h)):
        mn, mx = max(0, int(hi + 4 - S)), min(int(lo - 4), taille - S)
        pos.append(rng.randint(mn, mx) if mn <= mx else int(np.clip((lo + hi) / 2 - S / 2, 0, taille - S)))
    return pos[0], pos[1], S


def etiquettes(m, x0, y0, S, ppd):
    """Lignes YOLO du recadrage : panneaux sûrs en classe « panneau », le reste en zone ignorée, et la zone « _reel »."""
    e, out, codes = T / S, [], []
    haut = 0.0  # la route ne monte guère à plus de 6° au-dessus de l'horizon : plus haut, pas de marquage possible
    if m["horizon"] is not None:
        haut = float(np.clip((m["horizon"] - 6 * ppd - y0) / S, 0, 1))
    if haut < 0.98:
        out.append(f"{DET_REEL} 0.5 {(1 + haut) / 2:.6f} 1 {1 - haut:.6f}")
    for a in m["annots"]:
        bx1, by1, bx2, by2 = a["box"]
        cx1, cy1, cx2, cy2 = max(bx1, x0), max(by1, y0), min(bx2, x0 + S), min(by2, y0 + S)
        if cx2 <= cx1 or cy2 <= cy1:
            continue
        visible = (cx2 - cx1) * (cy2 - cy1) / max((bx2 - bx1) * (by2 - by1), 1e-6)
        bw, bh = (cx2 - cx1) * e, (cy2 - cy1) * e
        nature, code = code_catalogue(a["code"])
        sur = nature != "inconnu" and visible >= 0.6 and max(bw, bh) >= PETIT and min(bw, bh) >= 4 and (a["det"] is None or a["det"] >= 0.35)
        if not sur and max(bw, bh) < 3:
            continue
        k = DET_PANNEAU if sur else DET_IGNORER
        out.append(f"{k} {((cx1 + cx2) / 2 - x0) / S:.6f} {((cy1 + cy2) / 2 - y0) / S:.6f} {(cx2 - cx1) / S:.6f} {(cy2 - cy1) / S:.6f}")
        if sur:  # type du panneau, pour évaluer la chaîne détecteur + classifieur : code du catalogue, « autre » ou « ? »
            codes.append(f"{code or ('autre' if nature == 'autre' else '?')} {out[-1][2:]}")
    return out, codes


def ecrire_etiquettes(racine, split, nom, lignes):
    """Entraînement : toutes les lignes. Validation : les vrais objets dans labels/, tout dans labels_complets/."""
    texte = lambda ls: "\n".join(ls) + ("\n" if ls else "")  # noqa: E731
    if split == "val":
        (racine / "labels_complets" / split).mkdir(parents=True, exist_ok=True)
        (racine / "labels_complets" / split / f"{nom}.txt").write_text(texte(lignes))
        lignes = [l for l in lignes if int(l.split()[0]) < DET_IGNORER]
    (racine / "labels" / split / f"{nom}.txt").write_text(texte(lignes))


def vignette(img, box, marge=1.3, maxi=250):
    """Carré de côté 2 x marge x (grand côté du panneau) centré sur la boîte, complété par répétition du bord si besoin,
    et la boîte en millièmes de ce carré. None si le panneau est trop près du bord de la vue."""
    x1, y1, x2, y2 = box
    c = max(x2 - x1, y2 - y1)
    cx, cy, d = (x1 + x2) / 2, (y1 + y2) / 2, marge * c
    X1, Y1, X2, Y2 = int(round(cx - d)), int(round(cy - d)), int(round(cx + d)), int(round(cy + d))
    H, W = img.shape[:2]
    if X1 < -0.6 * c or Y1 < -0.6 * c or X2 > W + 0.6 * c or Y2 > H + 0.6 * c:
        return None
    pad = cv2.copyMakeBorder(img[max(Y1, 0) : min(Y2, H), max(X1, 0) : min(X2, W)], max(-Y1, 0), max(Y2 - H, 0), max(-X1, 0), max(X2 - W, 0), cv2.BORDER_REPLICATE)
    if pad.shape[0] > maxi:  # inutile de garder plus de 96 px de panneau
        pad = cv2.resize(pad, (maxi, maxi), interpolation=cv2.INTER_AREA)
    return pad, "_".join(str(int(round(1000 * v / (2 * d)))) for v in (x1 - X1, y1 - Y1, x2 - X1, y2 - Y1))


def vignettes(m, img, split, out, rng):
    """Panneaux découpés à pleine définition avec leur décor (le cadrage final est tiré à l'entraînement) : une classe par
    dossier, « autre » pour les panneaux hors liste, « _inconnu » pour les objets non identifiés, et des morceaux de
    décor sans panneau en « fond »."""
    n = 0
    boites = [(*a["box"], *code_catalogue(a["code"]), a) for a in m["annots"]]
    for i, (x1, y1, x2, y2, nature, code, a) in enumerate(boites):
        if nature == "panneau" or (nature != "inconnu" and a["cls"] is not None and a["cls"] < 0.9) or (a["det"] is not None and a["det"] < 0.5):
            continue
        if max(x2 - x1, y2 - y1) < 14 or min(x2 - x1, y2 - y1) < 8:
            continue
        r = vignette(img, (x1, y1, x2, y2))
        if r is None:
            continue
        dossier = out / "vignettes" / split / (code or ("_inconnu" if nature == "inconnu" else "autre"))
        dossier.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(dossier / f"{m['id']}_{i}_{r[1]}.jpg"), r[0], [cv2.IMWRITE_JPEG_QUALITY, 92])
        n += 1
    if rng.random() < 0.3:  # décor : une boîte au hasard qui ne touche aucun panneau
        H, W = img.shape[:2]
        for _ in range(8):
            w, h = (rng.uniform(18, 110) * rng.uniform(0.7, 1.0) for _ in range(2))
            x, y = rng.uniform(0, W - w), rng.uniform(0.15 * H, 0.85 * H - h)
            if all(x + w < b[0] - 10 or x > b[2] + 10 or y + h < b[1] - 10 or y > b[3] + 10 for b in boites):
                r = vignette(img, (x, y, x + w, y + h))
                if r is not None:
                    dossier = out / "vignettes" / split / "fond"
                    dossier.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(dossier / f"{m['id']}_f_{r[1]}.jpg"), r[0], [cv2.IMWRITE_JPEG_QUALITY, 92])
                    n += 1
                    break
    return n


def traiter(job):
    fj, out, fov, faire_vignettes = job
    m = json.loads(Path(fj).read_text(encoding="utf-8"))
    split = "val" if en_validation(m["lon"], m["lat"]) else "train"
    img = cv2.imread(str(Path(fj).with_suffix(".jpg")))
    if img is None:
        return None
    m["h"], m["w"] = img.shape[:2]
    rng = random.Random(zlib.crc32(m["id"].encode()))
    ppd = m["px_par_degre"] or m["w"] / (fov or FOV_DEFAUT)
    crops = [fenetre(m, rng, ppd)]
    if m["plate"] and rng.random() < 0.35:  # second recadrage ailleurs dans les photos plates : du fond, d'autres panneaux
        crops.append(fenetre(m, rng, ppd, principal=False))
    stats, fenetres = collections.Counter(), {}
    for k, (x0, y0, S) in enumerate(crops):
        nom = f"{m['id']}_{'ab'[k]}"
        fenetres[nom] = [x0, y0, S]
        im = cv2.resize(img[y0 : y0 + S, x0 : x0 + S], (T, T), interpolation=cv2.INTER_AREA if S > T else cv2.INTER_LINEAR)
        cv2.imwrite(str(out / "reel" / "images" / split / f"{nom}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 90])
        lignes, codes = etiquettes(m, x0, y0, S, ppd)
        ecrire_etiquettes(out / "reel", split, nom, lignes)
        if split == "val":
            (out / "reel" / "codes" / split).mkdir(parents=True, exist_ok=True)
            (out / "reel" / "codes" / split / f"{nom}.txt").write_text("\n".join(codes) + ("\n" if codes else ""))
        stats["images"] += 1
        stats["panneaux"] += sum(l.startswith(f"{DET_PANNEAU} ") for l in lignes)
        stats["ignorés"] += sum(l.startswith(f"{DET_IGNORER} ") for l in lignes)
    if faire_vignettes:
        stats["vignettes"] += vignettes(m, img, split, out, rng)
    src = {"id": m["id"], "split": split, "auteur": m["producteur"], "date": m["date"], "licence": m["licence"], "source": m["source"], "lon": m["lon"], "lat": m["lat"],
           "fenetres": fenetres}  # recadrages (x, y, côté) dans la vue d'origine
    return stats, src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vues", default="datasets_src/panoramax")
    ap.add_argument("--out", default="datasets")
    ap.add_argument("--vignettes", action="store_true", help="découper aussi les panneaux pour le classifieur")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    a = ap.parse_args()
    vues, out = Path(a.vues), Path(a.out)
    for split in ("train", "val"):
        for d in ("images", "labels"):
            (out / "reel" / d / split).mkdir(parents=True, exist_ok=True)
    fichiers = sorted((vues / "vues").glob("*.json"))
    ids = {f.stem for f in fichiers}
    fov = {}
    for line in open(vues / "photos.jsonl", encoding="utf-8"):  # champ de vision des photos plates, quand il est connu
        i = line.find('"id": "') + 7
        if line[i : i + 36] in ids:
            p = json.loads(line)
            if p["tuiles"] is None and p["fov"] and p["fov"] < 200:
                fov[p["id"]] = p["fov"]
    total, sources = collections.Counter(), []
    with ProcessPoolExecutor(a.workers) as ex:
        for n, r in enumerate(ex.map(traiter, [(str(f), out, fov.get(f.stem), a.vignettes) for f in fichiers], chunksize=32)):
            if r:
                total.update(r[0])
                total[r[1]["split"]] += 1
                sources.append(r[1])
            if n % 2000 == 0:
                print(f"{n}/{len(fichiers)}  {dict(total)}", flush=True)
    with open(out / "reel" / "sources.jsonl", "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(s, ensure_ascii=False) + "\n" for s in sources)
    print(f"Terminé : {dict(total)}")


if __name__ == "__main__":
    main()
