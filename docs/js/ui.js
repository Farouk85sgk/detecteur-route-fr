// Petits outils d'interface : échappement, icônes, feuilles du bas, dialogues, toasts, sons, vibrations, dates.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

// ---------- icônes (SVG, couleur = currentColor sauf indication) ----------
const S = (body, vb = "0 0 24 24") => `<svg viewBox="${vb}" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
export const ICONES = {
  fermer: S('<path d="M5 5l14 14M19 5L5 19"/>'),
  chevron: S('<path d="M6 9l6 6 6-6"/>'),
  reglages: S('<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2.4"/><circle cx="10" cy="17" r="2.4"/>'),
  son: S('<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4.2 4.2 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11"/>'),
  sonCoupe: S('<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>'),
  oeil: S('<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>'),
  oeilBarre: S('<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><path d="M4 4l16 16"/>'),
  enregistrer: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2.2"/><circle cx="12" cy="12" r="5.4" fill="#e0262b"/></svg>',
  stop: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6.5" y="6.5" width="11" height="11" rx="2" fill="currentColor"/></svg>',
  lecture: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor"/></svg>',
  pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6.5" y="5" width="3.8" height="14" rx="1.2" fill="currentColor"/><rect x="13.7" y="5" width="3.8" height="14" rx="1.2" fill="currentColor"/></svg>',
  recul5: S('<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 4.5v3.6h3.6"/><text x="12" y="15.6" font-size="8.5" font-weight="800" text-anchor="middle" fill="currentColor" stroke="none">5</text>'),
  avance5: S('<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v3.6h-3.6"/><text x="12" y="15.6" font-size="8.5" font-weight="800" text-anchor="middle" fill="currentColor" stroke="none">5</text>'),
  coche: S('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
  plus: S('<path d="M12 5v14M5 12h14"/>'),
  recherche: S('<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/>'),
  camera: S('<path d="M4 8.5h3l1.8-2.5h6.4L17 8.5h3v10H4z"/><circle cx="12" cy="13.2" r="3.4"/>'),
  ecran: S('<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>'),
  partage: S('<path d="M12 15V4M7.5 8.5L12 4l4.5 4.5"/><path d="M5 13v6.5h14V13"/>'),
  poubelle: S('<path d="M5 7h14M10 7V4.5h4V7M7 7l1 12.5h8L17 7"/>'),
  retour: S('<path d="M15 5l-7 7 7 7"/>'),
  gemme: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M8 4h16l6 8-14 17L2 12z" fill="#ffc61e"/><path d="M2 12h28M8 4l4 8 4 17 4-17 4-8M12 12L16 4l4 8" fill="none" stroke="#c98a00" stroke-width="1.4" stroke-linejoin="round"/></svg>',
  flamme: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3c1 6 9 9 9 17a9 9 0 0 1-18 0c0-5 3-8 5-10 0 3 1 5 3 6-1-6 1-10 1-13z" fill="#f07d19"/><path d="M16 17c3 2 4 4 4 6a4 4 0 0 1-8 0c0-2 2-3 2-5 1 1 1 2 2 2 0-1 0-2 0-3z" fill="#ffd23f"/></svg>',
  flammeGrise: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3c1 6 9 9 9 17a9 9 0 0 1-18 0c0-5 3-8 5-10 0 3 1 5 3 6-1-6 1-10 1-13z" fill="#5d6488"/></svg>',
  coeur: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 28S3 20 3 11a6.5 6.5 0 0 1 13-1 6.5 6.5 0 0 1 13 1c0 9-13 17-13 17z" fill="#e0262b"/></svg>',
  coeurVide: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 28S3 20 3 11a6.5 6.5 0 0 1 13-1 6.5 6.5 0 0 1 13 1c0 9-13 17-13 17z" fill="none" stroke="#9aa0c0" stroke-width="2.4"/></svg>',
  cadenas: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10.5" width="14" height="10" rx="2.5" fill="#fff"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" fill="none" stroke="#fff" stroke-width="2.6"/></svg>',
  couronne: '<svg viewBox="0 0 48 40" aria-hidden="true"><path d="M4 30L2 8l12 10 10-16 10 16 12-10-2 22z" fill="#ffc61e"/><rect x="4" y="32" width="40" height="6" rx="2" fill="#ffc61e"/></svg>',
  coffre: '<svg viewBox="0 0 96 74" aria-hidden="true"><path d="M8 30a40 22 0 0 1 80 0v38H8z" fill="#5a4b3a"/><path d="M8 34h80" stroke="#8b7558" stroke-width="7"/><rect x="40" y="27" width="16" height="16" rx="3" fill="#8b7558"/><path d="M8 30a40 22 0 0 1 80 0" fill="none" stroke="#6b5a45" stroke-width="3"/></svg>',
  coffreOuvert: '<svg viewBox="0 0 96 74" aria-hidden="true"><path d="M8 38h80v30H8z" fill="#5a4b3a"/><path d="M14 36L20 6h56l6 30z" fill="#6b5a45"/><circle cx="48" cy="26" r="11" fill="#ffc61e"/><path d="M8 40h80" stroke="#8b7558" stroke-width="7"/></svg>',
  loupe: S('<circle cx="10.5" cy="10.5" r="6.2"/><path d="M15.2 15.2L20.5 20.5"/>'),
  potion: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.5 3h5M10 3v5.2L5.6 15.8a3.6 3.6 0 0 0 3.1 5.2h6.6a3.6 3.6 0 0 0 3.1-5.2L14 8.2V3" fill="none" stroke="#fff" stroke-width="2"/><path d="M7 15h10l1 2.4a2.2 2.2 0 0 1-2 3.1H8a2.2 2.2 0 0 1-2-3.1z" fill="#e0262b"/></svg>',
  bouclier: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.3-7.5 9.5-4.3-1.2-7.5-4.9-7.5-9.5V6z" fill="none" stroke="#fff" stroke-width="2"/><path d="M12 8v8M8 12h8" stroke="#f07d19" stroke-width="2.6" stroke-linecap="round"/></svg>',
  mystere: '<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 8L58 54H6z" fill="#545b80"/><text x="32" y="48" font-size="30" font-weight="800" text-anchor="middle" fill="#ffc61e" font-family="Bricolage, sans-serif">?</text></svg>',
};

export const LOGO = `<svg viewBox="0 0 100 100" aria-hidden="true"><rect x="15" y="15" width="70" height="70" rx="12" transform="rotate(45 50 50)" fill="#12163a"/><rect x="25" y="25" width="50" height="50" rx="7" transform="rotate(45 50 50)" fill="#ffc61e"/><path d="M36 51 L46 61 L65 40" stroke="#12163a" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

