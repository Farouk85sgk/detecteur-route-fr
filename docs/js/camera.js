// Écran caméra : détection en direct (caméra ou vidéo), carte du dernier élément, historique, lecteur vidéo, pause
// avec zoom et toucher d'un panneau, annonces vocales, photos incrustées, vidéo du trajet, GPS, résumé du trajet.
import { APP, FAMILLES } from "./contenu.js";
import { D, icone } from "./donnees.js";
import { FINS_VITESSE, Moteur, TAILLES, LIGNES } from "./moteur.js";
import { evenement, noterAlbum, verifierBadges, verifierMystere, PROG } from "./progression.js";
import { aller } from "./nav.js";
import { idbMettre, idbSupprimerPrefixe, profil, sauver } from "./stockage.js";
import { $, ICONES, duree, el, esc, heure, ouvrirFeuille, son, tempsVideo, toast, vibrer } from "./ui.js";

export const moteur = new Moteur();
let C = null;  // session caméra en cours
let chargement = null;  // chargement des modèles en cours (un seul à la fois, même si l'écran est fermé puis rouvert)
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
    <div class="zoom-cam cache"><button class="cam-btn verre" data-a="zoommoins" aria-label="Dézoomer" disabled>−</button><span class="zoom-val verre" aria-live="polite">1×</span><button class="cam-btn verre" data-a="zoomplus" aria-label="Zoomer">+</button></div>
    <div class="cam-bas"><div class="astuce-cam cache">Zoom : pince ou double-touche. Touche un panneau pour lire sa fiche ; s'il n'est pas reconnu, touche-le pour dire ce que c'est.</div>
      <div class="cam-toasts" aria-live="polite"></div>
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
    dernier: {}, historique: [], file: [], zones: [], derniereCarte: null, dernierePhoto: 0, nPhoto: 0, pos: null, fps: 0, tPrec: performance.now(), lignes: {}, enregistreur: null,
  };
  PROG.notifier = message;
  D.items.forEach(it => imageDe(icone(it)));  // icônes en mémoire : affichage immédiat pendant la détection
  racine.addEventListener("click", clic);
  // une commande touchée (doigt, souris ou clavier) redevient nette : tant que le doigt est posé, puis encore 2,5 s
  const surCommande = e => e.target.closest?.(".cam-haut, .lecteur, .historique, .zoom-cam");
  racine.addEventListener("pointerdown", e => { if (C && surCommande(e)) { C.doigt = true; reveiller(); } });
  for (const ev of ["pointerup", "pointercancel"]) racine.addEventListener(ev, () => { if (C?.doigt) { C.doigt = false; reveiller(); } });
  for (const ev of ["input", "focusin", "keydown", "click"]) racine.addEventListener(ev, e => { if (surCommande(e)) reveiller(); });
  brancherZoom();
  addEventListener("resize", disposer);
  document.addEventListener("visibilitychange", visibilite);

  // Après chaque attente, on vérifie que cette session est toujours la session en cours : l'écran a pu être fermé (ou fermé
  // puis rouvert) pendant le chargement des modèles ou l'ouverture de la caméra.
  const moi = C;
  moteur.reinitialiser();
  try {
    if (!moteur.pret) await (chargement ??= moteur.charger({ backend: new URLSearchParams(location.search).get("backend"), progression: t => statut(t, "charge") }).finally(() => (chargement = null)));
    if (C !== moi) return;
    window.__moteurGPU = moteur.fournisseurs[0] === "webgpu";
    configurerMoteur(p);
    await demarrerSource();
    if (C !== moi) return;
    C.demarre = true;
    majVoile();
  } catch (e) {
    console.error(e);
    if (C !== moi) return;
    statut("Erreur", "erreur");
    $(".cam-bas", racine).prepend(el(`<div class="cam-carte" style="grid-template-columns:1fr"><div><h2>Impossible de démarrer</h2><p>${esc(messageErreur(e))}</p></div></div>`));
    return;
  }
  if (r.paysage) paysage();
  if ("wakeLock" in navigator) navigator.wakeLock.request("screen").then(w => { if (C === moi) C.verrou = w; else w.release?.().catch(() => {}); }).catch(() => {});
  if (r.gps && !fichier && "geolocation" in navigator)
    C.geo = navigator.geolocation.watchPosition(g => { if (C === moi) C.pos = { lat: +g.coords.latitude.toFixed(6), lon: +g.coords.longitude.toFixed(6) }; }, () => {}, { enableHighAccuracy: true, maximumAge: 5000 });
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
  const moi = C, { video, fichier } = C;
  if (fichier) {
    video.src = URL.createObjectURL(fichier);
    video.loop = false;
    await video.play();
    if (C !== moi) return;
    $(".lecteur", C.racine).classList.remove("cache");
    const plage = $(".lecteur input", C.racine);
    video.addEventListener("loadedmetadata", () => (plage.max = video.duration || 1));
    plage.max = video.duration || 1;
    plage.oninput = () => { video.currentTime = +plage.value; };
    // On se déplace dans la vidéo : le suivi repart de zéro (pistes, vitesse retenue, lignes) et « C.tour » change, pour qu'une
    // analyse encore en cours sur l'ancienne image soit jetée. En pause, la nouvelle image est analysée six fois : il faut
    // jusqu'à cinq vues pour confirmer une ligne, et les usagers ne sont cherchés qu'une image sur deux.
    video.addEventListener("seeked", () => { if (C !== moi) return; C.tour = (C.tour || 0) + 1; moteur.reinitialiser(); if (C.pause) C.aRevoir = 6; });
    video.addEventListener("ended", () => basculerPause(true));
    statut("Vidéo", "");
  } else {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 }, zoom: true } });
    const eteindre = () => stream.getTracks().forEach(t => t.stop());
    if (C !== moi) return eteindre();  // écran fermé pendant l'ouverture de la caméra : on l'éteint, sinon son voyant reste allumé
    video.srcObject = stream;
    await video.play();
    if (C !== moi) return eteindre();
    statut("Caméra", "");
    // zoom de l'objectif (la plupart des téléphones Android) : les panneaux lointains sont plus gros, donc mieux reconnus
    try {
      const piste = stream.getVideoTracks()[0], z = piste.getCapabilities?.().zoom;
      if (z && z.min > 0 && z.max > z.min) {  // (une plage qui part de 0 ne se lit pas comme un grossissement : on s'en passe)
        C.objectif = { piste, min: z.min, max: Math.min(z.max, z.min * 8), v: piste.getSettings?.().zoom || z.min };
        const voulu = C.p.reglages.zoomCamera || 1;
        if (voulu > 1.01) await objectif(z.min * voulu, false); else majZoom();
      }
    } catch (e) { console.warn("zoom de la caméra indisponible", e); if (C === moi) C.objectif = null; }
    if (C !== moi) return;
  }
  disposer();
}

