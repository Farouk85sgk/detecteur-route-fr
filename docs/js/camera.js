// Écran caméra : détection en direct (caméra ou vidéo), carte du dernier élément, historique, lecteur vidéo, pause
// avec zoom et toucher d'un panneau, annonces vocales, photos incrustées, vidéo du trajet, GPS, résumé du trajet.
import { APP, FAMILLES } from "./contenu.js";
import { D, icone } from "./donnees.js";
import { Moteur, TAILLES } from "./moteur.js";
import { evenement, noterAlbum, verifierBadges, verifierMystere, PROG } from "./progression.js";
import { aller } from "./nav.js";
import { idbMettre, idbSupprimerPrefixe, profil, sauver } from "./stockage.js";
import { $, ICONES, duree, el, esc, heure, ouvrirFeuille, son, tempsVideo, toast, vibrer } from "./ui.js";

export const moteur = new Moteur();
let C = null;  // session caméra en cours
const imgs = {};
const imageDe = url => { if (!imgs[url]) { imgs[url] = new Image(); imgs[url].src = url; } return imgs[url]; };

// Réglages du profil -> moteur (taille d'analyse, usagers, éléments affichés)
export function configurerMoteur(p = profil()) {
  const r = p.reglages;
  const auto = moteur.fournisseurs[0] === "webgpu" ? "fine" : "equilibree";
  const actifs = new Set();
  for (const it of D.items) {
    const fam = it.famille === "perso" ? true : r.familles[it.famille] !== false;
    if (fam && !r.exclus.includes(it.code)) actifs.add(it.index);
  }
  const usagers = ["F_rouge", "F_orange", "F_vert", "U_pieton", "U_cycliste", "U_deux_roues"].some(c => actifs.has(D.parCode[c].index));
  moteur.configurer({ cote: TAILLES[r.qualite === "auto" ? auto : r.qualite] || 512, avecUsagers: usagers, actifs: actifs.size === D.items.length ? null : actifs });
}

export async function ouvrirCamera({ fichier = null, apresFermeture = () => {} } = {}) {
  const p = profil(), r = p.reglages;
  const racine = el(`<div class="camera" role="application" aria-label="Détection en direct">
    <video playsinline muted></video><canvas class="calque"></canvas><div class="calque-touche"></div>
    <div class="cam-haut"><button class="statut verre charge" data-a="pause"><i></i><span>Chargement…</span></button>
      <div class="cam-boutons">
        <button class="cam-btn verre" data-a="rec" aria-label="Enregistrer la vidéo">${ICONES.enregistrer}</button>
        <button class="cam-btn verre" data-a="son" aria-label="Annonce vocale">${r.voix ? ICONES.son : ICONES.sonCoupe}</button>
        <button class="cam-btn verre" data-a="reglages" aria-label="Réglages">${ICONES.reglages}</button>
        <button class="cam-btn verre" data-a="fermer" aria-label="Terminer le trajet">${ICONES.fermer}</button>
      </div></div>
    <div class="cam-gauche"><div class="vitesse-cam cache"></div><div class="lignes"></div></div>
    <div class="astuce-cam cache">Pince pour zoomer, puis touche un panneau</div>
    <div class="cam-bas"><div class="cam-toasts" aria-live="polite"></div>
      <div class="lecteur verre cache"><button data-a="recul" aria-label="Reculer de 5 s">${ICONES.recul5}</button>
        <button class="jouer" data-a="lecture" aria-label="Lecture ou pause">${ICONES.pause}</button>
        <button data-a="avance" aria-label="Avancer de 5 s">${ICONES.avance5}</button><span class="temps">0:00</span><input type="range" min="0" max="1" step="0.1" value="0" aria-label="Position dans la vidéo"></div>
      <div class="historique"><div class="defile"></div><button class="cam-btn verre" data-a="cadres" aria-label="Afficher ou masquer les cadres">${ICONES.oeil}</button></div>
      <button class="cam-carte cache" data-a="fiche"></button></div></div>`);
  document.body.append(racine);
  document.body.classList.add("sans-defilement");
  const video = $("video", racine), calque = $("canvas", racine), ctx = calque.getContext("2d");
  C = {
    racine, video, calque, ctx, fichier, apresFermeture, p, pause: false, cadres: true, fini: false, zoom: { k: 1, x: 0, y: 0 },
    trajet: { id: "t" + Date.now().toString(36), debut: Date.now(), source: fichier ? "video" : "camera", fichier: fichier?.name || null, elements: {}, nouveaux: [], photos: 0, evenements: [] },
    dernier: {}, historique: [], derniereCarte: null, dernierePhoto: 0, nPhoto: 0, pos: null, fps: 0, tPrec: performance.now(), lignes: {}, enregistreur: null,
  };
  PROG.notifier = (texte, badge) => toast(texte, badge, $(".cam-toasts", racine));
  D.items.forEach(it => imageDe(icone(it)));  // icônes en mémoire : affichage immédiat pendant la détection
  racine.addEventListener("click", clic);
  brancherZoom();
  addEventListener("resize", disposer);
  document.addEventListener("visibilitychange", visibilite);

  try {
    if (!moteur.pret) await moteur.charger({ backend: new URLSearchParams(location.search).get("backend"), progression: t => statut(t, "charge") });
    window.__moteurGPU = moteur.fournisseurs[0] === "webgpu";
    configurerMoteur(p);
    await demarrerSource();
  } catch (e) {
    console.error(e);
    statut("Erreur", "erreur");
    $(".cam-bas", racine).prepend(el(`<div class="cam-carte" style="grid-template-columns:1fr"><div><h2>Impossible de démarrer</h2><p>${esc(messageErreur(e))}</p></div></div>`));
    return;
  }
  if (r.paysage) paysage();
  if ("wakeLock" in navigator) navigator.wakeLock.request("screen").then(w => (C.verrou = w)).catch(() => {});
  if (r.gps && !fichier && "geolocation" in navigator)
    C.geo = navigator.geolocation.watchPosition(g => (C.pos = { lat: +g.coords.latitude.toFixed(6), lon: +g.coords.longitude.toFixed(6) }), () => {}, { enableHighAccuracy: true, maximumAge: 5000 });
  if (r.video) demarrerEnregistrement();
  boucle();
}

