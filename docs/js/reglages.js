// Feuilles « Réglages » et « Profils » (ouvertes depuis l'accueil ou depuis la caméra).
import { APP, FAMILLES, FONDS } from "./contenu.js";
import { D, icone, itemsFamille } from "./donnees.js";
import { nbAlbum } from "./progression.js";
import { ajouterProfil, changerProfil, effacerHistorique, profil, profils, renommer, sauver, supprimerProfil } from "./stockage.js";
import { $, $$, ICONES, avatar, bascule, confirmer, demander, esc, ouvrirFeuille, fermerFeuille, toast } from "./ui.js";

export const EVENEMENTS = { profilChange: () => {}, reglagesChanges: () => {} };

const OPTIONS = [
  ["voix", "Annonce vocale", "Lit le nom de l'élément dès qu'il est confirmé."],
  ["vibration", "Vibration", ""],
  ["lireLimitations", "Lire les limitations", "Annonce « Limitation à 50 » au lieu du nom du panneau."],
  ["expliquer", "Expliquer la règle à voix haute", "Après le nom : ce qu'il faut faire."],
  ["photos", "Photo de chaque élément repéré", "Une photo de la route à chaque annonce, rangée dans « Mes trajets » sur l'accueil. Reste sur le téléphone."],
  ["gps", "Position GPS des photos", "Pour retrouver l'endroit exact sur une carte (caméra seulement). Le téléphone demande l'autorisation."],
  ["video", "Enregistrer chaque trajet en vidéo", "Démarre avec la caméra, cadres et panneau annoncé incrustés. À la fin du trajet : enregistrer ou partager. Le bouton rond en haut lance ou arrête aussi l'enregistrement."],
  ["paysage", "Écran en paysage pendant la conduite", "L'écran passe en paysage au lancement : la route à gauche, le panneau annoncé à droite."],
  ["sons", "Effets sonores", "Petits sons des quiz, de l'album et de la quête."],
];
const QUALITES = [["rapide", "Rapide"], ["equilibree", "Équilibrée"], ["fine", "Fine"]];

function nbActifs(p) {
  const r = p.reglages;
  return D.items.filter(it => (it.famille === "perso" || r.familles[it.famille] !== false) && !r.exclus.includes(it.code)).length;
}

export function appliquerTheme(p = profil()) { document.documentElement.dataset.fond = p.fond || "sauge"; }

async function reconfigurer() {
  const { configurerMoteur } = await import("./camera.js");
  configurerMoteur();
  EVENEMENTS.reglagesChanges();
}

export function ouvrirReglages({ depuisCamera = false } = {}) {
  const corps = ouvrirFeuille("Réglages", "", { onFerme: () => EVENEMENTS.reglagesChanges() });
  dessiner(corps, depuisCamera);
  corps.addEventListener("change", async e => {
    const p = profil(), r = p.reglages, cible = e.target;
    if (cible.dataset.reglage) { r[cible.dataset.reglage] = cible.checked; sauver(); if (cible.dataset.reglage === "voix" && cible.checked && "speechSynthesis" in window) speechSynthesis.speak(Object.assign(new SpeechSynthesisUtterance("Annonces activées"), { lang: "fr-FR" })); }
    if (cible.dataset.famille) { r.familles[cible.dataset.famille] = cible.checked; sauver(); majCompte(corps); reconfigurer(); }
    if (cible.dataset.element) {
      const c = cible.dataset.element;
      r.exclus = cible.checked ? r.exclus.filter(x => x !== c) : [...new Set([...r.exclus, c])];
      sauver(); majCompte(corps); reconfigurer();
    }
    if (cible.dataset.reglage === "debug") reconfigurer();
  });
  corps.addEventListener("click", async e => {
    const b = e.target.closest("[data-r]");
    if (!b) return;
    const p = profil(), r = p.reglages, a = b.dataset.r;
    if (a === "fond") { p.fond = b.dataset.v; sauver(); appliquerTheme(p); $$(".nuancier button", corps).forEach(x => x.setAttribute("aria-pressed", x === b)); EVENEMENTS.reglagesChanges(); }
    if (a === "qualite") { r.qualite = b.dataset.v; sauver(); $$(".segments [data-r=qualite]", corps).forEach(x => x.setAttribute("aria-pressed", x === b)); reconfigurer(); }
    if (a === "profils") ouvrirProfils();
    if (a === "tout") { r.familles = {}; r.exclus = []; sauver(); dessiner(corps, depuisCamera); reconfigurer(); }
    if (a === "rien") { r.familles = Object.fromEntries(FAMILLES.map(f => [f.id, false])); sauver(); dessiner(corps, depuisCamera); reconfigurer(); }
    if (a === "effacer" && await confirmer("Effacer l'historique ?", "Les trajets et leurs photos de ce profil seront supprimés. L'album, les quiz et la quête sont gardés.", { oui: "Effacer", danger: true })) {
      await effacerHistorique(p); toast("Historique effacé"); EVENEMENTS.reglagesChanges();
    }
  });
  corps.addEventListener("input", e => { if (e.target.matches("[data-recherche]")) filtrer(corps, e.target.value); });
}

