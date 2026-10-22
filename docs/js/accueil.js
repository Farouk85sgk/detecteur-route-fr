// Accueil : héros (caméra, vidéo), carte de la quête, niveau et badges, code et examens, trajets, Mes panneaux,
// réseau, ce que l'appli détecte, diagnostic, ce que l'appli reconnaît.
import { APP, BADGES, FAMILLES, QUETE } from "./contenu.js";
import { D, icone, itemsFamille } from "./donnees.js";
import { assurerJour, etatRegion, majCoeurs, nbAlbum, nbBadges, nbEclats, nbQuetesFaites, niveau, regionCourante, statsClassement } from "./progression.js";
import { miniCarte } from "./quete.js";
import { EVENEMENTS, ouvrirProfils, ouvrirReglages } from "./reglages.js";
import { brancherCodes, carteCodes } from "./series.js";
import { profil, sauver } from "./stockage.js";
import { sousTitreTrajet } from "./trajets.js";
import { $, ICONES, LOGO, avatar, bascule, dateLongue, esc, ilYa, ouvrirFeuille, toast } from "./ui.js";

export async function pageAccueil(racine, { moteur, appris, lancerCamera }) {
  const p = profil();
  majCoeurs(p);
  const j = assurerJour(p), nv = niveau(p.xp), c = regionCourante(p), fc = FAMILLES[c], ec = etatRegion(p, c);
  const dernier = p.trajets[0], nDernier = dernier ? Object.keys(dernier.elements).length : 0;
  const stats = statsClassement(p), faites = nbQuetesFaites(p), eclats = nbEclats(p);
  const recit = ec.etat === "vaincue" ? `Tous les gardiens sont vaincus : le Panneau d'Or est reconstitué !`
    : ec.etat === "gardien" ? `${fc.region} : ${fc.gardien} t'attend au donjon.`
    : `${fc.region} : repère sur la route encore ${ec.besoin - ec.vus} élément${ec.besoin - ec.vus > 1 ? "s" : ""} de la famille « ${fc.nom} » pour affronter ${fc.gardien}.`;
  const mys = D.parCode[j.mystere];
  racine.innerHTML = `<div class="page">
    <header class="heros">
      <div class="heros-haut"><button class="puce-profil" data-a="profils">${avatar(p)}<span>${esc(p.nom)}</span>${ICONES.chevron.replace("<svg", '<svg class="chevron"')}</button>
        <button class="btn-reglages" data-a="reglages">${ICONES.reglages}Réglages</button></div>
      <h1 class="marque">${esc(APP.nom)}${LOGO}</h1>
      <p class="slogan">${esc(APP.slogan)}</p>
      <p class="accroche">${esc(APP.accroche)}</p>
      <button class="btn btn-grand btn-camera" data-a="camera"><span class="point-rec"></span>Lancer la caméra</button>
      <label class="btn btn-grand" style="font-size:1.15rem">Tester sur une vidéo<input type="file" accept="video/*" hidden data-video></label>
    </header>
    <div class="contenu">
      <section class="carte carte-quete"><div class="bandeau">${miniCarte(p)}</div><div class="corps">
        <div class="medaillon-ligne">${medaillon(eclats)}<div><h2>${esc(QUETE.titre)}</h2><p>${esc(recit)}</p></div></div>
        <div class="stats-ligne"><span>${Array.from({ length: QUETE.coeursMax }, (_, k) => k < p.coeurs ? ICONES.coeur : ICONES.coeurVide).join("")}</span>
          <span>${ICONES.gemme}${p.pepites}</span><span>${p.flamme.jours ? ICONES.flamme : ICONES.flammeGrise}${p.flamme.jours}<small>jour${p.flamme.jours > 1 ? "s" : ""}</small></span>
          <span>${eclats}<small>/${FAMILLES.length} éclats</small></span></div>
        <button class="mini-bloc" data-nav="#/quete/jour"><span class="icone-mystere">${j.trouve ? `<img src="${esc(icone(mys))}" alt="" style="width:56px;height:56px;object-fit:contain">` : ICONES.mystere}</span>
          <span><b>Panneau mystère du jour</b><br><span class="doux">${j.trouve ? `Trouvé : ${esc(mys.nom)}` : "Repère-le sur la route : +40 pépites"}</span></span></button>
        <button class="mini-bloc" data-nav="#/quete/jour"><b>Quêtes du jour</b><span class="points-quetes">${j.quetes.map((q, k) => `<i class="${k < faites ? "fait" : ""}"></i>`).join("")} ${faites} sur 3</span></button>
        <button class="btn btn-plein btn-grand" data-nav="#/quete">Ouvrir la carte</button></div></section>

      <section class="carte carte-niveau"><div class="niveau-tete"><span class="losange"><b>${nv.n}</b></span><div><h2>${esc(nv.nom)}</h2>
          <div class="jauge-xp"><i style="width:${(100 * (p.xp - nv.debut) / (nv.fin - nv.debut)).toFixed(1)}%"></i></div>
          <p class="doux">Niveau ${nv.n}. Encore ${nv.reste} XP pour le niveau ${nv.n + 1}</p></div></div>
        <div class="tuiles"><button class="tuile" data-nav="#/album"><b>${nbAlbum(p)}<small>/${D.nbOfficiels}</small></b><span>Album</span></button>
          <button class="tuile" data-nav="#/quiz"><b>${stats.erudit ? `${stats.erudit}<small>%</small>` : "?"}</b><span>Quiz</span></button>
          <button class="tuile" data-a="badges"><b>${nbBadges(p)}<small>/${BADGES.length}</small></b><span>Badges</span></button></div>
        ${nDernier ? `<button class="barre-trajet" data-nav="#/quiz/trajet/${dernier.id}"><span>Dernier trajet : <b>${nDernier} élément${nDernier > 1 ? "s" : ""}</b>, ${ilYa(dernier.fin || dernier.debut)}</span><b>Quiz du trajet ▸</b></button>` : ""}
        <div class="reglage" style="padding-bottom:0"><div><h3>Expliquer la règle à voix haute</h3><p class="doux">Après le nom : ce qu'il faut faire.</p></div>${bascule("expliquer", p.reglages.expliquer)}</div></section>

      <div class="zone-codes"></div>

      <section class="carte"><div class="carte-titre"><h2>Mes trajets</h2>${p.trajets.length ? `<span class="pastille">${p.trajets.length}</span>` : ""}</div>
        <p class="doux">Une photo à chaque panneau, feu, marquage ou usager repéré, avec l'heure et l'endroit. Touche un trajet pour revoir la situation.</p>
        ${p.trajets.length ? `<div class="liste-lignes">${p.trajets.slice(0, 3).map(t => `<button class="element-liste" data-nav="#/trajet/${t.id}"><div><b>${esc(dateLongue(t.debut))}</b><div class="doux">${esc(sousTitreTrajet(t))}</div></div></button>`).join("")}</div>
          ${p.trajets.length > 3 ? `<button class="btn" data-nav="#/trajets">Voir les ${p.trajets.length} trajets</button>` : ""}` : ""}</section>

      <div class="zone-appris"></div>

      <section class="carte"><div class="carte-titre"><h2>Réseau</h2><span class="etat-reseau ${navigator.onLine ? "" : "hors"}"><i></i>${navigator.onLine ? "Connecté" : "Hors ligne"}</span></div>
        <div class="segments"><button data-reseau="avec" aria-pressed="${p.reglages.reseau !== "sans"}">Avec réseau</button><button data-reseau="sans" aria-pressed="${p.reglages.reseau === "sans"}">Sans réseau</button></div>
        <p class="doux texte-reseau">${p.reglages.reseau === "sans" ? "L'appli n'utilise plus le réseau : tout fonctionne avec ce qui est déjà sur le téléphone." : "L'appli vérifie les mises à jour à chaque ouverture."} <span class="taille-hors-ligne"></span></p>
        <button class="btn" data-a="horsligne">Tout préparer pour rouler sans réseau</button></section>

      <details class="carte repli"><summary><div><h2>Ce que je veux détecter</h2><span class="doux gras">${D.items.filter(it => (it.famille === "perso" || p.reglages.familles[it.famille] !== false) && !p.reglages.exclus.includes(it.code)).length} sur ${D.items.length}</span></div>${ICONES.chevron.replace("<svg", '<svg class="chevron"')}</summary>
        <div class="repli-corps"><p class="doux">Coupe une famille entière ou un seul élément : ce qui est coupé n'est ni encadré ni annoncé.</p><button class="btn btn-plein" data-a="reglages">Choisir dans les réglages</button></div></details>

      <details class="carte repli"><summary><h2>Diagnostic</h2>${ICONES.chevron.replace("<svg", '<svg class="chevron"')}</summary><div class="repli-corps diagnostic"></div></details>

      <section class="carte"><h2>Ce que ${esc(APP.nom)} reconnaît</h2>
        <p class="doux">${D.nbOfficiels} panneaux, feux, marquages au sol et usagers de la route, plus tes panneaux appris. Les limitations sont lues de 30 à 130 km/h.</p>
        <div class="table-reconnait">${FAMILLES.map(f => `<div><span>${esc(f.nom)}</span><span>${itemsFamille(f.id).length}</span></div>`).join("")}
          ${appris.length ? `<div><span>Mes panneaux</span><span>${appris.length}</span></div>` : ""}</div></section>

      <p class="credits centre">Outil d'aide pédagogique : il ne remplace ni ton attention ni la signalisation réelle. En voiture, le téléphone est fixé sur un support et le conducteur ne le manipule pas.
        <br><a href="${APP.depot}" target="_blank" rel="noopener">Code source (licence AGPL-3.0)</a></p>
    </div></div>`;

  const codes = $(".zone-codes", racine);
  codes.innerHTML = await carteCodes();
  brancherCodes(codes, () => pageAccueil(racine, { moteur, appris, lancerCamera }));
  const { carteMesPanneaux, brancherMesPanneaux } = await import("./mespanneaux.js");
  const za = $(".zone-appris", racine);
  za.innerHTML = carteMesPanneaux(appris);
  brancherMesPanneaux(za, moteur, () => EVENEMENTS.profilChange());
  tailleHorsLigne(racine);

  racine.onclick = async e => {
    const b = e.target.closest("[data-a],[data-reseau]");
    if (!b) return;
    if (b.dataset.reseau) {
      p.reglages.reseau = b.dataset.reseau; sauver();
      navigator.serviceWorker?.controller?.postMessage({ type: "mode", mode: p.reglages.reseau });
      return pageAccueil(racine, { moteur, appris, lancerCamera });
    }
    const a = b.dataset.a;
    if (a === "camera") lancerCamera();
    if (a === "profils") ouvrirProfils();
    if (a === "reglages") ouvrirReglages();
    if (a === "badges") ouvrirBadges();
    if (a === "horsligne") preparerHorsLigne(racine);
  };
  racine.onchange = e => {
    if (e.target.matches("[data-video]") && e.target.files[0]) { const f = e.target.files[0]; e.target.value = ""; lancerCamera(f); }
    if (e.target.dataset.reglage === "expliquer") { p.reglages.expliquer = e.target.checked; sauver(); }
  };
  racine.querySelectorAll("details.repli").forEach(d => d.addEventListener("toggle", () => { if (d.open && d.querySelector(".diagnostic")) diagnostic(d.querySelector(".diagnostic"), moteur); }));
}