function messageErreur(e) {
  if (e?.name === "NotAllowedError") return "L'accès à la caméra a été refusé. Autorise la caméra pour ce site dans les réglages du navigateur.";
  if (e?.name === "NotFoundError") return "Aucune caméra trouvée sur cet appareil.";
  if (e?.name === "NotSupportedError") return "Ce navigateur ne sait pas lire cette vidéo : essaie une vidéo MP4 (H.264) ou WebM.";
  if (!isSecureContext) return "La caméra n'est accessible qu'en HTTPS (ou sur localhost).";
  return e?.message || String(e);
}

async function demarrerSource() {
  const { video, fichier } = C;
  if (fichier) {
    video.src = URL.createObjectURL(fichier);
    video.loop = false;
    await video.play();
    $(".lecteur", C.racine).classList.remove("cache");
    const plage = $(".lecteur input", C.racine);
    video.addEventListener("loadedmetadata", () => (plage.max = video.duration || 1));
    plage.max = video.duration || 1;
    plage.oninput = () => { video.currentTime = +plage.value; };
    video.addEventListener("ended", () => basculerPause(true));
    statut("Vidéo", "");
  } else {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } } });
    video.srcObject = stream;
    await video.play();
    statut("Caméra", "");
  }
  disposer();
}

function statut(texte, cls) {
  const s = $(".statut", C.racine);
  s.className = `statut verre ${cls || ""}`;
  $("span", s).textContent = texte;
}

// ---------- disposition : la vidéo remplit l'écran (ou y tient entière si les proportions diffèrent trop) ----------
function disposer() {
  if (!C) return;
  const { video, calque, zoom } = C, vw = video.videoWidth, vh = video.videoHeight;
  if (!vw) return;
  const paysage = innerWidth > innerHeight && innerWidth > 700;
  C.racine.classList.toggle("paysage", paysage);
  const W = paysage ? innerWidth * 0.58 : innerWidth, H = innerHeight, couvre = Math.abs(Math.log((vw / vh) / (W / H))) < 0.35;
  const s = (couvre ? Math.max(W / vw, H / vh) : Math.min(W / vw, H / vh)) * zoom.k;
  const dw = vw * s, dh = vh * s, ox = (W - dw) / 2 + zoom.x, oy = (H - dh) / 2 + zoom.y;
  for (const e of [video, calque]) Object.assign(e.style, { width: dw + "px", height: dh + "px", left: ox + "px", top: oy + "px" });
  const dpr = devicePixelRatio || 1;
  calque.width = Math.round(Math.min(dw, W * 2) * dpr); calque.height = Math.round(Math.min(dh, H * 2) * dpr);
  calque.style.width = dw + "px"; calque.style.height = dh + "px";
  C.s = s; C.ox = ox; C.oy = oy; C.vw = vw; C.vh = vh;
}

