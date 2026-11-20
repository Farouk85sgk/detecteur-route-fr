#!/usr/bin/env python
"""Mesure la détection « en direct » sur les trajets de contrôle (tools/trajets_reels.py), avec le vrai moteur de l'appli.

Chaque trajet est une suite de photos prises en roulant (une tous les 1 à 6 mètres). L'outil ouvre l'appli dans un
navigateur, crée un moteur (docs/js/moteur.js) et lui donne les images une par une, comme la caméra du téléphone :
image de 1 280 x 720 (téléphone couché) ou de 720 x 1 280 (téléphone debout, champ plus étroit). Il relève chaque
annonce (panneau confirmé par le suivi) et la compare à la vérité terrain :

- un « passage » (un vrai panneau vu sur plusieurs images) est annoncé si, pendant le passage, le suivi du moteur tient
  à cet endroit un panneau annoncé sous le bon nom. Peu importe quand l'annonce a été faite : la vue au loin annonce un
  panneau bien avant que Panoramax ne l'annote (il ne l'annote qu'une fois assez gros). À défaut de suivi au bon
  endroit, une annonce du bon nom pendant le passage ou juste autour compte aussi ;
- « avance » : nombre d'images entre l'annonce et la fin du passage (plus c'est grand, plus le conducteur est prévenu tôt) ;
- une annonce de panneau qui ne se rattache à aucun passage est « à tort ou invérifiable » (Panoramax n'annote pas
  tous les panneaux : ce chiffre sert à comparer deux réglages, pas à juger une annonce).

    python tools/mesurer_trajets.py --trajets datasets/trajets_reels --ort DOSSIER_DIST_ONNXRUNTIME \\
        --cas "actuel:cote=512" "loin:cote=512,loin=1" --pas 1 2 --modes couche debout

Dans un cas, ces clés décrivent l'image et non le moteur : flux=1920 (définition de la caméra), echelle=0.6 (objectif
ultra grand-angle : tout est plus petit), zoom=0.02 (flou d'avancée), flou=1.2 (points), bruit=4, jpeg=45, lum=0.6,
rep=2 (deux analyses par image : téléphone deux fois plus rapide), penche=8 (téléphone penché de 8° vers le haut).
--pas 2 : une image sur deux (le véhicule roule deux fois plus vite, ou le téléphone calcule deux fois moins vite).
Les photos sont espacées de 3,6 m en moyenne : à 50 km/h, --pas 1 vaut 4 analyses par seconde, rep=4 en vaut 16.
"""
import argparse, asyncio, collections, functools, http.server, json, math, os, sys, tempfile, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JS = """
async (cfg) => {
  const { Moteur } = await import('./js/moteur.js');
  const { D } = await import('./js/donnees.js');
  const m = window.__m || (window.__m = new Moteur());
  if (!m.pret) await m.charger(cfg.gpu ? {} : { backend: 'wasm' });
  // (le moteur sert à tous les cas : chaque cas repart des réglages d'origine, pas de ceux du cas précédent)
  const origine = window.__origine || (window.__origine = { loin: m.loin, proche: m.proche });
  m.configurer({ cote: cfg.cote, avecUsagers: false, actifs: null, ...origine, ...cfg.options });
  m.reinitialiser();
  m.oublierHorizon?.();  // chaque trajet est une autre voiture, un autre support
  const cv = document.createElement('canvas'); cv.width = cfg.w; cv.height = cfg.h;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const annonces = [], vus = [], suivis = [];
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
    // rep analyses par image : un téléphone rep fois plus rapide (ou un véhicule rep fois plus lent) voit rep fois la même scène
    for (let i = 0; i < (cfg.rep || 1); i++) {
      const t0 = performance.now();
      const res = await m.analyser(cv, cfg.w, cfg.h, {});
      ms += performance.now() - t0;
      for (const t of res.nouveaux) annonces.push({ image: k, id: t.id, code: D.items[m.classe(t)].code, groupe: t.groupe, box: t.box.map(v => Math.round(v)), conf: +t.conf.toFixed(3), vues: t.hits, corrige: !!t.corrige, loin: !!res.champ });
    }
    vus.push(m.pistes.filter(t => t.groupe === 's' && t.misses === 0).length);
    // panneaux annoncés que le suivi tient encore sur cette image, avec le nom dit au conducteur
    suivis.push(m.pistes.filter(t => t.ok && t.groupe === 's' && t.misses <= 1).map(t => ({ id: t.id, code: D.items[t.annonce].code, box: t.box.map(v => Math.round(v)) })));
  }
  return { annonces, vus, suivis, ms: ms / Math.max(1, cfg.images.length * (cfg.rep || 1)) };
}
"""


