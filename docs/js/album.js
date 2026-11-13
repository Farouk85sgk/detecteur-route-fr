// Album : tout ce que l'appli reconnaît, rangé par famille ; ce qui a été repéré sur la route est en couleur.
// Les panneaux que la caméra ne sait pas reconnaître ont seulement leur fiche (toujours visible, hors compteur).
// Fiche d'un élément : sens, bon réflexe, forme de la famille, ta photo.
import { FAMILLES } from "./contenu.js";
import { D, detectables, famille, icone, itemsFamille } from "./donnees.js";
import { nbAlbum, vuFamille } from "./progression.js";
import { aller } from "./nav.js";
import { idbLire, profil, sauver } from "./stockage.js";
import { ICONES, dateCourte, esc, ouvrirFeuille, toast } from "./ui.js";

const caseHtml = (it, p) => {
  const vu = p.album[it.code];
  if (!it.detecte && !vu) return `<button class="case fiche" data-fiche="${esc(it.code)}" aria-label="${esc(it.nom)} (fiche)"><img src="${esc(icone(it))}" alt="" loading="lazy"><span>${esc(it.nom)}</span></button>`;
  return `<button class="case ${vu ? "" : "inconnue"}" data-fiche="${esc(it.code)}" aria-label="${vu ? esc(it.nom) : "Élément pas encore repéré"}">
    <img src="${esc(icone(it))}" alt="" loading="lazy"><span>${vu ? esc(it.nom) : "???"}</span>${vu?.photo ? '<i class="photo-mini" title="Photo"></i>' : ""}</button>`;
};

export function pageAlbum(racine) {
  const p = profil(), total = D.nbDetectables, n = Math.min(nbAlbum(p), total), circ = 2 * Math.PI * 64;
  const persos = D.items.filter(it => it.famille === "perso");
  racine.innerHTML = `<div class="page"><div class="entete"><h1>Album</h1><button class="btn-rond" data-nav="#/" aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="contenu">
      <div class="anneau-ligne"><div class="anneau"><svg viewBox="0 0 150 150"><circle cx="75" cy="75" r="64" stroke="var(--bord)" stroke-width="14" fill="none"/>
        ${n ? `<circle cx="75" cy="75" r="64" stroke="var(--jaune)" stroke-width="14" fill="none" stroke-linecap="round" stroke-dasharray="${(circ * n / total).toFixed(1)} ${circ.toFixed(1)}"/>` : ""}</svg>
        <div><b>${n}</b><small>/${total}</small></div></div>
        <p class="doux">Chaque panneau, feu, marquage ou usager repéré pendant un trajet rejoint l'album. Touche une case pour voir sa fiche, même si tu ne l'as pas encore croisé.
          Les cases au cadre pointillé sont de simples fiches : la caméra ne sait pas encore reconnaître ces éléments.</p></div>
      ${FAMILLES.map(f => {
        const items = itemsFamille(f.id), nd = detectables(f.id).length, vus = Math.min(vuFamille(p, f.id), nd);
        return `<section class="section-album"><h2>${esc(f.nom)} <small>${vus}/${nd}</small></h2><div class="jauge"><i style="width:${nd ? 100 * vus / nd : 0}%"></i></div>
          <div class="grille-album">${items.map(it => caseHtml(it, p)).join("")}</div></section>`;
      }).join("")}
      ${persos.length ? `<section class="section-album"><h2>Mes panneaux <small>${persos.length}</small></h2><div class="jauge"><i style="width:100%"></i></div>
        <div class="grille-album">${persos.map(it => caseHtml(it, p)).join("")}</div></section>` : ""}
    </div></div>`;
  racine.onclick = e => { const b = e.target.closest("[data-fiche]"); if (b) ouvrirFiche(b.dataset.fiche); };
}