// ---------- boucle d'analyse ----------
async function boucle() {
  if (!C || C.fini) return;
  const { video } = C;
  if (!C.pause && !document.hidden && video.readyState >= 2 && video.videoWidth) {
    if (video.videoWidth !== C.vw || video.videoHeight !== C.vh) disposer();
    try {
      const res = await moteur.analyser(video, video.videoWidth, video.videoHeight, { debug: C.p.reglages.debug });
      if (!C || C.fini) return;
      C.brutes = res.brutes;
      for (const t of res.nouveaux) annoncer(t);
      for (const { t, avant } of res.changes) if (D.items[avant]?.code === "F_rouge" && D.items[moteur.classe(t)]?.code === "F_vert") annoncer(t, "Le feu passe au vert");
      dessiner();
      if (C.enregistreur) composer(C.compoVideo, C.compoVideo.width);
      const now = performance.now();
      C.fps = C.fps ? 0.9 * C.fps + 0.1 * 1000 / (now - C.tPrec) : 1000 / (now - C.tPrec);
      C.tPrec = now;
      if (moteur.image % 20 === 1) window.__etatDetecteur = decrireMoteur();
      majLecteur();
    } catch (e) { console.error(e); }
  } else if (C.fichier) majLecteur();
  C.raf = setTimeout(() => requestAnimationFrame(boucle), 15);
}

const visibilite = () => { if (C && !document.hidden) C.tPrec = performance.now(); };
const decrireMoteur = () => `Prêt (${moteur.fournisseurs[0] === "webgpu" ? "carte graphique" : `processeur, ${navigator.hardwareConcurrency || "?"} cœurs`}, classifieur ${moteur.cls ? "actif" : "absent"}, `
  + `usagers ${moteur.usagers ? "actifs" : "inactifs"}${moteur.emp ? ", Mes panneaux actif" : ""}, ${Math.round(moteur.ms)} ms par image, ${C?.fps ? C.fps.toFixed(1) : "?"} images/s).`;

// ---------- annonce d'un élément confirmé ----------
function annoncer(t, phrase = null) {
  const { p } = C, r = p.reglages, cls = moteur.classe(t), it = D.items[cls];
  if (!it) return;
  const maintenant = Date.now(), dernier = C.dernier[it.code] || 0;
  const pause = it.groupe === "u" || it.groupe === "f" ? 20000 : 8000;
  // trajet, album, quêtes : chaque confirmation compte
  C.trajet.elements[it.code] = (C.trajet.elements[it.code] || 0) + 1;
  if (C.trajet.evenements.length < 400) C.trajet.evenements.push({ code: it.code, t: tempsTrajet(), pos: C.pos });
  if (it.index < D.nbOfficiels) {
    const neuf = noterAlbum(p, it.code);
    if (neuf) {
      C.trajet.nouveaux.push(it.code);
      toast(`Nouveau dans l'album : ${it.nom}`, "+20 XP", $(".cam-toasts", C.racine));
      son("nouveau", r.sons);
      evenement("nouveau");
    }
    evenement("repere");
    verifierMystere(p, it.code);
  }
  if (!phrase && maintenant - dernier < pause) return;
  C.dernier[it.code] = maintenant;
  montrerCarte(it, t, false);
  ajouterHistorique(it);
  if (r.voix && "speechSynthesis" in window) {
    let texte = phrase || (r.lireLimitations && it.code.startsWith("B14_") ? `Limitation à ${it.vitesse}` : it.voix || it.nom);
    if (it.groupe === "u" && t.dist) texte += `, à ${arrondiDistance(t.dist)} mètres`;
    if (r.expliquer && !phrase) texte += ". " + it.reflexe;
    if (speechSynthesis.pending) speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(texte); u.lang = "fr-FR"; speechSynthesis.speak(u);
  }
  vibrer(it.groupe === "u" ? 40 : 70, r.vibration);
  if (r.photos && maintenant - C.dernierePhoto > 1200 && C.trajet.photos < 80) prendrePhoto(t);
}
const arrondiDistance = d => Math.max(5, Math.round(d / 5) * 5);
const tempsTrajet = () => C.fichier ? +C.video.currentTime.toFixed(1) : Math.round((Date.now() - C.trajet.debut) / 1000);

