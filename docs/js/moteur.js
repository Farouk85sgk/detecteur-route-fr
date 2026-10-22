// Moteur de détection dans le navigateur (ONNX Runtime Web : WebGPU si possible, sinon WebAssembly).
// 1. YOLOv5n panneaux + marquages ; les panneaux sont d'abord regroupés en une pseudo-classe « panneau » et le
//    classifieur (second étage) choisit la classe exacte ou rejette (même logique que route_fr/detector.py).
// 2. YOLOv5n COCO d'origine (une image sur deux) : piétons, cyclistes, deux-roues et feux tricolores (couleur lue
//    sur l'image).
// 3. « Mes panneaux » : empreinte de chaque panneau détecté comparée à celles des panneaux appris.
// 4. Suivi dans le temps (comme route_fr/tracker.py) : un élément n'est confirmé qu'après 2 détections, sa classe
//    est votée sur plusieurs images ; mémoire de la vitesse maximale.
/* global ort */
import { D } from "./donnees.js";

const CONF = 0.35, CONF_SIGNS = 0.15, SIGN_FACTOR = 1.3, IOU = 0.45, MIN_HITS = 2, MAX_MISSES = 6;
const CLS_SIZE = 64, MEAN = [0.485, 0.456, 0.406], STD = [0.229, 0.224, 0.225];
const SIGN = -2;
const COCO = { personne: 0, velo: 1, moto: 2, feu: 3 };  // ordre des classes gardées dans usagers.onnx
const HAUTEUR = { U_pieton: 1.7, U_cycliste: 1.75, U_deux_roues: 1.45 };  // m, pour estimer la distance
export const TAILLES = { rapide: 416, equilibree: 512, fine: 640 };

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
    this.clsMap = []; this.fournisseurs = []; this.isSign = [];
    this.cote = 640; this.avecUsagers = true; this.actifs = null; this.appris = []; this.seuilAppris = 0.5;
    this.work = document.createElement("canvas"); this.wctx = this.work.getContext("2d", { willReadFrequently: true });
    this.crop = Object.assign(document.createElement("canvas"), { width: CLS_SIZE, height: CLS_SIZE });
    this.cctx = this.crop.getContext("2d", { willReadFrequently: true });
    this.cfeu = document.createElement("canvas"); this.fctx = this.cfeu.getContext("2d", { willReadFrequently: true });
    this.reinitialiser();
    this.ms = 0; this.image = 0;
  }

  async charger({ backend = null, progression = () => {} } = {}) {
    this.fournisseurs = backend ? [backend] : ("gpu" in navigator) ? ["webgpu", "wasm"] : ["wasm"];
    const opts = { executionProviders: this.fournisseurs, graphOptimizationLevel: "all" };
    progression("Chargement du détecteur…");
    try { this.session = await ort.InferenceSession.create("modele.onnx", opts); }
    catch (e) {  // WebGPU indisponible ou défaillant : repli sur le processeur
      if (this.fournisseurs[0] === "wasm") throw e;
      this.fournisseurs = ["wasm"];
      this.session = await ort.InferenceSession.create("modele.onnx", { ...opts, executionProviders: ["wasm"] });
    }
    this.opts = { ...opts, executionProviders: this.fournisseurs };
    this.isSign = D.items.slice(0, D.nbModele).map(c => c.categorie !== "marquage");
    progression("Chargement du classifieur…");
    try {
      const noms = await (await fetch("classifieur.json")).json();
      this.cls = await ort.InferenceSession.create("classifieur.onnx", this.opts);
      this.clsMap = noms.map(n => D.parCode[n] && D.parCode[n].index < D.nbModele ? D.parCode[n].index : -1);  // -1 : autre panneau ou fond
    } catch (e) { console.warn("Classifieur indisponible", e); this.cls = null; }
    this.pret = true;
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
  configurer({ cote, avecUsagers, actifs, appris } = {}) {
    if (cote) this.cote = cote;
    if (avecUsagers !== undefined) this.avecUsagers = avecUsagers;
    if (actifs !== undefined) this.actifs = actifs;
    if (appris !== undefined) { this.appris = appris; if (appris.length) this.chargerEmpreinte(); }
    if (this.avecUsagers && this.pret) this.chargerUsagers();
  }
  reinitialiser() { this.pistes = []; this.prochainId = 1; this.vitesse = { valeur: null, code: null, quand: 0 }; this.image = 0; }

  // ---------- pré-traitement : image -> tenseur letterbox (multiple de 32) ----------
  tenseur(src, w, h, cote) {
    const r = cote / Math.max(w, h);
    const nw = Math.round(w * r), nh = Math.round(h * r);
    const W = Math.ceil(nw / 32) * 32, H = Math.ceil(nh / 32) * 32, px = (W - nw) / 2, py = (H - nh) / 2;
    this.work.width = W; this.work.height = H;
    this.wctx.fillStyle = "rgb(114,114,114)"; this.wctx.fillRect(0, 0, W, H);
    this.wctx.drawImage(src, px, py, nw, nh);
    const data = this.wctx.getImageData(0, 0, W, H).data, n = W * H, f = new Float32Array(3 * n);
    for (let i = 0; i < n; i++) { f[i] = data[4 * i] / 255; f[n + i] = data[4 * i + 1] / 255; f[2 * n + i] = data[4 * i + 2] / 255; }
    return { t: new ort.Tensor("float32", f, [1, 3, H, W]), r, px, py };
  }

  // ---------- panneaux et marquages ----------
  postRoute(out, { r, px, py }, seuilPanneaux = CONF_SIGNS) {
    const [, n, d] = out.dims, v = out.data, nc = d - 5, dets = [];
    const bas = this.cls ? Math.min(CONF, seuilPanneaux) : CONF;
    for (let i = 0; i < n; i++) {
      const o = i * d, obj = v[o + 4];
      if (obj < bas) continue;
      const cx = v[o], cy = v[o + 1], w = v[o + 2], h = v[o + 3];
      const box = [(cx - w / 2 - px) / r, (cy - h / 2 - py) / r, (cx + w / 2 - px) / r, (cy + h / 2 - py) / r];
      if (this.cls) {  // probabilités des panneaux sommées : le classifieur choisira la classe exacte
        let bm = 0, cm = 0, s = 0;
        for (let k = 0; k < nc; k++) { const p = v[o + 5 + k]; if (this.isSign[k]) s += p; else if (p > bm) { bm = p; cm = k; } }
        if (obj * bm >= CONF) dets.push({ box, conf: obj * bm, cls: cm });
        if (obj * Math.min(1, s) >= seuilPanneaux) dets.push({ box: box.slice(), conf: obj * Math.min(1, s), cls: SIGN });
      } else {
        let best = 0, c = 0;
        for (let k = 0; k < nc; k++) if (v[o + 5 + k] > best) { best = v[o + 5 + k]; c = k; }
        if (obj * best >= CONF) dets.push({ box, conf: obj * best, cls: c });
      }
    }
    return nms(dets).slice(0, 100);
  }

  vignettes(src, boxes, marge = 1.15) {
    const S = CLS_SIZE, plan = S * S, f = new Float32Array(boxes.length * 3 * plan);
    boxes.forEach((b, i) => {
      const [x1, y1, x2, y2] = b, s = Math.max(x2 - x1, y2 - y1) * marge, cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
      this.cctx.fillStyle = "rgb(114,114,114)"; this.cctx.fillRect(0, 0, S, S);
      this.cctx.drawImage(src, cx - s / 2, cy - s / 2, s, s, 0, 0, S, S);
      const px = this.cctx.getImageData(0, 0, S, S).data, o = i * 3 * plan;
      for (let k = 0; k < plan; k++) for (let c = 0; c < 3; c++) f[o + c * plan + k] = (px[4 * k + c] / 255 - MEAN[c]) / STD[c];
    });
    return new ort.Tensor("float32", f, [boxes.length, 3, S, S]);
  }

  async classer(src, signes) {
    const x = this.vignettes(src, signes.map(d => d.box));
    const out = await this.cls.run({ [this.cls.inputNames[0]]: x });
    const logits = out[this.cls.outputNames[0]].data, nc = logits.length / signes.length;
    return signes.map((d, i) => {
      let m = -Infinity, k = 0, sum = 0;
      for (let j = 0; j < nc; j++) if (logits[i * nc + j] > m) { m = logits[i * nc + j]; k = j; }
      for (let j = 0; j < nc; j++) sum += Math.exp(logits[i * nc + j] - m);
      return { g: this.clsMap[k], p: 1 / sum, x };
    });
  }

  async empreintes(x) {
    const out = await this.emp.run({ [this.emp.inputNames[0]]: x });
    const e = out[this.emp.outputNames[0]].data, dim = e.length / x.dims[0];
    return Array.from({ length: x.dims[0] }, (_, i) => e.subarray(i * dim, (i + 1) * dim));
  }

  // second étage : classe exacte de chaque panneau, rejet des leurres, puis panneaux appris
  async affiner(src, dets) {
    const signes = dets.filter(d => d.cls === SIGN), autres = dets.filter(d => d.cls !== SIGN);
    if (!this.cls || !signes.length) return autres;
    const res = await this.classer(src, signes);
    let emb = null;
    if (this.appris.length && this.emp) emb = await this.empreintes(res[0].x);
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
      if (d.conf >= SIGN_FACTOR * CONF) gardes.push(d);
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
  suivre(dets, groupes, w, h) {
    const groupeDe = c => D.items[c].groupe, taille = b => Math.max(b[2] - b[0], b[3] - b[1]) * 640 / Math.max(w, h);
    const nouveaux = [], changes = [], pairs = [], tUsed = new Set(), dUsed = new Set();
    this.pistes.forEach((t, i) => { if (!groupes.has(t.groupe)) return; dets.forEach((d, j) => { if (groupeDe(d.cls) === t.groupe) { const v = iou(t.box, d.box); if (v >= 0.25) pairs.push([v, i, j]); } }); });
    pairs.sort((a, b) => b[0] - a[0]);
    const toucher = (t, d) => {
      const a = t.hits ? 0.55 : 1;
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
    for (const [, i, j] of pairs) { if (tUsed.has(i) || dUsed.has(j)) continue; tUsed.add(i); dUsed.add(j); toucher(this.pistes[i], dets[j]); }
    dets.forEach((d, j) => {
      if (dUsed.has(j)) return;
      const t = { id: this.prochainId++, box: d.box.slice(), groupe: groupeDe(d.cls), scores: {}, conf: 0, hits: 0, misses: 0, ok: false, debut: performance.now() };
      toucher(t, d);
      this.pistes.push(t); tUsed.add(this.pistes.length - 1);
    });
    this.pistes.forEach((t, i) => {
      if (!groupes.has(t.groupe)) return;
      if (!tUsed.has(i)) { t.misses++; for (const k in t.scores) t.scores[k] *= 0.9; }
      else if (!t.ok && (t.hits >= MIN_HITS || t.conf > 0.85) && (t.groupe === "m" || taille(t.box) >= 18)) { t.ok = true; nouveaux.push(t); }
    });
    this.pistes = this.pistes.filter(t => t.misses <= MAX_MISSES);
    return { nouveaux, changes };
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
      if ((it.vitesse != null || it.code === "B33" || it.code === "B31") && t.conf >= 0.4 && taille(t.box) >= 20 && (!best || taille(t.box) > taille(best.box))) best = t;
    }
    if (best) {
      const it = D.items[this.classe(best)];
      if (it.code !== this.vitesse.code) this.vitesse = { valeur: it.vitesse, code: it.code, quand: Date.now() };
    }
  }

  // ---------- analyse d'une image de la vidéo ----------
  async analyser(src, w, h, { debug = false } = {}) {
    const t0 = performance.now();
    this.image++;
    const prep = this.tenseur(src, w, h, this.cote);
    const out = await this.session.run({ [this.session.inputNames[0]]: prep.t });
    let dets = await this.affiner(src, this.postRoute(out[this.session.outputNames[0]], prep));
    const groupes = new Set(["s", "m"]);
    if (this.avecUsagers && this.usagers && this.image % 2 === 0) {
      const p2 = this.tenseur(src, w, h, Math.min(this.cote, 512));
      const o2 = await this.usagers.run({ [this.usagers.inputNames[0]]: p2.t });
      const { usagers, feux } = this.postUsagers(o2[this.usagers.outputNames[0]], p2, w, h);
      const f = 0.73 * Math.max(w, h);
      for (const u of usagers) u.dist = f * HAUTEUR[D.items[u.cls].code] / Math.max(1, u.box[3] - u.box[1]);
      for (const fe of feux) { const c = this.couleurFeu(src, fe.box); if (c) dets.push({ box: fe.box, conf: fe.conf, cls: D.parCode[c].index }); }
      dets = dets.concat(usagers);
      groupes.add("u"); groupes.add("f");
    }
    const brutes = debug ? dets.map(d => ({ ...d })) : null;
    if (this.actifs) dets = dets.filter(d => this.actifs.has(d.cls));
    const { nouveaux, changes } = this.suivre(dets, groupes, w, h);
    this.majVitesse(w, h);
    const ms = performance.now() - t0;
    this.ms = this.ms ? 0.9 * this.ms + 0.1 * ms : ms;
    return { nouveaux, changes, brutes };
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
    const ts = marges.map(m => this.vignettes(img, [box], m).data);
    const f = new Float32Array(ts.length * ts[0].length);
    ts.forEach((t, i) => f.set(t, i * t.length));
    return new ort.Tensor("float32", f, [ts.length, 3, CLS_SIZE, CLS_SIZE]);
  }
}