function medaillon(eclats) {
  const n = FAMILLES.length, r = 50, parts = [];
  for (let i = 0; i < n; i++) {
    const a0 = (i / n) * 2 * Math.PI - Math.PI / 2, a1 = ((i + 1) / n) * 2 * Math.PI - Math.PI / 2;
    const p = (a, rr) => `${(56 + rr * Math.cos(a)).toFixed(2)} ${(56 + rr * Math.sin(a)).toFixed(2)}`;
    parts.push(`<path d="M ${p(a0, 20)} L ${p(a0, r)} A ${r} ${r} 0 0 1 ${p(a1, r)} L ${p(a1, 20)} A 20 20 0 0 0 ${p(a0, 20)} Z" fill="${i < eclats ? "#ffc61e" : "#1b2050"}" stroke="#3a4290" stroke-width="1.5" stroke-dasharray="${i < eclats ? "" : "3 3"}"/>`);
  }
  return `<svg viewBox="0 0 112 112" width="112" height="112" aria-label="${eclats} éclats sur ${n}"><circle cx="56" cy="56" r="55" fill="#12163a"/>${parts.join("")}
    <circle cx="56" cy="56" r="18" fill="#12163a" stroke="#3a4290" stroke-width="1.5"/><text x="56" y="63" text-anchor="middle" font-size="20" font-weight="800" fill="#ffc61e" font-family="Bricolage, sans-serif">${eclats === n ? "★" : "?"}</text></svg>`;
}