function montrerCarte(it, t, forcer = true) {
  const carte = $(".cam-carte", C.racine);
  // un marquage au sol ne chasse pas un panneau, un feu ou un usager affiché depuis moins de 4 s
  if (!forcer && it.groupe === "m" && C.carteGroupe && C.carteGroupe !== "m" && Date.now() - C.derniereCarte < 4000) return;
  if (!carte.firstElementChild) carte.innerHTML = `<img alt=""><div><h2></h2><p></p><div class="meta"><span class="code-badge"></span><span></span></div></div>`;
  const img = carte.querySelector("img"), src = icone(it);
  if (img.getAttribute("src") !== src) img.src = src;
  carte.querySelector("h2").textContent = it.nom;
  carte.querySelector("p").textContent = it.explication;
  carte.querySelector(".code-badge").textContent = it.etiquette;
  carte.querySelector(".meta span:last-child").textContent = `à l'instant${it.groupe === "u" && t?.dist ? ` · ≈ ${arrondiDistance(t.dist)} m` : ""}`;
  carte.classList.remove("cache");
  carte.dataset.code = it.code;
  C.derniereCarte = Date.now();
  C.carteGroupe = it.groupe;
}
function ajouterHistorique(it) {
  if (C.historique[0] === it.code) return;
  C.historique = [it.code, ...C.historique.filter(c => c !== it.code)].slice(0, 14);
  const zone = $(".defile", C.racine);
  zone.querySelector(`[data-code="${CSS.escape(it.code)}"]`)?.remove();
  zone.prepend(el(`<button data-a="histo" data-code="${esc(it.code)}" aria-label="${esc(it.nom)}"><img src="${esc(icone(it))}" alt=""></button>`));
  while (zone.children.length > 14) zone.lastElementChild.remove();
}

// ---------- dessin des cadres ----------
function etiquette(it, t) {
  if (it.groupe === "u" && t.dist) return `${it.nom} ≈ ${arrondiDistance(t.dist)} m`;
  return it.groupe === "m" ? it.nom : `${it.nom} ${Math.round(t.conf * 100)} %`;
}
function dessiner() {
  const { ctx, calque, s } = C, dpr = calque.width / Math.max(1, parseFloat(calque.style.width));
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, calque.width, calque.height);
  const k = s * dpr;
  ctx.font = `700 ${Math.round(14 * dpr)}px Overpass, system-ui, sans-serif`;
  ctx.textBaseline = "middle";
  if (C.p.reglages.debug && C.brutes) {
    ctx.lineWidth = 1.5 * dpr; ctx.strokeStyle = "rgba(170,120,255,.9)";
    for (const d of C.brutes) ctx.strokeRect(d.box[0] * k, d.box[1] * k, (d.box[2] - d.box[0]) * k, (d.box[3] - d.box[1]) * k);
  }
  const lignes = {};
  for (const t of moteur.pistes) {
    if (!t.ok || t.misses > 2) continue;
    const it = D.items[moteur.classe(t)];
    if (!it) continue;
    if (it.groupe === "m" && /^M_ligne_(continue|discontinue|mixte)$/.test(it.code)) {
      const cote = (t.box[0] + t.box[2]) / 2 < C.vw / 2 ? "g" : "d";
      if (!lignes[cote] || t.conf > lignes[cote].conf) lignes[cote] = { nom: it.nom, conf: t.conf };
    }
    if (!C.cadres) continue;
    const [x1, y1, x2, y2] = t.box.map(v => v * k);
    ctx.lineWidth = (it.groupe === "m" ? 2 : 3) * dpr;
    ctx.strokeStyle = it.couleur;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x1, y1, x2 - x1, y2 - y1, 6 * dpr) : ctx.rect(x1, y1, x2 - x1, y2 - y1); ctx.stroke();
    const txt = etiquette(it, t), tw = ctx.measureText(txt).width + 14 * dpr, th = 24 * dpr;
    const ty = y1 - th - 3 * dpr > 0 ? y1 - th - 3 * dpr : y2 + 3 * dpr;
    ctx.fillStyle = it.couleur;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x1, ty, tw, th, 8 * dpr) : ctx.rect(x1, ty, tw, th); ctx.fill();
    ctx.fillStyle = ["zone", "priorite", "marquage", "feu"].includes(it.categorie) ? "#111" : "#fff";
    ctx.fillText(txt, x1 + 7 * dpr, ty + th / 2 + dpr);
  }
  // lignes de part et d'autre, vitesse en cours
  const html = (lignes.g ? `<div class="puce-ligne verre">◂ ${esc(lignes.g.nom)}</div>` : "") + (lignes.d ? `<div class="puce-ligne verre">${esc(lignes.d.nom)} ▸</div>` : "");
  const zl = $(".lignes", C.racine);
  if (zl.dataset.html !== html) { zl.innerHTML = html; zl.dataset.html = html; zl.style.display = "flex"; zl.style.flexDirection = "column"; zl.style.gap = "10px"; }
  const v = moteur.vitesse, zv = $(".vitesse-cam", C.racine);
  const val = v.valeur != null && !["B33", "B31"].includes(v.code) ? String(v.valeur) : "";
  if (zv.textContent !== val) { zv.textContent = val; zv.classList.toggle("cache", !val); }
  if (C.derniereCarte) { const meta = $(".cam-carte .meta span:last-child", C.racine); if (meta && Date.now() - C.derniereCarte > 5000) meta.textContent = `il y a ${Math.round((Date.now() - C.derniereCarte) / 1000)} s`; }
}

