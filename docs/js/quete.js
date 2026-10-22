// La quête : carte (une région par famille, repérages sur la route puis gardien au donjon), quêtes du jour,
// classement (profils du téléphone et amis ajoutés par code) et échoppe (objets et titres).
import { CATEGORIES_CLASSEMENT, FAMILLES, OBJETS, QUETE, TITRES } from "./contenu.js";
import { D, icone, itemsFamille } from "./donnees.js";
import { aller } from "./nav.js";
import { assurerJour, codeAmi, etatRegion, lireCodeAmi, majCoeurs, minutesProchainCoeur, nbEclats, nbQuetesFaites, ouvrirCoffre, participants, queteDef, regionCourante } from "./progression.js";
import { profil, sauver } from "./stockage.js";
import { $, ICONES, LOGO, avatar, confirmer, dateCourte, demander, esc, graine, ouvrirFeuille, son, toast } from "./ui.js";

const ONGLETS = [["carte", "Carte"], ["jour", "Du jour"], ["classement", "Classement"], ["echoppe", "Échoppe"]];

export function pageQuete(racine, onglet = "carte") {
  if (!ONGLETS.some(o => o[0] === onglet)) onglet = "carte";
  const p = profil();
  majCoeurs(p);
  assurerJour(p);
  racine.innerHTML = `<div class="page page-sombre"><div class="quete-tete"><h1>La quête</h1>
      <div class="compteurs"><span>${ICONES.gemme}${p.pepites}</span><span>${p.flamme.jours ? ICONES.flamme : ICONES.flammeGrise}${p.flamme.jours}</span></div>
      <button class="btn-rond" data-x="son" aria-label="Effets sonores">${p.reglages.sons ? ICONES.son : ICONES.sonCoupe}</button>
      <button class="btn-rond" data-nav="#/" aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="onglets" role="tablist">${ONGLETS.map(([id, nom]) => `<button role="tab" aria-selected="${id === onglet}" data-onglet="${id}">${nom}</button>`).join("")}</div>
    <div class="quete-corps">${{ carte, jour, classement, echoppe }[onglet](p)}</div></div>`;
  racine.onclick = e => clic(e, racine, onglet);
  if (onglet === "carte") requestAnimationFrame(() => racine.querySelector(".region.courante")?.scrollIntoView({ block: "center" }));
}

async function clic(e, racine, onglet) {
  const p = profil(), b = e.target.closest("[data-x],[data-onglet],[data-region],[data-acheter],[data-porter]");
  if (!b) return;
  if (b.dataset.onglet) return aller(`#/quete/${b.dataset.onglet}`);
  if (b.dataset.region) return ouvrirRegion(+b.dataset.region);
  if (b.dataset.acheter) {
    const o = [...OBJETS, ...TITRES].find(x => x.id === b.dataset.acheter);
    if (!o || p.pepites < o.prix) return;
    p.pepites -= o.prix;
    if (OBJETS.includes(o)) { p.objets[o.id] = (p.objets[o.id] || 0) + 1; toast(`${o.nom} achetée`, `−${o.prix} 💎`); }
    else { p.titres.push(o.id); p.titre = o.nom; toast(`Nouveau titre : ${o.nom}`, `−${o.prix} 💎`); }
    son("piece", p.reglages.sons); sauver(); return pageQuete(racine, onglet);
  }
  if (b.dataset.porter) { const t = TITRES.find(x => x.id === b.dataset.porter); p.titre = p.titre === t.nom ? null : t.nom; sauver(); return pageQuete(racine, onglet); }
  const x = b.dataset.x;
  if (x === "son") { p.reglages.sons = !p.reglages.sons; sauver(); b.innerHTML = p.reglages.sons ? ICONES.son : ICONES.sonCoupe; }
  if (x === "coffre") { const lot = ouvrirCoffre(p); if (lot) { son("victoire", p.reglages.sons); toast("Coffre ouvert !", lot.pepites ? `+${lot.pepites} 💎` : `+1 ${OBJETS.find(o => o.id === lot.objet).nom}`); pageQuete(racine, onglet); } }
  if (x === "moncode") {
    const code = codeAmi(p);
    try { await navigator.clipboard.writeText(code); toast("Ton code ami est copié : envoie-le à tes amis"); }
    catch { await demander("Ton code ami (copie-le)", code); }
  }
  if (x === "ajouterami") {
    const code = await demander("Code ami reçu", "", { placeholder: "REPERE-…", ok: "Ajouter" });
    if (!code) return;
    const ami = lireCodeAmi(code);
    if (!ami) return toast("Ce code ami n'est pas valable");
    if (ami.id === p.id) return toast("C'est ton propre code !");
    p.amis = [...p.amis.filter(a => a.id !== ami.id), ami];
    sauver(); toast(`Ami ajouté : ${ami.nom}`); pageQuete(racine, onglet);
  }
  if (x === "retirerami" && await confirmer(`Retirer ${p.amis.find(a => a.id === b.dataset.id)?.nom} du classement ?`)) {
    p.amis = p.amis.filter(a => a.id !== b.dataset.id); sauver(); pageQuete(racine, onglet);
  }
}