// corriger : fonction appelée par « Ce n'est pas ce panneau » (fiche ouverte depuis l'image en pause de la caméra)
export async function ouvrirFiche(code, { corriger = null } = {}) {
  const it = D.parCode[code];
  if (!it) return;
  const p = profil(), a = p.album[code], f = famille(it.famille);
  const quoi = it.groupe === "m" ? "ce marquage" : it.groupe === "s" ? "ce panneau" : "cet élément";
  // toute la famille peut être coupée dans les réglages : l'élément n'est alors pas annoncé, quel que soit son propre réglage
  const familleCoupee = it.famille !== "perso" && p.reglages.familles[it.famille] === false;
  const enDetection = !!document.querySelector(".camera");  // fiche ouverte par-dessus l'écran de détection
  const corps = ouvrirFeuille(it.nom, `
    <div class="fiche-tete"><img src="${esc(icone(it))}" alt=""><div><p class="doux">${esc(f?.nom || "Mes panneaux")}</p>
      <p style="margin:8px 0"><span class="code-badge">${esc(it.etiquette)}</span></p>
      <p class="doux">${a ? `Repéré ${a.vu} fois, la première fois le ${dateCourte(a.premier).toLowerCase()}` : it.detecte ? "Pas encore repéré sur la route" : `Fiche : la caméra ne reconnaît pas encore ce ${it.groupe === "m" ? "marquage" : "panneau"}`}</p></div></div>
    ${corriger ? `<button class="btn" data-corriger>Ce n'est pas ce panneau : le corriger</button>` : ""}
    <div class="fiche-bloc"><h4>Ce qu'il signifie</h4><p>${esc(it.explication)}</p></div>
    ${it.reflexe && it.reflexe !== it.explication ? `<div class="fiche-bloc"><h4>Bon réflexe</h4><p>${esc(it.reflexe)}</p></div>` : ""}
    ${f ? `<div class="fiche-bloc"><h4>Le reconnaître</h4><p>${esc(f.forme)}</p></div>` : ""}
    <div class="photo-fiche"></div>
    ${it.detecte || it.famille === "perso" ? `<div class="reglage fiche-annonce"><div><h3>L'annoncer pendant la détection</h3>
      <p>${familleCoupee ? `Toute la famille « ${esc(f?.nom || "")} » est coupée dans les Réglages : ${quoi} n'est pas annoncé.` : `Coupé : ${quoi} n'est plus ni encadré ni annoncé. À couper s'il est annoncé à tort.`}</p></div>
      <label class="bascule"><input type="checkbox" data-annoncer ${p.reglages.exclus.includes(code) || familleCoupee ? "" : "checked"} ${familleCoupee ? "disabled" : ""} aria-label="Annoncer ${esc(it.nom)}"><span></span></label></div>` : ""}
    ${f && !enDetection ? `<button class="btn btn-plein" data-quiz="${f.id}">S'entraîner : ${esc(f.nom)}</button>` : ""}`);
  corps.onclick = e => {
    const b = e.target.closest("[data-quiz]");
    if (b) aller(`#/quiz/famille/${b.dataset.quiz}`);
    if (e.target.closest("[data-corriger]")) corriger();
  };
  corps.onchange = async e => {
    if (!e.target.matches("[data-annoncer]")) return;
    const r = p.reglages;
    r.exclus = e.target.checked ? r.exclus.filter(c => c !== code) : [...new Set([...r.exclus, code])];
    sauver();
    (await import("./camera.js")).configurerMoteur();
    toast(e.target.checked ? `${it.nom} : de nouveau annoncé` : `${it.nom} : plus annoncé (à rétablir ici ou dans les Réglages)`);
  };
  if (a?.photo) {
    const ph = await idbLire("photos", a.photo);
    if (ph?.blob) corps.querySelector(".photo-fiche").innerHTML = `<div class="fiche-bloc"><h4>Ta photo</h4><img class="fiche-photo" src="${URL.createObjectURL(ph.blob)}" alt="Photo de ${esc(it.nom)}"></div>`;
  }
}