function statut(texte, cls) {
  if (!C) return;
  const s = $(".statut", C.racine);
  s.className = `statut verre ${cls || ""}`;
  $("span", s).textContent = texte;
}

// ---------- disposition : la vidéo remplit l'écran (ou y tient entière si les proportions diffèrent trop) ----------
function disposer() {
  if (!C) return;
  const { video, calque, zoom } = C, vw = video.videoWidth, vh = video.videoHeight;
  if (!vw) return;
  const paysage = innerWidth > innerHeight && (innerWidth > 700 || innerHeight <= 540);  // écran large, ou téléphone couché
  C.racine.classList.toggle("paysage", paysage);
  const W = paysage ? innerWidth * 0.58 : innerWidth, H = innerHeight, couvre = Math.abs(Math.log((vw / vh) / (W / H))) < 0.35;
  const base = couvre ? Math.max(W / vw, H / vh) : Math.min(W / vw, H / vh), s = base * zoom.k;
  // Place laissée libre par les commandes : sous la barre du haut et au-dessus du bloc du bas (lecteur, derniers panneaux et
  // carte, comptée pour 180 points même quand elle n'est pas encore là : l'image ne saute pas à la première annonce).
  const T = $(".cam-haut", C.racine).getBoundingClientRect().bottom + 8, lecteur = $(".lecteur", C.racine), carte = $(".cam-carte", C.racine);
  let B = 0;
  if (paysage) B = lecteur.classList.contains("cache") ? 0 : H - lecteur.getBoundingClientRect().top + 8;
  else {
    const hauts = [lecteur, $(".historique", C.racine), carte].filter(e => !e.classList.contains("cache")).map(e => e.getBoundingClientRect().top);
    B = H - Math.min(...hauts) + 8 + (carte.classList.contains("cache") ? 180 : Math.max(0, 170 - carte.offsetHeight));
  }
  // Une image qui ne remplit pas l'écran (vidéo large sur téléphone debout) se place dans cette zone libre, pas sous les commandes.
  const dhBase = vh * base, cy = dhBase <= H - T - B ? T + (H - T - B) / 2 : Math.min(H / 2, T + dhBase / 2);
  // Téléphone couché : l'image dépasse de la zone vidéo des deux côtés, et le volet de droite en recouvrait le bord droit, là
  // où passent la plupart des panneaux. On la décale vers la gauche : 5 % seulement restent sous le volet (le bord gauche,
  // côté voie d'en face, sort un peu plus de l'écran).
  const dwBase = vw * base, bx = paysage && dwBase > W ? -Math.max(0, (dwBase - W) / 2 - 0.05 * dwBase) : 0;
  const dw = vw * s, dh = vh * s;
  if (zoom.k > 1.001) {  // rotation ou redimensionnement pendant la pause : les décalages d'avant sont ramenés dans les nouvelles bornes
    const mx = Math.max(0, (dw - W) / 2), haut = T + dh / 2 - cy, bas = H - B - dh / 2 - cy;
    zoom.x = Math.min(mx - bx, Math.max(-mx - bx, zoom.x));
    zoom.y = bas > haut ? 0 : Math.min(haut, Math.max(bas, zoom.y));
  }
  const ox = (W - dw) / 2 + bx + zoom.x, oy = cy - dh / 2 + zoom.y;
  Object.assign(video.style, { width: dw + "px", height: dh + "px", left: ox + "px", top: oy + "px" });
  // Le calque des cadres couvre l'écran, pas l'image agrandie : mêmes proportions en largeur et en hauteur à tout niveau de zoom
  // (un calque étiré avec l'image décalait les cadres dès qu'on zoomait), et des traits toujours nets.
  const dpr = devicePixelRatio || 1, cw = Math.round(innerWidth * dpr), ch = Math.round(H * dpr);
  Object.assign(calque.style, { width: innerWidth + "px", height: H + "px", left: "0px", top: "0px" });
  if (calque.width !== cw || calque.height !== ch) { calque.width = cw; calque.height = ch; }
  C.s = s; C.ox = ox; C.oy = oy; C.vw = vw; C.vh = vh; C.sBase = base; C.W = W; C.H = H; C.cy = cy; C.T = T; C.B = B; C.bx = bx;
  dessiner();
}