function ouvrirBadges() {
  const p = profil();
  ouvrirFeuille("Badges", `<p class="doux">${nbBadges(p)} badge${nbBadges(p) > 1 ? "s" : ""} sur ${BADGES.length}.</p>
    <div class="badges">${BADGES.map((b, i) => `<div class="badge-case ${p.badges[b.id] ? "" : "non"}" title="${esc(b.texte)}"><i><b>${p.badges[b.id] ? "✓" : i + 1}</b></i>${esc(b.nom)}</div>`).join("")}</div>
    <div class="liste-lignes">${BADGES.map(b => `<div class="element-liste"><div><b>${esc(b.nom)}</b><div class="doux">${esc(b.texte)}</div></div><span class="doux">${p.badges[b.id] ? "obtenu" : ""}</span></div>`).join("")}</div>`);
}

async function tailleHorsLigne(racine) {
  const z = $(".taille-hors-ligne", racine);
  if (!z || !("caches" in window)) return;
  let total = 0, lourds = 0;
  for (const nom of await caches.keys()) {
    const cache = await caches.open(nom);
    for (const req of await cache.keys()) {
      const rep = await cache.match(req);
      const n = +(rep.headers.get("content-length") || 0) || (await rep.clone().blob()).size;
      total += n;
      if (/\.(onnx|wasm)$/.test(req.url)) lourds++;
    }
  }
  if (total) z.textContent = lourds >= 4 ? `Elle est prête sans réseau (${Math.round(total / 1e6)} Mo).` : `Déjà sur le téléphone : ${Math.round(total / 1e6)} Mo.`;
}

