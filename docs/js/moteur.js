// Moteur de détection dans le navigateur (ONNX Runtime Web : WebGPU si possible, sinon WebAssembly).
// 1. YOLOv5n : marquages au sol classe par classe, et panneaux en une seule classe « panneau ». Le classifieur (second
//    étage) dit ensuite de quel panneau il s'agit, ou le rejette (même logique que route_fr/detector.py). Il regarde un
//    carré autour du panneau prolongé vers le bas, pour lire aussi le panonceau placé dessous.
// 2. YOLOv5n COCO d'origine (une image sur deux) : piétons, cyclistes, deux-roues et feux tricolores (couleur lue
//    sur l'image).
// 3. « Mes panneaux » : empreinte de chaque panneau détecté comparée à celles des panneaux appris.
// 4. Suivi dans le temps (comme route_fr/tracker.py) : un élément n'est confirmé qu'après 2 détections, sa classe
//    est votée sur plusieurs images ; mémoire de la vitesse maximale.
/* global ort */
import { APP } from "./contenu.js";
import { D } from "./donnees.js";

const CONF = 0.35, CONF_SIGNS = 0.15, SIGN_FACTOR = 1.3, IOU = 0.45, MIN_HITS = 2, MAX_MISSES = 6;
// lignes au sol : leur type se lit mal sur une seule image (une ligne discontinue vue de près ressemble à une continue)
export const LIGNES = /^M_ligne_(continue|discontinue|mixte|dissuasion|rive)$/;
const EMB = 64, MEAN = [0.485, 0.456, 0.406], STD = [0.229, 0.224, 0.225];  // EMB : côté des vignettes d'empreinte
const SIGN = -2;
const COCO = { personne: 0, velo: 1, moto: 2, feu: 3 };  // ordre des classes gardées dans usagers.onnx
const HAUTEUR = { U_pieton: 1.7, U_cycliste: 1.75, U_deux_roues: 1.45 };  // m, pour estimer la distance
export const TAILLES = { rapide: 416, equilibree: 512, fine: 640 };
// panneaux qui effacent la vitesse maximale gardée en mémoire sans en donner une nouvelle (la fin d'autoroute efface le 130)
export const FINS_VITESSE = ["B33", "B31", "C208"];

export function iou(a, b) {
  const x1 = Math.max(a[0], b[0]), y1 = Math.max(a[1], b[1]), x2 = Math.min(a[2], b[2]), y2 = Math.min(a[3], b[3]);
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9);
}
function nms(dets, seuil = IOU, parClasse = true) {
  dets.sort((a, b) => b.conf - a.conf);
  const garde = [];
  for (const d of dets) if (!garde.some(k => (!parClasse || k.cls === d.cls) && iou(k.box, d.box) > seuil)) garde.push(d);
  return garde;
}

export class Moteur {
  constructor() {
    this.pret = false; this.session = null; this.cls = null; this.usagers = null; this.emp = null;
    this.clsMap = []; this.detMap = []; this.fournisseurs = []; this.wCls = 64; this.hCls = 96;
    this.cote = 640; this.avecUsagers = true; this.actifs = null; this.appris = []; this.seuilAppris = 0.5;
    this.loin = 0; this.pleines = 0; this.horizon = null;  // vue au loin : une analyse sur « loin » (0 : jamais)
    this.proche = true; this.reports = 0;  // vue au loin reportée tant qu'un panneau tout proche attend d'être confirmé
    this.apercus = 0;  // panneaux aperçus depuis le chargement (pistes créées) : sert au diagnostic d'un trajet
    this.work = document.createElement("canvas"); this.wctx = this.work.getContext("2d", { willReadFrequently: true });
    this.crop = document.createElement("canvas"); this.cctx = this.crop.getContext("2d", { willReadFrequently: true });
    this.cfeu = document.createElement("canvas"); this.fctx = this.cfeu.getContext("2d", { willReadFrequently: true });
    this.reinitialiser();
    this.ms = 0; this.image = 0;
  }

  async charger({ backend = null, progression = () => {} } = {}) {
    // carte graphique seulement si le navigateur en fournit vraiment une (sinon ONNX Runtime se replierait sans le dire
    // sur le processeur, et l'appli choisirait une qualité d'analyse trop lourde pour lui)
    let gpu = false;
    if (!backend && "gpu" in navigator) {
      try { gpu = !!(await Promise.race([navigator.gpu.requestAdapter(), new Promise(r => setTimeout(() => r(null), 4000))])); } catch { gpu = false; }
    }
    // (carte graphique déjà trouvée fausse sur ce téléphone, voir verifierGpu : on ne la prépare même pas)
    if (gpu && this.noteGpu()?.ok === false) { gpu = false; this.gpuEcarte = true; }
    this.fournisseurs = backend ? [backend] : gpu ? ["webgpu", "wasm"] : ["wasm"];
    // plusieurs fils de calcul seulement si la page est isolée (voir sw.js) ; sinon ONNX Runtime n'en utilise qu'un
    let monofil = false;
    try { monofil = localStorage.getItem("repere.monofil") === "1"; } catch { /* stockage indisponible */ }
    this.fils = self.crossOriginIsolated && !monofil ? Math.max(1, Math.min(4, Math.ceil((navigator.hardwareConcurrency || 2) / 2))) : 1;
    ort.env.wasm.numThreads = this.fils;
    const opts = { executionProviders: this.fournisseurs, graphOptimizationLevel: "all" };
    progression("Détecteur…");
    try {
      try { this.session = await ort.InferenceSession.create("detecteur.onnx", opts); }
      catch (e) {  // WebGPU indisponible ou défaillant : repli sur le processeur
        if (this.fournisseurs[0] === "wasm") throw e;
        this.fournisseurs = ["wasm"];
        this.session = await ort.InferenceSession.create("detecteur.onnx", { ...opts, executionProviders: ["wasm"] });
      }
    } catch (e) {
      // le calcul sur plusieurs fils ne démarre pas sur ce navigateur : on le note et on recharge l'appli avec un seul fil
      if (this.fils > 1) { try { localStorage.setItem("repere.monofil", "1"); location.reload(); await new Promise(() => {}); } catch { /* on laisse l'erreur remonter */ } }
      throw e;
    }
    this.opts = { ...opts, executionProviders: this.fournisseurs };
    // classe du détecteur -> élément du catalogue (marquages), SIGN pour « panneau », -1 pour les classes techniques
    this.detMap = D.detecteur.map(n => n === "panneau" ? SIGN : D.parCode[n] ? D.parCode[n].index : -1);
    progression("Classifieur…");
    try {
      const conf = await (await fetch("panneaux.json")).json();
      [this.wCls, this.hCls] = conf.taille;
      this.cls = await ort.InferenceSession.create("panneaux.onnx", this.opts);
      this.clsMap = conf.classes.map(n => D.parCode[n] && D.parCode[n].index < D.nbModele ? D.parCode[n].index : -1);  // -1 : autre panneau ou fond
    } catch (e) { console.warn("Classifieur indisponible : les panneaux ne seront pas identifiés", e); this.cls = null; }
    if (this.fournisseurs[0] === "webgpu") await this.verifierGpu(opts, progression);
    this.pret = true;
  }