// ---------- boucle d'analyse ----------
async function boucle(moi = C) {
  if (!C || C !== moi || C.fini) return;  // (« moi » : la session qui a lancé cette boucle ; une autre a pu la remplacer)
  const { video } = C;
  // En pause, l'image arrêtée est analysée encore deux fois (C.aRevoir) : les cadres tombent juste sur ce qu'on voit, au lieu
  // de rester là où étaient les panneaux quelques images plus tôt.
  const fige = C.pause && C.aRevoir > 0 && !video.seeking;
  if ((!C.pause || fige) && !document.hidden && video.readyState >= 2 && video.videoWidth) {
    if (video.videoWidth !== C.vw || video.videoHeight !== C.vh) disposer();
    try {
      const tour = C.tour;
      const res = await moteur.analyser(video, video.videoWidth, video.videoHeight, { debug: C.p.reglages.debug, net: fige });
      if (C !== moi || C.fini) return;
      if (tour !== C.tour) {  // on s'est déplacé dans la vidéo pendant le calcul : ce résultat est celui d'une image qu'on ne voit plus
        moteur.reinitialiser();
        C.raf = setTimeout(() => requestAnimationFrame(() => boucle(moi)), 15);
        return;
      }
      if (fige) C.aRevoir--;
      C.brutes = res.brutes;
      for (const t of res.nouveaux) annoncer(t);
      majZones();  // après les annonces : une piste tout juste confirmée ne doit pas « rafraîchir » l'endroit d'un panneau plus ancien
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
  if (C === moi) C.raf = setTimeout(() => requestAnimationFrame(() => boucle(moi)), 15);
}

const visibilite = () => { if (C && !document.hidden) C.tPrec = performance.now(); };
const decrireMoteur = () => `Prêt (${moteur.fournisseurs[0] === "webgpu" ? "carte graphique" : `processeur, ${moteur.fils > 1 ? `${moteur.fils} fils de calcul` : "un seul fil de calcul"}`}, classifieur ${moteur.cls ? "actif" : "absent"}, `
  + `usagers ${moteur.usagers ? "actifs" : "inactifs"}${moteur.emp ? ", Mes panneaux actif" : ""}, ${Math.round(moteur.ms)} ms par image, ${C?.fps ? C.fps.toFixed(1) : "?"} images/s).`;

// pistes encadrées à l'écran : confirmées et vues à l'instant (en pause, une fois l'image arrêtée analysée : celles qu'on y a retrouvées)
function pistesVues() {
  const max = C.pause && !C.aRevoir ? 1 : 2;
  return moteur.pistes.filter(t => t.ok && t.misses <= max && D.items[moteur.classe(t)]);
}

// ---------- annonce d'un élément confirmé ----------
function annoncer(t, phrase = null) {
  const { p } = C, r = p.reglages, cls = moteur.classe(t), it = D.items[cls];
  if (!it) return;
  const maintenant = Date.now(), dernier = C.dernier[it.code] || 0;
  const pause = it.groupe === "u" || it.groupe === "f" ? 20000 : 8000;
  // une annonce refaite parce que le nom a changé (t.corrige) passe toujours : l'endroit retenu prend simplement le nouveau nom
  const correction = t.corrige;
  t.corrige = false;
  if (correction) { const z = C.zones.find(z => recouvrement(z.box, t.box) > 0.3); if (z) Object.assign(z, { code: it.code, box: t.box.slice(), vu: Date.now() }); }
  else if (!phrase && it.groupe === "s" && dejaLa(t, it)) return;
  const fete = r.recompenses !== false;  // réglage « Récompenses pendant la détection »
  PROG.silence = !fete;
  // Correction : cette piste avait été comptée sous un autre nom. On retire ce qu'elle avait compté (trajet, événement, album
  // si c'était sa seule vue) : un panneau lu 110 puis 130 n'est qu'un panneau, et le 110 n'a pas à rester dans le trajet.
  if (correction && t.compte) {
    const a = t.compte;
    if (C.trajet.elements[a.code] > 1) C.trajet.elements[a.code]--; else delete C.trajet.elements[a.code];
    const k = C.trajet.evenements.indexOf(a.evenement);
    if (k >= 0) C.trajet.evenements.splice(k, 1);
    if (a.neuf) { const j = C.trajet.nouveaux.lastIndexOf(a.code); if (j >= 0) C.trajet.nouveaux.splice(j, 1); }
    const fiche = p.album[a.code];
    if (fiche) { if (fiche.vu > 1) fiche.vu--; else if (a.neuf) delete p.album[a.code]; }
  }
  // Le même nom confirmé de nouveau dans les secondes qui suivent, c'est presque toujours le même panneau dont la piste s'est
  // perdue puis retrouvée : on ne le recompte pas (le trajet affichait « vu 4 fois » pour un seul panneau). Une correction
  // passe quand son nom n'est pas celui qui est affiché : sans cela la carte et la voix resteraient sur le mauvais panneau.
  if (!phrase && maintenant - dernier < pause && !(correction && C.historique[0] !== it.code)) return;
  // trajet, album, quêtes : chaque annonce compte
  const ev = { code: it.code, t: tempsTrajet(), pos: C.pos };
  let neuf = false;
  C.trajet.elements[it.code] = (C.trajet.elements[it.code] || 0) + 1;
  if (C.trajet.evenements.length < 400) C.trajet.evenements.push(ev);
  if (it.index < D.nbOfficiels) {
    neuf = noterAlbum(p, it.code);
    if (neuf) {
      C.trajet.nouveaux.push(it.code);
      if (fete) { message(`Nouveau dans l'album : ${it.nom}`, "+20 XP"); son("nouveau", r.sons); }
      evenement("nouveau");
    }
    if (!correction) evenement("repere");  // la quête « repérer » ne compte qu'une fois un panneau corrigé
    verifierMystere(p, it.code);
  }
  if (!phrase) t.compte = { code: it.code, evenement: ev, neuf };
  C.dernier[it.code] = maintenant;
  // Lignes au sol : elles bordent la voie en permanence et se confondent de loin. Elles s'affichent de chaque côté de
  // l'image (vote sur les dernières images) ; sans le réglage « Annoncer les lignes au sol », ni grande carte ni voix.
  if (LIGNES.test(it.code) && !r.lignesVoix) return;
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

// Objet fixe devant la caméra (autocollant du pare-brise, reflet, tableau de bord) pris pour un panneau : sa piste se perd et
// renaît au même endroit, et il serait annoncé sans fin. On retient l'endroit de chaque annonce, et on note tant qu'un
// panneau y est encore vu (majZones). Une nouvelle piste au même endroit n'est pas annoncée si l'endroit n'a pas été quitté :
// le même panneau y était encore il y a moins de 20 s, ou un panneau quelconque il y a moins de 3 s. Un panneau de la
// route, lui, traverse l'image et s'en va : l'endroit se libère, et le panneau suivant est annoncé normalement.
const aireBoite = b => Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);
const recouvrement = (a, b) => { const i = aireBoite([Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])]); return i / (aireBoite(a) + aireBoite(b) - i || 1); };
function dejaLa(t, it) {
  const maintenant = Date.now();
  C.zones = C.zones.filter(z => maintenant - z.vu < 60000);
  const z = C.zones.find(z => (z.code === it.code && maintenant - z.vu < 20000 && recouvrement(z.box, t.box) > 0.4) || (maintenant - z.vu < 3000 && recouvrement(z.box, t.box) > 0.6));
  if (z) { Object.assign(z, { code: it.code, box: t.box.slice(), vu: maintenant }); return true; }
  C.zones.push({ code: it.code, box: t.box.slice(), vu: maintenant });
  return false;
}
// après chaque image analysée : un endroit encore occupé par son panneau reste « vu »
function majZones() {
  if (!C.zones.length) return;
  const maintenant = Date.now();
  for (const t of moteur.pistes) {
    if (!t.ok || t.misses || t.groupe !== "s") continue;
    const code = D.items[moteur.classe(t)]?.code;
    for (const z of C.zones) if (z.code === code && recouvrement(z.box, t.box) > 0.4) z.vu = maintenant;
  }
}
const tempsTrajet = () => C.fichier ? +C.video.currentTime.toFixed(1) : Math.round((Date.now() - C.trajet.debut) / 1000);