export const avatar = (p, cls = "") => `<span class="avatar ${cls}" style="background:${esc(p.couleur)}">${esc((p.nom || "?").trim().charAt(0).toUpperCase() || "?")}</span>`;
export const bascule = (id, on, attrs = "") => `<label class="bascule"><input type="checkbox" ${on ? "checked" : ""} data-reglage="${id}" ${attrs}><span></span></label>`;

// ---------- feuille du bas (une seule à la fois ; le bouton retour du téléphone la ferme) ----------
let feuille = null;
export function ouvrirFeuille(titre, corps, { onFerme, classe = "" } = {}) {
  fermerFeuille(true);
  const voile = el('<div class="voile"></div>');
  const f = el(`<section class="feuille ${classe}" role="dialog" aria-modal="true" aria-label="${esc(titre)}"><div class="poignee"></div>
    <div class="feuille-tete"><h2>${esc(titre)}</h2><button class="btn-rond contour" data-fermer aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="feuille-corps"></div></section>`);
  const zone = f.querySelector(".feuille-corps");
  if (typeof corps === "string") zone.innerHTML = corps; else zone.append(corps);
  document.body.append(voile, f);
  document.body.classList.add("sans-defilement");
  feuille = { voile, f, onFerme };
  voile.onclick = () => fermerFeuille();
  f.querySelector("[data-fermer]").onclick = () => fermerFeuille();
  history.pushState({ feuille: true }, "");
  return zone;
}
export function fermerFeuille(remplacee = false) {
  if (!feuille) return;
  const { voile, f, onFerme } = feuille;
  feuille = null;
  voile.remove(); f.remove();
  if (!document.querySelector(".camera:not(.cache)")) document.body.classList.remove("sans-defilement");
  if (!remplacee && history.state?.feuille) history.back();
  onFerme?.();
}
export const feuilleOuverte = () => !!feuille;
addEventListener("popstate", () => { if (feuille) { const f = feuille; feuille = null; f.voile.remove(); f.f.remove(); document.body.classList.remove("sans-defilement"); f.onFerme?.(); } });

