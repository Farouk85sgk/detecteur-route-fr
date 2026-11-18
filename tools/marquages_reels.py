#!/usr/bin/env python
"""Vraies photos de marquages au sol : collecte, annotation, mesure du détecteur, export pour l'entraînement.

Le détecteur a d'abord appris les marquages sur des images de synthèse seulement. Mesuré sur de vraies rues, il ne
trouvait que 16 % des marquages (pictogramme vélo 6 %, passage piétons 19 %, « BUS » 19 %). Cet outil sert à constituer
et à utiliser un jeu de vraies photos annotées, tirées de Panoramax (instance IGN, Licence Ouverte 2.0).

  collecte --nom paris_rivoli --bbox 2.3400,48.8590,2.3470,48.8610 --max 60 --out DOSSIER
      cherche les photos de la zone, en garde une tous les 13 m environ, et enregistre de chacune une vue « conducteur »
      de 1280 x 720 (photos à 360° : vue vers l'avant reprojetée ; photos ordinaires : partie basse de l'image)
      -> DOSSIER/vues/<id>.jpg et DOSSIER/meta.jsonl (une ligne par vue : id, zone, lon, lat, auteur, date, licence, type)
  refaire --dossier DOSSIER
      retélécharge les vues notées dans DOSSIER/meta.jsonl (ou seulement les vues annotées avec --annotees) : les
      annotations du dépôt (data/marquages_reels/) suffisent ainsi à reconstituer le jeu d'images
  reparer --dossier DOSSIER [--appliquer]
      refait les vues à 360° dont l'ancienne découpe avait étiré les bords (photos découpées en 16 x 8 tuiles) et signale
      les cadres d'annotation tombés dans la partie étirée (rapport : DOSSIER/reparation.json)
  planches --dossier DOSSIER
      assemble les vues en planches de 9 (3 x 3, numérotées) -> DOSSIER/planches/p_000.jpg ... et DOSSIER/planches/index.json
  grille --dossier DOSSIER --id IDENTIFIANT [...]
      vue quadrillée tous les 80 points, pour lire les coordonnées d'un marquage
  annote --dossier DOSSIER --id IDENTIFIANT --boites "M_velo:612,300,700,352;M_bus:..."
      enregistre tous les marquages d'une vue (cadres resserrés sur la peinture) et écrit une image de contrôle
  detecte --dossier DOSSIER [--poids FICHIER.pt] [--conf 0.2]     puis     compare --dossier DOSSIER
      passe le détecteur sur les vues annotées, puis compare ses détections aux annotations (tableau par classe)
  bilan POIDS.pt NOM --dossiers D1 D2 ...
      même mesure, additionnée sur plusieurs dossiers, aux seuils 0,25 et 0,35
  exporte --dossiers D1 D2 ... --vers datasets/marquages_reels --partie train
      fenêtres de 416 points et étiquettes YOLO, avec les zones techniques (_ignorer au-dessus de l'horizon, _reel dessous)
"""
import argparse, json, math, os, shutil, sys, time, urllib.request
from pathlib import Path
import cv2
import numpy as np

API = "https://panoramax.ign.fr/api"
ROOT = Path(__file__).resolve().parents[1]


def ecrire_image(chemin, image, qualite=90):
    """Écrit une image et vérifie qu'elle est bien sur le disque (cv2.imwrite ne dit rien quand le disque est plein)."""
    chemin = str(chemin)
    ok = cv2.imwrite(chemin, image, [cv2.IMWRITE_JPEG_QUALITY, qualite])
    if not ok or not os.path.exists(chemin) or os.path.getsize(chemin) < 1000:
        try:
            os.remove(chemin)
        except OSError:
            pass
        libre = shutil.disk_usage(os.path.dirname(chemin)).free // 2**20
        raise SystemExit(f"ÉCRITURE IMPOSSIBLE : {chemin} (place libre : {libre} Mo). Arrête-toi et signale-le : rien n'a été noté pour cette image.")


def get(url, essais=4, delai=30):
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "outil-de-mesure/1.0"})
            with urllib.request.urlopen(req, timeout=delai) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if k == essais - 1:
                print("échec", url.split("/api/")[-1][:80], e, file=sys.stderr)
                return None
            time.sleep(1.5 * (k + 1))


