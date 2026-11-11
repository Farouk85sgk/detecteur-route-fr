"""Télécharge de vraies vues de routes françaises depuis Panoramax (instance IGN, Licence Ouverte Etalab 2.0), avec les
panneaux qui y sont annotés (index produit par tools/panoramax_index.py).

Pour chaque photo retenue :
- photo 360° : un bloc de tuiles haute définition autour d'un panneau (environ 45 à 90° de champ), assemblé tel quel
  (projection équirectangulaire, quasi sans déformation près de l'horizon) ;
- photo « plate » (caméra embarquée, téléphone) : l'image en définition standard (2048 px de large).
Sorties : <out>/vues/<id>.jpg et <id>.json (panneaux en pixels de la vue, horizon, source et auteur pour l'attribution).

La sélection vise un nombre de photos par code de panneau (les codes rares d'abord), en variant séquences et producteurs.
Le script se relance sans rien retélécharger.

    python tools/panoramax_telecharge.py --index datasets_src/panoramax --out datasets_src/panoramax --par-code 130
"""

import argparse
import collections
import json
import random
import threading
import time
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

API = "https://panoramax.ign.fr/api/pictures"
UA = "outil-pedagogique-signalisation/1.0"
SD = 2048  # largeur des images « sd » de Panoramax
BLOCS = {768: (2, 2), 512: (3, 2), 720: (2, 2), 960: (2, 2), 1536: (1, 1)}  # tuiles (colonnes, lignes) par taille de tuile
compteur = collections.Counter()
verrou = threading.Lock()


def get(url, essais=4):
    for k in range(essais):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return r.read()
        except Exception as e:
            if "404" in repr(e):
                return None
            time.sleep(2 + 4 * k)
    return None


def codes_fr(a):
    """Codes français d'une annotation (« FR:B6d;FR:M6h » -> ["B6d", "M6h"]) ; [] si le panneau n'est pas classé."""
    return [c[3:] for c in a["code"].split(";") if c.startswith("FR:")]


