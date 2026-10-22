// Démarrage de l'appli et navigation entre les pages (#/, #/quiz, #/album, #/quete, #/trajets, #/codes...).
import { pageAccueil } from "./accueil.js";
import { pageAlbum } from "./album.js";
import { cameraOuverte, configurerMoteur, moteur, ouvrirCamera } from "./camera.js";
import { chargerDonnees } from "./donnees.js";
import { chargerAppris } from "./mespanneaux.js";
import { NAV, aller } from "./nav.js";
import { verifierBadges } from "./progression.js";
import { pageQuete } from "./quete.js";
import { lancer, pageQuiz } from "./quiz.js";
import { EVENEMENTS, appliquerTheme } from "./reglages.js";
import { brancherCodes, carteCodes } from "./series.js";
import { charger, profil } from "./stockage.js";
import { pageTrajet, pageTrajets } from "./trajets.js";
import { ICONES, esc } from "./ui.js";

const racine = document.getElementById("app");
let appris = [], dernier = null;

async function rendre() {
  const h = location.hash || "#/";
  dernier = h;
  const [, page, a, b, c] = h.split("/");
  // chaque affichage a son propre conteneur : un affichage plus ancien encore en cours écrit dans un élément détaché
  const zone = document.createElement("div");
  racine.replaceChildren(zone);
  try {
    if (!page) await pageAccueil(zone, { moteur, appris, lancerCamera });
    else if (page === "quiz" && a) await lancer(zone, a, b, c);
    else if (page === "quiz") pageQuiz(zone);
    else if (page === "album") pageAlbum(zone);
    else if (page === "quete") pageQuete(zone, a);
    else if (page === "trajets") pageTrajets(zone);
    else if (page === "trajet") await pageTrajet(zone, a);
    else if (page === "codes") await pageCodes(zone);
    else return aller("#/");
  } catch (e) {
    console.error(e);
    zone.innerHTML = `<div class="page"><div class="contenu"><h2>Oups</h2><p>${esc(e.message || e)}</p><button class="btn" data-nav="#/">Accueil</button></div></div>`;
  }
  scrollTo({ top: 0 });
}
NAV.rendre = rendre;

async function pageCodes(zone) {
  zone.innerHTML = `<div class="page"><div class="entete"><h1>Séries de code</h1><button class="btn-rond" data-nav="#/quiz" aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="contenu zone-codes">${await carteCodes()}</div></div>`;
  brancherCodes(zone.querySelector(".zone-codes"), rendre);
}

function lancerCamera(fichier = null) {
  if (cameraOuverte()) return;
  ouvrirCamera({ fichier, apresFermeture: () => { if (location.hash === dernier) rendre(); } });
}

// liens internes : <... data-nav="#/album">
document.addEventListener("click", e => {
  const n = e.target.closest("[data-nav]");
  if (n) { e.preventDefault(); aller(n.dataset.nav); }
});
addEventListener("popstate", () => { if ((location.hash || "#/") !== dernier) rendre(); });

EVENEMENTS.profilChange = async () => { appliquerTheme(); appris = await chargerAppris(moteur); configurerMoteur(); rendre(); };
EVENEMENTS.reglagesChanges = () => { if (!cameraOuverte() && (location.hash || "#/") === "#/") rendre(); };

async function demarrer() {
  charger();
  appliquerTheme();
  await chargerDonnees();
  appris = await chargerAppris(moteur);
  verifierBadges(profil());
  await rendre();
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
    navigator.serviceWorker.register("sw.js").then(() => navigator.serviceWorker.ready).then(r => r.active?.postMessage({ type: "mode", mode: profil().reglages.reseau })).catch(e => console.warn("Service worker", e));
  }
}
demarrer();