// ---------- photo incrustée (cadres, bandeau du panneau annoncé) ----------
function composer(canvas, largeur, focus = null) {
  const { video } = C, vw = video.videoWidth, vh = video.videoHeight, W = largeur, H = Math.round(largeur * vh / vw), k = W / vw;
  canvas.width = W; canvas.height = H;
  const g = canvas.getContext("2d");
  g.drawImage(video, 0, 0, W, H);
  g.font = `700 ${Math.round(W / 46)}px Overpass, system-ui, sans-serif`;
  g.textBaseline = "middle";
  for (const t of moteur.pistes) {
    if (!t.ok || t.misses > 2) continue;
    const it = D.items[moteur.classe(t)];
    if (!it) continue;
    const [x1, y1, x2, y2] = t.box.map(v => v * k);
    g.lineWidth = Math.max(2, W / 320); g.strokeStyle = it.couleur; g.strokeRect(x1, y1, x2 - x1, y2 - y1);
    const txt = etiquette(it, t), tw = g.measureText(txt).width + W / 70, th = W / 30;
    const ty = y1 - th > 0 ? y1 - th : y2;
    g.fillStyle = it.couleur; g.fillRect(x1, ty, tw, th);
    g.fillStyle = ["zone", "priorite", "marquage", "feu"].includes(it.categorie) ? "#111" : "#fff";
    g.fillText(txt, x1 + W / 140, ty + th / 2);
  }
  const it = focus || (C.historique[0] && D.parCode[C.historique[0]]);
  if (it) {
    const bh = Math.round(H * 0.16);
    g.fillStyle = "rgba(246,247,250,.94)"; g.fillRect(0, H - bh, W, bh);
    const ic = imageDe(icone(it));
    if (ic.complete && ic.naturalWidth) { const s = bh * 0.72, r = Math.min(s / ic.naturalWidth, s / ic.naturalHeight); g.drawImage(ic, bh * 0.16, H - bh + (bh - ic.naturalHeight * r) / 2, ic.naturalWidth * r, ic.naturalHeight * r); }
    g.fillStyle = "#12163a"; g.font = `800 ${Math.round(bh * 0.3)}px Bricolage, system-ui, sans-serif`;
    g.fillText(it.nom, bh * 1.05, H - bh * 0.64);
    g.font = `400 ${Math.round(bh * 0.2)}px Overpass, system-ui, sans-serif`; g.fillStyle = "#3f4c74";
    g.fillText(it.explication.slice(0, 90), bh * 1.05, H - bh * 0.28);
  }
  const tag = `${APP.nom}  ${C.fichier ? tempsVideo(C.video.currentTime) : heure(Date.now())}`;
  g.font = `700 ${Math.round(W / 60)}px Overpass, system-ui, sans-serif`;
  const tw = g.measureText(tag).width + W / 50;
  g.fillStyle = "rgba(18,22,58,.75)"; g.fillRect(W / 80, W / 80, tw, W / 34);
  g.fillStyle = "#fff"; g.fillText(tag, W / 80 + W / 100, W / 80 + W / 68);
}