def serveur(racine):
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=racine))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def cadre(mode, vue, echelle=1.0, flux=1280, penche=0.0):
    """(largeur, hauteur du flux simulé, découpe de la vue -> flux, fonction cadre de la vue -> cadre du flux).
    echelle < 1 : objectif plus large que celui prévu (ultra grand-angle), la vue n'occupe que le milieu de l'image.
    flux : largeur de l'image de la caméra (1280 ou 1920).
    penche : téléphone penché de tant de degrés vers le haut (l'horizon descend dans l'image), ou vers le bas si négatif."""
    W, H = vue
    bascule = penche * flux / 68  # points de l'image par degré, pour un objectif qui voit 68° dans sa grande dimension
    if mode == "couche":
        w, h = flux, flux * 9 // 16
        e = w / W * echelle
        ox, oy = (w - W * e) / 2, (h - H * e) / 2 + bascule
        return w, h, [0, 0, W, H, ox, oy, W * e, H * e], lambda b: [b[0] * e + ox, b[1] * e + oy, b[2] * e + ox, b[3] * e + oy]
    # debout : le téléphone voit 68° en hauteur et 41,6° en largeur ; la vue (68° x 41,6°) n'en couvre que la bande centrale
    f = (W / 2) / math.tan(math.radians(68 / 2))
    demi = f * math.tan(math.atan(math.tan(math.radians(34)) * 720 / 1280))  # demi-largeur vue par le téléphone debout
    x0, larg = W / 2 - demi, 2 * demi
    w, h = flux * 9 // 16, flux
    e = w / larg
    dy = (h - H * e) / 2 + bascule
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
    suivis = res.get("suivis") or []
    def au_meme_endroit(a, b):  # cadre suivi et cadre de la vérité : centres proches (le cadre suivi traîne un peu derrière le panneau)
        return iou(a, b) >= 0.1 or math.hypot((a[0] + a[2] - b[0] - b[2]) / 2, (a[1] + a[3] - b[1] - b[3]) / 2) <= max(a[2] - a[0], a[3] - a[1], b[2] - b[0], b[3] - b[1])
    pris = set()  # identifiants des pistes rattachées à un passage (bon nom ou non)
    for p in passages:
        bilan["passages"] += 1
        bons, autres = set(), {}
        for v in p["vues"]:
            for s in (suivis[v["k"]] if v["k"] < len(suivis) else []):
                if au_meme_endroit(s["box"], v["box"]):
                    if s["code"] == p["code"]: bons.add(s["id"])
                    else: autres[s["id"]] = s["code"]
        a = None
        if bons:  # première annonce, sous le bon nom, d'une de ces pistes
            a = min((x for x in sign if x["id"] in bons and x["code"] == p["code"]), key=lambda x: x["image"], default=None)
            pris |= bons
        if a is None:  # pas de piste au bon endroit : une annonce du bon nom pendant le passage ou juste autour
            a = min((x for x in sign if x["code"] == p["code"] and x["id"] not in pris and p["debut"] - 2 <= x["image"] <= p["fin"] + 2), key=lambda x: x["image"], default=None)
            if a: pris.add(a["id"])
        if a:
            bilan["annonces_justes"] += 1
            bilan["avance_images"] += max(0, p["fin"] - a["image"])
            bilan["annonces_au_loin"] += 1 if a.get("loin") else 0
            vue = min(p["vues"], key=lambda v: abs(v["k"] - a["image"]))
            details.append({"code": p["code"], "annonce": a["image"], "debut": p["debut"], "fin": p["fin"], "loin": bool(a.get("loin")), "cote": round(vue["cote"] * 640 / max(w, h), 1)})
        else:
            pris |= set(autres)
            bilan["confondus" if autres else "manques"] += 1
            details.append({"code": p["code"], "manque": True, "pris_pour": next(iter(autres.values()), None), "debut": p["debut"], "fin": p["fin"], "vues": len(p["vues"]),
                            "cote_max": round(max(v["cote"] for v in p["vues"]) * 640 / max(w, h), 1)})
    bilan["autres_annonces"] = len({x["id"] for x in sign} - pris)
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
        opts = {k: (float(v) if v.lstrip("-").replace(".", "", 1).isdigit() else v) for k, v in opts.items()}
        mesure = {k: opts.pop(k) for k in list(opts) if k in ("zoom", "flou", "bruit", "jpeg", "lum", "echelle", "flux", "rep", "penche")}  # défauts de l'image, pas du moteur
        cas.append((nom, cote, opts, mesure))
    resultats = {}
    async with async_playwright() as p:
        # --gpu : carte graphique WebGPU logicielle de Chromium (lente, mais c'est le vrai chemin de calcul des téléphones)
        gpu = ["--enable-unsafe-webgpu", "--enable-features=Vulkan,WebGPU", "--use-vulkan=swiftshader", "--use-webgpu-adapter=swiftshader", "--ignore-gpu-blocklist",
               "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] if a.gpu else []
        b = await p.chromium.launch(executable_path=a.chromium or None, args=gpu)
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
                        w, h, decoupe, vers_flux = cadre(mode, v["vue"]["taille"], mesure.get("echelle", 1.0), int(mesure.get("flux", 1280)), mesure.get("penche", 0.0))
                        images = [f"/trajets/{d.name}/{im['fichier']}" for k, im in enumerate(v["images"]) if k % pas == 0]
                        res = await pg.evaluate(JS, {"cote": cote, "options": opts, "w": w, "h": h, "cadre": decoupe, "images": images, "degrade": mesure, "rep": int(mesure.get("rep", 1)), "gpu": a.gpu})
                        bilan, details = juger(v, res, pas, w, h, vers_flux, a.minimum)
                        total.update(bilan); ms.append(res["ms"])
                        tous.append({"trajet": d.name, "bilan": dict(bilan), "details": details, "annonces": res["annonces"]})
                    if a.gpu and not resultats: print("moteur :", await pg.evaluate("window.__m.fournisseurs.join('+') + (window.__m.gpuEcarte ? ' (carte graphique écartée)' : '')"), flush=True)
                    n = max(1, total["passages"])
                    cle = f"{nom} | {mode} | 1 image sur {pas}"
                    resultats[cle] = {"bilan": dict(total), "trajets": tous, "ms": sum(ms) / max(1, len(ms))}
                    print(f"{cle:44s} passages {total['passages']:3d}  annoncés {total['annonces_justes']:3d} ({100 * total['annonces_justes'] / n:4.0f} %)  confondus {total['confondus']:2d}  "
                          f"manqués {total['manques']:3d}  autres annonces {total['autres_annonces']:3d}  avance {total['avance_images'] / max(1, total['annonces_justes']):.1f} image(s)  "
                          f"dont {total['annonces_au_loin']:2d} par la vue au loin  {sum(ms) / max(1, len(ms)):.0f} ms", flush=True)
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
    ap.add_argument("--gpu", action="store_true", help="détecteur sur la carte graphique WebGPU logicielle de Chromium, au lieu du processeur")
    asyncio.run(mesurer(ap.parse_args()))
