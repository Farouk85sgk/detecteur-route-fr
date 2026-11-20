// Mes trajets : liste des trajets filmés et, pour chacun, les photos prises à chaque élément repéré (avec l'heure,
// le moment dans la vidéo et l'endroit), pour revoir la situation.
import { D, icone } from "./donnees.js";
import { aller } from "./nav.js";
import { idbLire, idbSupprimerPrefixe, idbTout, profil, sauver } from "./stockage.js";
import { ICONES, confirmer, dateLongue, duree, esc, heure, ouvrirFeuille, tempsVideo } from "./ui.js";

let urls = [];
const liberer = () => { urls.forEach(u => URL.revokeObjectURL(u)); urls = []; };
const objetUrl = blob => { const u = URL.createObjectURL(blob); urls.push(u); return u; };

export function sousTitreTrajet(t) {
  const min = t.fin ? duree((t.fin - t.debut) / 1000) : "";
  return [`${t.photos} photo${t.photos > 1 ? "s" : ""}`, min, t.source === "video" ? `vidéo « ${t.fichier || "?"} »` : "caméra"].filter(Boolean).join(", ");
}

// Diagnostic d'un trajet : ce que la caméra a donné et le rythme d'analyse. À lire quand la détection a trouvé peu de
// choses : image trop petite, calcul trop lent, panneaux aperçus mais trop brièvement pour être annoncés.
function diagnostic(t) {
  const d = t.diag;
  if (!d || !d.analyses) return "";
  const [w, h] = d.flux, fr = v => String(v).replace(".", ","), s = n => n > 1 ? "s" : "";
  const calcul = d.moteur === "gpu" ? "carte graphique" : `processeur (${d.moteur === "cpu1" ? "un seul fil de calcul" : `${d.moteur.slice(3)} fils de calcul`}${d.gpuEcarte ? " ; la carte graphique a été écartée, ses calculs étaient faux" : ""})`;
  const annonces = Object.entries(t.elements || {}).filter(([c]) => D.parCode[c]?.groupe === "s").reduce((n, [, v]) => n + v, 0);
  const conseils = [];
  if (d.ips !== null && d.ips < 4) conseils.push("Le calcul est lent sur ce téléphone : au-dessus de 30 km/h, un panneau passe sans être vu assez de fois. Essaie la qualité « Rapide » dans les réglages.");
  if (Math.max(w, h) < 1000) conseils.push("L'image donnée par la caméra est petite : les panneaux ne sont reconnus que de très près.");
  if (d.vus >= 16 && annonces < d.vus / 8) conseils.push("Beaucoup de panneaux ont été aperçus sans être annoncés : ils étaient trop petits ou sont passés trop vite. Fixe le téléphone, la route au milieu de l'image, et essaie « Changer de caméra » dans les réglages si l'image paraît très large.");
  if (t.source !== "video" && d.vus < 3 && d.analyses > 150) conseils.push("Presque aucun panneau n'a été aperçu. Vérifie que la caméra voit bien la route (pare-brise propre, pas de reflet, téléphone droit).");
  return `<details class="diag-trajet doux petit"><summary style="padding:12px 0;cursor:pointer"><b>Diagnostic de ce trajet</b></summary>
    <p>Image de ${w} × ${h} points (${w >= h ? "en largeur" : "en hauteur"})${d.zoom && d.zoom > 1.05 ? `, zoom ${fr(d.zoom)}×` : ""}${d.camera ? `, caméra « ${esc(d.camera.slice(0, 40))} »` : ""}.</p>
    <p>Calcul : ${calcul}, analyse en ${d.cote} points${d.loin >= 0.05 ? `, avec la vue au loin (${Math.round(d.loin * 100)} % des analyses)` : ""}${d.ips !== null ? `, ${fr(d.ips)} image${d.ips >= 2 ? "s" : ""} par seconde` : ""}${d.ms ? ` (${d.ms} ms par image)` : ""}.</p>
    <p>${d.analyses} image${s(d.analyses)} analysée${s(d.analyses)}, ${d.vus} panneau${d.vus > 1 ? "x" : ""} aperçu${s(d.vus)}, ${annonces} annoncé${s(annonces)}.</p>
    ${conseils.map(c => `<p><b>${esc(c)}</b></p>`).join("")}</details>`;
}

export function pageTrajets(racine) {
  liberer();
  const p = profil();
  racine.innerHTML = `<div class="page"><div class="entete"><h1>Mes trajets</h1><button class="btn-rond" data-nav="#/" aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="contenu">${p.trajets.length ? `<div class="carte"><div class="liste-lignes">${p.trajets.map(t => `<button class="element-liste" data-nav="#/trajet/${t.id}">
      <div><b>${esc(dateLongue(t.debut))}</b><div class="doux">${esc(sousTitreTrajet(t))}</div></div>${ICONES.chevron.replace("<svg", '<svg class="chevron" style="transform:rotate(-90deg)"')}</button>`).join("")}</div></div>`
      : `<p class="vide">Aucun trajet pour l'instant. Lance la caméra depuis l'accueil : chaque élément repéré sera pris en photo.</p>`}</div></div>`;
}