function prendrePhoto(t) {
  C.dernierePhoto = Date.now();
  const cv = document.createElement("canvas");
  const it = D.items[moteur.classe(t)];
  composer(cv, Math.min(960, C.video.videoWidth), it);
  const noms = [...new Set(moteur.pistes.filter(x => x.ok && x.misses === 0 && x.groupe !== "m").map(x => D.items[moteur.classe(x)]?.nom).filter(Boolean))];
  const meta = { code: it.code, noms: noms.length ? noms.slice(0, 3) : [it.nom], t: tempsTrajet(), quand: Date.now(), pos: C.pos };
  const n = C.nPhoto++, { p, trajet } = C;
  cv.toBlob(async blob => {
    if (!blob) return;
    const cle = `${p.id}/${trajet.id}/${String(n).padStart(3, "0")}`;
    await idbMettre("photos", cle, { blob, ...meta });
    trajet.photos++;
    p.stats.photos++;
    if (p.album[it.code] && !p.album[it.code].photo) p.album[it.code].photo = cle;
    sauver();
  }, "image/jpeg", 0.74);
}

// ---------- vidéo du trajet (cadres et panneau incrustés) ----------
function demarrerEnregistrement() {
  if (!("MediaRecorder" in window) || C.enregistreur) return;
  C.compoVideo = document.createElement("canvas");
  composer(C.compoVideo, Math.min(1280, C.video.videoWidth || 1280));
  const type = ["video/mp4;codecs=avc1", "video/mp4", "video/webm;codecs=vp9", "video/webm"].find(t => MediaRecorder.isTypeSupported(t)) || "";
  try {
    const rec = new MediaRecorder(C.compoVideo.captureStream(20), type ? { mimeType: type, videoBitsPerSecond: 2_500_000 } : {});
    C.morceaux = [];
    rec.ondataavailable = e => e.data.size && C.morceaux.push(e.data);
    rec.start(1000);
    C.enregistreur = rec;
    $("[data-a=rec]", C.racine).classList.add("actif");
    $("[data-a=rec]", C.racine).innerHTML = ICONES.stop;
    toast("Enregistrement de la vidéo", "●", $(".cam-toasts", C.racine));
  } catch (e) { console.warn(e); toast("Enregistrement vidéo impossible sur cet appareil"); }
}
function arreterEnregistrement() {
  return new Promise(ok => {
    const rec = C?.enregistreur;
    if (!rec) return ok(null);
    C.enregistreur = null;
    $("[data-a=rec]", C.racine).classList.remove("actif");
    $("[data-a=rec]", C.racine).innerHTML = ICONES.enregistrer;
    rec.onstop = () => ok(new Blob(C.morceaux, { type: rec.mimeType || "video/webm" }));
    rec.stop();
  });
}

// ---------- commandes ----------
async function clic(e) {
  const b = e.target.closest("[data-a]");
  if (!b || !C) return;
  const a = b.dataset.a;
  if (a === "fermer") return terminer();
  if (a === "son") {
    const r = C.p.reglages; r.voix = !r.voix; sauver();
    b.innerHTML = r.voix ? ICONES.son : ICONES.sonCoupe;
    if (r.voix && "speechSynthesis" in window) speechSynthesis.speak(Object.assign(new SpeechSynthesisUtterance("Annonces activées"), { lang: "fr-FR" }));
    else if ("speechSynthesis" in window) speechSynthesis.cancel();
  }
  if (a === "reglages") { const { ouvrirReglages } = await import("./reglages.js"); ouvrirReglages({ depuisCamera: true }); }
  if (a === "rec") { if (C.enregistreur) { const blob = await arreterEnregistrement(); if (blob) C.videoBlob = blob; toast("Vidéo prête : elle sera proposée à la fin du trajet", "", $(".cam-toasts", C.racine)); } else demarrerEnregistrement(); }
  if (a === "cadres") { C.cadres = !C.cadres; b.innerHTML = C.cadres ? ICONES.oeil : ICONES.oeilBarre; dessiner(); }
  if (a === "pause") basculerPause();
  if (a === "lecture") basculerPause();
  if (a === "recul") { C.video.currentTime = Math.max(0, C.video.currentTime - 5); moteur.reinitialiser(); }
  if (a === "avance") { C.video.currentTime = Math.min(C.video.duration || 0, C.video.currentTime + 5); moteur.reinitialiser(); }
  if (a === "histo") { const it = D.parCode[b.dataset.code]; montrerCarte(it); $(".cam-carte .meta span:last-child", C.racine).textContent = "vu pendant ce trajet"; }
  if (a === "fiche") { const { ouvrirFiche } = await import("./album.js"); ouvrirFiche(b.dataset.code); }
}

