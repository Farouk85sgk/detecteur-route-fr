// Quiz : séries de 10 questions (tout le code, une famille, le dernier trajet, l'album, les erreurs à revoir),
// donjons des gardiens (cœurs et objets), examen blanc (40 questions, 35 pour réussir), séries importées.
import { FAMILLES, QUETE, VITESSE_APRES } from "./contenu.js";
import { D, famille, icone, itemsFamille, officiels } from "./donnees.js";
import { aller } from "./nav.js";
import { evenement, gagner, majCoeurs, minutesProchainCoeur, verifierBadges } from "./progression.js";
import { listerPacks } from "./series.js";
import { profil, sauver } from "./stockage.js";
import { $, ICONES, esc, ilYa, melanger, son, toast } from "./ui.js";

let Q = null;  // partie en cours

// ---------- génération des questions ----------
const VITESSES = [30, 50, 70, 80, 90, 110, 130];
const titreGroupe = it => it.groupe === "m" ? "ce marquage" : it.groupe === "f" ? "ce feu" : "ce panneau";
function distracteurs(it, n, cle = x => x.nom) {
  const vus = new Set([cle(it)]), out = [];
  const meme = melanger(itemsFamille(it.famille).filter(x => x !== it));
  const autres = melanger(officiels().filter(x => x.groupe === it.groupe && x.famille !== it.famille));
  for (const x of [...meme, ...autres, ...melanger(officiels())]) {
    if (out.length >= n) break;
    const k = cle(x);
    if (!vus.has(k)) { vus.add(k); out.push(x); }
  }
  return out;
}
function question(it, types) {
  const possibles = types.filter(t => (t !== "vitesse" || VITESSE_APRES[it.code]) && (t !== "sens" || it.groupe !== "u"));
  const type = possibles[Math.floor(Math.random() * possibles.length)] || "regle";
  const q = { code: it.code, type, image: icone(it), explication: it.reflexe || it.explication };
  if (type === "sens") {
    q.texte = `Que signifie ${titreGroupe(it)}\u00a0?`;
    q.choix = melanger([{ label: it.nom, ok: true }, ...distracteurs(it, 3).map(x => ({ label: x.nom }))]);
    q.explication = `${it.nom}. ${it.reflexe}`;
  } else if (type === "image") {
    q.texte = `Lequel signifie «\u00a0${it.nom}\u00a0»\u00a0?`; q.image = null;
    q.choix = melanger([{ img: icone(it), label: it.nom, ok: true }, ...distracteurs(it, 3).map(x => ({ img: icone(x), label: x.nom }))]);
  } else if (type === "regle") {
    q.texte = it.groupe === "u" ? "Tu croises cet usager\u00a0: que fais-tu\u00a0?" : "Que dois-tu faire\u00a0?";
    q.choix = melanger([{ label: it.reflexe, ok: true }, ...distracteurs(it, 3, x => x.reflexe).map(x => ({ label: x.reflexe }))]);
    q.explication = `${it.nom} : ${it.reflexe}`;
  } else {
    const v = VITESSE_APRES[it.code];
    q.texte = "Après ce panneau, quelle est la vitesse maximale autorisée (par temps sec)\u00a0?";
    q.choix = melanger([v, ...melanger(VITESSES.filter(x => x !== v)).slice(0, 3)]).map(x => ({ label: `${x} km/h`, ok: x === v }));
    q.explication = `${it.nom} : ${it.explication}`;
  }
  return q;
}
export function genererQuestions(codes, n, types = ["sens", "sens", "sens", "image", "regle", "vitesse"]) {
  const items = codes.map(c => D.parCode[c]).filter(Boolean);
  if (!items.length) return [];
  let tirage = melanger(items);
  while (tirage.length < n) tirage = tirage.concat(melanger(items));
  return tirage.slice(0, n).map(it => question(it, types));
}

