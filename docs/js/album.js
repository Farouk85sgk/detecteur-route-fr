// Album : tout ce que l'appli reconnaît, rangé par famille ; ce qui a été repéré sur la route est en couleur.
// Fiche d'un élément : sens, bon réflexe, forme de la famille, ta photo.
import { FAMILLES } from "./contenu.js";
import { D, famille, icone, itemsFamille } from "./donnees.js";
import { nbAlbum, vuFamille } from "./progression.js";
import { aller } from "./nav.js";
import { idbLire, profil } from "./stockage.js";
import { ICONES, dateCourte, esc, ouvrirFeuille } from "./ui.js";

const caseHtml = (it, p) => {
  const vu = p.album[it.code];
  return `<button class="case ${vu ? "" : "inconnue"}" data-fiche="${esc(it.code)}" aria-label="${vu ? esc(it.nom) : "Élément pas encore repéré"}">
    <img src="${esc(icone(it))}" alt="" loading="lazy"><span>${vu ? esc(it.nom) : "???"}</span>${vu?.photo ? '<i class="photo-mini" title="Photo"></i>' : ""}</button>`;
};

export function pageAlbum(racine) {
  const p = profil(), total = D.nbOfficiels, n = nbAlbum(p), circ = 2 * Math.PI * 64;
  const persos = D.items.filter(it => it.famille === "perso");
  racine.innerHTML = `<div class="page"><div class="entete"><h1>Album</h1><button class="btn-rond" data-nav="#/" aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="contenu">
      <div class="anneau-ligne"><div class="anneau"><svg viewBox="0 0 150 150"><circle cx="75" cy="75" r="64" stroke="var(--bord)" stroke-width="14" fill="none"/>
        ${n ? `<circle cx="75" cy="75" r="64" stroke="var(--jaune)" stroke-width="14" fill="none" stroke-linecap="round" stroke-dasharray="${(circ * n / total).toFixed(1)} ${circ.toFixed(1)}"/>` : ""}</svg>
        <div><b>${n}</b><small>/${total}</small></div></div>
        <p class="doux">Chaque panneau, feu, marquage ou usager repéré pendant un trajet rejoint l'album. Touche une case pour voir sa fiche, même si tu ne l'as pas encore croisé.</p></div>
      ${FAMILLES.map(f => {
        const items = itemsFamille(f.id), vus = vuFamille(p, f.id);
        return `<section class="section-album"><h2>${esc(f.nom)} <small>${vus}/${items.length}</small></h2><div class="jauge"><i style="width:${100 * vus / items.length}%"></i></div>
          <div class="grille-album">${items.map(it => caseHtml(it, p)).join("")}</div></section>`;
      }).join("")}
      ${persos.length ? `<section class="section-album"><h2>Mes panneaux <small>${persos.length}</small></h2><div class="jauge"><i style="width:100%"></i></div>
        <div class="grille-album">${persos.map(it => caseHtml(it, p)).join("")}</div></section>` : ""}
    </div></div>`;
  racine.onclick = e => { const b = e.target.closest("[data-fiche]"); if (b) ouvrirFiche(b.dataset.fiche); };
}

export async function ouvrirFiche(code) {
  const it = D.parCode[code];
  if (!it) return;
  const p = profil(), a = p.album[code], f = famille(it.famille);
  const corps = ouvrirFeuille(it.nom, `
    <div class="fiche-tete"><img src="${esc(icone(it))}" alt=""><div><p class="doux">${esc(f?.nom || "Mes panneaux")}</p>
      <p style="margin:8px 0"><span class="code-badge">${esc(it.etiquette)}</span></p>
      <p class="doux">${a ? `Repéré ${a.vu} fois, la première fois le ${dateCourte(a.premier).toLowerCase()}` : "Pas encore repéré sur la route"}</p></div></div>
    <div class="fiche-bloc"><h4>Ce qu'il signifie</h4><p>${esc(it.explication)}</p></div>
    ${it.reflexe && it.reflexe !== it.explication ? `<div class="fiche-bloc"><h4>Bon réflexe</h4><p>${esc(it.reflexe)}</p></div>` : ""}
    ${f ? `<div class="fiche-bloc"><h4>Le reconnaître</h4><p>${esc(f.forme)}</p></div>` : ""}
    <div class="photo-fiche"></div>
    ${f ? `<button class="btn btn-plein" data-quiz="${f.id}">S'entraîner : ${esc(f.nom)}</button>` : ""}`);
  corps.onclick = e => { const b = e.target.closest("[data-quiz]"); if (b) aller(`#/quiz/famille/${b.dataset.quiz}`); };
  if (a?.photo) {
    const ph = await idbLire("photos", a.photo);
    if (ph?.blob) corps.querySelector(".photo-fiche").innerHTML = `<div class="fiche-bloc"><h4>Ta photo</h4><img class="fiche-photo" src="${URL.createObjectURL(ph.blob)}" alt="Photo de ${esc(it.nom)}"></div>`;
  }
}