// ---------- carte ----------
const H_REGION = 190, LARGEUR = 400;
function carte(p) {
  const n = FAMILLES.length, H = n * H_REGION + 120, courante = regionCourante(p);
  const pts = FAMILLES.map((_, i) => ({ x: i % 2 ? 280 : 120, y: H - 90 - i * H_REGION }));
  let d = `M ${pts[0].x} ${H + 20} L ${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < n; i++) { const a = pts[i - 1], b = pts[i], m = (a.y + b.y) / 2; d += ` C ${a.x} ${m}, ${b.x} ${m}, ${b.x} ${b.y}`; }
  d += ` L ${pts[n - 1].x} -20`;
  const r = graine("carte");
  const deco = Array.from({ length: 34 }, () => ({ x: r() * LARGEUR, y: r() * H, sapin: r() < 0.55 }))
    .filter(o => pts.every(q => Math.hypot(q.x - o.x, q.y - o.y) > 95))
    .map(o => o.sapin ? `<path d="M${o.x} ${o.y - 14} l11 22 h-22z" fill="#1d3b3a"/>` : `<circle cx="${o.x}" cy="${o.y}" r="2.2" fill="#4a5280"/>`).join("");
  const regions = FAMILLES.map((f, i) => {
    const e = etatRegion(p, i), droite = i % 2 === 1;
    const libelle = { bloquee: "Bloquée", reperage: `Repérage ${e.vus}/${e.besoin}`, gardien: "Gardien à vaincre", vaincue: "Vaincue ✓" }[e.etat];
    const classeTexte = { gardien: "or", vaincue: "vert" }[e.etat] || "";
    const cls = { bloquee: "bloquee", reperage: "en-cours", gardien: "gardien", vaincue: "vaincue" }[e.etat];
    return `<button class="region ${droite ? "droite" : ""} ${i === courante ? "courante" : ""}" data-region="${i}"
        style="top:${((pts[i].y - 54) / H * 100).toFixed(3)}%;${droite ? `right:calc(${100 - pts[i].x / LARGEUR * 100}% - 54px)` : `left:calc(${pts[i].x / LARGEUR * 100}% - 54px)`}">
      <span class="noeud ${cls}"><img src="${esc(icone(D.parCode[f.icone]))}" alt="">${e.etat === "bloquee" ? `<span class="cadenas">${ICONES.cadenas}</span>` : ""}</span>
      <span><h3>${esc(f.region)}</h3><small class="${classeTexte}">${libelle}</small></span></button>`;
  }).join("");
  const c = pts[courante];
  const repere = `<g transform="translate(${c.x + (courante % 2 ? -78 : 78)} ${c.y - 70})"><rect x="-2" y="10" width="4" height="34" rx="2" fill="#9aa0c0"/><g transform="translate(-20 -22) scale(.4)">${LOGO.replace(/<\/?svg[^>]*>/g, "")}</g></g>`;
  return `<div class="carte-route"><svg class="route" viewBox="0 0 ${LARGEUR} ${H}" aria-hidden="true">${deco}
      <path d="${d}" stroke="#2b3373" stroke-width="62" fill="none" stroke-linecap="round"/><path d="${d}" stroke="#ffc61e" stroke-width="4.5" fill="none" stroke-dasharray="16 22"/>${repere}</svg>${regions}</div>
    <p class="doux centre">Les éléments repérés avant comptent aussi : ton album est déjà dans la quête. ${nbEclats(p)}/${FAMILLES.length} éclats du Panneau d'Or.</p>`;
}

