#!/usr/bin/env python
"""Trajets de contrôle : de vraies suites de photos prises en roulant, pour mesurer la détection « en direct ».

Les mesures sur photos isolées (tools/evaluer_chaine.py) disent si un panneau est reconnu quand il est bien visible.
En roulant, c'est autre chose : le panneau est d'abord minuscule, grossit, puis sort du champ ; l'appli n'a que
quelques images pour le reconnaître. Cet outil reconstitue cette situation avec des séquences Panoramax (instance IGN,
Licence Ouverte 2.0) : des photos à 360° prises tous les 3 à 6 mètres par un véhicule, dans les zones de validation
(jamais vues à l'entraînement), dont on tire la vue qu'aurait un téléphone fixé au pare-brise.

  choisir --index datasets_src/panoramax/photos.jsonl
      cherche dans l'index les suites de photos consécutives des zones de validation et en retient une quinzaine, de
      producteurs variés -> data/trajets_reels/trajets.json (séquence, rang de début et de fin dans la séquence)
  telecharge --out DOSSIER
      pour chaque trajet, télécharge les photos (avec une dizaine de photos d'approche avant le premier panneau annoté)
      et enregistre la vue « téléphone » de 1920 x 1080 (champ horizontal 68°) -> DOSSIER/<trajet>/NNN.jpg, et la
      vérité terrain DOSSIER/<trajet>/verite.json : pour chaque image, les panneaux annotés par Panoramax (code du
      catalogue, cadre dans la vue), reliés d'une image à l'autre en « passages » (un panneau réel, vu sur plusieurs images)
  planche --out DOSSIER --trajet NOM
      planche de contrôle d'un trajet (images réduites, cadres de la vérité terrain)

La mesure elle-même se fait dans le navigateur, avec le vrai moteur de l'appli : tools/mesurer_trajets.py.
"""
import argparse, collections, hashlib, json, math, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
API = "https://panoramax.ign.fr/api"
VUE = (1920, 1080)
HFOV = 68.0  # champ horizontal d'un téléphone en vidéo (objectif principal, image 16:9)
LISTE = ROOT / "data" / "trajets_reels" / "trajets.json"


def get(url, essais=4, brut=False):
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "outil-de-mesure/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = r.read()
                return d if brut else json.loads(d)
        except Exception as e:  # noqa: BLE001
            if k == essais - 1:
                print("échec", url.split("/api/")[-1][:90], e, file=sys.stderr)
                return None
            time.sleep(1.5 * (k + 1))


def en_validation(lon, lat):
    """Même découpage que tools/panoramax_dataset.py : mailles de 0,2° réservées à la validation."""
    maille = f"{int(lon * 5)}_{int(lat * 5)}"
    return int(hashlib.md5(maille.encode()).hexdigest(), 16) % 100 < 6


def distance(a, b):
    k = math.cos(math.radians(a["lat"]))
    return 111320 * math.hypot((a["lon"] - b["lon"]) * k, a["lat"] - b["lat"])