async function preparerHorsLigne(racine) {
  const sw = navigator.serviceWorker?.controller;
  if (!sw) return toast("Le mode sans réseau sera disponible après le prochain chargement de la page");
  toast("Téléchargement des modèles pour rouler sans réseau…");
  sw.postMessage({ type: "tout-preparer" });
  navigator.serviceWorker.addEventListener("message", function fin(e) {
    if (e.data?.type !== "pret") return;
    navigator.serviceWorker.removeEventListener("message", fin);
    toast(e.data.ok ? "Tout est prêt pour rouler sans réseau" : "Téléchargement incomplet : réessaie avec une meilleure connexion");
    tailleHorsLigne(racine);
  });
}

async function diagnostic(zone, moteur) {
  const est = await navigator.storage?.estimate?.().catch(() => null);
  const lignes = [
    ["Appli", `${APP.nom} ${APP.version}`],
    ["Détecteur", moteur.pret ? `prêt, ${moteur.fournisseurs[0] === "webgpu" ? "carte graphique (WebGPU)" : "processeur (WebAssembly)"}` : "chargé au lancement de la caméra"],
    ["Classifieur de panneaux", moteur.cls ? "actif" : moteur.pret ? "absent" : "—"],
    ["Feux et usagers", moteur.usagers ? "actifs" : "chargés avec la caméra"],
    ["Mes panneaux", moteur.emp ? `actif (${moteur.appris.length / 3} appris)` : "inactif"],
    ["Temps par image", moteur.ms ? `${Math.round(moteur.ms)} ms` : "—"],
    ["Taille d'analyse", `${moteur.cote} px`],
    ["Processeur", `${navigator.hardwareConcurrency || "?"} cœurs`],
    ["WebGPU", "gpu" in navigator ? "disponible" : "non disponible"],
    ["Stockage utilisé", est ? `${(est.usage / 1e6).toFixed(1)} Mo sur ${(est.quota / 1e9).toFixed(1)} Go` : "—"],
    ["Mode hors ligne", navigator.serviceWorker?.controller ? "actif" : "inactif"],
  ];
  zone.innerHTML = `<div class="liste-lignes">${lignes.map(([k, v]) => `<div class="element-liste"><span class="doux">${esc(k)}</span><b style="text-align:right">${esc(v)}</b></div>`).join("")}</div>
    <button class="btn" data-maj>Recharger la dernière version</button>`;
  zone.querySelector("[data-maj]").onclick = async () => {
    for (const k of await caches.keys()) if (!k.includes("lourds")) await caches.delete(k);
    (await navigator.serviceWorker?.getRegistration())?.update();
    location.reload();
  };
}