def choisir(index, par_code, graine=0):
    """Photos à télécharger : pour chaque code (du plus rare au plus fréquent), `par_code` photos au plus, de séquences
    et de producteurs variés, en gardant un panneau « principal » autour duquel la vue sera cadrée."""
    rng = random.Random(graine)
    photos = {}
    par = collections.defaultdict(list)
    for line in open(index / "photos.jsonl", encoding="utf-8"):
        p = json.loads(line)
        if p.get("licence") != "etalab-2.0" or not p.get("dims"):
            continue
        plate = p["tuiles"] is None
        if plate and (p["fov"] == 360 or p["dims"][0] < 1600):
            continue  # 360° sans tuiles ou image trop petite
        if not plate and int(p["tuiles"][2]) not in BLOCS:
            continue
        photos[p["id"]] = p
        ech = SD / p["dims"][0] if plate else 1.0
        for k, a in enumerate(p["annots"]):
            cs = codes_fr(a)
            cote = max(a["box"][2] - a["box"][0], a["box"][3] - a["box"][1]) * ech
            if not cs or cote < (14 if plate else 18) or (a["cls"] is not None and a["cls"] < 0.9):
                continue
            par[cs[0] if len(cs) == 1 else ";".join(cs)].append((p["id"], k))
    choisies = {}  # id -> indice de l'annotation principale
    stats = {}
    for code in sorted(par, key=lambda c: len(par[c])):
        cands = par[code][:]
        rng.shuffle(cands)
        cands.sort(key=lambda c: photos[c[0]]["tuiles"] is not None)  # les photos plates d'abord (plus proches d'un téléphone)
        seq, prod, n, plates = collections.Counter(), collections.Counter(), 0, 0
        deja = sum(1 for pid, _ in cands if pid in choisies)
        for pid, k in cands:
            if n + deja >= par_code:
                break
            p = photos[pid]
            if pid in choisies or seq[p["col"]] >= 2 or prod[p["prod"]] >= max(12, par_code // 3):
                continue
            plate = p["tuiles"] is None
            if plate and plates >= par_code * 0.5:
                continue
            choisies[pid] = k
            seq[p["col"]] += 1
            prod[p["prod"]] += 1
            n += 1
            plates += plate
        stats[code] = (len(par[code]), n + deja)
    return photos, choisies, stats


def fenetre(p, k, rng):
    """Bloc de tuiles (col0, lig0, ncol, nlig) contenant l'annotation principale, placé au hasard autour d'elle."""
    ncols, nligs, tw = int(p["tuiles"][0]), int(p["tuiles"][1]), int(p["tuiles"][2])
    bc, bl = BLOCS[tw]
    x1, y1, x2, y2 = p["annots"][k]["box"]
    c1, c2, l1, l2 = int(x1 // tw), int(x2 // tw), int(max(0, y1) // tw), int(min(nligs * tw - 1, y2) // tw)
    bc, bl = max(bc, c2 - c1 + 1), min(nligs, max(bl, l2 - l1 + 1))
    col0 = rng.randint(c2 - bc + 1, c1)  # peut être négatif : le panorama boucle à 360°
    # lignes : le bloc qui contient le panneau et dont le milieu est le plus près de l'horizon (ni tout ciel, ni tout bitume)
    lignes = [lg for lg in range(max(0, l2 - bl + 1), min(l1, nligs - bl) + 1)] or [min(max(l1, 0), nligs - bl)]
    lig0 = min(lignes, key=lambda lg: (abs(lg + bl / 2 - nligs / 2), rng.random()))
    return col0, lig0, bc, bl


def traiter(p, k, out):
    pid = p["id"]
    fj, fi = out / "vues" / f"{pid}.json", out / "vues" / f"{pid}.jpg"
    if fj.exists():
        return
    rng = random.Random(zlib.crc32(pid.encode()))
    W, H = p["dims"]
    if p["tuiles"] is None:
        b = get(f"{API}/{pid}/sd.jpg")
        img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) if b else None
        if img is None:
            with verrou:
                compteur["échec"] += 1
            return
        ech, ox, oy, horizon, tours = img.shape[1] / W, 0.0, 0.0, None, [0]
        with verrou:
            compteur["requêtes"] += 1
    else:
        col0, lig0, bc, bl = fenetre(p, k, rng)
        ncols, tw = int(p["tuiles"][0]), int(p["tuiles"][2])
        img = np.zeros((bl * tw, bc * tw, 3), np.uint8)
        for j in range(bl):
            for i in range(bc):
                b = get(f"{API}/{pid}/tiled/{(col0 + i) % ncols}_{lig0 + j}.jpg")
                t = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) if b else None
                if t is None or t.shape[0] != tw or t.shape[1] != tw:
                    with verrou:
                        compteur["échec"] += 1
                    return
                img[j * tw : (j + 1) * tw, i * tw : (i + 1) * tw] = t
        ech, ox, oy, horizon, tours = 1.0, col0 * tw, lig0 * tw, H / 2 - lig0 * tw, [-W, 0, W]
        with verrou:
            compteur["requêtes"] += bc * bl
    h, w = img.shape[:2]
    annots = []
    for i, a in enumerate(p["annots"]):
        for dx in tours:  # le panorama boucle : une boîte peut tomber dans la vue après un tour
            x1, y1, x2, y2 = ((a["box"][0] + dx) * ech - ox, a["box"][1] * ech - oy, (a["box"][2] + dx) * ech - ox, a["box"][3] * ech - oy)
            ix, iy = min(x2, w) - max(x1, 0), min(y2, h) - max(y1, 0)
            if ix > 0 and iy > 0 and ix * iy >= 0.5 * (x2 - x1) * (y2 - y1):
                annots.append({"code": a["code"], "box": [round(max(x1, 0), 1), round(max(y1, 0), 1), round(min(x2, w), 1), round(min(y2, h), 1)],
                               "det": a["det"], "cls": a["cls"], "modele": a["modele"], "principal": i == k})
                break
    cv2.imwrite(str(fi), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    meta = {"id": pid, "plate": p["tuiles"] is None, "w": w, "h": h, "horizon": horizon, "echelle": round(ech, 4), "px_par_degre": round(W * ech / 360, 2) if p["fov"] == 360 else None,
            "lon": p["lon"], "lat": p["lat"], "date": (p["ts"] or "")[:10], "producteur": p["prod"], "sequence": p["col"], "licence": p["licence"],
            "source": f"https://panoramax.ign.fr/#focus=pic&pic={pid}", "annots": annots}
    fj.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    with verrou:
        compteur["vues"] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="datasets_src/panoramax")
    ap.add_argument("--out", default="datasets_src/panoramax")
    ap.add_argument("--par-code", type=int, default=130)
    ap.add_argument("--fils", type=int, default=8)
    ap.add_argument("--max", type=int, default=0, help="nombre maximal de photos (0 = toutes)")
    ap.add_argument("--graine", type=int, default=0)
    a = ap.parse_args()
    index, out = Path(a.index), Path(a.out)
    (out / "vues").mkdir(parents=True, exist_ok=True)
    photos, choisies, stats = choisir(index, a.par_code, a.graine)
    ids = list(choisies)
    random.Random(a.graine).shuffle(ids)  # ordre aléatoire : un arrêt en cours de route laisse un échantillon équilibré
    if a.max:
        ids = ids[: a.max]
    plates = sum(photos[i]["tuiles"] is None for i in ids)
    print(f"{len(photos)} photos indexées, {len(ids)} retenues ({plates} plates), {len(stats)} codes", flush=True)
    (out / "selection.json").write_text(json.dumps({"stats": stats, "n": len(ids)}, ensure_ascii=False), encoding="utf-8")
    t0 = time.time()
    with ThreadPoolExecutor(a.fils) as ex:
        for n, _ in enumerate(ex.map(lambda i: traiter(photos[i], choisies[i], out), ids)):
            if n % 500 == 0:
                print(f"{n}/{len(ids)}  {dict(compteur)}  {time.time() - t0:.0f} s", flush=True)
    print(f"Terminé : {dict(compteur)} en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