def carte_vue(W, H, sortie=(1280, 720), hfov=82.0, tangage=-12.0):
    """Pour chaque point de la vue « conducteur », sa position (px, py) dans le panorama équirectangulaire entier de W x H points."""
    w, h = sortie
    f = (w / 2) / math.tan(math.radians(hfov / 2))
    xs, ys = np.meshgrid(np.arange(w) - w / 2 + 0.5, np.arange(h) - h / 2 + 0.5)
    d = np.stack([xs, -ys, np.full_like(xs, f)], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    t = math.radians(tangage)
    y = d[..., 1] * math.cos(t) + d[..., 2] * math.sin(t)
    z = -d[..., 1] * math.sin(t) + d[..., 2] * math.cos(t)
    lon, lat = np.arctan2(d[..., 0], z), np.arcsin(np.clip(y, -1, 1))
    return (lon / (2 * math.pi) + 0.5) * W, (0.5 - lat / math.pi) * H


def vue_avant(pano, W, H, x0, y0, sortie=(1280, 720), hfov=82.0, tangage=-12.0):
    """Vue rectiligne vers l'avant tirée d'un panorama équirectangulaire (pano : morceau du panorama dont le coin haut gauche est (x0, y0))."""
    px, py = carte_vue(W, H, sortie, hfov, tangage)
    return cv2.remap(pano, (px - x0).astype(np.float32), (py - y0).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def tuiles_vue(mw, mh, tw, th):
    """Colonnes et rangées de tuiles qu'il faut pour couvrir toute la vue (bornes comprises).

    Avant novembre 2026, l'outil prenait toujours les 2 x 2 tuiles du centre. C'est assez pour un panorama découpé en
    8 x 4 tuiles (45° par tuile), mais pas pour les photos récentes découpées en 16 x 8 (22,5° par tuile) : la vue
    n'avait que 45° de vraie image et ses bords étaient étirés. On calcule maintenant les tuiles nécessaires."""
    px, py = carte_vue(mw * tw, mh * th)
    c0, c1 = max(0, int(math.floor(px.min())) // tw), min(mw - 1, (int(math.ceil(px.max())) + 1) // tw)
    r0, r1 = max(0, int(math.floor(py.min())) // th), min(mh - 1, (int(math.ceil(py.max())) + 1) // th)
    return c0, c1, r0, r1


def vue_360(pid, tm):
    """Vue « conducteur » d'une photo à 360°, assemblée à partir des tuiles qui la couvrent ; None si une tuile manque."""
    mw, mh, tw, th = int(tm[0]["matrixWidth"]), int(tm[0]["matrixHeight"]), int(tm[0]["tileWidth"]), int(tm[0]["tileHeight"])
    c0, c1, r0, r1 = tuiles_vue(mw, mh, tw, th)
    lignes = []
    for r in range(r0, r1 + 1):
        ligne = []
        for c in range(c0, c1 + 1):
            b = get(f"{API}/pictures/{pid}/tiled/{c}_{r}.jpg")
            t = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) if b else None
            if t is None:
                return None
            ligne.append(t if t.shape[:2] == (th, tw) else cv2.resize(t, (tw, th), interpolation=cv2.INTER_AREA))
        lignes.append(np.hstack(ligne))
    return vue_avant(np.vstack(lignes), mw * tw, mh * th, c0 * tw, r0 * th)


def collecte(a):
    out = Path(a.out); (out / "vues").mkdir(parents=True, exist_ok=True)
    deja = {json.loads(l)["id"] for l in (out / "meta.jsonl").read_text().splitlines()} if (out / "meta.jsonl").exists() else set()
    b = get(f"{API}/search?bbox={a.bbox}&limit={a.limite}")
    if not b:
        raise SystemExit("recherche impossible")
    feats = json.loads(b)["features"]
    vus, n = set(), 0
    with open(out / "meta.jsonl", "a") as meta:
        for ft in feats:
            if n >= a.max:
                break
            p, pid = ft["properties"], ft["id"]
            lon, lat = ft["geometry"]["coordinates"]
            case = (round(lon / 0.00018), round(lat / 0.00012))
            if case in vus or pid in deja:
                continue
            vus.add(case)
            io = p.get("pers:interior_orientation") or {}
            tm = (p.get("tiles:tile_matrix_sets") or {}).get("geovisio", {}).get("tileMatrix")
            if io.get("field_of_view") == 360 and tm:
                vue, genre = vue_360(pid, tm), "360"
                if vue is None:
                    continue
            else:
                d = get(f"{API}/pictures/{pid}/sd.jpg")
                img = cv2.imdecode(np.frombuffer(d, np.uint8), cv2.IMREAD_COLOR) if d else None
                if img is None or img.shape[1] < img.shape[0]:  # photo debout : écartée
                    continue
                img = cv2.resize(img, (1280, round(1280 * img.shape[0] / img.shape[1])), interpolation=cv2.INTER_AREA)
                if img.shape[0] < 720:
                    continue
                y0 = round((img.shape[0] - 720) * 0.75)
                vue, genre = img[y0 : y0 + 720], "ordinaire"
            ecrire_image(out / "vues" / f"{pid}.jpg", vue)
            meta.write(json.dumps({"id": pid, "zone": a.nom, "lon": lon, "lat": lat, "auteur": p.get("geovisio:producer"), "date": (p.get("datetime") or "")[:10],
                                   "licence": p.get("license"), "type": genre, "source": f"https://panoramax.ign.fr/#focus=pic&pic={pid}"}, ensure_ascii=False) + "\n")
            n += 1
    print(f"{a.nom} : {len(feats)} photos trouvées dans la zone, {n} vues enregistrées dans {out / 'vues'}")


def planches(a):
    d = Path(a.dossier); (d / "planches").mkdir(exist_ok=True)
    fichiers = sorted((d / "vues").glob("*.jpg"))
    index = {}
    for k in range(0, len(fichiers), 9):
        lot = fichiers[k : k + 9]
        cases = []
        for i, f in enumerate(lot):
            src = cv2.imread(str(f))
            if src is None:
                continue
            im = cv2.resize(src, (640, 360), interpolation=cv2.INTER_AREA)
            cv2.rectangle(im, (0, 0), (78, 34), (0, 0, 0), -1)
            cv2.putText(im, str(k + i), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
            index[k + i] = f.stem
            cases.append(im)
        while len(cases) < 9:
            cases.append(np.zeros((360, 640, 3), np.uint8))
        ecrire_image(d / "planches" / f"p_{k // 9:03d}.jpg", np.vstack([np.hstack(cases[r * 3 : r * 3 + 3]) for r in range(3)]), 85)
    (d / "planches" / "index.json").write_text(json.dumps(index, indent=0))
    print(f"{len(fichiers)} vues -> {math.ceil(len(fichiers) / 9)} planches dans {d / 'planches'} (numéro -> identifiant : planches/index.json)")


COULEURS = {"M_bus": (0, 200, 255), "M_livraison": (0, 220, 220), "M_vitesse_sol": (255, 120, 0), "M_velo": (0, 220, 0), "M_zigzag": (0, 255, 255), "panneau": (60, 60, 255)}


def detecte(a):
    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "yolov5"))
    import torch
    torch.set_num_threads(2)  # plusieurs mesures tournent souvent en même temps sur la même machine
    from models.experimental import attempt_load
    from utils.general import non_max_suppression
    d = Path(a.dossier); (d / "det").mkdir(exist_ok=True)
    model = attempt_load(a.poids, device=torch.device("cpu"), fuse=True).eval()
    noms = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
    fichiers = sorted((d / "vues").glob("*.jpg"))
    if a.seulement:
        fichiers = [f for f in fichiers if f.stem in set(a.seulement)]
    elif not a.toutes and (d / "annots").exists() and list((d / "annots").glob("*.json")):
        # par défaut, seules les vues annotées sont analysées : c'est ce que « compare » regarde, et c'est bien plus rapide
        annotees = {f.stem for f in (d / "annots").glob("*.json")}
        fichiers = [f for f in fichiers if f.stem in annotees]
    fdet = d / (a.sortie or "det.json")
    res = json.loads(fdet.read_text()) if fdet.exists() and not a.sortie else {}
    for f in fichiers:
        im = cv2.imread(str(f)); H, W = im.shape[:2]
        k = 640 / max(H, W); nh, nw = round(H * k), round(W * k)
        x = cv2.copyMakeBorder(cv2.resize(im, (nw, nh)), 0, (32 - nh % 32) % 32, 0, (32 - nw % 32) % 32, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        x = torch.from_numpy(x[..., ::-1].copy()).permute(2, 0, 1)[None].float() / 255
        with torch.no_grad():
            y = model(x)[0].float()
        det = non_max_suppression(y, a.conf, 0.5, max_det=100)[0].numpy()
        liste = []
        for x1, y1, x2, y2, c, cl in det:
            nom = noms[int(cl)]
            if nom.startswith("_"):
                continue
            box = [round(float(v) / k, 1) for v in (x1, y1, x2, y2)]
            liste.append({"classe": nom, "conf": round(float(c), 3), "box": box})
            coul = COULEURS.get(nom, (255, 255, 255))
            cv2.rectangle(im, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), coul, 2)
            cv2.rectangle(im, (int(box[0]), max(0, int(box[1]) - 20)), (int(box[0]) + 10 * len(nom) + 52, max(20, int(box[1]))), coul, -1)
            cv2.putText(im, f"{nom} {c:.2f}", (int(box[0]) + 3, max(15, int(box[1]) - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        res[f.stem] = liste
        if not a.sortie:
            cv2.imwrite(str(d / "det" / f"{f.stem}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 88])
    fdet.write_text(json.dumps(res))
    import collections
    c = collections.Counter(x["classe"] for l in res.values() for x in l)
    if not getattr(a, "silence", False):
        print(f"{len(fichiers)} vues analysées (seuil {a.conf}) -> {d / 'det'} ; détections par classe : {dict(c.most_common())}")


def vue_de(pid):
    """Vue « conducteur » d'une photo Panoramax connue par son identifiant (même découpe que « collecte »)."""
    b = get(f"{API}/search?ids={pid}")
    feats = json.loads(b).get("features", []) if b else []
    if not feats:
        return None
    p = feats[0]["properties"]
    io = p.get("pers:interior_orientation") or {}
    tm = (p.get("tiles:tile_matrix_sets") or {}).get("geovisio", {}).get("tileMatrix")
    if io.get("field_of_view") == 360 and tm:
        return vue_360(pid, tm)
    d = get(f"{API}/pictures/{pid}/sd.jpg")
    img = cv2.imdecode(np.frombuffer(d, np.uint8), cv2.IMREAD_COLOR) if d else None
    if img is None or img.shape[1] < img.shape[0]:
        return None
    img = cv2.resize(img, (1280, round(1280 * img.shape[0] / img.shape[1])), interpolation=cv2.INTER_AREA)
    if img.shape[0] < 720:
        return None
    y0 = round((img.shape[0] - 720) * 0.75)
    return img[y0 : y0 + 720]


def refaire(a):
    d = Path(a.dossier); (d / "vues").mkdir(parents=True, exist_ok=True)
    ids = [json.loads(l)["id"] for l in (d / "meta.jsonl").read_text().splitlines() if l.strip()]
    if a.annotees:
        annotees = {f.stem for f in (d / "annots").glob("*.json")}
        ids = [i for i in ids if i in annotees]
    n = 0
    for pid in ids:
        f = d / "vues" / f"{pid}.jpg"
        if f.exists():
            continue
        vue = vue_de(pid)
        if vue is None:
            print("introuvable :", pid); continue
        ecrire_image(f, vue); n += 1
    print(f"{d} : {n} vues retéléchargées, {len(ids)} attendues")


def zone_saine(mw, mh, tw, th):
    """Points de la vue que l'ancienne découpe (les 2 x 2 tuiles du centre) couvrait vraiment ; ailleurs, l'image était étirée."""
    px, py = carte_vue(mw * tw, mh * th)
    c0, r0 = mw // 2 - 1, mh // 2 - 1
    return (px >= c0 * tw) & (px <= (c0 + 2) * tw - 1) & (py >= r0 * th) & (py <= (r0 + 2) * th - 1)


def reparer(a):
    """Refait les vues à 360° que l'ancienne découpe avait étirées sur les bords (panoramas découpés en 16 x 8 tuiles) et
    signale les cadres d'annotation tombés dans la partie étirée. La partie saine de la vue ne change pas : les cadres qui
    s'y trouvent restent justes. Sans --appliquer, rien n'est modifié : le rapport (reparation.json) dit ce qui le serait."""
    d = Path(a.dossier)
    rapport, n_ref = {}, 0
    for f in sorted((d / "annots").glob("*.json")):
        pid = f.stem
        b = get(f"{API}/search?ids={pid}")
        feats = json.loads(b).get("features", []) if b else []
        if not feats:
            rapport[pid] = {"erreur": "photo introuvable"}; continue
        p = feats[0]["properties"]
        tm = (p.get("tiles:tile_matrix_sets") or {}).get("geovisio", {}).get("tileMatrix")
        if (p.get("pers:interior_orientation") or {}).get("field_of_view") != 360 or not tm:
            continue
        mw, mh, tw, th = int(tm[0]["matrixWidth"]), int(tm[0]["matrixHeight"]), int(tm[0]["tileWidth"]), int(tm[0]["tileHeight"])
        if tuiles_vue(mw, mh, tw, th) == (mw // 2 - 1, mw // 2, mh // 2 - 1, mh // 2):
            continue  # les 2 x 2 tuiles du centre suffisaient : vue juste
        saine = zone_saine(mw, mh, tw, th)
        ancienne = cv2.imread(str(d / "vues" / f"{pid}.jpg"))
        nouvelle = vue_360(pid, tm)
        if nouvelle is None:
            rapport[pid] = {"erreur": "tuiles manquantes"}; continue
        ecart = float(np.abs(nouvelle.astype(np.int16) - ancienne.astype(np.int16))[saine].mean()) if ancienne is not None else None
        objets = json.loads(f.read_text())
        douteux = []
        for k, o in enumerate(objets):
            x1, y1, x2, y2 = (int(round(v)) for v in o["box"])
            m = saine[max(0, y1) : max(0, y2), max(0, x1) : max(0, x2)]
            hors = float(1 - m.mean()) if m.size else 1.0
            if hors > 0.15:
                douteux.append({"cadre": k, "classe": o["classe"], "box": o["box"], "part_etiree": round(hors, 2)})
        appliquee = bool(a.appliquer and (ecart is None or ecart < 8))
        rapport[pid] = {"tuiles": f"{mw}x{mh}", "part_saine": round(float(saine.mean()), 3), "ecart_partie_saine": None if ecart is None else round(ecart, 2),
                        "cadres_douteux": douteux, "refaite": appliquee}
        if appliquee:
            (d / "vues_etirees").mkdir(exist_ok=True)
            if ancienne is not None and not (d / "vues_etirees" / f"{pid}.jpg").exists():
                shutil.copy(d / "vues" / f"{pid}.jpg", d / "vues_etirees" / f"{pid}.jpg")
            ecrire_image(d / "vues" / f"{pid}.jpg", nouvelle)
            dessiner_controle(d, pid, objets)
            n_ref += 1
    (d / "reparation.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1))
    etirees = [k for k, v in rapport.items() if "tuiles" in v]
    print(f"{d} : {len(etirees)} vues étirées sur {len(list((d / 'annots').glob('*.json')))} annotées, {n_ref} refaites, "
          f"{sum(len(rapport[k]['cadres_douteux']) for k in etirees)} cadres à revoir, {sum('erreur' in v for v in rapport.values())} erreurs")


def bilan(a):
    """Additionne la mesure de « compare » sur plusieurs dossiers, pour un jeu de poids donné."""
    import collections, types
    for conf in a.conf:
        tot = collections.defaultdict(collections.Counter); autres = collections.defaultdict(collections.Counter); vues = 0
        for dossier in a.dossiers:
            d = Path(dossier)
            ids = [f.stem for f in (d / "annots").glob("*.json")] if (d / "annots").exists() else []
            if not ids:
                continue
            det = f"det_{a.nom}.json"
            if conf == a.conf[0]:
                detecte(types.SimpleNamespace(dossier=str(d), poids=a.poids, conf=0.1, seulement=ids, toutes=False, sortie=det, silence=True))
            compare(types.SimpleNamespace(dossier=str(d), conf=conf, det=det, silence=True))
            b = json.loads((d / f"comparaison_{det}").read_text())["bilan"]; vues += len(ids)
            for c, v in b.items():
                for k in ("instances", "bien", "manques", "fausses"):
                    tot[c][k] += v[k]
                for k, n in v["autre_nom"].items():
                    autres[c][k] += n; tot[c]["autre"] += n
        print(f"\n{a.nom} : {vues} vues annotées, seuil {conf}")
        print(f"{'classe':28s} {'inst.':>5s} {'bien':>5s} {'%':>5s} {'autre nom':>9s} {'manqués':>7s} {'fausses':>7s}")
        S = collections.Counter()
        for c in sorted(tot, key=lambda c: -tot[c]["instances"]):
            v = tot[c]
            if c.startswith("M_ligne_"):
                continue
            for k in ("instances", "bien", "autre", "manques", "fausses"):
                S[k] += v[k]
            print(f"{c:28s} {v['instances']:5d} {v['bien']:5d} {100 * v['bien'] / max(1, v['instances']):4.0f}% {v['autre']:9d} {v['manques']:7d} {v['fausses']:7d}   {dict(autres[c]) or ''}")
        print(f"{'TOTAL (hors lignes)':28s} {S['instances']:5d} {S['bien']:5d} {100 * S['bien'] / max(1, S['instances']):4.0f}% {S['autre']:9d} {S['manques']:7d} {S['fausses']:7d}")


CLASSES_MARQUAGES = None


def classes_marquages():
    global CLASSES_MARQUAGES
    if CLASSES_MARQUAGES is None:
        sys.path.insert(0, str(ROOT))
        from route_fr.classes import DETECTEUR
        CLASSES_MARQUAGES = list(DETECTEUR)
    return CLASSES_MARQUAGES


def grille(a):
    """Vue quadrillée tous les 80 points, axes chiffrés : pour lire les coordonnées d'un marquage avant de l'annoter."""
    d = Path(a.dossier); (d / "grilles").mkdir(exist_ok=True)
    for pid in a.id:
        im = cv2.imread(str(d / "vues" / f"{pid}.jpg"))
        if im is None:
            print("vue introuvable :", pid); continue
        H, W = im.shape[:2]
        for x in range(0, W, 80):
            cv2.line(im, (x, 0), (x, H), (255, 255, 0) if x % 160 == 0 else (120, 200, 120), 1)
            if x % 160 == 0:
                for y in (14, H // 2, H - 6):
                    cv2.putText(im, str(x), (x + 2, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv2.LINE_AA); cv2.putText(im, str(x), (x + 2, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)
        for y in range(0, H, 80):
            cv2.line(im, (0, y), (W, y), (255, 255, 0) if y % 160 == 0 else (120, 200, 120), 1)
            for x in (2, W // 2, W - 36):
                cv2.putText(im, str(y), (x, y + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv2.LINE_AA); cv2.putText(im, str(y), (x, y + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)
        ecrire_image(d / "grilles" / f"{pid}.jpg", im, 88)
        print(d / "grilles" / f"{pid}.jpg")


def ajuster(im, box, jaune):
    """Resserre le cadre sur la peinture (claire, ou jaune) trouvée à l'intérieur du cadre agrandi de 12 %."""
    H, W = im.shape[:2]
    x1, y1, x2, y2 = box
    mx, my = 0.12 * (x2 - x1) + 4, 0.12 * (y2 - y1) + 4
    X1, Y1, X2, Y2 = int(max(0, x1 - mx)), int(max(0, y1 - my)), int(min(W, x2 + mx)), int(min(H, y2 + my))
    zone = im[Y1:Y2, X1:X2]
    if zone.size == 0:
        return box
    hsv = cv2.cvtColor(zone, cv2.COLOR_BGR2HSV).astype(np.int32)
    v = hsv[..., 2]
    if jaune:
        masque = (hsv[..., 0] > 12) & (hsv[..., 0] < 40) & (hsv[..., 1] > 70) & (v > 90)
    else:
        seuil = max(np.percentile(v, 45) + 28, 0.72 * np.percentile(v, 98))
        masque = (v > seuil) & (hsv[..., 1] < 90)
    masque = cv2.morphologyEx(masque.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ys, xs = np.nonzero(masque)
    if len(xs) < 0.04 * masque.size or len(xs) > 0.85 * masque.size:
        return box
    nx1, ny1, nx2, ny2 = X1 + np.percentile(xs, 1), Y1 + np.percentile(ys, 1), X1 + np.percentile(xs, 99) + 1, Y1 + np.percentile(ys, 99) + 1
    if (nx2 - nx1) < 0.45 * (x2 - x1) or (ny2 - ny1) < 0.45 * (y2 - y1):  # la peinture trouvée est bien plus petite que le cadre donné : on garde le cadre
        return box
    return [float(max(0, nx1 - 2)), float(max(0, ny1 - 2)), float(min(W, nx2 + 2)), float(min(H, ny2 + 2))]


def dessiner_controle(d, pid, liste, im=None):
    """Image de contrôle d'une vue annotée (annots/<id>.jpg) : chaque cadre avec le nom de sa classe."""
    im = cv2.imread(str(d / "vues" / f"{pid}.jpg")) if im is None else im
    for o in liste:
        x1, y1, x2, y2 = (int(v) for v in o["box"])
        cv2.rectangle(im, (x1, y1), (x2, y2), (0, 255, 0) if o["classe"] != "_ignorer" else (128, 128, 128), 2)
        cv2.rectangle(im, (x1, max(0, y1 - 18)), (x1 + 9 * len(o["classe"]) + 6, max(18, y1)), (0, 255, 0), -1)
        cv2.putText(im, o["classe"], (x1 + 3, max(13, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    ecrire_image(d / "annots" / f"{pid}.jpg", im, 88)


def annote(a):
    """Enregistre les marquages d'une vue : --boites "M_velo:612,300,700,352;M_bus:..." (remplace l'annotation précédente de cette vue)."""
    d = Path(a.dossier); (d / "annots").mkdir(exist_ok=True)
    im = cv2.imread(str(d / "vues" / f"{a.id}.jpg"))
    if im is None:
        raise SystemExit(f"vue introuvable : {a.id}")
    noms = classes_marquages()
    liste = []
    for morceau in [m for m in a.boites.split(";") if m.strip()]:
        nom, coords = morceau.strip().split(":")
        nom = nom.strip()
        if nom not in noms or nom == "panneau" or nom == "_reel":
            raise SystemExit(f"classe inconnue : {nom}. Classes permises : {[n for n in noms if n not in ('panneau', '_reel')]}")
        box = [float(v) for v in coords.split(",")]
        if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
            raise SystemExit(f"cadre invalide : {morceau} (attendu x1,y1,x2,y2 avec x2 > x1 et y2 > y1)")
        if not a.sans_ajustement and nom != "_ignorer" and not nom.startswith("M_ligne_") and nom not in ("M_zebras", "M_passage_pietons", "M_damier"):
            box = ajuster(im, box, jaune=nom in ("M_zigzag", "M_livraison"))
        liste.append({"classe": nom, "box": [round(v, 1) for v in box]})
    (d / "annots" / f"{a.id}.json").write_text(json.dumps(liste))
    dessiner_controle(d, a.id, liste, im)
    print(f"{len(liste)} marquage(s) enregistré(s) ; contrôle visuel : {d / 'annots' / (a.id + '.jpg')} ; cadres retenus : {[(o['classe'], o['box']) for o in liste]}")


def iou(a, b):
    ix, iy = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def compare(a):
    """Compare les détections (det.json) aux annotations : par classe, trouvés et bien nommés, pris pour autre chose, manqués, et fausses détections."""
    import collections
    d = Path(a.dossier)
    det = json.loads((d / (a.det or "det.json")).read_text())
    table = collections.defaultdict(lambda: {"instances": 0, "bien": 0, "autre_nom": collections.Counter(), "manques": 0, "fausses": 0})
    details = []
    for f in sorted((d / "annots").glob("*.json")):
        pid = f.stem
        gts = [g for g in json.loads(f.read_text())]
        ign = [g["box"] for g in gts if g["classe"] == "_ignorer"]
        gts = [g for g in gts if g["classe"] != "_ignorer"]
        ds = [x for x in det.get(pid, []) if x["conf"] >= a.conf and x["classe"] != "panneau"]
        pris = set()
        for g in gts:
            b = table[g["classe"]]; b["instances"] += 1
            cands = sorted(((iou(g["box"], x["box"]), k) for k, x in enumerate(ds) if k not in pris), reverse=True)
            meme = [(v, k) for v, k in cands if ds[k]["classe"] == g["classe"] and v >= 0.3]
            if meme:
                pris.add(meme[0][1]); b["bien"] += 1
            elif cands and cands[0][0] >= 0.3:
                pris.add(cands[0][1]); b["autre_nom"][ds[cands[0][1]]["classe"]] += 1; details.append((pid, g["classe"], "pris pour " + ds[cands[0][1]]["classe"]))
            else:
                b["manques"] += 1; details.append((pid, g["classe"], "manqué"))
        for k, x in enumerate(ds):  # détections sans marquage annoté dessous (les lignes ne sont pas comptées : elles ne sont pas toutes annotées)
            if k in pris or x["classe"].startswith("M_ligne_") or any(iou(x["box"], z) > 0.2 for z in ign) or any(iou(x["box"], g["box"]) >= 0.3 for g in gts):
                continue
            table[x["classe"]]["fausses"] += 1; details.append((pid, x["classe"], f"fausse détection {x['conf']}"))
    silence = getattr(a, "silence", False)
    if not silence:
        print(f"{len(list((d / 'annots').glob('*.json')))} vues annotées, seuil {a.conf}")
        print(f"{'classe':28s} {'inst.':>5s} {'bien':>5s} {'autre nom':>9s} {'manqués':>7s} {'fausses':>7s}")
    for c in sorted(table):
        b = table[c]
        if not silence:
            print(f"{c:28s} {b['instances']:5d} {b['bien']:5d} {sum(b['autre_nom'].values()):9d} {b['manques']:7d} {b['fausses']:7d}   {dict(b['autre_nom']) or ''}")
    (d / ("comparaison.json" if not a.det else "comparaison_" + a.det)).write_text(json.dumps({"seuil": a.conf, "bilan": {c: {**b, "autre_nom": dict(b["autre_nom"])} for c, b in table.items()}, "details": details}, ensure_ascii=False))


def exporte(a):
    """Fait des vues annotées un jeu d'entraînement au format YOLO : fenêtres carrées de 416 points découpées dans les vues
    (trois fenêtres fixes de 720 points de côté, plus une fenêtre rapprochée par marquage), étiquettes des marquages, et
    zones techniques : rien n'est compté au-dessus de l'horizon (_ignorer : les panneaux n'y sont pas annotés), et sous
    l'horizon seuls les marquages annotés comptent (_reel : un marquage non annoté n'est pas traité comme du fond)."""
    import random, zlib
    noms = classes_marquages()
    k_ign, k_reel = noms.index("_ignorer"), noms.index("_reel")
    dest = Path(a.vers)
    (dest / "images" / a.partie).mkdir(parents=True, exist_ok=True); (dest / "labels" / a.partie).mkdir(parents=True, exist_ok=True)
    n_vues = n_fen = 0
    import collections
    compte = collections.Counter()
    HORIZON = 230
    for dossier in a.dossiers:
        d = Path(dossier)
        for f in sorted((d / "annots").glob("*.json")):
            pid = f.stem
            objets = json.loads(f.read_text())
            im = cv2.imread(str(d / "vues" / f"{pid}.jpg"))
            if im is None or not objets:
                continue
            H, W = im.shape[:2]
            rng = random.Random(zlib.crc32(pid.encode()))
            fenetres = [(x0, 0, 720) for x0 in (0, (W - 720) // 2, W - 720)]
            if a.partie == "train":
                for o in objets:
                    if o["classe"] == "_ignorer" or o["classe"].startswith("M_ligne_"):
                        continue
                    x1, y1, x2, y2 = o["box"]
                    s = int(min(H, max(300, 3.2 * max(x2 - x1, y2 - y1) * rng.uniform(0.8, 1.3))))
                    cx, cy = (x1 + x2) / 2 + rng.uniform(-0.15, 0.15) * s, (y1 + y2) / 2 + rng.uniform(-0.15, 0.15) * s
                    fenetres.append((int(min(max(0, cx - s / 2), W - s)), int(min(max(0, cy - s / 2), H - s)), s))
            n_vues += 1
            for k, (x0, y0, s) in enumerate(fenetres):
                e = 416 / s
                lignes = []
                for o in objets:
                    x1, y1, x2, y2 = o["box"]
                    ix1, iy1, ix2, iy2 = max(x1, x0), max(y1, y0), min(x2, x0 + s), min(y2, y0 + s)
                    if ix2 <= ix1 or iy2 <= iy1:
                        continue
                    part = (ix2 - ix1) * (iy2 - iy1) / max(1e-6, (x2 - x1) * (y2 - y1))
                    garde = o["classe"] != "_ignorer" and part >= 0.6 and max(ix2 - ix1, iy2 - iy1) * e >= 8
                    if not garde and part < 0.05:
                        continue
                    c = noms.index(o["classe"]) if garde else k_ign
                    lignes.append((c, ((ix1 + ix2) / 2 - x0) / s, ((iy1 + iy2) / 2 - y0) / s, (ix2 - ix1) / s, (iy2 - iy1) / s))
                    if garde:
                        compte[o["classe"]] += 1
                if not any(c < k_ign for c, *_ in lignes):
                    continue
                yh = min(max(0, HORIZON - y0), s)
                if yh > 0:
                    lignes.append((k_ign, 0.5, yh / (2 * s), 1.0, yh / s))
                if yh < s:
                    lignes.append((k_reel, 0.5, (yh + s) / (2 * s), 1.0, (s - yh) / s))
                cv2.imwrite(str(dest / "images" / a.partie / f"{pid}_{k}.jpg"), cv2.resize(im[y0 : y0 + s, x0 : x0 + s], (416, 416), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 90])
                (dest / "labels" / a.partie / f"{pid}_{k}.txt").write_text("".join(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n" for c, x, y, w, h in lignes))
                n_fen += 1
    print(f"{n_vues} vues annotées -> {n_fen} fenêtres dans {dest}/images/{a.partie} ; marquages : {dict(compte.most_common())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("collecte"); c.add_argument("--nom", required=True); c.add_argument("--bbox", required=True); c.add_argument("--max", type=int, default=60)
    c.add_argument("--limite", type=int, default=400); c.add_argument("--out", required=True)
    p = sp.add_parser("planches"); p.add_argument("--dossier", required=True)
    t = sp.add_parser("detecte"); t.add_argument("--dossier", required=True); t.add_argument("--poids", default=str(ROOT / "weights" / "route_fr_yolov5n.pt")); t.add_argument("--conf", type=float, default=0.2)
    t.add_argument("--seulement", nargs="*"); t.add_argument("--toutes", action="store_true", help="analyser toutes les vues, pas seulement les vues annotées"); t.add_argument("--sortie", default="", help="autre nom de fichier que det.json (sans images dessinées), pour essayer d'autres poids")
    g = sp.add_parser("grille"); g.add_argument("--dossier", required=True); g.add_argument("--id", nargs="+", required=True)
    n = sp.add_parser("annote"); n.add_argument("--dossier", required=True); n.add_argument("--id", required=True); n.add_argument("--boites", required=True)
    n.add_argument("--sans-ajustement", action="store_true", help="garder exactement les cadres donnés (sinon ils sont resserrés sur la peinture)")
    m = sp.add_parser("compare"); m.add_argument("--dossier", required=True); m.add_argument("--conf", type=float, default=0.25); m.add_argument("--det", default="", help="fichier de détections à comparer (défaut : det.json)")
    x = sp.add_parser("exporte"); x.add_argument("--dossiers", nargs="+", required=True); x.add_argument("--vers", required=True); x.add_argument("--partie", default="train", choices=["train", "val"])
    f = sp.add_parser("refaire"); f.add_argument("--dossier", required=True); f.add_argument("--annotees", action="store_true", help="seulement les vues annotées")
    rp = sp.add_parser("reparer"); rp.add_argument("--dossier", required=True); rp.add_argument("--appliquer", action="store_true", help="remplacer les vues étirées (sinon : rapport seulement)")
    bl = sp.add_parser("bilan"); bl.add_argument("poids"); bl.add_argument("nom"); bl.add_argument("--dossiers", nargs="+", required=True); bl.add_argument("--conf", type=float, nargs="+", default=[0.25, 0.35])
    a = ap.parse_args()
    {"collecte": collecte, "planches": planches, "detecte": detecte, "grille": grille, "annote": annote, "compare": compare, "exporte": exporte, "refaire": refaire, "reparer": reparer, "bilan": bilan}[a.cmd](a)