function basculerPause(forcer = null) {
  C.pause = forcer ?? !C.pause;
  const { video } = C;
  if (C.pause) video.pause(); else { if (C.fichier && video.ended) video.currentTime = 0; video.play().catch(() => {}); C.zoom = { k: 1, x: 0, y: 0 }; disposer(); }
  statut(C.pause ? "En pause" : C.fichier ? "Vidéo" : "Caméra", C.pause ? "pause" : "");
  $(".astuce-cam", C.racine).classList.toggle("cache", !C.pause);
  const bj = $("[data-a=lecture]", C.racine);
  if (bj) bj.innerHTML = C.pause ? ICONES.lecture : ICONES.pause;
}

function majLecteur() {
  if (!C.fichier) return;
  const v = C.video;
  $(".lecteur .temps", C.racine).textContent = tempsVideo(v.currentTime || 0);
  const plage = $(".lecteur input", C.racine);
  if (document.activeElement !== plage) { plage.max = v.duration || 1; plage.value = v.currentTime || 0; }
}

// pause : pincer pour zoomer, glisser pour se déplacer, toucher un cadre pour ouvrir sa fiche
function brancherZoom() {
  const zone = $(".calque-touche", C.racine), doigts = new Map();
  let depart = null;
  zone.addEventListener("pointerdown", e => { doigts.set(e.pointerId, { x: e.clientX, y: e.clientY }); depart = { ...C.zoom, d: ecart(), cx: centre().x, cy: centre().y, t: Date.now(), x0: e.clientX, y0: e.clientY }; });
  zone.addEventListener("pointermove", e => {
    if (!C.pause || !doigts.has(e.pointerId)) return;
    doigts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const c = centre();
    if (doigts.size === 2 && depart.d) C.zoom.k = Math.min(5, Math.max(1, depart.k * ecart() / depart.d));
    C.zoom.x = depart.x + c.x - depart.cx; C.zoom.y = depart.y + c.y - depart.cy;
    disposer(); dessiner();
  });
  const fin = e => {
    const tap = depart && doigts.size === 1 && Date.now() - depart.t < 300 && Math.hypot(e.clientX - depart.x0, e.clientY - depart.y0) < 10;
    doigts.delete(e.pointerId);
    if (tap) toucher(e.clientX, e.clientY);
    if (doigts.size) depart = { ...C.zoom, d: ecart(), cx: centre().x, cy: centre().y, t: 0 };
  };
  zone.addEventListener("pointerup", fin);
  zone.addEventListener("pointercancel", e => doigts.delete(e.pointerId));
  const pts = () => [...doigts.values()];
  function ecart() { const p = pts(); return p.length === 2 ? Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y) : 0; }
  function centre() { const p = pts(); return p.length ? { x: p.reduce((s, q) => s + q.x, 0) / p.length, y: p.reduce((s, q) => s + q.y, 0) / p.length } : { x: 0, y: 0 }; }
}
async function toucher(x, y) {
  if (!C.pause) return basculerPause(true);
  const vx = (x - C.ox) / C.s, vy = (y - C.oy) / C.s;
  const t = moteur.pistes.filter(t => t.ok && vx >= t.box[0] && vx <= t.box[2] && vy >= t.box[1] && vy <= t.box[3])
    .sort((a, b) => (a.box[2] - a.box[0]) - (b.box[2] - b.box[0]))[0];
  if (t) { const it = D.items[moteur.classe(t)]; montrerCarte(it, t); const { ouvrirFiche } = await import("./album.js"); ouvrirFiche(it.code); }
}

function paysage() {
  document.documentElement.requestFullscreen?.().then(() => screen.orientation?.lock?.("landscape")).catch(() => {});
}

