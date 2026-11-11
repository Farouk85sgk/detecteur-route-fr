"""Index des panneaux annotés dans Panoramax (instance IGN, photos sous Licence Ouverte Etalab 2.0).

Panoramax publie, pour chaque photo, les panneaux repérés automatiquement et leur code français
(« osm|traffic_sign » = FR:B14[50], FR:AB4...). Ce script interroge l'API par code et enregistre, pour chaque photo
trouvée, ses annotations (une ligne JSON par photo dans <out>/photos.jsonl). Il se relance sans rien refaire.

    python tools/panoramax_index.py --out datasets_src/panoramax --codes data/panoramax_codes.txt

Les photos elles-mêmes sont téléchargées ensuite par tools/panoramax_vignettes.py et tools/panoramax_vues.py.
"""

import argparse
import json
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://panoramax.ign.fr/api/search"
UA = "outil-pedagogique-signalisation/1.0"
CLE = "osm|traffic_sign"
verrou = threading.Lock()


def get(params, essais=5):
    url = API + "?" + urllib.parse.urlencode(params)
    for k in range(essais):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180) as r:
                return json.load(r)
        except Exception as e:  # réseau instable : on réessaie en espaçant
            print(f"  nouvel essai {k + 1} ({e!r:.100})", flush=True)
            time.sleep(5 + 10 * k)
    return None


def resume(f):
    """Garde l'essentiel d'une photo : identité, lieu, géométrie de l'image et annotations de panneaux."""
    p = f["properties"]
    io = p.get("pers:interior_orientation") or {}
    tm = ((p.get("tiles:tile_matrix_sets") or {}).get("geovisio") or {}).get("tileMatrix") or [{}]
    annots = []
    for a in p.get("annotations") or []:
        sem = {s["key"]: s["value"] for s in a.get("semantics") or []}
        code = sem.get(CLE)
        if code is None:
            continue
        xs = [c[0] for c in a["shape"]["coordinates"][0]]
        ys = [c[1] for c in a["shape"]["coordinates"][0]]
        # panneau + panonceau reconnus ensemble (« FR:B6d;FR:M6h ») : confiances jointes par « ; », on garde la plus faible
        conf = lambda prefixe: next((min(float(x) for x in v.split(";")) for k, v in sem.items() if k.startswith(prefixe)), None)  # noqa: E731
        annots.append({"code": code, "box": [min(xs), min(ys), max(xs), max(ys)], "det": conf("detection_confidence"), "cls": conf("classification_confidence"),
                       "modele": next((v for k, v in sem.items() if k.startswith("classification_model")), None)})
    lon, lat = (f.get("geometry") or {}).get("coordinates") or [None, None]
    return {"id": f["id"], "col": f.get("collection"), "lon": lon, "lat": lat, "ts": p.get("datetime"), "prod": p.get("geovisio:producer"),
            "fov": io.get("field_of_view"), "dims": io.get("sensor_array_dimensions"), "cam": io.get("camera_model"),
            "tuiles": [tm[0].get("matrixWidth"), tm[0].get("matrixHeight"), tm[0].get("tileWidth")] if tm[0] else None,
            "azimut": p.get("view:azimuth"), "tangage": p.get("pers:pitch"), "roulis": p.get("pers:roll"), "licence": p.get("license"), "annots": annots}


def traiter(code, out, vus, faits, limite):
    """Deux tirages par code : identifiants croissants puis décroissants (les identifiants sont aléatoires, donc
    l'échantillon couvre toute la base au lieu des seules photos récentes)."""
    total = 0
    for tri in ("+id", "-id"):
        cle = f"{code}\t{tri}"
        if cle in faits:
            continue
        d = get({"limit": limite, "sortby": tri, "filter": f"\"semantics.{CLE}\"='{code}'"})
        if d is None:
            print(f"{code} {tri} : échec", flush=True)
            return
        fs = d.get("features") or []
        lignes = []
        for f in fs:
            try:
                lignes.append((f["id"], json.dumps(resume(f), ensure_ascii=False)))
            except Exception as e:  # annotation inattendue : on passe la photo
                print(f"  photo ignorée {f.get('id')} ({e!r:.80})", flush=True)
        with verrou:
            with open(out / "photos.jsonl", "a", encoding="utf-8") as fh:
                for pid, ligne in lignes:
                    if pid not in vus:
                        vus.add(pid)
                        fh.write(ligne + "\n")
            with open(out / "faits.txt", "a", encoding="utf-8") as fh:
                fh.write(f"{cle}\t{len(fs)}\n")
            faits.add(cle)
        total += len(fs)
        if len(fs) < limite:  # tout a été renvoyé : inutile de tirer dans l'autre sens
            break
    print(f"{code} : {total} photos", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="datasets_src/panoramax")
    ap.add_argument("--codes", required=True, help="fichier texte, un code par ligne (FR:AB4, FR:B14[50]...)")
    ap.add_argument("--limite", type=int, default=1000)
    ap.add_argument("--fils", type=int, default=3)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    vus, faits = set(), set()
    if (out / "photos.jsonl").exists():
        vus = {json.loads(line)["id"] for line in open(out / "photos.jsonl", encoding="utf-8")}
    if (out / "faits.txt").exists():
        faits = {"\t".join(line.split("\t")[:2]) for line in open(out / "faits.txt", encoding="utf-8")}
    codes = [c.strip() for c in open(a.codes, encoding="utf-8") if c.strip() and not c.startswith("#")]
    print(f"{len(codes)} codes, {len(vus)} photos déjà indexées", flush=True)
    with ThreadPoolExecutor(a.fils) as ex:
        list(ex.map(lambda c: traiter(c, out, vus, faits, a.limite), codes))
    print(f"Terminé : {len(vus)} photos indexées dans {out / 'photos.jsonl'}")


if __name__ == "__main__":
    main()