// ---------- menu des quiz ----------
export function pageQuiz(racine) {
  const p = profil(), dernier = p.trajets[0], nAlbum = Object.keys(p.album).length, nRevoir = Object.keys(p.aRevoir).length;
  const nbDernier = dernier ? Object.keys(dernier.elements).length : 0;
  racine.innerHTML = `<div class="page"><div class="entete"><h1>Quiz</h1><button class="btn-rond" data-nav="#/" aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="contenu"><div class="choix-menu">
      ${nbDernier ? `<button class="vedette" data-q="#/quiz/trajet/${dernier.id}"><b>Quiz du dernier trajet</b><span>${nbDernier} élément${nbDernier > 1 ? "s" : ""} repéré${nbDernier > 1 ? "s" : ""} ${ilYa(dernier.fin || dernier.debut)}</span></button>` : ""}
      ${nAlbum ? `<button data-q="#/quiz/album"><b>Mon album</b><span>Sur les ${nAlbum} élément${nAlbum > 1 ? "s" : ""} déjà repéré${nAlbum > 1 ? "s" : ""}</span></button>` : ""}
      <button data-q="#/quiz/tout"><b>Tout le code</b><span>10 questions au hasard</span></button>
      ${nRevoir ? `<button data-q="#/quiz/revoir"><b>À revoir</b><span>${nRevoir} élément${nRevoir > 1 ? "s" : ""} où tu t'es trompé</span></button>` : ""}
      <button data-q="#/quiz/examen"><b>Examen blanc</b><span>40 questions, 20 secondes chacune, 35 bonnes réponses pour réussir</span></button>
      <button data-q="#/codes"><b>Séries de code</b><span>Démo et séries importées de ton auto-école</span></button></div>
      <h3 class="doux" style="font-family:var(--corps);font-size:1.1rem;margin-top:8px">Par famille</h3>
      <div class="grille-familles">${FAMILLES.map(f => `<button data-q="#/quiz/famille/${f.id}"><img src="${esc(icone(D.parCode[f.icone]))}" alt="">${esc(f.nom)}</button>`).join("")}</div>
    </div></div>`;
  racine.onclick = e => { const b = e.target.closest("[data-q]"); if (b) aller(b.dataset.q); };
}

// ---------- lancement d'une partie ----------
export async function lancer(racine, mode, arg, arg2) {
  const p = profil();
  let questions = [], titre = "Quiz", options = {};
  if (mode === "tout") { titre = "Tout le code"; questions = genererQuestions(officiels().map(it => it.code), 10); }
  if (mode === "famille") { const f = famille(arg); titre = f?.nom || "Famille"; questions = genererQuestions(f?.codes || [], 10); options.famille = arg; }
  if (mode === "album") { titre = "Mon album"; questions = genererQuestions(Object.keys(p.album).filter(c => D.parCode[c]), 10); }
  if (mode === "revoir") { titre = "À revoir"; questions = genererQuestions(Object.keys(p.aRevoir), 10); }
  if (mode === "trajet") {
    const t = p.trajets.find(x => x.id === arg) || p.trajets[0];
    titre = "Quiz du trajet"; questions = genererQuestions(Object.keys(t?.elements || {}), Math.min(10, Math.max(5, Object.keys(t?.elements || {}).length * 2)));
  }
  if (mode === "donjon") {
    const f = famille(arg); majCoeurs(p);
    if (p.coeurs <= 0) { toast(`Plus de cœur : le prochain revient dans ${minutesProchainCoeur(p)} min (ou bois une potion)`); return aller("#/quete"); }
    titre = `Donjon : ${f.gardien}`; questions = genererQuestions(f.codes, QUETE.questionsDonjon, ["sens", "sens", "image", "regle", "regle", "vitesse"]);
    options = { donjon: true, famille: arg };
  }
  if (mode === "examen") {
    titre = "Examen blanc";
    const codes = melanger(officiels().map(it => it.code));
    questions = genererQuestions(codes, 40, ["sens", "regle", "regle", "image", "vitesse"]);
    options = { examen: true, chrono: 20 };
  }
  if (mode === "pack") {
    const pack = (await listerPacks()).find(x => x.id === arg), serie = pack?.series[+arg2];
    if (!serie) return aller("#/codes");
    titre = serie.titre;
    questions = melanger(serie.questions).map(q => ({ ...q, importee: true }));
    options = { examen: serie.type === "examen", chrono: serie.type === "examen" ? 20 : 0, pack: pack.id };
    if (serie.type !== "examen") questions = questions.slice(0, 40);
  }
  if (!questions.length) { toast("Rien à réviser ici pour l'instant"); return aller("#/quiz"); }
  Q = { mode, titre, questions, i: 0, score: 0, resultats: [], retour: mode === "donjon" ? "#/quete" : mode === "pack" ? "#/codes" : "#/quiz", ...options, reponse: null, ecartes: [] };
  afficher(racine);
}

// ---------- affichage d'une question ----------
function afficher(racine) {
  const q = Q.questions[Q.i], p = profil(), n = Q.questions.length;
  clearInterval(Q.minuteur);
  const segments = n <= 12 ? `<div class="q-segments">${Q.questions.map((_, k) => `<i class="${k < Q.resultats.length ? (Q.resultats[k] ? "juste" : "faux") : k === Q.i ? "en-cours" : ""}"></i>`).join("")}</div>`
    : `<div class="q-segments"><span class="doux gras">Question ${Q.i + 1}/${n}</span></div>`;
  const multi = q.importee && q.choix.filter(c => c.ok).length > 1;
  racine.innerHTML = `<div class="page"><div class="entete"><h1>${esc(Q.titre)}</h1><button class="btn-rond" data-x="quitter" aria-label="Quitter">${ICONES.fermer}</button></div>
    <div class="q-tete">${segments}${Q.donjon ? `<span class="q-coeurs">${Array.from({ length: QUETE.coeursMax }, (_, k) => k < p.coeurs ? ICONES.coeur : ICONES.coeurVide).join("")}</span>`
      : Q.examen ? "" : `<span class="q-score">${Q.score} ${ICONES.coche.replace("<svg", '<svg width="22" height="22"')}</span>`}</div>
    ${Q.chrono ? `<div class="q-chrono"><i style="width:100%"></i></div>` : ""}
    ${Q.donjon ? `<div class="q-objets"><button data-x="loupe" ${p.objets.loupe ? "" : "disabled"}>${ICONES.loupe} Loupe × ${p.objets.loupe}</button>
      <button data-x="potion" ${p.objets.potion && p.coeurs < QUETE.coeursMax ? "" : "disabled"} style="color:inherit">${ICONES.potion.replace('stroke="#fff"', 'stroke="currentColor"')} Potion × ${p.objets.potion}</button></div>` : ""}
    ${q.image ? `<div class="q-image ${q.importee && !q.image.startsWith("icones/") ? "photo" : ""}"><img src="${esc(q.image)}" alt="" referrerpolicy="no-referrer"></div>` : '<div style="height:24px"></div>'}
    <h2 class="q-question">${esc(q.texte)}</h2>
    <div class="q-choix ${q.choix.some(c => c.img) ? "images" : ""}">${q.choix.map((c, k) => `<button data-c="${k}" ${Q.ecartes.includes(k) ? "disabled class=\"ecarte\"" : ""}>${c.img ? `<img src="${esc(c.img)}" alt="${esc(c.label)}">` : esc(c.label)}</button>`).join("")}</div>
    ${multi ? `<p class="doux centre" style="margin-top:10px">Plusieurs bonnes réponses possibles</p>` : ""}
    <div class="q-suite"></div></div>`;
  const choisis = new Set();
  racine.onclick = e => {
    const x = e.target.closest("[data-x]")?.dataset.x;
    if (x === "quitter") { clearInterval(Q.minuteur); const r = Q.retour; Q = null; return aller(r); }
    if (x === "loupe") return utiliserLoupe(racine);
    if (x === "potion") { p.objets.potion--; p.coeurs = Math.min(QUETE.coeursMax, p.coeurs + 1); sauver(); son("piece", p.reglages.sons); return afficher(racine); }
    if (x === "suivant") return suivante(racine);
    if (x === "valider") return repondre(racine, [...choisis]);
    const b = e.target.closest("[data-c]");
    if (!b || Q.reponse) return;
    if (multi) { const k = +b.dataset.c; choisis.has(k) ? choisis.delete(k) : choisis.add(k); b.classList.toggle("choisi"); $(".q-suite", racine).innerHTML = choisis.size ? '<div class="q-pied"><button class="btn btn-plein btn-grand" data-x="valider">Valider</button></div>' : ""; return; }
    repondre(racine, [+b.dataset.c]);
  };
  if (Q.chrono) {
    const fin = Date.now() + Q.chrono * 1000, barre = $(".q-chrono i", racine);
    requestAnimationFrame(() => (barre.style.width = "0%"));
    barre.style.transition = `width ${Q.chrono}s linear`;
    Q.minuteur = setInterval(() => { if (Date.now() >= fin && Q && !Q.reponse) repondre(racine, []); }, 250);
  }
}

function utiliserLoupe(racine) {
  const p = profil(), q = Q.questions[Q.i];
  if (!p.objets.loupe || Q.ecartes.length) return;
  p.objets.loupe--; sauver();
  Q.ecartes = melanger(q.choix.map((c, k) => (c.ok ? null : k)).filter(k => k !== null)).slice(0, 2);
  son("clic", p.reglages.sons);
  afficher(racine);
}

function repondre(racine, ks) {
  const q = Q.questions[Q.i], p = profil();
  clearInterval(Q.minuteur);
  const bonnes = q.choix.map((c, k) => (c.ok ? k : -1)).filter(k => k >= 0);
  const juste = ks.length === bonnes.length && ks.every(k => bonnes.includes(k));
  Q.reponse = ks;
  Q.resultats.push(juste);
  q.donnee = ks;
  if (juste) Q.score++;
  if (q.code && !q.importee) {
    if (juste) { if (p.aRevoir[q.code] && --p.aRevoir[q.code] <= 0) delete p.aRevoir[q.code]; }
    else p.aRevoir[q.code] = (p.aRevoir[q.code] || 0) + 1;
  }
  if (Q.examen) { Q.reponse = null; Q.ecartes = []; return suivante(racine, true); }
  son(juste ? "juste" : "faux", p.reglages.sons);
  if (Q.donjon && !juste) { p.coeurs = Math.max(0, p.coeurs - 1); p.coeursMaj = p.coeurs < QUETE.coeursMax && p.coeurs === QUETE.coeursMax - 1 ? Date.now() : p.coeursMaj; }
  sauver();
  racine.querySelectorAll("[data-c]").forEach(b => {
    const k = +b.dataset.c;
    b.disabled = true;
    if (bonnes.includes(k)) b.classList.add("juste");
    else if (ks.includes(k)) b.classList.add("faux");
  });
  const fin = Q.donjon && p.coeurs <= 0;
  $(".q-suite", racine).innerHTML = `<div class="q-explication ${juste ? "" : "faux"}"><b>${juste ? "Bonne réponse !" : ks.length ? "Raté…" : "Temps écoulé"}</b>${esc(q.explication || "")}</div>
    <div class="q-pied"><button class="btn btn-plein btn-grand" data-x="suivant">${fin ? "Voir le résultat" : Q.i + 1 < Q.questions.length ? "Continuer" : "Voir le résultat"}</button></div>`;
  if (Q.donjon) racine.querySelector(".q-coeurs").innerHTML = Array.from({ length: QUETE.coeursMax }, (_, k) => k < p.coeurs ? ICONES.coeur : ICONES.coeurVide).join("");
  else racine.querySelector(".q-score").innerHTML = `${Q.score} ${ICONES.coche.replace("<svg", '<svg width="22" height="22"')}`;
  racine.querySelector("[data-x=suivant]").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function suivante(racine, examen = false) {
  const p = profil();
  Q.reponse = null; Q.ecartes = [];
  if ((Q.donjon && p.coeurs <= 0) || Q.i + 1 >= Q.questions.length) return resultat(racine);
  Q.i++;
  afficher(racine);
  if (!examen) scrollTo({ top: 0 });
}

// ---------- résultat et récompenses ----------
function resultat(racine) {
  const p = profil(), n = Q.resultats.length, k = Q.score, gains = { xp: 0, pepites: 0 };
  let titre, message, detail = "";
  p.stats.reponses += n; p.stats.justes += k;
  if (Q.donjon) {
    const f = famille(Q.famille), gagne = p.coeurs > 0 && n === Q.questions.length;
    p.stats.donjons++;
    if (gagne) {
      const premiere = !p.gardiens[f.id];
      p.gardiens[f.id] ||= Date.now();
      gains.xp = 100; gains.pepites = premiere ? QUETE.recompenseGardien : 15;
      titre = premiere ? "Gardien vaincu !" : "Victoire !";
      message = premiere ? `Tu as battu ${f.gardien} et gagné un éclat du Panneau d'Or.` : `${f.gardien} s'incline encore une fois.`;
      son("victoire", p.reglages.sons);
    } else {
      titre = "Le gardien a gagné…"; message = `Plus de cœur. ${f.gardien.charAt(0).toUpperCase() + f.gardien.slice(1)} t'attend : révise la famille « ${f.nom} » et reviens.`;
      gains.xp = 5 * k; son("defaite", p.reglages.sons);
    }
  } else if (Q.examen) {
    const reussi = k >= 35 && n === 40;
    titre = reussi ? "Examen réussi !" : "Examen non réussi"; message = `${k} bonnes réponses sur ${n}. Il en faut 35 sur 40.`;
    if (!Q.pack || n === 40) p.examens.push({ date: Date.now(), score: k, total: n });
    gains.xp = 5 * k; gains.pepites = reussi ? 30 : 5;
    son(reussi ? "victoire" : "defaite", p.reglages.sons);
    const erreurs = Q.questions.filter((q, i) => !Q.resultats[i]);
    if (erreurs.length) detail = `<h3>À retenir</h3><div class="liste-lignes">${erreurs.map(q => `<div class="element-liste" style="align-items:flex-start">
      ${q.image ? `<img src="${esc(q.image)}" alt="" style="width:52px;height:52px;object-fit:contain;flex:none">` : ""}<div style="flex:1"><b>${esc(q.texte)}</b>
      <div class="doux">Réponse : ${esc(q.choix.filter(c => c.ok).map(c => c.label).join(" ; "))}</div>${q.explication ? `<div class="doux petit">${esc(q.explication)}</div>` : ""}</div></div>`).join("")}</div>`;
  } else {
    const parfait = k === n && n >= 5;
    p.stats.series++;
    if (parfait) p.stats.parfaits++;
    gains.xp = 10 * k; gains.pepites = 2 * k + (parfait ? 10 : 0);
    titre = parfait ? "Sans faute !" : k >= n * 0.7 ? "Bien joué !" : "Continue !";
    message = `${k} bonne${k > 1 ? "s" : ""} réponse${k > 1 ? "s" : ""} sur ${n}.`;
    evenement("serie");
    if (parfait) evenement("sansfaute");
    if (Q.famille) { p.stats.familles++; evenement("famille"); }
    son(parfait ? "victoire" : "juste", p.reglages.sons);
  }
  if (k) evenement("juste", k);
  gagner(p, gains);
  verifierBadges(p);
  sauver();
  const rejouer = location.hash;
  racine.innerHTML = `<div class="page"><div class="entete"><h1>${esc(Q.titre)}</h1><button class="btn-rond" data-x="retour" aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="resultat"><div class="gros">${k}/${n}</div><h2>${esc(titre)}</h2><p class="doux">${esc(message)}</p>
      <div class="gains">${gains.xp ? `<span>+${gains.xp} XP</span>` : ""}${gains.pepites ? `<span class="pep">${ICONES.gemme} +${gains.pepites}</span>` : ""}</div></div>
    <div class="contenu">${detail}<button class="btn btn-plein btn-grand" data-x="rejouer">${Q.donjon ? "Retenter" : "Rejouer"}</button><button class="btn" data-x="retour">Retour</button></div></div>`;
  const retour = Q.retour;
  Q = null;
  racine.onclick = e => {
    const x = e.target.closest("[data-x]")?.dataset.x;
    if (x === "retour") aller(retour);
    if (x === "rejouer") { history.replaceState(null, "", rejouer); aller(rejouer); }
  };
}
export const partieEnCours = () => !!Q;