function ouvrirRegion(i) {
  const p = profil(), f = FAMILLES[i], e = etatRegion(p, i);
  majCoeurs(p);
  const items = itemsFamille(f.id);
  const texte = {
    bloquee: () => `Cette région s'ouvre quand le gardien de « ${FAMILLES[i - 1]?.region} » est vaincu.`,
    reperage: () => `Repère sur la route ${e.besoin} éléments différents de la famille « ${f.nom} » (ceux déjà dans ton album comptent) : ${e.vus}/${e.besoin}. Ensuite, ${f.gardien} t'attendra au donjon.`,
    gardien: () => `${f.gardien.charAt(0).toUpperCase() + f.gardien.slice(1)} t'attend au donjon : ${QUETE.questionsDonjon} questions sur « ${f.nom} ». Chaque erreur coûte un cœur ; la loupe et la potion peuvent t'aider.`,
    vaincue: () => `Tu as vaincu ${f.gardien} le ${dateCourte(p.gardiens[f.id]).toLowerCase()} et gagné son éclat. Tu peux retourner au donjon pour t'entraîner.`,
  }[e.etat]();
  const coeurs = Array.from({ length: QUETE.coeursMax }, (_, k) => k < p.coeurs ? ICONES.coeur : ICONES.coeurVide).join("");
  const corps = ouvrirFeuille(f.region, `<p class="doux">${esc(f.nom)}</p><p>${esc(texte)}</p>
    <div class="grille-album">${items.map(it => `<div class="case ${p.album[it.code] ? "" : "inconnue"}"><img src="${esc(icone(it))}" alt=""><span>${p.album[it.code] ? esc(it.nom) : "???"}</span></div>`).join("")}</div>
    ${["gardien", "vaincue"].includes(e.etat) ? `<div class="ligne"><span class="q-coeurs">${coeurs}</span><span class="doux">${p.coeurs < QUETE.coeursMax ? `prochain cœur dans ${minutesProchainCoeur(p)} min` : "cœurs pleins"}</span></div>
      <button class="btn btn-plein btn-grand" data-r="donjon" ${p.coeurs ? "" : "disabled"}>${e.etat === "vaincue" ? "Retourner au donjon" : "Entrer dans le donjon"}</button>` : ""}
    ${e.etat !== "bloquee" ? `<button class="btn" data-r="reviser">Réviser : ${esc(f.nom)}</button>` : ""}`);
  corps.onclick = ev => {
    const r = ev.target.closest("[data-r]")?.dataset.r;
    if (r === "donjon") aller(`#/quiz/donjon/${f.id}`);
    if (r === "reviser") aller(`#/quiz/famille/${f.id}`);
  };
}