// ---------- dialogues ----------
export function confirmer(titre, texte = "", { oui = "Oui", non = "Annuler", danger = false } = {}) {
  return new Promise(ok => {
    const d = el(`<div class="dialogue" role="alertdialog"><div><h3>${esc(titre)}</h3>${texte ? `<p class="doux">${esc(texte)}</p>` : ""}
      <div class="duo"><button class="btn" data-r="0">${esc(non)}</button><button class="btn btn-plein ${danger ? "btn-danger" : ""}" data-r="1">${esc(oui)}</button></div></div></div>`);
    d.onclick = e => { const b = e.target.closest("[data-r]"); if (b || e.target === d) { d.remove(); ok(b?.dataset.r === "1"); } };
    document.body.append(d);
  });
}
export function demander(titre, valeur = "", { placeholder = "", ok = "Valider" } = {}) {
  return new Promise(res => {
    const d = el(`<div class="dialogue" role="dialog"><div><h3>${esc(titre)}</h3><input class="champ" maxlength="40" value="${esc(valeur)}" placeholder="${esc(placeholder)}">
      <div class="duo"><button class="btn" data-r="0">Annuler</button><button class="btn btn-plein" data-r="1">${esc(ok)}</button></div></div></div>`);
    const input = d.querySelector("input");
    const fin = v => { d.remove(); res(v); };
    d.onclick = e => { const b = e.target.closest("[data-r]"); if (b) fin(b.dataset.r === "1" ? input.value.trim() : null); else if (e.target === d) fin(null); };
    input.onkeydown = e => { if (e.key === "Enter") fin(input.value.trim()); };
    document.body.append(d);
    setTimeout(() => input.focus(), 50);
  });
}

// ---------- toasts ----------
let zoneToasts = null;
export function toast(texte, badge = "", zone = null) {
  const cible = zone || (zoneToasts ??= document.body.appendChild(el('<div class="toasts" aria-live="polite"></div>')));
  const t = el(`<div class="toast"><span>${esc(texte)}</span>${badge ? `<span class="badge">${esc(badge)}</span>` : ""}</div>`);
  cible.append(t);
  setTimeout(() => t.remove(), 3700);
  while (cible.children.length > 3) cible.firstElementChild.remove();
}

// ---------- sons (synthétisés : aucun fichier à télécharger) et vibrations ----------
let audio = null;
const NOTES = {
  juste: [[660, .09], [880, .14]], faux: [[220, .16], [180, .2]], nouveau: [[523, .08], [659, .08], [784, .08], [1046, .2]],
  piece: [[988, .06], [1319, .16]], victoire: [[523, .12], [659, .12], [784, .12], [1046, .35]], clic: [[700, .04]], defaite: [[392, .18], [330, .18], [262, .4]],
};
export function son(nom, actif = true) {
  if (!actif || !NOTES[nom]) return;
  try {
    audio ??= new (window.AudioContext || window.webkitAudioContext)();
    let t = audio.currentTime + .02;
    for (const [f, d] of NOTES[nom]) {
      const o = audio.createOscillator(), g = audio.createGain();
      o.type = nom === "faux" || nom === "defaite" ? "triangle" : "sine";
      o.frequency.value = f;
      g.gain.setValueAtTime(.0001, t);
      g.gain.exponentialRampToValueAtTime(.22, t + .015);
      g.gain.exponentialRampToValueAtTime(.0001, t + d);
      o.connect(g).connect(audio.destination);
      o.start(t); o.stop(t + d + .02);
      t += d * .9;
    }
  } catch { /* pas de son disponible */ }
}
export const vibrer = (ms, actif = true) => { if (actif && navigator.vibrate) try { navigator.vibrate(ms); } catch { /* ignoré */ } };

// ---------- dates et durées en français ----------
const JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const maj = s => s.charAt(0).toUpperCase() + s.slice(1);
export const heure = ts => { const d = new Date(ts); return `${d.getHours()} h ${String(d.getMinutes()).padStart(2, "0")}`; };
export const dateCourte = ts => { const d = new Date(ts); return `${maj(JOURS[d.getDay()])} ${d.getDate()} ${MOIS[d.getMonth()]}`; };
export const dateLongue = ts => `${dateCourte(ts)} à ${heure(ts)}`;
export const jourCle = (ts = Date.now()) => { const d = new Date(ts); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
export function ilYa(ts) {
  const s = (Date.now() - ts) / 1000;
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.round(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.round(s / 3600)} h`;
  if (s < 172800) return "hier";
  return `le ${dateCourte(ts).toLowerCase()}`;
}
export const duree = s => s < 60 ? `${Math.max(1, Math.round(s))} s` : s < 3600 ? `${Math.round(s / 60)} min` : `${Math.floor(s / 3600)} h ${String(Math.round(s % 3600 / 60)).padStart(2, "0")}`;
export const tempsVideo = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

// Tirage pseudo-aléatoire reproductible (quêtes du jour, panneau mystère)
export function graine(texte) {
  let h = 2166136261;
  for (const c of texte) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => { h = Math.imul(h ^ (h >>> 15), 2246822507); h = Math.imul(h ^ (h >>> 13), 3266489909); return ((h ^= h >>> 16) >>> 0) / 4294967296; };
}
export const melanger = (t, r = Math.random) => { const a = t.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
