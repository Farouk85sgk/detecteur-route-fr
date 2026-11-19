#!/usr/bin/env python
"""Mesure la détection « en direct » sur les trajets de contrôle (tools/trajets_reels.py), avec le vrai moteur de l'appli.

Chaque trajet est une suite de photos prises en roulant (une tous les 1 à 6 mètres). L'outil ouvre l'appli dans un
navigateur, crée un moteur (docs/js/moteur.js) et lui donne les images une par une, comme la caméra du téléphone :
image de 1 280 x 720 (téléphone couché) ou de 720 x 1 280 (téléphone debout, champ plus étroit). Il relève chaque
annonce (panneau confirmé par le suivi) et la compare à la vérité terrain :

- un « passage » (un vrai panneau vu sur plusieurs images) est annoncé si son code est annoncé pendant le passage, dans
  les deux images qui suivent, ou jusqu'à huit images avant (Panoramax n'annote un panneau qu'une fois assez gros) ;
- une annonce de panneau sans passage du même code à ce moment-là est « à tort ou invérifiable » (Panoramax n'annote pas
  tous les panneaux : ce chiffre sert à comparer deux réglages, pas à juger une annonce).

    python tools/mesurer_trajets.py --trajets datasets/trajets_reels --ort DOSSIER_DIST_ONNXRUNTIME \\
        --cas "actuel:cote=512" "loin:cote=512,loin=1" --pas 1 2 --modes couche debout

Dans un cas, ces clés décrivent l'image et non le moteur : flux=1920 (définition de la caméra), echelle=0.6 (objectif
ultra grand-angle : tout est plus petit), zoom=0.02 (flou d'avancée), flou=1.2 (points), bruit=4, jpeg=45, lum=0.6.
--pas 2 : une image sur deux (le véhicule roule deux fois plus vite, ou le téléphone calcule deux fois moins vite).
"""
import argparse, asyncio, collections, functools, http.server, json, os, sys, tempfile, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JS = """
async (cfg) => {
  const { Moteur } = await import('./js/moteur.js');
  const { D } = await import('./js/donnees.js');
  const m = window.__m || (window.__m = new Moteur());
  if (!m.pret) await m.charger({ backend: 'wasm' });
  m.configurer({ cote: cfg.cote, avecUsagers: false, actifs: null, ...cfg.options });
  m.reinitialiser();
  const cv = document.createElement('canvas'); cv.width = cfg.w; cv.height = cfg.h;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const annonces = [], vus = [];
  let ms = 0;
  // Défauts d'une vraie vidéo de téléphone, absents des photos de relevé : flou d'avancée (pose longue quand la lumière
  // baisse : tout s'étire depuis le centre), flou de bougé ou de mise au point, bruit, exposition, compression vidéo.
  const copie = () => { const c = document.createElement('canvas'); c.width = cfg.w; c.height = cfg.h; c.getContext('2d').drawImage(cv, 0, 0); return c; };
  let graine = 12345;
  const alea = () => ((graine = (graine * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  async function degrader(d) {
    if (d.zoom) { const t = copie(), n = 6; for (let i = 0; i < n; i++) { const e = 1 + d.zoom * i / (n - 1); ctx.globalAlpha = 1 / (i + 1); ctx.drawImage(t, cfg.w / 2 * (1 - e), cfg.h / 2 * (1 - e), cfg.w * e, cfg.h * e); } ctx.globalAlpha = 1; }
    if (d.flou || (d.lum && d.lum !== 1)) { const t = copie(); ctx.filter = `${d.flou ? `blur(${d.flou}px)` : ''} ${d.lum && d.lum !== 1 ? `brightness(${d.lum})` : ''}`; ctx.drawImage(t, 0, 0); ctx.filter = 'none'; }
    if (d.bruit) { const im = ctx.getImageData(0, 0, cfg.w, cfg.h), px = im.data; for (let i = 0; i < px.length; i += 4) { const b = (alea() + alea() + alea() - 1.5) * 2 * d.bruit; px[i] += b; px[i + 1] += b; px[i + 2] += b; } ctx.putImageData(im, 0, 0); }
    if (d.jpeg) { const blob = await new Promise(r => cv.toBlob(r, 'image/jpeg', d.jpeg / 100)); const b2 = await createImageBitmap(blob); ctx.drawImage(b2, 0, 0); b2.close(); }
  }
  for (const [k, url] of cfg.images.entries()) {
    const bmp = await createImageBitmap(await (await fetch(url)).blob());
    ctx.fillStyle = 'rgb(114,114,114)'; ctx.fillRect(0, 0, cfg.w, cfg.h);
    const [sx, sy, sw, sh, dx, dy, dw, dh] = cfg.cadre;
    ctx.drawImage(bmp, sx, sy, sw, sh, dx, dy, dw, dh);
    bmp.close();
    await degrader(cfg.degrade || {});
    const t0 = performance.now();
    const res = await m.analyser(cv, cfg.w, cfg.h, {});
    ms += performance.now() - t0;
    for (const t of res.nouveaux) annonces.push({ image: k, code: D.items[m.classe(t)].code, groupe: t.groupe, box: t.box.map(v => Math.round(v)), conf: +t.conf.toFixed(3), vues: t.hits, corrige: !!t.corrige });
    vus.push(m.pistes.filter(t => t.groupe === 's' && t.misses === 0).length);
  }
  return { annonces, vus, ms: ms / Math.max(1, cfg.images.length) };
}
"""