function dessiner(corps, depuisCamera) {
  const p = profil(), r = p.reglages;
  const qualite = r.qualite === "auto" ? (window.__moteurGPU ? "fine" : "equilibree") : r.qualite;
  const sections = [["Panneaux", FAMILLES.filter(f => !["marquages", "feux"].includes(f.id))], ["Feux et usagers", FAMILLES.filter(f => f.id === "feux")], ["Marquages au sol", FAMILLES.filter(f => f.id === "marquages")]];
  corps.innerHTML = `
    <div class="reglage" style="border-top:0"><div><h3>Profil</h3><div class="ligne" style="margin-top:8px">${avatar(p, "petit")}<b>${esc(p.nom)}</b></div></div>
      <button class="btn" style="width:auto" data-r="profils">Changer</button></div>
    <div class="ligne-sep"><h3 style="font-family:var(--corps);font-size:1.18rem;margin-bottom:14px">Couleur du fond</h3>
      <div class="nuancier">${FONDS.map(f => `<button data-r="fond" data-v="${f.id}" aria-pressed="${p.fond === f.id}"><i style="background:${{ auto: "linear-gradient(135deg,#f3f4f6 50%,#12163a 50%)", blanc: "#fff", creme: "#f4ecda", sauge: "#e3eadf", nuit: "#12163a" }[f.id]}"></i>${f.nom}</button>`).join("")}</div></div>
    ${OPTIONS.map(([id, titre, texte]) => `<div class="reglage"><div><h3>${titre}</h3>${texte ? `<p>${texte}</p>` : ""}</div>${bascule(id, r[id])}</div>`).join("")}
    <div class="ligne-sep"><div class="carte-titre"><div><h3 style="font-family:var(--corps);font-size:1.18rem">Ce que l'appli détecte</h3>
      <p class="doux">Coupe une famille entière, ou un seul élément avec « Choisir parmi… » ou la recherche. Ce qui est coupé n'est ni encadré ni annoncé.</p></div>
      <b class="compte-actifs" style="font-size:1.3rem;text-align:center;min-width:3.5em"></b></div></div>
    <div class="duo"><button class="btn" data-r="tout">Tout activer</button><button class="btn" data-r="rien">Tout couper</button></div>
    <div class="recherche">${ICONES.recherche}<input class="champ" data-recherche placeholder="Chercher un élément : piéton, stop, feu…" aria-label="Chercher un élément"></div>
    <div class="resultats-recherche cache"></div>
    <div class="filtres">${sections.map(([titre, fams]) => `<h4 class="doux" style="font-family:var(--corps);margin-top:10px">${titre}</h4>${fams.map(f => ligneFamille(f, r)).join("")}`).join("")}</div>
    <div class="ligne-sep"><h3 style="font-family:var(--corps);font-size:1.18rem;margin-bottom:12px">Qualité d'analyse</h3>
      <div class="segments">${QUALITES.map(([id, nom]) => `<button data-r="qualite" data-v="${id}" aria-pressed="${qualite === id}">${nom}</button>`).join("")}</div>
      <p class="doux petit" style="margin-top:8px">Rapide : plus d'images par seconde. Fine : panneaux lointains mieux vus.</p></div>
    <div class="reglage"><div><h3>Détecteur</h3><p class="etat-detecteur">${esc(window.__etatDetecteur || "Pas encore chargé : il démarre avec la caméra.")}</p></div></div>
    <div class="reglage"><div><h3>Afficher les zones testées</h3><p>Cadres violets de toutes les détections brutes, avant confirmation : pour régler l'appli.</p></div>${bascule("debug", r.debug)}</div>
    <button class="btn" data-r="effacer">Effacer l'historique</button>
    <p class="credits">${esc(APP.nom)} ${APP.version}. Détection : YOLOv5 © Ultralytics, licence AGPL-3.0, réentraîné pour les panneaux et marquages français ;
      exécuté par ONNX Runtime Web © Microsoft, licence MIT. Images d'entraînement : comma10k, licence MIT. Polices Bricolage Grotesque et Overpass, licence OFL.
      <a href="${APP.depot}" target="_blank" rel="noopener">Code source (licence AGPL-3.0)</a>.
      Outil d'aide pédagogique : il ne remplace ni ton attention ni la signalisation réelle.${depuisCamera ? "" : ""}</p>`;
  majCompte(corps);
}

function ligneFamille(f, r) {
  const items = itemsFamille(f.id);
  return `<div class="famille-filtre"><img src="${esc(icone(D.parCode[f.icone]))}" alt=""><div><b>${esc(f.nom)}</b><span class="doux">${items.length} élément${items.length > 1 ? "s" : ""}</span></div>
    <label class="bascule"><input type="checkbox" data-famille="${f.id}" ${r.familles[f.id] !== false ? "checked" : ""} aria-label="${esc(f.nom)}"><span></span></label>
    <details><summary>Choisir parmi les ${items.length} ${ICONES.chevron.replace("<svg", '<svg class="chevron"')}</summary>${items.map(it => ligneElement(it, r)).join("")}</details></div>`;
}
const ligneElement = (it, r) => `<div class="element-filtre"><img src="${esc(icone(it))}" alt=""><span>${esc(it.nom)}</span>
  <label class="bascule"><input type="checkbox" data-element="${esc(it.code)}" ${r.exclus.includes(it.code) ? "" : "checked"} aria-label="${esc(it.nom)}"><span></span></label></div>`;

function majCompte(corps) { const z = $(".compte-actifs", corps); if (z) z.textContent = `${nbActifs(profil())} sur ${D.items.length}`; }

function filtrer(corps, q) {
  const z = $(".resultats-recherche", corps), filtres = $(".filtres", corps);
  const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  q = norm(q.trim());
  if (!q) { z.classList.add("cache"); filtres.classList.remove("cache"); return; }
  const r = profil().reglages, trouves = D.items.filter(it => norm(`${it.nom} ${it.affiche} ${it.explication}`).includes(q)).slice(0, 30);
  z.innerHTML = trouves.length ? trouves.map(it => ligneElement(it, r)).join("") : `<p class="vide">Aucun élément ne correspond.</p>`;
  z.classList.remove("cache"); filtres.classList.add("cache");
}

// ---------- profils ----------
export function ouvrirProfils() {
  const corps = ouvrirFeuille("Profils", "");
  const dessinerProfils = () => {
    const actif = profil(), liste = profils();
    corps.innerHTML = `<div class="liste-lignes">${liste.map(x => `<div class="element-liste" style="cursor:pointer" data-p="ouvrir" data-id="${x.id}">
        <div class="ligne">${avatar(x, x.id === actif.id ? "grand" : "")}<div><b>${esc(x.nom)}</b>
        <div class="doux">${x.id === actif.id ? "Profil ouvert, " : ""}${x.trajets.length} trajet${x.trajets.length > 1 ? "s" : ""}, ${nbAlbum(x)} élément${nbAlbum(x) > 1 ? "s" : ""} dans l'album, ${x.xp} XP</div></div></div>
        ${x.id === actif.id ? `<button class="btn" style="width:auto;min-height:48px" data-p="renommer">Renommer</button>` : `<button class="btn" style="width:auto;min-height:48px" data-p="ouvrir" data-id="${x.id}">Ouvrir</button>`}</div>`).join("")}</div>
      <button class="btn btn-plein btn-grand" data-p="ajouter">Ajouter un profil</button>
      <p class="doux">Chaque profil garde ses réglages, la couleur du fond, ses trajets et photos, son album, ses quiz, « Mes panneaux » et ses résultats d'examens.
        Les séries de code importées sont communes à tous. Tout reste sur ce téléphone.</p>
      ${liste.length > 1 ? `<button class="btn btn-danger" data-p="supprimer">Supprimer « ${esc(actif.nom)} »</button>` : ""}`;
  };
  dessinerProfils();
  corps.onclick = async e => {
    const b = e.target.closest("[data-p]");
    if (!b) return;
    const a = b.dataset.p;
    if (a === "renommer") { e.stopPropagation(); const nom = await demander("Nouveau nom du profil", profil().nom); if (nom) { renommer(profil().id, nom); dessinerProfils(); EVENEMENTS.profilChange(); } return; }
    if (a === "ouvrir" && b.dataset.id !== profil().id) { changerProfil(b.dataset.id); appliquerTheme(); fermerFeuille(); EVENEMENTS.profilChange(); toast(`Profil ouvert : ${profil().nom}`); }
    if (a === "ajouter") { const nom = await demander("Nom du nouveau profil", "", { placeholder: "Prénom" }); if (nom) { ajouterProfil(nom); appliquerTheme(); fermerFeuille(); EVENEMENTS.profilChange(); toast(`Profil créé : ${nom}`); } }
    if (a === "supprimer" && await confirmer(`Supprimer « ${profil().nom} » ?`, "Son album, ses trajets, ses photos et sa progression seront effacés de ce téléphone.", { oui: "Supprimer", danger: true })) {
      await supprimerProfil(profil().id); appliquerTheme(); fermerFeuille(); EVENEMENTS.profilChange();
    }
  };
}