def choisir(a):
    from route_fr.panoramax import code_catalogue
    par_col = collections.defaultdict(list)
    with open(a.index) as f:
        for ligne in f:
            p = json.loads(ligne)
            if p["lon"] is not None and p["fov"] == 360 and p["tuiles"] and en_validation(p["lon"], p["lat"]):
                par_col[p["col"]].append(p)
    suites = []
    for col, ps in par_col.items():
        ps.sort(key=lambda p: p["ts"] or "")
        run = [ps[0]]
        for x, y in zip(ps, ps[1:]):
            if 1.0 <= distance(x, y) <= 14.0:
                run.append(y)
            else:
                if len(run) >= 10:
                    suites.append(run)
                run = [y]
        if len(run) >= 10:
            suites.append(run)
    infos = []
    for r in suites:
        codes = collections.Counter(c for p in r for an in p["annots"] for nat, c in [code_catalogue(an["code"])] if nat == "classe")
        infos.append({"col": r[0]["col"], "producteur": r[0]["prod"], "date": (r[0]["ts"] or "")[:10], "premiere": r[0]["id"], "derniere": r[-1]["id"],
                      "photos": len(r), "codes": len(codes), "pas": round(sum(distance(x, y) for x, y in zip(r, r[1:])) / (len(r) - 1), 1)})
    infos.sort(key=lambda i: (-i["codes"], -i["photos"]))
    retenus, par_prod, par_seq = [], collections.Counter(), collections.Counter()
    for i in infos:  # variété : quatre trajets au plus par producteur, deux par séquence
        if len(retenus) >= a.nombre or par_prod[i["producteur"]] >= 4 or par_seq[i["col"]] >= 2 or i["codes"] < 2:
            continue
        par_prod[i["producteur"]] += 1; par_seq[i["col"]] += 1
        i["nom"] = f"t{len(retenus) + 1:02d}"
        retenus.append(i)
    LISTE.parent.mkdir(parents=True, exist_ok=True)
    LISTE.write_text(json.dumps(retenus, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(suites)} suites de photos consécutives en zone de validation, {len(retenus)} trajets retenus -> {LISTE}")
    for i in retenus:
        print(f"  {i['nom']} {i['producteur'][:38]:38s} {i['date']} {i['photos']:3d} photos, {i['codes']:2d} panneaux différents, {i['pas']} m entre deux photos")


def carte(W, H, tangage=0.0):
    """Pour chaque point de la vue « téléphone », sa position dans le panorama équirectangulaire de W x H points."""
    w, h = VUE
    f = (w / 2) / math.tan(math.radians(HFOV / 2))
    xs, ys = np.meshgrid(np.arange(w) - w / 2 + 0.5, np.arange(h) - h / 2 + 0.5)
    d = np.stack([xs, -ys, np.full_like(xs, f)], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    t = math.radians(tangage)
    y = d[..., 1] * math.cos(t) + d[..., 2] * math.sin(t)
    z = -d[..., 1] * math.sin(t) + d[..., 2] * math.cos(t)
    lon, lat = np.arctan2(d[..., 0], z), np.arcsin(np.clip(y, -1, 1))
    return (lon / (2 * math.pi) + 0.5) * W, (0.5 - lat / math.pi) * H


def vers_vue(px, py, W, H, tangage=0.0):
    """Point du panorama -> point de la vue (None s'il est derrière)."""
    lon, lat = (px / W - 0.5) * 2 * math.pi, (0.5 - py / H) * math.pi
    x, y, z = math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon)
    t = math.radians(tangage)
    yc, zc = y * math.cos(t) - z * math.sin(t), y * math.sin(t) + z * math.cos(t)
    if zc <= 0.05:
        return None
    w, h = VUE
    f = (w / 2) / math.tan(math.radians(HFOV / 2))
    return w / 2 + f * x / zc, h / 2 - f * yc / zc


def vue_photo(pid, tm):
    mw, mh, tw, th = int(tm[0]["matrixWidth"]), int(tm[0]["matrixHeight"]), int(tm[0]["tileWidth"]), int(tm[0]["tileHeight"])
    W, H = mw * tw, mh * th
    px, py = carte(W, H)
    c0, c1 = max(0, int(math.floor(px.min())) // tw), min(mw - 1, (int(math.ceil(px.max())) + 1) // tw)
    r0, r1 = max(0, int(math.floor(py.min())) // th), min(mh - 1, (int(math.ceil(py.max())) + 1) // th)
    urls = [(c, r, f"{API}/pictures/{pid}/tiled/{c}_{r}.jpg") for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    with ThreadPoolExecutor(6) as ex:
        tuiles = dict(zip([(c, r) for c, r, _ in urls], ex.map(lambda u: get(u[2], brut=True), urls)))
    lignes = []
    for r in range(r0, r1 + 1):
        ligne = []
        for c in range(c0, c1 + 1):
            b = tuiles[(c, r)]
            t = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) if b else None
            if t is None:
                return None, W, H
            ligne.append(t if t.shape[:2] == (th, tw) else cv2.resize(t, (tw, th), interpolation=cv2.INTER_AREA))
        lignes.append(np.hstack(ligne))
    pano = np.vstack(lignes)
    # panorama plus fin que la vue : on le réduit d'abord (sinon le rééchantillonnage laisse du crénelage)
    return cv2.remap(pano, (px - c0 * tw).astype(np.float32), (py - r0 * th).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE), W, H


def annotations(p, W, H):
    """Panneaux annotés d'une photo, placés dans la vue : [{code, nature, box, conf}] (code du catalogue, ou None)."""
    from route_fr.panoramax import code_catalogue
    out = []
    for an in p.get("annotations") or []:
        sem = {s["key"]: s["value"] for s in an.get("semantics") or []}
        brut = sem.get("osm|traffic_sign")
        if brut is None:
            continue
        xs = [c[0] for c in an["shape"]["coordinates"][0]]; ys = [c[1] for c in an["shape"]["coordinates"][0]]
        coins = [vers_vue(x, y, W, H) for x in (min(xs), max(xs)) for y in (min(ys), max(ys))]
        if any(c is None for c in coins):
            continue
        x1, y1, x2, y2 = min(c[0] for c in coins), min(c[1] for c in coins), max(c[0] for c in coins), max(c[1] for c in coins)
        if x2 < 0 or y2 < 0 or x1 > VUE[0] or y1 > VUE[1] or (x2 - x1) > VUE[0] / 2:
            continue
        dedans = (min(x2, VUE[0]) - max(x1, 0)) * (min(y2, VUE[1]) - max(y1, 0)) / max(1e-6, (x2 - x1) * (y2 - y1))
        nature, code = code_catalogue(brut)
        conf = next((min(float(x) for x in v.split(";")) for k, v in sem.items() if k.startswith("classification_confidence")), None)
        out.append({"code": code, "nature": nature, "brut": brut, "box": [round(v, 1) for v in (x1, y1, x2, y2)], "dedans": round(dedans, 2), "conf": conf})
    return out


def relier(images):
    """Relie les annotations d'une image à l'autre : un « passage » = un même panneau réel suivi sur plusieurs images
    (même code, images voisines, position qui a peu bougé au regard de sa taille)."""
    passages, ouverts = [], []
    for k, im in enumerate(images):
        pris = set()
        for a in im["panneaux"]:
            if a["nature"] != "classe" or a["dedans"] < 0.6:
                continue
            cx, cy, cote = (a["box"][0] + a["box"][2]) / 2, (a["box"][1] + a["box"][3]) / 2, max(a["box"][2] - a["box"][0], a["box"][3] - a["box"][1])
            best = None
            for p in ouverts:
                if p["code"] != a["code"] or id(p) in pris or k - p["fin"] > 2:
                    continue
                d = math.hypot(cx - p["cx"], cy - p["cy"]) / max(cote, p["cote"], 24)
                if d <= 6 and (best is None or d < best[0]):
                    best = (d, p)
            if best:
                p = best[1]
            else:
                p = {"code": a["code"], "debut": k, "vues": []}
                passages.append(p); ouverts.append(p)
            pris.add(id(p))
            p.update(fin=k, cx=cx, cy=cy, cote=cote)
            p["vues"].append({"image": k, "box": a["box"], "cote": round(cote, 1)})
        ouverts = [p for p in ouverts if k - p["fin"] <= 2]
    return [{"code": p["code"], "debut": p["debut"], "fin": p["fin"], "cote_max": max(v["cote"] for v in p["vues"]), "vues": p["vues"]} for p in passages]


def telecharge(a):
    out = Path(a.out)
    for t in json.loads(LISTE.read_text()):
        d = out / t["nom"]
        if (d / "verite.json").exists() and not a.refaire:
            continue
        d.mkdir(parents=True, exist_ok=True)
        rang = lambda pid: (get(f"{API}/collections/{t['col']}/items/{pid}") or {}).get("properties", {}).get("geovisio:rank_in_collection")  # noqa: E731
        r0, r1 = rang(t["premiere"]), rang(t["derniere"])
        if not r0 or not r1:
            print(t["nom"], ": rangs introuvables"); continue
        if r1 < r0:
            r0, r1 = r1, r0
        debut = max(0, r0 - 1 - a.approche)
        items = get(f"{API}/collections/{t['col']}/items?limit={r1 - debut + 3}&startAfterRank={debut}")
        feats = sorted((items or {}).get("features", []), key=lambda f: f["properties"].get("geovisio:rank_in_collection") or 0)
        images = []
        for f in feats:
            p = f["properties"]
            tm = (p.get("tiles:tile_matrix_sets") or {}).get("geovisio", {}).get("tileMatrix")
            if not tm:
                continue
            vue, W, H = vue_photo(f["id"], tm)
            if vue is None:
                continue
            nom = f"{len(images):03d}.jpg"
            cv2.imwrite(str(d / nom), vue, [cv2.IMWRITE_JPEG_QUALITY, 90])
            lon, lat = f["geometry"]["coordinates"]
            images.append({"fichier": nom, "id": f["id"], "rang": p.get("geovisio:rank_in_collection"), "lon": lon, "lat": lat, "quand": p.get("datetime"), "panneaux": annotations(p, W, H)})
        for x, y in zip(images, images[1:]):
            y["avance"] = round(distance(x, y), 1)
        passages = relier(images)
        (d / "verite.json").write_text(json.dumps({"trajet": t, "vue": {"taille": VUE, "champ": HFOV}, "images": images, "passages": passages}, ensure_ascii=False))
        print(f"{t['nom']} : {len(images)} images, {len(passages)} passages de panneaux du catalogue ({sum(p['cote_max'] >= 30 for p in passages)} de 30 points ou plus), {t['producteur']}")


def planche(a):
    d = Path(a.out) / a.trajet
    v = json.loads((d / "verite.json").read_text())
    cases = []
    for k, im in enumerate(v["images"]):
        img = cv2.imread(str(d / im["fichier"]))
        for p in im["panneaux"]:
            x1, y1, x2, y2 = (int(c) for c in p["box"])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0) if p["nature"] == "classe" else (160, 160, 160), 3)
            cv2.putText(img, p["code"] or p["nature"], (x1, max(24, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
        img = cv2.resize(img, (640, 360), interpolation=cv2.INTER_AREA)
        cv2.putText(img, str(k), (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
        cases.append(img)
    cases = cases[a.debut : a.debut + 12]
    while len(cases) % 4:
        cases.append(np.zeros((360, 640, 3), np.uint8))
    f = d / f"planche_{a.debut:03d}.jpg"
    cv2.imwrite(str(f), np.vstack([np.hstack(cases[i : i + 4]) for i in range(0, len(cases), 4)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
    print(f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("choisir"); c.add_argument("--index", default=str(ROOT / "datasets_src" / "panoramax" / "photos.jsonl")); c.add_argument("--nombre", type=int, default=16)
    t = sp.add_parser("telecharge"); t.add_argument("--out", required=True); t.add_argument("--approche", type=int, default=10); t.add_argument("--refaire", action="store_true")
    p = sp.add_parser("planche"); p.add_argument("--out", required=True); p.add_argument("--trajet", required=True); p.add_argument("--debut", type=int, default=0)
    a = ap.parse_args()
    {"choisir": choisir, "telecharge": telecharge, "planche": planche}[a.cmd](a)