function montrerCarte(it, t, forcer = true) {
  const carte = $(".cam-carte", C.racine);
  // un marquage au sol ne chasse pas un panneau, un feu ou un usager affiché depuis moins de 4 s
  if (!forcer && it.groupe === "m" && C.carteGroupe && C.carteGroupe !== "m" && Date.now() - C.derniereCarte < 4000) return;
  if (!carte.firstElementChild) carte.innerHTML = `<img alt=""><div><h2></h2><p></p><div class="meta"><span class="code-badge"></span><span></span></div></div>`;
  const img = carte.querySelector("img"), src = icone(it);
  // tant que le nouveau dessin n'est pas chargé, on cache l'ancien : jamais le dessin d'un panneau avec le nom d'un autre
  if (img.getAttribute("src") !== src) { img.style.visibility = "hidden"; img.onload = img.onerror = () => { img.style.visibility = ""; }; img.src = src; }
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
  const k = s * dpr, dx = C.ox * dpr, dy = C.oy * dpr;  // point (x, y) de la vidéo → point (x·k + dx, y·k + dy) du calque
  ctx.font = `700 ${Math.round(14 * dpr)}px Overpass, system-ui, sans-serif`;
  ctx.textBaseline = "middle";
  if (C.p.reglages.debug && C.brutes) {
    ctx.lineWidth = 1.5 * dpr; ctx.strokeStyle = "rgba(170,120,255,.9)";
    for (const d of C.brutes) ctx.strokeRect(d.box[0] * k + dx, d.box[1] * k + dy, (d.box[2] - d.box[0]) * k, (d.box[3] - d.box[1]) * k);
  }
  // largeur visible du calque : la zone vidéo, ou tout l'écran quand l'image agrandie passe sous le volet du mode couché
  const LW = (C.zoom.k > 1.001 ? innerWidth : C.W) * dpr;
  // (un cadre entièrement sorti de l'écran n'est pas dessiné : son étiquette, ramenée au bord, flotterait seule sur l'image)
  const vues = (C.cadres ? pistesVues() : []).filter(t => t.box[2] * k + dx > 0 && t.box[0] * k + dx < LW && t.box[3] * k + dy > 0 && t.box[1] * k + dy < calque.height);
  const boites = vues.map(t => t.box.map((v, i) => v * k + (i % 2 ? dy : dx)));
  for (const [i, t] of vues.entries()) {
    const it = D.items[moteur.classe(t)];
    const [x1, y1, x2, y2] = boites[i];
    ctx.lineWidth = (it.groupe === "m" ? 2 : 3) * dpr;
    ctx.strokeStyle = it.couleur;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x1, y1, x2 - x1, y2 - y1, 6 * dpr) : ctx.rect(x1, y1, x2 - x1, y2 - y1); ctx.stroke();
    const txt = etiquette(it, t), tw = ctx.measureText(txt).width + 14 * dpr, th = 24 * dpr;
    let tx = x1, ty = y1 - th - 3 * dpr > 0 ? y1 - th - 3 * dpr : y2 + 3 * dpr;
    // panneaux empilés sur un même mât : l'étiquette du dessous couvrirait le panneau du dessus ; elle passe alors sur le côté
    const gene = (x, y) => boites.some((b, j) => j !== i && x < b[2] && x + tw > b[0] && y < b[3] && y + th > b[1]);
    if (gene(tx, ty)) {
      const droite = x2 + 4 * dpr, gauche = x1 - tw - 4 * dpr, my = (y1 + y2 - th) / 2;
      if (droite + tw <= LW && !gene(droite, my)) { tx = droite; ty = my; }
      else if (gauche >= 0 && !gene(gauche, my)) { tx = gauche; ty = my; }
    }
    tx = Math.max(2 * dpr, Math.min(tx, LW - tw - 2 * dpr));  // l'étiquette reste entière à l'écran (les panneaux sont souvent au bord droit)
    ctx.fillStyle = it.couleur;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(tx, ty, tw, th, 8 * dpr) : ctx.rect(tx, ty, tw, th); ctx.fill();
    ctx.fillStyle = ["zone", "priorite", "marquage", "feu", "temporaire", "panonceau"].includes(it.categorie) ? "#111" : "#fff";
    ctx.fillText(txt, tx + 7 * dpr, ty + th / 2 + dpr);
  }
  // lignes de part et d'autre, vitesse en cours
  const lg = D.parCode[moteur.ligne("g")], ld = D.parCode[moteur.ligne("d")];
  const html = (lg ? `<div class="puce-ligne verre">◂ ${esc(lg.nom)}</div>` : "") + (ld ? `<div class="puce-ligne verre">${esc(ld.nom)} ▸</div>` : "");
  const zl = $(".lignes", C.racine);
  if (zl.dataset.html !== html) { zl.innerHTML = html; zl.dataset.html = html; zl.style.display = "flex"; zl.style.flexDirection = "column"; zl.style.gap = "10px"; }
  const v = moteur.vitesse, zv = $(".vitesse-cam", C.racine);
  const val = v.valeur != null && !FINS_VITESSE.includes(v.code) ? String(v.valeur) : "";
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
    g.fillStyle = ["zone", "priorite", "marquage", "feu", "temporaire", "panonceau"].includes(it.categorie) ? "#111" : "#fff";
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
    message("Enregistrement de la vidéo", "●");
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
  if (a === "rec") { if (C.enregistreur) { const blob = await arreterEnregistrement(); if (blob) C.videoBlob = blob; message("Vidéo prête : elle sera proposée à la fin du trajet"); } else demarrerEnregistrement(); }
  if (a === "cadres") { C.cadres = !C.cadres; b.innerHTML = C.cadres ? ICONES.oeil : ICONES.oeilBarre; dessiner(); }
  if (a === "pause") basculerPause();
  if (a === "zoomplus" || a === "zoommoins") {
    const f = a === "zoomplus" ? 1.6 : 1 / 1.6;
    if (C.pause) zoomer(C.zoom.k * f); else if (C.objectif) objectif(C.objectif.v * (a === "zoomplus" ? 1.5 : 1 / 1.5));
  }
  if (a === "lecture") basculerPause();
  if (a === "recul") { C.video.currentTime = Math.max(0, C.video.currentTime - 5); moteur.reinitialiser(); }
  if (a === "avance") { C.video.currentTime = Math.min(C.video.duration || 0, C.video.currentTime + 5); moteur.reinitialiser(); }
  if (a === "histo") { const it = D.parCode[b.dataset.code]; montrerCarte(it); $(".cam-carte .meta span:last-child", C.racine).textContent = "vu pendant ce trajet"; }
  if (a === "fiche") { const { ouvrirFiche } = await import("./album.js"); ouvrirFiche(b.dataset.code); }
}