def serveur(racine):
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=racine))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def cadre(mode, vue, echelle=1.0, flux=1280):
    """(largeur, hauteur du flux simulé, découpe de la vue -> flux, fonction cadre de la vue -> cadre du flux).
    echelle < 1 : objectif plus large que celui prévu (ultra grand-angle), la vue n'occupe que le milieu de l'image.
    flux : largeur de l'image de la caméra (1280 ou 1920)."""
    W, H = vue
    if mode == "couche":
        w, h = flux, flux * 9 // 16
        e = w / W * echelle
        ox, oy = (w - W * e) / 2, (h - H * e) / 2
        return w, h, [0, 0, W, H, ox, oy, W * e, H * e], lambda b: [b[0] * e + ox, b[1] * e + oy, b[2] * e + ox, b[3] * e + oy]
    # debout : le téléphone voit 68° en hauteur et 41,6° en largeur ; la vue (68° x 41,6°) n'en couvre que la bande centrale
    import math
    f = (W / 2) / math.tan(math.radians(68 / 2))
    demi = f * math.tan(math.atan(math.tan(math.radians(34)) * 720 / 1280))  # demi-largeur vue par le téléphone debout
    x0, larg = W / 2 - demi, 2 * demi
    w, h = flux * 9 // 16, flux
    e = w / larg
    dy = (h - H * e) / 2
    return w, h, [x0, 0, larg, H, 0, dy, w, H * e], lambda b: [(b[0] - x0) * e, b[1] * e + dy, (b[2] - x0) * e, b[3] * e + dy]