// ---------- du jour ----------
function jour(p) {
  const j = assurerJour(p), m = D.parCode[j.mystere], fm = FAMILLES.find(f => f.id === m?.famille), faites = nbQuetesFaites(p);
  return `<div class="mystere"><div class="icone-mystere">${j.trouve ? `<img src="${esc(icone(m))}" alt="">` : ICONES.mystere}</div><div>
      <h3>Panneau mystère du jour</h3><p class="doux">${j.trouve ? `Trouvé : ${esc(m.nom)} ! +40 pépites.` : `Il se cache sur ta route aujourd'hui. Indice : famille « ${esc(fm?.nom || "?")} ». Le repérer en conduisant rapporte 40 pépites.`}</p></div></div>
    <h2 style="font-size:1.6rem;margin-top:10px">Quêtes du jour</h2>
    <div>${j.quetes.map(q => { const def = queteDef(q.id), fait = q.avance >= def.but; return `<div class="quete-jour">
      <span class="rond ${fait ? "fait" : ""}">${fait ? ICONES.coche : ""}</span>
      <div><b>${esc(def.texte)}</b><div class="jauge"><i style="width:${100 * q.avance / def.but}%"></i></div></div>
      <div class="droite">${fait ? "Fait" : `${q.avance}/${def.but}`}<small>+${def.gain} ${ICONES.gemme}</small></div></div>`; }).join("")}</div>
    <button class="coffre ${faites >= 3 && !j.coffre ? "pret" : ""}" data-x="coffre" ${faites >= 3 && !j.coffre ? "" : "disabled"}>${j.coffre ? ICONES.coffreOuvert : ICONES.coffre}
      <span><h3>Coffre du jour</h3><span class="doux">${j.coffre ? "Ouvert : reviens demain !" : faites >= 3 ? "Touche pour l'ouvrir !" : "Accomplis les 3 quêtes pour l'ouvrir"}</span></span></button>
    <div class="bloc-sombre" style="display:grid;grid-template-columns:60px 1fr;gap:14px;align-items:start"><span style="width:52px">${p.flamme.jours ? ICONES.flamme : ICONES.flammeGrise}</span>
      <div><h3>${p.flamme.jours} jour${p.flamme.jours > 1 ? "s" : ""} de suite</h3><p class="doux">Une quête du jour accomplie chaque jour fait grandir la flamme. Record : ${p.flamme.record} jour${p.flamme.record > 1 ? "s" : ""}.
        Un bouclier, à l'échoppe, la protège si tu oublies une journée${p.objets.bouclier ? ` (tu en as ${p.objets.bouclier})` : ""}.</p></div></div>`;
}

// ---------- classement ----------
function classement(p) {
  const gens = participants(p), tetes = {};
  const cartes = CATEGORIES_CLASSEMENT.map(c => {
    const tri = gens.filter(g => g.stats[c.id] > 0).sort((a, b) => b.stats[c.id] - a.stats[c.id]).slice(0, 3);
    if (tri[0]) tetes[tri[0].id] = (tetes[tri[0].id] || 0) + 1;
    return `<div class="bloc-sombre"><h3>${esc(c.nom)}</h3><p class="doux">${esc(c.texte)}</p>
      ${tri.length ? tri.map((g, k) => `<div class="rang">${k === 0 ? ICONES.couronne : `<b style="width:34px;text-align:center">${k + 1}</b>`}${avatar(g, "petit")}
        <span class="nom ${g.toi ? "" : "autre"}">${esc(g.nom)}${g.toi ? " (toi)" : g.ami ? " (ami)" : ""}${g.titre ? `<br><small class="doux">${esc(g.titre)}</small>` : ""}</span><span class="val">${esc(c.unite(g.stats[c.id]))}</span></div>`).join("")
        : `<p class="doux">Personne pour l'instant : à toi de jouer.</p>`}</div>`;
  }).join("");
  const roi = Object.entries(tetes).sort((a, b) => b[1] - a[1])[0];
  const qui = roi && gens.find(g => g.id === roi[0]);
  return `<div class="bloc-sombre bloc-couronne">${ICONES.couronne}<div><h3>${qui ? `${esc(qui.nom)}${qui.toi ? " (toi)" : ""}` : "Personne"}</h3>
      <p class="doux">${qui ? `porte la couronne : en tête dans ${roi[1]} catégorie${roi[1] > 1 ? "s" : ""} sur ${CATEGORIES_CLASSEMENT.length}.` : "ne porte encore la couronne : à toi de jouer."}</p></div></div>
    <p class="doux">Les profils de ce téléphone, et les amis dont tu as ajouté le code. Rien ne part sur internet.</p>
    <div class="duo"><button class="btn btn-jaune" data-x="moncode">Mon code ami</button><button class="btn" style="border-color:#fff;color:#fff" data-x="ajouterami">Ajouter un ami</button></div>
    ${cartes}
    ${p.amis.length ? `<div class="bloc-sombre"><h3>Mes amis</h3>${p.amis.map(a => `<div class="rang">${avatar(a, "petit")}<span class="nom autre">${esc(a.nom)}<br><small class="doux">code du ${dateCourte(a.date).toLowerCase()}</small></span>
      <button class="btn-lien" style="color:#fff" data-x="retirerami" data-id="${esc(a.id)}">Retirer</button></div>`).join("")}</div>` : ""}`;
}

