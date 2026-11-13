// « Code de la route » : la banque de questions intégrée (series/banque.json : les dix thèmes de l'examen, compilée par
// tools/construire_series.py), avec la progression du profil, les erreurs à revoir et l'examen blanc ; plus les séries
// d'un prestataire (auto-école, éditeur) importées depuis un fichier JSON ou un lien, communes à tous les profils du
// téléphone (format : voir README), et une démo sur les panneaux.
import { APP } from "./contenu.js";
import { D, icone, officiels } from "./donnees.js";
import { aller } from "./nav.js";
import { idbMettre, idbSupprimer, idbTout, profil } from "./stockage.js";
import { blocVisible, montrerBloc } from "./reglages.js";
import { ICONES, confirmer, demander, esc, graine, melanger, ouvrirFeuille, toast } from "./ui.js";

// ---------- banque intégrée ----------
let BANQUE = null;
export async function banque() {
  if (!BANQUE) {
    const b = await (await fetch("series/banque.json")).json();
    b.parId = {};
    for (const lot of b.lots) for (const q of lot.questions) { q.theme = lot.theme; q.lot = lot.id; b.parId[q.id] = q; }
    for (const t of b.themes) { t.lots = b.lots.filter(l => l.theme === t.id); t.questions = t.lots.flatMap(l => l.questions); }
    b.total = Object.keys(b.parId).length;
    BANQUE = b;
  }
  return BANQUE;
}
const reussies = (p, qs) => qs.filter(q => p.code.q[q.id] === 1).length;
export const nbErreursCode = (p, b) => Object.keys(p.code.q).filter(id => p.code.q[id] === 0 && b.parId[id]).length;
export const themesMaitrises = (p, b) => b.themes.filter(t => t.questions.length && reussies(p, t.questions) === t.questions.length).length;

// question de la banque -> question du quiz (réponses mélangées, sauf Oui / Non)
function versQuiz(q) {
  const choix = q.c.map((label, k) => ({ label, ok: q.b.includes(k) }));
  return { qid: q.id, texte: q.q, image: q.p && D.parCode[q.p] ? icone(D.parCode[q.p]) : null, explication: q.e, importee: true,
    choix: q.c.length === 2 && /^(oui|non)$/i.test(q.c[0]) ? choix : melanger(choix) };
}

// Parties du quiz : examen (40 questions réparties par thème comme à l'épreuve), série d'un lot, 10 questions d'un thème
// (celles jamais réussies d'abord), erreurs à revoir.
export async function partieCode(genre, id) {
  const b = await banque(), p = profil();
  if (genre === "examen") {
    const qs = b.themes.flatMap(t => melanger(t.questions).slice(0, t.examen));
    return { titre: "Examen blanc du code", questions: melanger(qs).map(versQuiz), options: { examen: true, chrono: 30, code: "examen" } };
  }
  if (genre === "lot") {
    const lot = b.lots.find(l => l.id === id);
    return lot && { titre: lot.titre, questions: lot.questions.map(versQuiz), options: { code: "lot", lot: lot.id } };
  }
  if (genre === "theme") {
    const t = b.themes.find(x => x.id === id);
    if (!t) return null;
    const tri = melanger(t.questions).sort((x, y) => (p.code.q[x.id] ?? -1) - (p.code.q[y.id] ?? -1));  // jamais vues, puis ratées, puis réussies
    return { titre: t.nom, questions: melanger(tri.slice(0, 10)).map(versQuiz), options: { code: "theme" } };
  }
  if (genre === "erreurs") {
    const qs = melanger(Object.keys(p.code.q).filter(k => p.code.q[k] === 0 && b.parId[k]).map(k => b.parId[k])).slice(0, 20);
    return { titre: "Mes erreurs", questions: qs.map(versQuiz), options: { code: "erreurs" } };
  }
  return null;
}

// vraies photos de routes françaises pour le quiz « En situation réelle » (tools/photos_quiz.py)
let PHOTOS = null;
export async function photosQuiz() {
  PHOTOS ??= await fetch("series/photos.json").then(r => r.json()).catch(() => ({ photos: [] }));
  return PHOTOS;
}

const jauge = (n, total) => `<div class="jauge"><i style="width:${total ? (100 * n / total).toFixed(1) : 0}%"></i></div>`;

// carte de l'accueil
export async function carteCodes() {
  const b = await banque(), p = profil(), ok = reussies(p, Object.values(b.parId)), err = nbErreursCode(p, b);
  const meilleur = Math.max(0, ...p.examens.filter(e => e.code).map(e => e.score));
  return `<section class="carte carte-codes"><div class="carte-titre"><h2>Code de la route</h2><span class="pastille">${b.total} questions</span></div>
    <p class="doux">Les dix thèmes de l'examen, en séries de 12 questions expliquées, et des examens blancs de 40 questions.</p>
    ${jauge(ok, b.total)}<p class="doux petit">${ok} question${ok > 1 ? "s" : ""} réussie${ok > 1 ? "s" : ""} sur ${b.total}${meilleur ? `. Meilleur examen : ${meilleur}/40` : ""}${err ? `. ${err} à revoir` : ""}</p>
    <div class="duo"><button class="btn btn-plein" data-nav="#/codes">Séries par thème</button><button class="btn" data-nav="#/quiz/code/examen">Examen blanc</button></div></section>`;
}