export async function pageTrajet(racine, id) {
  liberer();
  const p = profil(), t = p.trajets.find(x => x.id === id);
  if (!t) return aller("#/trajets");
  racine.innerHTML = `<div class="page"><div class="entete"><h1>${esc(dateLongue(t.debut).replace(" à ", ", "))}</h1><button class="btn-rond" data-nav="#/" aria-label="Fermer">${ICONES.fermer}</button></div>
    <p class="sous-titre">${esc(sousTitreTrajet(t))}</p>
    <div class="contenu"><div class="grille-photos"><p class="doux">Chargement des photos…</p></div>
      <div class="elements-trajet"></div>
      <button class="btn btn-plein btn-grand" data-a="quiz">Quiz de ce trajet</button>
      <button class="btn btn-danger" data-a="supprimer">Supprimer ce trajet</button>
      ${diagnostic(t)}</div></div>`;
  const photos = await idbTout("photos", `${p.id}/${t.id}/`);
  const grille = racine.querySelector(".grille-photos");
  const quand = ph => t.source === "video" ? `à ${tempsVideo(ph.t || 0)} dans la vidéo` : `à ${heure(ph.quand)}`;
  grille.innerHTML = photos.length ? photos.map(({ cle, valeur: ph }) => `<button class="photo-carte" data-photo="${esc(cle)}"><img src="${objetUrl(ph.blob)}" alt="" loading="lazy">
      <div><b>${esc((ph.noms || [D.parCode[ph.code]?.nom]).join(", "))}</b><div class="doux">${esc(quand(ph))}</div></div></button>`).join("")
    : `<p class="vide" style="grid-column:1/3">Pas de photo pour ce trajet${p.reglages.photos ? "" : " (les photos sont coupées dans les réglages)"}.</p>`;
  const elements = Object.entries(t.elements).sort((a, b) => b[1] - a[1]);
  racine.querySelector(".elements-trajet").innerHTML = elements.length ? `<section class="carte"><h3>${elements.length} élément${elements.length > 1 ? "s" : ""} repéré${elements.length > 1 ? "s" : ""}</h3>
    <div class="liste-lignes">${elements.map(([c, n]) => D.parCode[c] ? `<div class="element-liste"><div class="ligne"><img src="${esc(icone(D.parCode[c]))}" alt="" style="width:44px;height:44px;object-fit:contain">
      <b>${esc(D.parCode[c].nom)}</b></div><span class="doux">× ${n}${t.nouveaux.includes(c) ? " · nouveau" : ""}</span></div>` : "").join("")}</div></section>` : "";
  racine.onclick = async e => {
    const a = e.target.closest("[data-a]")?.dataset.a;
    if (a === "quiz") return aller(`#/quiz/trajet/${t.id}`);
    if (a === "supprimer" && await confirmer("Supprimer ce trajet ?", "Ses photos seront effacées. L'album et la progression sont gardés.", { oui: "Supprimer", danger: true })) {
      await idbSupprimerPrefixe("photos", `${p.id}/${t.id}/`);
      for (const a2 of Object.values(p.album)) if (a2.photo?.startsWith(`${p.id}/${t.id}/`)) delete a2.photo;
      p.trajets = p.trajets.filter(x => x.id !== t.id); sauver();
      return aller("#/trajets");
    }
    const b = e.target.closest("[data-photo]");
    if (b) ouvrirPhoto(b.dataset.photo, t);
  };
}

async function ouvrirPhoto(cle, t) {
  const ph = await idbLire("photos", cle);
  if (!ph) return;
  const it = D.parCode[ph.code];
  const lieu = ph.pos ? `<a class="btn" href="https://www.openstreetmap.org/?mlat=${ph.pos.lat}&mlon=${ph.pos.lon}#map=18/${ph.pos.lat}/${ph.pos.lon}" target="_blank" rel="noopener">Voir l'endroit sur la carte</a>` : "";
  const corps = ouvrirFeuille(it?.nom || "Photo", `<img class="fiche-photo" src="${objetUrl(ph.blob)}" alt="">
    <p class="doux">${esc((ph.noms || []).join(", "))} · ${t.source === "video" ? `à ${tempsVideo(ph.t || 0)} dans la vidéo` : `${esc(dateLongue(ph.quand))}`}</p>
    ${it ? `<p>${esc(it.reflexe || it.explication)}</p><button class="btn btn-plein" data-fiche="${esc(it.code)}">Voir la fiche</button>` : ""}${lieu}`);
  corps.onclick = async e => { const b = e.target.closest("[data-fiche]"); if (b) { const { ouvrirFiche } = await import("./album.js"); ouvrirFiche(b.dataset.fiche); } };
}