// ---------- échoppe ----------
function echoppe(p) {
  return `<div class="ligne" style="align-items:flex-start"><span style="width:44px;flex:none">${ICONES.gemme}</span><p><b style="font-size:1.6rem">${p.pepites}</b>
      <span class="doux"> pépites. Les pépites se gagnent en repérant des panneaux, avec les quiz, les séries de code, les quêtes du jour et les gardiens.</span></p></div>
    <h2 style="font-size:1.6rem">Objets</h2>
    <div>${OBJETS.map(o => `<div class="objet-ligne"><span class="ic">${ICONES[o.icone]}</span><div><b>${esc(o.nom)}</b><p class="doux">${esc(o.texte)} Tu en as ${p.objets[o.id] || 0}.</p></div>
      <button class="btn-prix" data-acheter="${o.id}" ${p.pepites >= o.prix ? "" : "disabled"}>${o.prix} ${ICONES.gemme}</button></div>`).join("")}</div>
    <h2 style="font-size:1.6rem">Titres</h2><p class="doux">Ton titre s'affiche sous ton nom dans le classement.</p>
    <div>${TITRES.map(t => { const a = p.titres.includes(t.id); return `<div class="objet-ligne"><span class="ic">${ICONES.couronne}</span><div><b>${esc(t.nom)}</b>
      <p class="doux">${a ? (p.titre === t.nom ? "Porté" : "Acheté") : "À acheter"}</p></div>
      ${a ? `<button class="btn-prix" data-porter="${t.id}">${p.titre === t.nom ? "Retirer" : "Porter"}</button>` : `<button class="btn-prix" data-acheter="${t.id}" ${p.pepites >= t.prix ? "" : "disabled"}>${t.prix} ${ICONES.gemme}</button>`}</div>`; }).join("")}</div>`;
}

// mini-carte de l'accueil (bande sinueuse, région courante en jaune)
export function miniCarte(p) {
  const n = FAMILLES.length, c = regionCourante(p), W = 400, pts = FAMILLES.map((_, i) => ({ x: 22 + i * (W - 44) / (n - 1), y: i % 2 ? 70 : 40 }));
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < n; i++) { const a = pts[i - 1], b = pts[i], m = (a.x + b.x) / 2; d += ` C ${m} ${a.y}, ${m} ${b.y}, ${b.x} ${b.y}`; }
  const noeuds = pts.map((q, i) => {
    const e = etatRegion(p, i).etat, col = i === c ? "#ffc61e" : e === "vaincue" ? "#1f9d55" : i === 0 && e !== "vaincue" ? "#e0262b" : "#3a4290";
    return `<circle cx="${q.x}" cy="${q.y}" r="${i === c ? 13 : 11}" fill="${i === c ? "#12163a" : "#2b3373"}" stroke="${col}" stroke-width="${i === c ? 5 : 3}"/>`;
  }).join("");
  const q = pts[c];
  return `<svg viewBox="0 0 ${W} 100" aria-hidden="true"><path d="${d}" stroke="#2b3373" stroke-width="22" fill="none" stroke-linecap="round"/>
    <path d="${d}" stroke="#ffc61e" stroke-width="2" fill="none" stroke-dasharray="7 9" opacity=".8"/>${noeuds}
    <g transform="translate(${q.x - 13} ${q.y - 50})"><rect x="11.5" y="22" width="3" height="14" fill="#9aa0c0"/><g transform="scale(.27)">${LOGO.replace(/<\/?svg[^>]*>/g, "")}</g></g></svg>`;
}