// ---------- fin du trajet ----------
export async function terminer() {
  if (!C || C.fini) return;
  C.fini = true;
  clearTimeout(C.raf);
  const videoBlob = (await arreterEnregistrement()) || C.videoBlob;
  const { p, trajet, video } = C;
  video.srcObject?.getTracks().forEach(t => t.stop());
  if (C.fichier) URL.revokeObjectURL(video.src);
  C.verrou?.release?.().catch(() => {});
  if (C.geo != null) navigator.geolocation.clearWatch(C.geo);
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  removeEventListener("resize", disposer);
  document.removeEventListener("visibilitychange", visibilite);
  PROG.notifier = (texte, badge) => toast(texte, badge);
  C.racine.remove();
  document.body.classList.remove("sans-defilement");
  moteur.reinitialiser();
  const fin = Date.now(), secondes = (fin - trajet.debut) / 1000;
  const total = Object.values(trajet.elements).reduce((a, b) => a + b, 0);
  const apres = C.apresFermeture;
  C = null;
  if (secondes < 20 && !total) { apres(); return; }
  Object.assign(trajet, { fin, minutes: +(secondes / 60).toFixed(1) });
  p.trajets.unshift(trajet);
  for (const vieux of p.trajets.splice(30)) idbSupprimerPrefixe("photos", `${p.id}/${vieux.id}/`);
  p.stats.minutes += secondes / 60;
  evenement("trajet", secondes / 60);
  verifierBadges(p);
  sauver();
  resume(trajet, videoBlob, apres);
}

function resume(trajet, videoBlob, apres) {
  const distincts = Object.keys(trajet.elements);
  const fams = FAMILLES.filter(f => distincts.some(c => f.codes.includes(c))).length;
  const nouveaux = trajet.nouveaux.map(c => D.parCode[c]).filter(Boolean);
  const ext = videoBlob?.type.includes("mp4") ? "mp4" : "webm";
  const nomVideo = `trajet-${new Date(trajet.debut).toISOString().slice(0, 16).replace(/[:T]/g, "-")}.${ext}`;
  const corps = ouvrirFeuille("Trajet terminé", `
    <p class="doux">${duree((trajet.fin - trajet.debut) / 1000)} · ${distincts.length} élément${distincts.length > 1 ? "s" : ""} différent${distincts.length > 1 ? "s" : ""} · ${fams} famille${fams > 1 ? "s" : ""} · ${trajet.photos} photo${trajet.photos > 1 ? "s" : ""}</p>
    ${nouveaux.length ? `<h3>Nouveaux dans l'album</h3><div class="vignettes">${nouveaux.map(it => `<img src="${esc(icone(it))}" alt="${esc(it.nom)}" title="${esc(it.nom)}">`).join("")}</div>` : ""}
    ${distincts.length ? `<h3>Repérés pendant le trajet</h3><div class="vignettes">${distincts.map(c => D.parCode[c]).map(it => `<img src="${esc(icone(it))}" alt="${esc(it.nom)}" title="${esc(it.nom)}">`).join("")}</div>` : `<p class="vide">Aucun élément repéré cette fois.</p>`}
    ${videoBlob ? `<div class="duo"><a class="btn btn-plein" data-x="video" download="${nomVideo}">Enregistrer la vidéo</a><button class="btn" data-x="partager">Partager</button></div>` : ""}
    ${distincts.length ? `<button class="btn btn-plein btn-grand" data-x="quiz">Quiz du trajet</button>` : ""}
    <div class="duo"><button class="btn" data-x="voir">Voir le trajet</button><button class="btn" data-x="accueil">Accueil</button></div>`, { onFerme: apres });
  if (videoBlob) {
    const url = URL.createObjectURL(videoBlob);
    $("[data-x=video]", corps).href = url;
    $("[data-x=partager]", corps).onclick = async () => {
      const f = new File([videoBlob], nomVideo, { type: videoBlob.type });
      if (navigator.canShare?.({ files: [f] })) navigator.share({ files: [f], title: "Mon trajet" }).catch(() => {});
      else toast("Partage impossible ici : utilise « Enregistrer la vidéo »");
    };
  }
  corps.onclick = e => {
    const x = e.target.closest("[data-x]")?.dataset.x;
    if (!x || x === "video" || x === "partager") return;
    aller(x === "quiz" ? `#/quiz/trajet/${trajet.id}` : x === "voir" ? `#/trajet/${trajet.id}` : "#/");
  };
}

export const cameraOuverte = () => !!C;
export const sessionCamera = () => C;
