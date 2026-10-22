// Navigation entre les pages (adresse #/...) sans conflit avec les feuilles du bas, qui ajoutent une étape à
// l'historique pour que le bouton retour du téléphone les ferme.
import { fermerFeuille, feuilleOuverte } from "./ui.js";

export const NAV = { rendre: () => {} };

export function aller(hash) {
  if (feuilleOuverte()) { fermerFeuille(true); history.replaceState(null, "", hash); }
  else if (location.hash !== hash) history.pushState(null, "", hash);
  NAV.rendre();
}
