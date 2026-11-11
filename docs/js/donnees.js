// Éléments connus de l'appli : le catalogue (catalogue.json, même ordre que route_fr/classes.py : panneaux puis
// marquages), les feux et usagers, puis les panneaux appris par l'utilisateur (« Mes panneaux », ajoutés au chargement
// du profil). Un élément du catalogue marqué detecte = false n'a qu'une fiche : les modèles ne le reconnaissent pas.
import { EXTRAS, FAMILLES, REFLEXES } from "./contenu.js";

export const D = { items: [], parCode: {}, nbModele: 0, nbOfficiels: 0, nbDetectables: 0, detecteur: [] };

export const COULEURS_CATEGORIE = {
  danger: "#dc2828", priorite: "#ffc800", interdiction: "#e63c3c", fin: "#969696", obligation: "#146ec8", zone: "#e6e6e6",
  indication: "#2a8cdc", service: "#3c5ac8", temporaire: "#ffd700", panonceau: "#ebebeb", balise: "#5aa0d2", marquage: "#50e650",
  feu: "#ffc61e", usager: "#f07d19", perso: "#8a3ffc",
};
const COULEURS_FEUX = { F_rouge: "#ff3b30", F_orange: "#ffb000", F_vert: "#27d36b" };

export async function chargerDonnees() {
  const catalogue = await (await fetch("catalogue.json")).json();
  D.detecteur = catalogue.detecteur;  // classes du réseau de détection : « panneau », les marquages, puis les classes techniques
  D.nbModele = catalogue.items.length;
  D.items = [...catalogue.items, ...EXTRAS.map(e => ({ vitesse: null, affiche: e.code, famille: "feux", detecte: true, reflexe: REFLEXES[e.code], ...e }))];
  D.nbOfficiels = D.items.length;
  D.items.forEach((it, i) => indexer(it, i));
  D.nbDetectables = D.items.filter(it => it.detecte).length;
  for (const f of FAMILLES) f.codes = D.items.filter(it => it.famille === f.id).map(it => it.code);
  const orphelins = D.items.filter(it => !FAMILLES.some(f => f.id === it.famille)).map(it => it.code);
  if (orphelins.length) console.warn("Éléments sans famille :", orphelins);
}

function indexer(it, i) {
  it.index = i;
  it.affiche ??= it.code;
  it.reflexe ||= it.explication;
  it.couleur = COULEURS_FEUX[it.code] || COULEURS_CATEGORIE[it.categorie] || "#fff";
  it.groupe = it.categorie === "marquage" ? "m" : it.categorie === "feu" ? "f" : it.categorie === "usager" ? "u" : "s";
  // étiquette affichée : code officiel des panneaux, sinon le type d'élément
  it.etiquette = it.categorie === "perso" ? "Mon panneau" : { m: "Marquage au sol", f: "Feu tricolore", u: "Usager de la route" }[it.groupe] || it.affiche;
  D.parCode[it.code] = it;
}

// Panneaux appris (« Mes panneaux ») : nouveaux éléments, ou correction d'un panneau connu
export function definirAppris(liste) {
  D.items.length = D.nbOfficiels;
  for (const k of Object.keys(D.parCode)) if (!D.items[D.parCode[k].index] || D.items[D.parCode[k].index].code !== k) delete D.parCode[k];
  for (const a of liste) {
    if (a.code && D.parCode[a.code]) continue;  // panneau connu : la reconnaissance renvoie directement sa classe
    const it = { code: `perso_${a.id}`, nom: a.nom, categorie: "perso", explication: a.explication || "Panneau appris à l'appli.", vitesse: null, voix: a.nom,
      famille: "perso", vignette: a.vignetteUrl, appris: a.id, detecte: true };
    indexer(it, D.items.length);
    D.items.push(it);
  }
}

export const icone = it => it?.vignette || `icones/${it?.code}.png`;
export const famille = id => FAMILLES.find(f => f.id === id);
export const itemsFamille = id => (famille(id)?.codes || []).map(c => D.parCode[c]).filter(Boolean);
export const detectables = id => itemsFamille(id).filter(it => it.detecte);  // ceux que la caméra peut reconnaître
export const officiels = () => D.items.slice(0, D.nbOfficiels);
export const estPanneau = it => it && it.groupe === "s";