function basculerPause(forcer = null) {
  // rien tant que la caméra ou la vidéo n'a pas démarré : un toucher pendant le chargement laissait l'écran en fausse
  // pause (l'image défilait, mais plus rien n'était analysé)
  if (!C.demarre) return;
  C.pause = forcer ?? !C.pause;
  const { video } = C;
  if (C.pause) { video.pause(); C.aRevoir = 2; } else { if (C.fichier && video.ended) video.currentTime = 0; video.play().catch(() => {}); C.zoom = { k: 1, x: 0, y: 0 }; disposer(); }
  statut(C.pause ? "En pause" : C.fichier ? "Vidéo" : "Caméra", C.pause ? "pause" : "");
  $(".astuce-cam", C.racine).classList.toggle("cache", !C.pause);
  majZoom();  // on entre en pause (ou on en sort) toujours à l'image entière
  const bj = $("[data-a=lecture]", C.racine);
  if (bj) bj.innerHTML = C.pause ? ICONES.lecture : ICONES.pause;
  majVoile();
}

// Pendant la lecture (vidéo ou direct), les commandes posées sur l'image deviennent translucides pour laisser voir la route
// (classe « joue »). Elles redeviennent nettes en pause, et quelques secondes quand on en touche une (classe « reveil »).
function majVoile() {
  C.racine.classList.toggle("joue", !!C.demarre && !C.pause);
}
function reveiller() {
  if (!C) return;
  const { racine } = C;
  racine.classList.add("reveil");
  clearTimeout(C.tReveil);
  C.tReveil = setTimeout(() => racine.classList.remove("reveil"), C.doigt ? 15000 : 2500);
}