def iou(a, b):
    ix, iy = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def juger(verite, res, pas, w, h, vers_flux, minimum):
    """Compare les annonces d'un trajet à ses passages. Les images sont celles gardées avec le pas (indices d'origine k * pas)."""
    bilan = collections.Counter(); details = []
    passages = []
    for p in verite["passages"]:
        vues = []
        for v in p["vues"]:
            if v["image"] % pas:
                continue
            b = vers_flux(v["box"])
            dedans = max(0, min(b[2], w) - max(b[0], 0)) * max(0, min(b[3], h) - max(b[1], 0)) / max(1e-6, (b[2] - b[0]) * (b[3] - b[1]))
            if dedans >= 0.6:
                vues.append({"k": v["image"] // pas, "box": b, "cote": max(b[2] - b[0], b[3] - b[1])})
        if vues and max(v["cote"] for v in vues) * 640 / max(w, h) >= minimum:  # assez gros, au moins une fois, pour être lisible à l'échelle 640
            passages.append({"code": p["code"], "vues": vues, "debut": vues[0]["k"], "fin": vues[-1]["k"]})
    sign = [a for a in res["annonces"] if a["groupe"] == "s"]
    pris = set()
    for p in passages:
        bilan["passages"] += 1
        # l'annonce peut précéder le passage : Panoramax n'annote un panneau qu'une fois assez gros, la vue au loin le voit avant
        tot = p["debut"] - max(2, -(-8 // pas))
        cand = [(i, a) for i, a in enumerate(sign) if a["code"] == p["code"] and tot <= a["image"] <= p["fin"] + 2 and i not in pris]
        if cand:
            i, a = min(cand, key=lambda ia: max(0, p["debut"] - ia[1]["image"]))  # de préférence une annonce faite pendant le passage
            pris.add(i)
            bilan["annonces_justes"] += 1
            reste = p["fin"] - a["image"]  # images restantes avant la fin du passage : plus c'est grand, plus l'annonce est tôt
            bilan["avance_images"] += max(0, reste)
            vue = min(p["vues"], key=lambda v: abs(v["k"] - a["image"]))
            details.append({"code": p["code"], "annonce": a["image"], "debut": p["debut"], "fin": p["fin"], "cote": round(vue["cote"] * 640 / max(w, h), 1)})
        else:
            autre = [a for a in sign if p["debut"] - 1 <= a["image"] <= p["fin"] + 2 and any(v["k"] == min(max(a["image"], p["debut"]), p["fin"]) and iou(a["box"], v["box"]) >= 0.2 for v in p["vues"])]
            bilan["confondus" if autre else "manques"] += 1
            details.append({"code": p["code"], "manque": True, "pris_pour": autre[0]["code"] if autre else None, "debut": p["debut"], "fin": p["fin"], "vues": len(p["vues"]),
                            "cote_max": round(max(v["cote"] for v in p["vues"]) * 640 / max(w, h), 1)})
    bilan["autres_annonces"] = len(sign) - len(pris)
    return bilan, details


async def mesurer(a):
    from playwright.async_api import async_playwright
    trajets = sorted(d for d in Path(a.trajets).iterdir() if (d / "verite.json").exists())
    if a.seulement:
        trajets = [d for d in trajets if d.name in a.seulement]
    racine = tempfile.mkdtemp(prefix="mesure_trajets_")
    os.symlink(Path(a.docs).resolve(), f"{racine}/app")
    os.symlink(Path(a.trajets).resolve(), f"{racine}/trajets")
    srv = serveur(racine); port = srv.server_address[1]
    cas = []
    for c in a.cas:
        nom, _, reste = c.partition(":")
        opts = dict(kv.split("=") for kv in reste.split(",") if kv)
        cote = int(opts.pop("cote", 512))
        opts = {k: (float(v) if v.replace(".", "", 1).isdigit() else v) for k, v in opts.items()}
        mesure = {k: opts.pop(k) for k in list(opts) if k in ("zoom", "flou", "bruit", "jpeg", "lum", "echelle", "flux")}  # défauts de l'image, pas du moteur
        cas.append((nom, cote, opts, mesure))
    resultats = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=a.chromium or None)
        ctx = await b.new_context(service_workers="block")
        if a.ort:
            async def cdn(route):
                nom = route.request.url.split("/dist/")[-1].split("?")[0]
                await route.fulfill(path=str(Path(a.ort) / nom), content_type="application/wasm" if nom.endswith(".wasm") else "text/javascript", headers={"Access-Control-Allow-Origin": "*"})
            await ctx.route("https://cdn.jsdelivr.net/npm/onnxruntime-web@*/dist/**", cdn)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: print("erreur de page :", e, file=sys.stderr))
        await pg.goto(f"http://127.0.0.1:{port}/app/?backend=wasm")
        await pg.wait_for_selector(".heros, .page", timeout=60000)
        for nom, cote, opts, mesure in cas:
            for mode in a.modes:
                for pas in a.pas:
                    total = collections.Counter(); tous = []; ms = []
                    for d in trajets:
                        v = json.loads((d / "verite.json").read_text())
                        w, h, decoupe, vers_flux = cadre(mode, v["vue"]["taille"], mesure.get("echelle", 1.0), int(mesure.get("flux", 1280)))
                        images = [f"/trajets/{d.name}/{im['fichier']}" for k, im in enumerate(v["images"]) if k % pas == 0]
                        res = await pg.evaluate(JS, {"cote": cote, "options": opts, "w": w, "h": h, "cadre": decoupe, "images": images, "degrade": mesure})
                        bilan, details = juger(v, res, pas, w, h, vers_flux, a.minimum)
                        total.update(bilan); ms.append(res["ms"])
                        tous.append({"trajet": d.name, "bilan": dict(bilan), "details": details, "annonces": res["annonces"]})
                    n = max(1, total["passages"])
                    cle = f"{nom} | {mode} | 1 image sur {pas}"
                    resultats[cle] = {"bilan": dict(total), "trajets": tous, "ms": sum(ms) / max(1, len(ms))}
                    print(f"{cle:44s} passages {total['passages']:3d}  annoncés {total['annonces_justes']:3d} ({100 * total['annonces_justes'] / n:4.0f} %)  confondus {total['confondus']:2d}  "
                          f"manqués {total['manques']:3d}  autres annonces {total['autres_annonces']:3d}  avance {total['avance_images'] / max(1, total['annonces_justes']):.1f} image(s)  {sum(ms) / max(1, len(ms)):.0f} ms", flush=True)
        await b.close()
    srv.shutdown()
    if a.sortie:
        Path(a.sortie).write_text(json.dumps(resultats, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trajets", required=True); ap.add_argument("--docs", default=str(ROOT / "docs"))
    ap.add_argument("--ort", default="", help="dossier dist d'onnxruntime-web (sinon chargé depuis le CDN)")
    ap.add_argument("--chromium", default="/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else "")
    ap.add_argument("--cas", nargs="+", default=["actuel:cote=512"], help="nom:cote=512,option=valeur... (options passées à moteur.configurer)")
    ap.add_argument("--modes", nargs="+", default=["couche"], choices=["couche", "debout"])
    ap.add_argument("--pas", nargs="+", type=int, default=[1])
    ap.add_argument("--minimum", type=float, default=14, help="taille (points à l'échelle 640) que le panneau doit atteindre pour compter")
    ap.add_argument("--seulement", nargs="*"); ap.add_argument("--sortie", default="")
    asyncio.run(mesurer(ap.parse_args()))