// page « Code de la route »
export async function pageCodes(zone, rendre) {
  const b = await banque(), p = profil(), err = nbErreursCode(p, b), ok = reussies(p, Object.values(b.parId));
  const packs = await listerPacks();
  zone.innerHTML = `<div class="page"><div class="entete"><h1>Code de la route</h1><button class="btn-rond" data-nav="#/" aria-label="Fermer">${ICONES.fermer}</button></div>
    <div class="contenu zone-codes">
      <div class="choix-menu">
        <button class="vedette" data-nav="#/quiz/code/examen"><b>Examen blanc</b><span>40 questions réparties comme à l'examen, 30 secondes chacune : 35 bonnes réponses pour réussir</span></button>
        ${err ? `<button data-nav="#/quiz/code/erreurs"><b>Mes erreurs</b><span>${err} question${err > 1 ? "s" : ""} à revoir</span></button>` : ""}
      </div>
      <p class="doux">${ok} question${ok > 1 ? "s" : ""} réussie${ok > 1 ? "s" : ""} sur ${b.total}</p>${jauge(ok, b.total)}
      <h3 class="doux" style="font-family:var(--corps);font-size:1.1rem;margin-top:14px">Les dix thèmes de l'examen</h3>
      <div class="liste-lignes">${b.themes.map(t => { const n = reussies(p, t.questions); return `<button class="element-liste" data-theme="${t.id}"><div style="flex:1"><b>${esc(t.nom)}</b>
        <div class="doux">${esc(t.detail)}</div>${jauge(n, t.questions.length)}<div class="doux petit">${n} sur ${t.questions.length} réussies, ${t.examen} question${t.examen > 1 ? "s" : ""} à l'examen</div></div></button>`; }).join("")}</div>
      ${blocVisible("import", p) ? `<section class="carte" style="margin-top:18px"><h2>Séries de ton auto-école</h2>
        <p class="doux">Importe le fichier de séries ou d'examens de ton auto-école, ou ajoute le lien de son catalogue.</p>
        <div class="liste-lignes">${packs.map(pk => `<button class="element-liste" data-pack="${esc(pk.id)}"><div><b>${esc(pk.titre)}</b><div class="doux">${esc([pk.auteur, resume(pk)].filter(Boolean).join(". "))}</div></div></button>`).join("")}</div>
        <div class="duo"><label class="btn btn-plein">Importer un fichier<input type="file" accept=".json,application/json" hidden data-importer></label><button class="btn" data-lien>Ajouter un lien</button></div>
        <button class="btn-lien masquer" data-masquer="import" aria-label="Masquer le bloc : Séries de l'auto-école">Masquer ce bloc</button></section>` : ""}
    </div></div>`;
  const z = zone.querySelector(".zone-codes");
  brancherCodes(z, rendre);
  z.addEventListener("click", e => {
    const t = e.target.closest("[data-theme]");
    if (t) ouvrirTheme(b.themes.find(x => x.id === t.dataset.theme));
    if (e.target.closest("[data-masquer]")) { montrerBloc("import", false, p); toast("Bloc masqué. Pour le revoir : Réglages, « Accueil : ce qui s'affiche »"); rendre(); }
  });
}

function ouvrirTheme(t) {
  const p = profil();
  ouvrirFeuille(t.nom, `<p class="doux">${esc(t.detail)}</p>
    <div class="choix-menu"><button class="vedette" data-nav="#/quiz/code/theme/${t.id}"><b>10 questions du thème</b><span>Celles que tu n'as pas encore réussies d'abord</span></button>
    ${t.lots.map(l => { const m = p.code.lots[l.id], n = reussies(p, l.questions); return `<button data-nav="#/quiz/code/lot/${l.id}"><b>${esc(l.titre)}</b>
      <span>${l.questions.length} questions${m ? `, meilleur score ${m.s}/${m.n}` : ""}${n === l.questions.length ? " ✓" : ""}</span></button>`; }).join("")}</div>`);
}

// ---------- séries importées et démo ----------
const txt = (s, n) => (typeof s === "string" ? s.trim().slice(0, n) : "");

function demo() {
  const r = graine("demo-series");
  const items = officiels().filter(it => it.groupe === "s");
  const q = it => {
    const autres = melanger(items.filter(x => x.famille === it.famille && x !== it), r).slice(0, 3);
    while (autres.length < 3) autres.push(items[Math.floor(r() * items.length)]);
    return { texte: "Que signifie ce panneau ?", image: icone(it), code: it.code, explication: `${it.nom} : ${it.explication}`,
      choix: melanger([{ label: it.nom, ok: true }, ...autres.map(x => ({ label: x.nom }))], r) };
  };
  const serie = (titre, n, type = "serie") => ({ titre, type, questions: melanger(items, r).slice(0, n).map(q) });
  return { id: "demo", titre: `Démo : les panneaux de ${APP.nom}`, auteur: APP.nom, demo: true,
    series: [serie("Série 1", 10), serie("Série 2", 10), { ...serie("Examen blanc", 40, "examen"), questions: melanger(items, r).concat(melanger(items, r)).slice(0, 40).map(q) }] };
}

export async function listerPacks() {
  const importes = (await idbTout("series")).map(x => x.valeur).sort((a, b) => b.ajoute - a.ajoute);
  return [demo(), ...importes];
}

export function lirePack(json, source = "") {
  if (!json || !Array.isArray(json.series)) throw new Error("Fichier non reconnu : il manque la liste « series ».");
  const pack = { id: "pk" + Date.now().toString(36), titre: txt(json.titre, 80) || "Séries importées", auteur: txt(json.auteur, 80), source: txt(source, 300), ajoute: Date.now(), series: [] };
  for (const s of json.series.slice(0, 60)) {
    const questions = (Array.isArray(s.questions) ? s.questions : []).slice(0, 200).map(q => {
      const choix = (Array.isArray(q.choix) ? q.choix : []).slice(0, 6).map(c => txt(String(c), 200)).filter(Boolean);
      const bonnes = (Array.isArray(q.bonnes) ? q.bonnes : [q.bonne]).map(Number).filter(k => Number.isInteger(k) && k >= 0 && k < choix.length);
      if (choix.length < 2 || !bonnes.length) return null;
      let image = null;
      if (typeof q.panneau === "string" && D.parCode[q.panneau]) image = icone(D.parCode[q.panneau]);
      else if (typeof q.image === "string" && /^(https:\/\/|data:image\/(png|jpe?g|webp|gif);base64,)/i.test(q.image) && q.image.length < 2_000_000) image = q.image;
      return { texte: txt(q.question, 300) || "Question", image, code: D.parCode[q.panneau] ? q.panneau : null, explication: txt(q.explication, 600),
        choix: choix.map((label, k) => ({ label, ok: bonnes.includes(k) })) };
    }).filter(Boolean);
    if (questions.length) pack.series.push({ titre: txt(s.titre, 80) || `Série ${pack.series.length + 1}`, type: s.type === "examen" ? "examen" : "serie", questions });
  }
  if (!pack.series.length) throw new Error("Aucune question valable dans ce fichier.");
  return pack;
}

const resume = pk => {
  const s = pk.series.filter(x => x.type !== "examen").length, e = pk.series.length - s;
  return [s && `${s} série${s > 1 ? "s" : ""}`, e && `${e} examen${e > 1 ? "s" : ""} blanc${e > 1 ? "s" : ""}`].filter(Boolean).join(", ");
};

export function brancherCodes(zone, apres) {
  zone.addEventListener("change", async e => {
    if (!e.target.matches("[data-importer]")) return;
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    try { const pk = lirePack(JSON.parse(await f.text()), f.name); await idbMettre("series", pk.id, pk); toast(`Importé : ${pk.titre}`, resume(pk)); apres(); }
    catch (err) { toast(`Import impossible : ${err.message}`); }
  });
  zone.addEventListener("click", async e => {
    if (e.target.closest("[data-lien]")) {
      const url = await demander("Lien du catalogue (fichier JSON)", "", { placeholder: "https://…" });
      if (!url) return;
      try {
        if (!/^https:\/\//i.test(url)) throw new Error("le lien doit commencer par https://");
        const rep = await fetch(url, { mode: "cors", credentials: "omit" });
        if (!rep.ok) throw new Error(`réponse ${rep.status}`);
        const pk = lirePack(await rep.json(), url);
        await idbMettre("series", pk.id, pk);
        toast(`Importé : ${pk.titre}`, resume(pk)); apres();
      } catch (err) { toast(`Lien impossible : ${err.message}`); }
      return;
    }
    const b = e.target.closest("[data-pack]");
    if (b) ouvrirPack(b.dataset.pack, apres);
  });
}

async function ouvrirPack(id, apres) {
  const pk = (await listerPacks()).find(x => x.id === id);
  if (!pk) return;
  const corps = ouvrirFeuille(pk.titre, `${pk.auteur ? `<p class="doux">${esc(pk.auteur)}</p>` : ""}
    <div class="choix-menu">${pk.series.map((s, i) => `<button data-s="${i}"><b>${esc(s.titre)}</b><span>${s.type === "examen" ? "Examen blanc, " : ""}${s.questions.length} question${s.questions.length > 1 ? "s" : ""}</span></button>`).join("")}</div>
    ${pk.demo ? "" : `<button class="btn btn-danger" data-suppr>Supprimer ces séries</button>`}`);
  corps.onclick = async e => {
    const s = e.target.closest("[data-s]");
    if (s) return aller(`#/quiz/pack/${pk.id}/${s.dataset.s}`);
    if (e.target.closest("[data-suppr]") && await confirmer(`Supprimer « ${pk.titre} » ?`, "Pour tous les profils de ce téléphone.", { oui: "Supprimer", danger: true })) {
      await idbSupprimer("series", pk.id); aller("#/"); apres();
    }
  };
}