// Messages du trajet (« Nouveau dans l'album », badges, enregistrement). Un seul à la fois, pour ne pas couvrir la route : ils
// passent l'un après l'autre, chacun au moins 1,6 s (sinon, de deux messages envoyés ensemble, le premier ne serait jamais vu).
function message(texte, badge = "") {
  if (!C) return toast(texte, badge);
  const etroit = C.racine.classList.contains("paysage") && matchMedia("(max-height: 540px)").matches;
  C.file.push([etroit ? texte.replace(/^Nouveau dans l'album : /, "Nouveau : ") : texte, badge]);  // volet étroit : le nom d'abord
  if (C.file.length > 4) C.file.shift();
  if (!C.tFile) messageSuivant();
}
function messageSuivant() {
  if (!C) return;
  const m = C.file.shift();
  if (!m) { C.tFile = null; return; }
  const zone = $(".cam-toasts", C.racine);
  zone.replaceChildren();
  toast(m[0], m[1], zone);
  C.tFile = setTimeout(messageSuivant, 1600);
}

function majLecteur() {
  if (!C.fichier) return;
  const v = C.video;
  $(".lecteur .temps", C.racine).textContent = tempsVideo(v.currentTime || 0);
  const plage = $(".lecteur input", C.racine);
  if (document.activeElement !== plage) { plage.max = v.duration || 1; plage.value = v.currentTime || 0; }
}

// Pause : pincer, double-toucher, molette ou boutons + et − pour zoomer (le point visé reste sous le doigt), glisser pour se
// déplacer ; toucher un cadre ouvre sa fiche, toucher ailleurs propose d'apprendre le panneau qui s'y trouve.
// Sans point visé (boutons − et +), on agrandit autour du milieu de la partie d'image visible entre les commandes : une vidéo
// large sur téléphone debout occupe le haut de l'écran, et zoomer autour du milieu de l'écran la faisait fuir vers le bas.
function zoomer(k, sx = null, sy = null) {
  if (sx == null) {
    const x1 = Math.max(C.ox, 0), x2 = Math.min(C.ox + C.vw * C.s, C.W), y1 = Math.max(C.oy, C.T), y2 = Math.min(C.oy + C.vh * C.s, C.H - C.B);
    sx = x2 > x1 ? (x1 + x2) / 2 : C.W / 2;
    sy = y2 > y1 ? (y1 + y2) / 2 : C.cy;
  }
  const u = { x: (sx - C.ox) / C.s, y: (sy - C.oy) / C.s };
  placer(Math.min(6, Math.max(1, k)), u, sx, sy);
}
// met le point u de l'image (en pixels vidéo) sous le point (sx, sy) de l'écran, au zoom k, sans laisser l'image quitter l'écran
// Image agrandie : elle peut glisser jusqu'à amener son bord sous la barre du haut ou au-dessus du bloc du bas, pour que tout
// point de l'image puisse être sorti de sous les commandes. À l'image entière, elle reprend sa place.
function placer(k, u, sx, sy) {
  const s = C.sBase * k, dw = C.vw * s, dh = C.vh * s, mx = Math.max(0, (dw - C.W) / 2);
  const haut = C.T + dh / 2 - C.cy, bas = C.H - C.B - dh / 2 - C.cy;  // décalage vertical permis : de « bas » à « haut »
  C.zoom.k = k;
  C.zoom.x = k <= 1.001 ? 0 : Math.min(mx - C.bx, Math.max(-mx - C.bx, sx - u.x * s - (C.W - dw) / 2 - C.bx));
  C.zoom.y = k <= 1.001 || bas > haut ? 0 : Math.min(haut, Math.max(bas, sy - u.y * s - (C.cy - dh / 2)));
  $(".astuce-cam", C.racine).classList.add("cache");  // le geste est compris : l'astuce laisse voir l'image
  disposer(); majZoom();
}
// Boutons − et + : en pause ils agrandissent l'image arrêtée ; en direct, ils règlent le zoom de l'objectif (s'il existe).
function majZoom() {
  const o = C.objectif, k = C.pause ? C.zoom.k : o ? o.v / o.min : 1, max = C.pause ? 6 : o ? o.max / o.min : 1;
  $(".zoom-cam", C.racine).classList.toggle("cache", !C.pause && !o);
  $(".zoom-val", C.racine).textContent = `${(Math.round(k * 10) / 10).toString().replace(".", ",")}×`;
  $("[data-a=zoommoins]", C.racine).disabled = k <= 1.001;
  $("[data-a=zoomplus]", C.racine).disabled = k >= max - 0.001;
}
async function objectif(v, memoriser = true) {
  const moi = C, o = C.objectif, avant = o.v;
  o.v = Math.min(o.max, Math.max(o.min, v));
  majZoom();
  try { await o.piste.applyConstraints({ advanced: [{ zoom: o.v }] }); }
  catch (e) {  // la caméra a refusé : on affiche ce qu'elle fait vraiment, et on ne retient rien
    console.warn(e);
    o.v = o.piste.getSettings?.().zoom || avant;
    if (C === moi) majZoom();
    return;
  }
  if (memoriser && C === moi) { C.p.reglages.zoomCamera = Math.round(100 * o.v / o.min) / 100; sauver(); }
}
function brancherZoom() {
  const zone = $(".calque-touche", C.racine), doigts = new Map();
  let depart = null, dernierTap = { t: 0, x: 0, y: 0 }, attente = null;
  const pts = () => [...doigts.values()];
  const ecart = () => { const p = pts(); return p.length === 2 ? Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y) : 0; };
  const centre = () => { const p = pts(); return p.length ? { x: p.reduce((s, q) => s + q.x, 0) / p.length, y: p.reduce((s, q) => s + q.y, 0) / p.length } : { x: 0, y: 0 }; };
  const reperer = (t = 0, x0 = 0, y0 = 0) => { const c = centre(); depart = { k: C.zoom.k, d: ecart(), u: { x: (c.x - C.ox) / C.s, y: (c.y - C.oy) / C.s }, t, x0, y0, v: C.objectif?.v }; };
  let tObjectif = 0;
  zone.addEventListener("pointerdown", e => {
    clearTimeout(attente);  // un doigt se pose : le toucher simple en attente n'aura pas lieu (double toucher, ou glissement qui commence)
    zone.setPointerCapture?.(e.pointerId);  // souris : le relâchement revient à l'image même s'il a lieu ailleurs
    doigts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    reperer(Date.now(), e.clientX, e.clientY);
    // second toucher d'un double toucher : jugé à la pose du doigt, pas à son lever (un doigt un peu lent n'y change rien)
    depart.suite = doigts.size === 1 && C.pause && depart.t - dernierTap.t < 320 && Math.hypot(e.clientX - dernierTap.x, e.clientY - dernierTap.y) < 40;
  });
  zone.addEventListener("pointermove", e => {
    if (!doigts.has(e.pointerId) || !depart) return;
    doigts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (!C.pause) {  // en direct : pincer règle le zoom de l'objectif (au plus dix réglages par seconde)
      if (C.objectif && doigts.size === 2 && depart.d && Date.now() - tObjectif > 100) { tObjectif = Date.now(); objectif(depart.v * ecart() / depart.d); }
      return;
    }
    if (doigts.size === 1 && Math.hypot(e.clientX - depart.x0, e.clientY - depart.y0) < 6) return;  // doigt posé : pas encore un glissement
    const c = centre();
    placer(doigts.size === 2 && depart.d ? Math.min(6, Math.max(1, depart.k * ecart() / depart.d)) : C.zoom.k, depart.u, c.x, c.y);
  });
  const fin = e => {
    if (!C) return;
    const tap = depart && doigts.size === 1 && Date.now() - depart.t < 300 && Math.hypot(e.clientX - depart.x0, e.clientY - depart.y0) < 10, suite = depart?.suite;
    doigts.delete(e.pointerId);
    if (doigts.size) reperer();
    if (!tap) return;
    const x = e.clientX, y = e.clientY, double = C.pause && suite;
    clearTimeout(attente);
    dernierTap = { t: double ? 0 : Date.now(), x, y };
    if (double) zoomer(C.zoom.k > 1.3 ? 1 : 2.5, x, y);  // double toucher : zoom sur ce point, ou retour à l'image entière
    else if (!C.pause) toucher(x, y);
    else {  // on attend de savoir si un second toucher suit ; le point est retenu dans l'image, qui peut bouger d'ici là
      const moi = C, v = [(x - C.ox) / C.s, (y - C.oy) / C.s];
      attente = setTimeout(() => { if (C === moi && C.pause) toucher(v[0] * C.s + C.ox, v[1] * C.s + C.oy); }, 300);
    }
  };
  zone.addEventListener("pointerup", fin);
  zone.addEventListener("pointercancel", e => { doigts.delete(e.pointerId); if (doigts.size) reperer(); });
  zone.addEventListener("wheel", e => { if (!C.pause) return; e.preventDefault(); zoomer(C.zoom.k * (e.deltaY < 0 ? 1.25 : 0.8), e.clientX, e.clientY); }, { passive: false });
}
async function toucher(x, y) {
  if (!C.pause) return basculerPause(true);
  const vx = (x - C.ox) / C.s, vy = (y - C.oy) / C.s;
  if (vx < 0 || vy < 0 || vx > C.vw || vy > C.vh) return;
  const m = 6 / C.s;  // marge de doigt : 6 points d'écran autour du cadre
  const t = pistesVues().filter(t => vx >= t.box[0] - m && vx <= t.box[2] + m && vy >= t.box[1] - m && vy <= t.box[3] + m)
    .sort((a, b) => (a.box[2] - a.box[0]) - (b.box[2] - b.box[0]))[0];
  if (!t) return apprendreIci(null, [vx, vy]);
  const it = D.items[moteur.classe(t)], box = t.box.slice();
  montrerCarte(it, t);
  const { ouvrirFiche } = await import("./album.js");
  ouvrirFiche(it.code, { corriger: it.groupe === "s" ? () => apprendreIci(box, [vx, vy]) : null });
}
// « Mes panneaux » depuis l'image en pause : l'utilisateur dit ce qu'est le panneau touché (ou corrige celui que l'appli a nommé)
async function apprendreIci(box, point) {
  // on garde ce que l'écran montre (zoom compris) : le panneau visé y est assez grand pour être cherché et vérifié d'un coup d'œil
  const x0 = Math.max(0, -C.ox / C.s), y0 = Math.max(0, -C.oy / C.s), x1 = Math.min(C.vw, (innerWidth - C.ox) / C.s), y1 = Math.min(C.vh, (C.H - C.oy) / C.s);
  if (x1 - x0 < 8 || y1 - y0 < 8) return;
  const w = x1 - x0, h = y1 - y0, k = Math.min(1, 1600 / Math.max(w, h));
  const cv = Object.assign(document.createElement("canvas"), { width: Math.round(w * k), height: Math.round(h * k) });
  cv.getContext("2d").drawImage(C.video, x0, y0, w, h, 0, 0, cv.width, cv.height);
  const vers = (v, i) => (v - (i % 2 ? y0 : x0)) * k;
  const { apprendreImage } = await import("./mespanneaux.js");
  apprendreImage(cv, moteur, () => { if (C) { configurerMoteur(C.p); message("Appris : il sera reconnu sur la route", "✓"); } }, { point: point.map(vers), box: box?.map(vers) });
}

function paysage() {
  document.documentElement.requestFullscreen?.().then(() => screen.orientation?.lock?.("landscape")).catch(() => {});
}

// ---------- fin du trajet ----------
export async function terminer() {
  if (!C || C.fini) return;
  C.fini = true;
  clearTimeout(C.raf);
  clearTimeout(C.tFile);
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
  PROG.silence = false;
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