  // Sur certains téléphones, le calcul sur carte graphique rend des résultats faux sans prévenir (pilote graphique) : le
  // détecteur ne trouve alors presque rien, ou n'importe quoi. Une fois par version de l'appli et du navigateur, la même
  // image d'essai est donc calculée par la carte graphique et par le processeur. Si les résultats diffèrent, la carte
  // graphique est écartée et tout se fait sur le processeur (plus lent, mais juste). Ce premier calcul sert aussi
  // d'échauffement : la toute première image de la route n'attend plus la préparation de la carte graphique.
  // note gardée sur le téléphone : { s: version de l'appli et du navigateur, ok }, ou null si elle date d'une autre version
  noteGpu() {
    try { const n = JSON.parse(localStorage.getItem("repere.gpu")); return n?.s === `1|${APP.version}|${navigator.userAgent}` ? n : null; } catch { return null; }
  }
  async verifierGpu(opts, progression) {
    const cle = "repere.gpu", signature = `1|${APP.version}|${navigator.userAgent}`;
    const note = this.noteGpu();
    const ecarter = async (det, cls) => {
      this.fournisseurs = ["wasm"]; this.gpuEcarte = true;
      this.opts = { ...opts, executionProviders: ["wasm"] };
      this.session = det || await ort.InferenceSession.create("detecteur.onnx", this.opts);
      if (this.cls) this.cls = cls || await ort.InferenceSession.create("panneaux.onnx", this.opts);
    };
    try {
      if (note) { if (!note.ok) await ecarter(); return; }
      progression("Vérification de la carte graphique…");
      const wasm = { ...opts, executionProviders: ["wasm"] };
      // image d'essai : une route grise avec quelques formes de panneaux (toujours la même)
      const essai = document.createElement("canvas"); essai.width = 1280; essai.height = 720;
      const g = essai.getContext("2d");
      const fond = g.createLinearGradient(0, 0, 0, 720); fond.addColorStop(0, "#9db4c8"); fond.addColorStop(0.5, "#b9b4a6"); fond.addColorStop(1, "#5c5c60");
      g.fillStyle = fond; g.fillRect(0, 0, 1280, 720);
      const formes = [[980, 250, 46, "#d2161e", "#fff"], [300, 300, 30, "#1c56b5", "#1c56b5"], [1120, 330, 70, "#d2161e", "#fff"], [640, 280, 22, "#f2c200", "#fff"]];
      for (const [x, y, r, bord, dedans] of formes) { g.fillStyle = bord; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); g.fillStyle = dedans; g.beginPath(); g.arc(x, y, r * 0.72, 0, 7); g.fill(); g.fillStyle = "#111"; g.fillRect(x - r * 0.3, y - r * 0.12, r * 0.6, r * 0.24); }
      g.fillStyle = "#f4f4f4"; for (let i = 0; i < 6; i++) g.fillRect(560 + i * 30, 470 + i * 40, 26 + i * 8, 14 + i * 4);
      const ecart = (a, b, pas = 1) => { let m = 0; for (let i = 0; i < a.length; i += pas) { const d = Math.abs(a[i] - b[i]); if (!(d <= m)) m = Number.isFinite(d) ? d : Infinity; } return m; };
      // détecteur : mêmes cadres (à 4 points près) et mêmes scores (à 0,1 près) sur toute la grille
      const prep = this.tenseur(essai, 1280, 720, this.cote);
      const detW = await ort.InferenceSession.create("detecteur.onnx", wasm);
      const nom = this.session.inputNames[0], sortie = this.session.outputNames[0];
      const a = (await this.session.run({ [nom]: prep.t }))[sortie], b = (await detW.run({ [nom]: prep.t }))[sortie];
      const larg = a.dims[2];
      let juste = a.data.length === b.data.length;
      if (juste) for (let i = 0; i < a.data.length && juste; i += larg) {
        for (let k = 0; k < 4; k++) if (!(Math.abs(a.data[i + k] - b.data[i + k]) <= 4)) juste = false;
        if (!(Math.abs(a.data[i + 4] - b.data[i + 4]) <= 0.1)) juste = false;
      }
      // classifieur : mêmes notes (à 0,5 près) sur deux vignettes
      let clsW = null;
      if (juste && this.cls) {
        const x = this.vignettes(essai, [[934, 204, 1026, 296], [270, 270, 330, 330]], this.wCls, this.hCls);
        clsW = await ort.InferenceSession.create("panneaux.onnx", wasm);
        const e = this.cls.inputNames[0], o = this.cls.outputNames[0];
        const c = (await this.cls.run({ [e]: x }))[o].data, d = (await clsW.run({ [e]: x }))[o].data;
        juste = c.length === d.length && ecart(c, d) <= 0.5;
      }
      try { localStorage.setItem(cle, JSON.stringify({ s: signature, ok: juste })); } catch { /* stockage indisponible */ }
      if (juste) { detW.release?.().catch(() => {}); clsW?.release?.().catch(() => {}); return; }
      console.warn("Carte graphique écartée : ses résultats diffèrent de ceux du processeur");
      await ecarter(detW, clsW);
    } catch (e) { console.warn("Vérification de la carte graphique impossible", e); }  // dans le doute, on la garde
  }
  async chargerUsagers() {
    if (this.usagers || this.chargeUsagers) return this.chargeUsagers;
    this.chargeUsagers = ort.InferenceSession.create("usagers.onnx", this.opts).then(s => (this.usagers = s)).catch(e => { console.warn("Usagers indisponibles", e); this.chargeUsagers = null; });
    return this.chargeUsagers;
  }
  async chargerEmpreinte() {
    if (this.emp) return this.emp;
    try {
      const conf = await (await fetch("empreinte.json")).json();
      this.seuilAppris = conf.seuil;
      this.emp = await ort.InferenceSession.create("empreinte.onnx", this.opts);
    } catch (e) { console.warn("Empreintes indisponibles", e); }
    return this.emp;
  }

  // cote : taille d'analyse ; actifs : Set des indices d'éléments affichés (null = tous) ; appris : [{index, emb, correction}]
  configurer({ cote, avecUsagers, actifs, appris, loin, proche } = {}) {
    if (cote) this.cote = cote;
    if (loin !== undefined) this.loin = +loin || 0;
    if (proche !== undefined) this.proche = !!+proche;
    if (avecUsagers !== undefined) this.avecUsagers = avecUsagers;
    if (actifs !== undefined) this.actifs = actifs;
    if (appris !== undefined) { this.appris = appris; if (appris.length) this.chargerEmpreinte(); }
    if (this.avecUsagers && this.pret) this.chargerUsagers();
  }
  // « generation » change à chaque remise à zéro : une analyse lancée avant (le calcul sur carte graphique rend la main à la page
  // pendant qu'il tourne) reconnaît ainsi que ses détections sont celles d'une image dépassée, et ne repeuple pas le suivi.
  reinitialiser() { this.pistes = []; this.prochainId = 1; this.vitesse = { valeur: null, code: null, quand: 0 }; this.image = 0; this.lignes = { g: {}, d: {} }; this.generation = (this.generation || 0) + 1; }

  // ---------- pré-traitement : image -> tenseur letterbox (multiple de 32) ----------
  // region [x, y, largeur, hauteur] : seule cette partie de l'image est analysée (vue au loin), à l'échelle cote / grand côté
  tenseur(src, w, h, cote, region = null) {
    const [rx, ry, rw, rh] = region || [0, 0, w, h];
    const r = cote / Math.max(rw, rh);
    const nw = Math.round(rw * r), nh = Math.round(rh * r);
    const W = Math.ceil(nw / 32) * 32, H = Math.ceil(nh / 32) * 32, px = (W - nw) / 2, py = (H - nh) / 2;
    this.work.width = W; this.work.height = H;
    this.wctx.fillStyle = "rgb(114,114,114)"; this.wctx.fillRect(0, 0, W, H);
    this.wctx.drawImage(src, rx, ry, rw, rh, px, py, nw, nh);
    const data = this.wctx.getImageData(0, 0, W, H).data, n = W * H, f = new Float32Array(3 * n);
    for (let i = 0; i < n; i++) { f[i] = data[4 * i] / 255; f[n + i] = data[4 * i + 1] / 255; f[2 * n + i] = data[4 * i + 2] / 255; }
    return { t: new ort.Tensor("float32", f, [1, 3, H, W]), r, px, py, ox: rx, oy: ry };
  }

  // Vue au loin : le milieu de l'image, autour de l'horizon, là où les panneaux apparaissent quand ils sont encore loin.
  // L'image entière est réduite de moitié environ avant l'analyse : un panneau n'y devient lisible qu'à une vingtaine de
  // mètres, et en roulant il ne reste qu'une seconde avant qu'il sorte du champ. Cette région, analysée à pleine
  // définition une image sur deux, le montre presque deux fois plus gros : il est reconnu vers 35 mètres.
  // 36° de large et 19° de haut (de 14° au-dessus de l'horizon à 5° en dessous), pour un objectif qui voit 68° dans sa
  // grande dimension ; l'horizon est pris au milieu de l'image tant que les lignes de la route n'ont pas dit mieux.
  regionLoin(w, h) {
    const ppd = Math.max(w, h) / 68;
    const rw = Math.min(w, Math.round(36 * ppd)), rh = Math.min(h, Math.round(19 * ppd));
    const yh = this.horizon?.w === w && this.horizon.h === h ? this.horizon.y : h / 2;
    return [Math.round((w - rw) / 2), Math.round(Math.min(Math.max(0, yh - 14 * ppd), h - rh)), rw, rh];
  }

  // ---------- panneaux et marquages ----------
  postRoute(out, { r, px, py, ox = 0, oy = 0 }, seuilPanneaux = CONF_SIGNS) {
    const [, n, d] = out.dims, v = out.data, nc = d - 5, dets = [];
    if (nc !== this.detMap.length && !this.averti) {  // détecteur et catalogue d'âges différents : les classes en trop sont ignorées
      this.averti = true;
      console.warn(`detecteur.onnx a ${nc} classes, catalogue.json en décrit ${this.detMap.length} : refaire le catalogue avec tools/export_web.py`);
    }
    const bas = Math.min(CONF, seuilPanneaux);
    for (let i = 0; i < n; i++) {
      const o = i * d, obj = v[o + 4];
      if (obj < bas) continue;
      let best = 0, c = 0;
      for (let k = 0; k < nc; k++) if (v[o + 5 + k] > best) { best = v[o + 5 + k]; c = k; }
      const cls = this.detMap[c], conf = obj * best;
      if (cls === -1 || cls === undefined || conf < (cls === SIGN ? seuilPanneaux : CONF)) continue;
      if (cls === SIGN && !this.cls) continue;  // sans classifieur, impossible de dire de quel panneau il s'agit
      const cx = v[o], cy = v[o + 1], w = v[o + 2], h = v[o + 3];
      dets.push({ box: [(cx - w / 2 - px) / r + ox, (cy - h / 2 - py) / r + oy, (cx + w / 2 - px) / r + ox, (cy + h / 2 - py) / r + oy], conf, cls });
    }
    return nms(dets).slice(0, 100);
  }

  // Vignettes W x H des boîtes, normalisées : un carré centré sur la boîte (grand côté x marge), prolongé vers le bas
  // quand H > W (64 x 96 pour le classifieur, qui lit aussi le panonceau sous le panneau ; 64 x 64 pour les empreintes).
  vignettes(src, boxes, W, H, marge = 1.15) {
    const plan = W * H, f = new Float32Array(boxes.length * 3 * plan);
    this.crop.width = W; this.crop.height = H;
    boxes.forEach((b, i) => {
      const [x1, y1, x2, y2] = b, s = Math.max(x2 - x1, y2 - y1) * marge, cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
      this.cctx.fillStyle = "rgb(114,114,114)"; this.cctx.fillRect(0, 0, W, H);
      this.cctx.drawImage(src, cx - s / 2, cy - s / 2, s, s * H / W, 0, 0, W, H);
      const px = this.cctx.getImageData(0, 0, W, H).data, o = i * 3 * plan;
      for (let k = 0; k < plan; k++) for (let c = 0; c < 3; c++) f[o + c * plan + k] = (px[4 * k + c] / 255 - MEAN[c]) / STD[c];
    });
    return new ort.Tensor("float32", f, [boxes.length, 3, H, W]);
  }

  async classer(src, signes) {
    const x = this.vignettes(src, signes.map(d => d.box), this.wCls, this.hCls);
    const out = await this.cls.run({ [this.cls.inputNames[0]]: x });
    const logits = out[this.cls.outputNames[0]].data, nc = logits.length / signes.length;
    return signes.map((d, i) => {
      let m = -Infinity, k = 0, sum = 0;
      for (let j = 0; j < nc; j++) if (logits[i * nc + j] > m) { m = logits[i * nc + j]; k = j; }
      for (let j = 0; j < nc; j++) sum += Math.exp(logits[i * nc + j] - m);
      return { g: this.clsMap[k], p: 1 / sum };
    });
  }

  async empreintes(x) {
    const out = await this.emp.run({ [this.emp.inputNames[0]]: x });
    const e = out[this.emp.outputNames[0]].data, dim = e.length / x.dims[0];
    return Array.from({ length: x.dims[0] }, (_, i) => e.subarray(i * dim, (i + 1) * dim));
  }

  // second étage : classe exacte de chaque panneau, rejet des leurres, puis panneaux appris
  async affiner(src, dets) {
    const signes = dets.filter(d => d.cls === SIGN).slice(0, 16), autres = dets.filter(d => d.cls !== SIGN);  // triés par confiance
    if (!this.cls || !signes.length) return autres;
    const res = await this.classer(src, signes);
    let emb = null;
    if (this.appris.length && this.emp) emb = await this.empreintes(this.vignettes(src, signes.map(d => d.box), EMB, EMB));
    const gardes = [];
    signes.forEach((d, i) => {
      let { g, p } = res[i];
      if (emb && Math.max(d.box[2] - d.box[0], d.box[3] - d.box[1]) >= 20) {
        let best = -1, qui = null;
        for (const a of this.appris) { let s = 0; for (let k = 0; k < a.emb.length; k++) s += a.emb[k] * emb[i][k]; if (s > best) { best = s; qui = a; } }
        // un panneau appris ne remplace une classe sûre du classifieur que s'il s'agit d'une correction, et avec plus de marge
        const sur = g >= 0 && p >= 0.8;
        if (qui && best >= this.seuilAppris + (sur ? (qui.correction ? 0.1 : 9) : 0)) { g = qui.index; p = Math.max(p, best); }
      }
      if (g < 0) return;
      d.cls = g; d.conf = Math.sqrt(d.conf * p);
      // seuil propre à certains panneaux souvent annoncés à tort sur les vraies photos (balises...) : voir route_fr/classes.py
      if (d.conf >= (D.items[g].seuil ?? SIGN_FACTOR * CONF)) gardes.push(d);
    });
    return autres.concat(nms(gardes, 0.5, false));
  }

  // ---------- usagers et feux ----------
  postUsagers(out, { r, px, py }, w, h) {
    const [, n, d] = out.dims, v = out.data, brut = [];
    for (let i = 0; i < n; i++) {
      const o = i * d, obj = v[o + 4];
      if (obj < 0.3) continue;
      let best = 0, c = 0;
      for (let k = 0; k < 4; k++) if (v[o + 5 + k] > best) { best = v[o + 5 + k]; c = k; }
      const conf = obj * best;
      if (conf < (c === COCO.feu ? 0.3 : 0.4)) continue;
      const cx = v[o], cy = v[o + 1], bw = v[o + 2], bh = v[o + 3];
      brut.push({ box: [(cx - bw / 2 - px) / r, (cy - bh / 2 - py) / r, (cx + bw / 2 - px) / r, (cy + bh / 2 - py) / r], conf, cls: c });
    }
    const dets = nms(brut);
    const pers = dets.filter(x => x.cls === COCO.personne), sorties = [], prises = new Set();
    const echelle = 640 / Math.max(w, h);
    for (const [coco, code] of [[COCO.velo, "U_cycliste"], [COCO.moto, "U_deux_roues"]]) {
      for (const v2 of dets.filter(x => x.cls === coco)) {
        // un vélo ou une moto n'est un usager que s'il porte quelqu'un (les vélos garés sont ignorés)
        const p = pers.find(q => !prises.has(q) && iou(q.box, v2.box) > 0.1 && (q.box[0] + q.box[2]) / 2 > v2.box[0] && (q.box[0] + q.box[2]) / 2 < v2.box[2]);
        if (!p) continue;
        prises.add(p);
        const box = [Math.min(p.box[0], v2.box[0]), Math.min(p.box[1], v2.box[1]), Math.max(p.box[2], v2.box[2]), Math.max(p.box[3], v2.box[3])];
        sorties.push({ box, conf: Math.max(p.conf, v2.conf), cls: D.parCode[code].index });
      }
    }
    for (const p of pers) if (!prises.has(p) && (p.box[3] - p.box[1]) * echelle >= 16) sorties.push({ ...p, cls: D.parCode.U_pieton.index });
    return { usagers: sorties, feux: dets.filter(x => x.cls === COCO.feu && (x.box[3] - x.box[1]) * echelle >= 10) };
  }

  couleurFeu(src, box) {
    const [x1, y1, x2, y2] = box, bw = x2 - x1, bh = y2 - y1;
    if (bw < 2 || bh < 2) return null;
    const W = 16, H = Math.max(12, Math.min(48, Math.round(16 * bh / bw)));
    this.cfeu.width = W; this.cfeu.height = H;
    this.fctx.drawImage(src, x1, y1, bw, bh, 0, 0, W, H);
    const d = this.fctx.getImageData(0, 0, W, H).data;
    const n = { F_rouge: 0, F_orange: 0, F_vert: 0 }, ys = { F_rouge: 0, F_orange: 0, F_vert: 0 };
    for (let i = 0; i < W * H; i++) {
      const R = d[4 * i], G = d[4 * i + 1], B = d[4 * i + 2], mx = Math.max(R, G, B), mn = Math.min(R, G, B);
      if (mx < 140 || (mx - mn) / mx < 0.35) continue;
      let hue = mx === mn ? 0 : mx === R ? 60 * (G - B) / (mx - mn) : mx === G ? 120 + 60 * (B - R) / (mx - mn) : 240 + 60 * (R - G) / (mx - mn);
      if (hue < 0) hue += 360;
      const c = hue < 18 || hue > 330 ? "F_rouge" : hue < 55 ? "F_orange" : hue >= 85 && hue <= 200 ? "F_vert" : null;
      if (c) { n[c]++; ys[c] += Math.floor(i / W) / H; }
    }
    const best = Object.keys(n).reduce((a, b) => n[a] >= n[b] ? a : b);
    if (n[best] < Math.max(3, 0.025 * W * H)) return null;
    // feu vertical : la lampe allumée doit être à la bonne hauteur (rouge en haut, vert en bas)
    if (bh > 1.6 * bw) {
      const y = ys[best] / n[best];
      if ((best === "F_rouge" && y > 0.55) || (best === "F_vert" && y < 0.45)) return null;
    }
    return best;
  }

  // ---------- suivi ----------
  // champ : région analysée par cette passe (vue au loin), ou null pour l'image entière
  suivre(dets, groupes, w, h, champ = null) {
    // taille d'un objet telle que l'a vue la passe qui l'a trouvé, ramenée à une analyse de 640 points : c'est elle qui dit
    // s'il était assez gros pour être lu (un panneau lointain est petit dans l'image, mais gros dans la vue au loin)
    const pleine = 640 / Math.max(w, h), ech = champ ? 640 / Math.max(champ[2], champ[3]) : pleine;
    const groupeDe = c => D.items[c].groupe, taille = b => Math.max(b[2] - b[0], b[3] - b[1]) * ech;
    const nouveaux = [], changes = [], pairs = [], tUsed = new Set(), dUsed = new Set();
    this.pistes.forEach((t, i) => { if (!groupes.has(t.groupe)) return; dets.forEach((d, j) => { if (groupeDe(d.cls) === t.groupe) { const v = iou(t.box, d.box); if (v >= 0.25) pairs.push([v, i, j]); } }); });
    pairs.sort((a, b) => b[0] - a[0]);
    // v : recouvrement entre le cadre suivi et le nouveau. Faible (l'objet a beaucoup bougé) : on prend presque tout le nouveau
    // cadre, sinon le cadre affiché traîne derrière l'objet.
    const toucher = (t, d, v = 1) => {
      const a = !t.hits || this.net ? 1 : v >= 0.5 ? 0.55 : 0.9;
      t.box = t.box.map((v, k) => a * d.box[k] + (1 - a) * v);
      t.conf = a * d.conf + (1 - a) * t.conf;
      if (t.groupe === "f") {  // un feu change de couleur : on suit la dernière couleur vue deux fois de suite
        if (d.cls === t.candidat) t.vus = (t.vus || 0) + 1; else { t.candidat = d.cls; t.vus = 1; }
        if (t.vus >= 2 && t.feu !== d.cls) { const avant = t.feu; t.feu = d.cls; if (avant != null && t.ok) changes.push({ t, avant }); }
        t.feu ??= d.cls;
      } else t.scores[d.cls] = (t.scores[d.cls] || 0) + d.conf * Math.min(1, taille(t.box) / 32);
      if (d.dist) t.dist = t.dist ? 0.7 * t.dist + 0.3 * d.dist : d.dist;
      t.hits++; t.misses = 0; t.vu = performance.now();
    };
    for (const [v, i, j] of pairs) { if (tUsed.has(i) || dUsed.has(j)) continue; tUsed.add(i); dUsed.add(j); toucher(this.pistes[i], dets[j], v); }
    // Seconde passe, panneaux, feux et marquages hors lignes : avec peu d'images par seconde (ou un objet tout proche), l'objet
    // ne recouvre plus son cadre précédent. On le rattache à la piste la plus proche qui porte le même nom (pour un feu : la
    // même couleur), vue il y a deux images au plus (à moins de 2,5 fois sa taille, 1,5 pour un feu, tailles comparables) :
    // la piste garde ses voix, au lieu d'une nouvelle piste jugée sur une seule image. Un objet d'un autre nom n'est jamais
    // rattaché ainsi : ce serait un autre objet, qui doit avoir sa propre piste. Les lignes, très étendues, et les usagers
    // ne se rattachent que par recouvrement.
    const centre = b => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2], cote = b => Math.max(b[2] - b[0], b[3] - b[1]), loin = [];
    this.pistes.forEach((t, i) => {
      if (tUsed.has(i) || !groupes.has(t.groupe) || t.groupe === "u" || t.misses > 2) return;
      const [tx, ty] = centre(t.box), ct = cote(t.box), nom = this.classe(t);
      if (t.groupe === "m" && LIGNES.test(D.items[nom]?.code || "")) return;
      dets.forEach((d, j) => {
        if (dUsed.has(j) || groupeDe(d.cls) !== t.groupe) return;
        const [dx, dy] = centre(d.box), cd = cote(d.box), ecart = Math.hypot(dx - tx, dy - ty) / Math.max(ct, cd);
        if ((t.groupe === "f" ? d.cls === t.feu && ecart <= 1.5 : d.cls === nom && ecart <= 2.5) && cd < 2.2 * ct && ct < 2.2 * cd) loin.push([ecart, i, j]);
      });
    });
    loin.sort((a, b) => a[0] - b[0]);
    for (const [, i, j] of loin) { if (tUsed.has(i) || dUsed.has(j)) continue; tUsed.add(i); dUsed.add(j); toucher(this.pistes[i], dets[j], 0); }
    dets.forEach((d, j) => {
      if (dUsed.has(j)) return;
      const t = { id: this.prochainId++, box: d.box.slice(), groupe: groupeDe(d.cls), scores: {}, conf: 0, hits: 0, misses: 0, ok: false, debut: performance.now() };
      if (t.groupe === "s") this.apercus++;
      toucher(t, d);
      this.pistes.push(t); tUsed.add(this.pistes.length - 1);
    });
    // Un objet non retrouvé ne compte comme manqué que si cette passe pouvait le voir : la vue au loin ne voit que sa
    // région, et l'image entière ne voit pas un panneau encore trop petit pour elle (trouvé jusqu'ici par la vue au loin).
    const visible = t => {
      const cx = (t.box[0] + t.box[2]) / 2, cy = (t.box[1] + t.box[3]) / 2, c = Math.max(t.box[2] - t.box[0], t.box[3] - t.box[1]);
      if (champ) return cx > champ[0] && cx < champ[0] + champ[2] && cy > champ[1] && cy < champ[1] + champ[3];
      return !(t.groupe === "s" && t.auLoin && c * pleine < 14);
    };
    this.pistes.forEach((t, i) => {
      if (!groupes.has(t.groupe)) return;
      if (tUsed.has(i)) t.auLoin = !!champ;
      if (!tUsed.has(i)) { if (visible(t)) { t.misses++; for (const k in t.scores) t.scores[k] *= 0.9; } }
      else if (!t.ok && this.confirme(t, taille(t.box))) { t.ok = true; t.annonce = this.classe(t); t.vuesAnnonce = t.hits; nouveaux.push(t); }
      else if (t.ok && t.groupe === "s" && this.classe(t) !== t.annonce && t.hits - t.vuesAnnonce >= 3 && t.conf >= 0.65) {
        // Le nom a changé depuis l'annonce : de près, le panneau se lit mieux (un 110 devient un 130). Quand le nouveau nom
        // réunit 60 % des voix, l'annonce est refaite avec le bon nom.
        const c = this.classe(t);
        let total = 0;
        for (const k in t.scores) total += t.scores[k];
        if (t.scores[c] >= 0.6 * total) { t.annonce = c; t.vuesAnnonce = t.hits; t.corrige = true; nouveaux.push(t); }
      }
    });
    this.pistes = this.pistes.filter(t => t.misses <= MAX_MISSES);
    return { nouveaux, changes };
  }

  // Un élément est annoncé quand il a été vu assez de fois.
  // Panneaux : plus le score est bas, plus on attend. Sur les photos de contrôle, une annonce au score de 0,46 à 0,65 n'est
  // juste qu'une fois sur deux (45 %), contre 77 % de 0,75 à 0,85 et 91 % au-dessus. Un vrai panneau grossit en approchant
  // et son score monte : attendre coûte une fraction de seconde, et les détections hésitantes qui clignotent ne passent plus.
  // (Essayé puis écarté : exiger en plus une durée de suivi, 0,2 s ou 0,5 s, pour qu'un téléphone rapide n'annonce pas sur
  // deux images presque identiques. Sur les trajets de contrôle, cela faisait perdre deux à quatre vrais panneaux sur
  // cent sans rien retirer de faux : les annonces en plus d'un téléphone rapide sont presque toutes de vrais panneaux.)
  // Marquages au sol : un type qui domine nettement, et plus d'images. Une ligne : 5 images et 65 % des voix. Les autres
  // marquages : 3 images et 55 % des voix, ou 2 images quand le score atteint 0,85 (un passage piétons net file vite sous
  // la voiture : à quelques images par seconde, il n'en laisse pas trois).
  confirme(t, cote) {
    if (t.groupe !== "m" && t.groupe !== "s") return (t.hits >= MIN_HITS || t.conf > 0.85) && cote >= 18;
    const c = this.classe(t);
    let total = 0;
    for (const k in t.scores) total += t.scores[k];
    const part = total ? t.scores[c] / total : 0;
    if (t.groupe === "s") {
      if (cote < 18) return false;
      if (t.conf >= 0.85) return true;             // évident : tout de suite
      if (t.conf >= 0.65) return t.hits >= 2;      // net : deux images
      return t.hits >= 4 && part >= 0.6;           // hésitant : quatre images, et un nom qui domine
    }
    if (LIGNES.test(D.items[c]?.code || "")) return t.hits >= 5 && part >= 0.65;
    return (t.hits >= 3 || (t.hits >= 2 && t.conf >= 0.85)) && part >= 0.55;
  }

  // ligne qui borde la voie, de chaque côté : vote sur les dernières images (la plus proche du milieu de l'image compte)
  majLignes(dets, w) {
    for (const cote of ["g", "d"]) {
      const v = this.lignes[cote];
      for (const k in v) { v[k] *= 0.82; if (v[k] < 0.05) delete v[k]; }
      let proche = null;
      for (const d of dets) {
        const code = D.items[d.cls]?.code, x = (d.box[0] + d.box[2]) / 2;
        if (!code || !LIGNES.test(code) || (x < w / 2 ? "g" : "d") !== cote) continue;
        if (!proche || Math.abs(x - w / 2) < Math.abs((proche.box[0] + proche.box[2]) / 2 - w / 2)) proche = d;
      }
      if (proche) { const code = D.items[proche.cls].code; v[code] = (v[code] || 0) + proche.conf; }
    }
  }
  ligne(cote) {
    const v = this.lignes[cote];
    let best = null, total = 0;
    for (const k in v) { total += v[k]; if (best === null || v[k] > v[best]) best = k; }
    return best && v[best] >= 1.3 && v[best] >= 0.62 * total ? best : null;
  }

  classe(t) {
    if (t.groupe === "f") return t.feu;
    let best = null;
    for (const k in t.scores) if (best === null || t.scores[k] > t.scores[best]) best = k;
    return +best;
  }

  majVitesse(w, h) {
    let best = null;
    const taille = b => Math.max(b[2] - b[0], b[3] - b[1]) * 640 / Math.max(w, h);
    for (const t of this.pistes) {
      if (!t.ok || t.groupe !== "s") continue;
      const it = D.items[this.classe(t)];
      if ((it.vitesse != null || FINS_VITESSE.includes(it.code)) && t.conf >= 0.4 && taille(t.box) >= 20 && (!best || taille(t.box) > taille(best.box))) best = t;
    }
    if (best) {
      const it = D.items[this.classe(best)];
      if (it.code !== this.vitesse.code) this.vitesse = { valeur: it.vitesse, code: it.code, quand: Date.now() };
    }
  }

  // ---------- analyse d'une image de la vidéo ----------
  // net : l'image est arrêtée (pause) ; les cadres suivis prennent exactement la place trouvée, sans lissage
  async analyser(src, w, h, { debug = false, net = false } = {}) {
    const t0 = performance.now(), generation = this.generation;
    this.net = net;
    this.image++;
    // vue au loin : une analyse sur « loin », jamais sur une image arrêtée (là, on veut tout ce que montre l'image)
    let champ = this.loin > 1 && !net && this.image % this.loin === 0 ? this.regionLoin(w, h) : null;
    // Sauf si un panneau proche, vu sur le côté par la dernière image entière, attend encore d'être confirmé : il aura quitté
    // l'image avant la prochaine image entière. On regarde alors de nouveau l'image entière (trois fois de suite au plus,
    // pour qu'un objet douteux sur le côté ne prive pas longtemps de la vue au loin).
    if (champ && this.proche) {
      const pleine = 640 / Math.max(w, h), dedans = b => b[0] > champ[0] + 2 && b[1] > champ[1] + 2 && b[2] < champ[0] + champ[2] - 2 && b[3] < champ[1] + champ[3] - 2;
      const attend = this.reports < 3 && this.pistes.some(t => t.groupe === "s" && !t.ok && !t.misses && t.hits < 4 && Math.max(t.box[2] - t.box[0], t.box[3] - t.box[1]) * pleine >= 18 && !dedans(t.box));
      if (attend) { champ = null; this.reports++; } else this.reports = 0;
    }
    if (champ) return this.analyserLoin(src, w, h, champ, t0, generation, debug);
    this.pleines++;
    const prep = this.tenseur(src, w, h, this.cote);
    const out = await this.session.run({ [this.session.inputNames[0]]: prep.t });
    let dets = await this.affiner(src, this.postRoute(out[this.session.outputNames[0]], prep));
    const ech = 640 / Math.max(w, h);
    for (const d of dets) d.ech = ech;
    this.majHorizon(dets, w, h);
    const groupes = new Set(["s", "m"]);
    // usagers : une analyse sur deux en tout (chaque image entière quand elle alterne avec la vue au loin)
    if (this.avecUsagers && this.usagers && (this.loin === 2 && !net ? true : this.loin > 2 && !net ? this.pleines % 2 === 0 : this.image % 2 === 0)) {
      const p2 = this.tenseur(src, w, h, Math.min(this.cote, 512));
      const o2 = await this.usagers.run({ [this.usagers.inputNames[0]]: p2.t });
      const { usagers, feux } = this.postUsagers(o2[this.usagers.outputNames[0]], p2, w, h);
      const f = 0.73 * Math.max(w, h);
      for (const u of usagers) u.dist = f * HAUTEUR[D.items[u.cls].code] / Math.max(1, u.box[3] - u.box[1]);
      for (const fe of feux) { const c = this.couleurFeu(src, fe.box); if (c) dets.push({ box: fe.box, conf: fe.conf, cls: D.parCode[c].index }); }
      dets = dets.concat(usagers);
      groupes.add("u"); groupes.add("f");
    }
    if (generation !== this.generation) return { nouveaux: [], changes: [], brutes: null };  // suivi remis à zéro pendant le calcul
    const brutes = debug ? dets.map(d => ({ ...d })) : null;
    if (this.actifs) dets = dets.filter(d => this.actifs.has(d.cls));
    this.majLignes(dets, w);
    const { nouveaux, changes } = this.suivre(dets, groupes, w, h);
    this.majVitesse(w, h);
    const ms = performance.now() - t0;
    this.ms = this.ms ? 0.9 * this.ms + 0.1 * ms : ms;
    return { nouveaux, changes, brutes };
  }

  // Analyse de la vue au loin : seulement les panneaux. Les marquages, les feux et les usagers restent à l'image entière
  // (au loin ils n'apprennent rien d'utile au conducteur), et leurs pistes ne sont pas touchées par cette passe.
  async analyserLoin(src, w, h, champ, t0, generation, debug) {
    const prep = this.tenseur(src, w, h, this.cote, champ);
    const out = await this.session.run({ [this.session.inputNames[0]]: prep.t });
    const bords = d => d.box[0] > champ[0] + 2 && d.box[1] > champ[1] + 2 && d.box[2] < champ[0] + champ[2] - 2 && d.box[3] < champ[1] + champ[3] - 2;
    // un panneau coupé par le bord de la région serait mal lu : il est laissé à l'image entière
    let dets = await this.affiner(src, this.postRoute(out[this.session.outputNames[0]], prep).filter(d => d.cls === SIGN && bords(d)));
    if (generation !== this.generation) return { nouveaux: [], changes: [], brutes: null };
    const ech = 640 / Math.max(champ[2], champ[3]);
    for (const d of dets) d.ech = ech;
    const brutes = debug ? dets.map(d => ({ ...d })) : null;
    if (this.actifs) dets = dets.filter(d => this.actifs.has(d.cls));
    const { nouveaux, changes } = this.suivre(dets, new Set(["s"]), w, h, champ);
    this.majVitesse(w, h);
    const ms = performance.now() - t0;
    this.ms = this.ms ? 0.9 * this.ms + 0.1 * ms : ms;
    return { nouveaux, changes, brutes, champ };
  }

  // Horizon : le haut des lignes de la route (elles se rejoignent à l'horizon), lissé d'image en image. Il sert à placer
  // la vue au loin quand le téléphone penche vers le haut ou vers le bas.
  majHorizon(dets, w, h) {
    let haut = null;
    for (const d of dets) if (d.conf >= 0.5 && LIGNES.test(D.items[d.cls]?.code || "") && d.box[3] - d.box[1] > 0.12 * h) haut = haut === null ? d.box[1] : Math.min(haut, d.box[1]);
    if (haut === null) return;
    haut = Math.min(Math.max(haut, 0.3 * h), 0.7 * h);
    this.horizon = this.horizon?.w === w && this.horizon.h === h ? { w, h, y: 0.92 * this.horizon.y + 0.08 * haut } : { w, h, y: haut };
  }

  // ---------- « Mes panneaux » : panneaux d'une photo, et empreintes d'un panneau choisi ----------
  async panneauxPhoto(img, w, h) {
    const prep = this.tenseur(img, w, h, 640);
    const out = await this.session.run({ [this.session.inputNames[0]]: prep.t });
    const signes = this.postRoute(out[this.session.outputNames[0]], prep, 0.08).filter(d => d.cls === SIGN).slice(0, 8);
    if (this.cls && signes.length) {
      const res = await this.classer(img, signes);
      signes.forEach((d, i) => { d.devine = res[i].g >= 0 && res[i].p >= 0.5 ? res[i].g : null; });
    }
    return signes;
  }
  async empreinteDe(img, box) {
    if (!(await this.chargerEmpreinte())) return [];
    const variantes = [1.05, 1.15, 1.3];
    const x = this.vignettesMultiples(img, box, variantes);
    return (await this.empreintes(x)).map(e => Array.from(e));
  }
  vignettesMultiples(img, box, marges) {
    const ts = marges.map(m => this.vignettes(img, [box], EMB, EMB, m).data);
    const f = new Float32Array(ts.length * ts[0].length);
    ts.forEach((t, i) => f.set(t, i * t.length));
    return new ort.Tensor("float32", f, [ts.length, 3, EMB, EMB]);
  }
}
