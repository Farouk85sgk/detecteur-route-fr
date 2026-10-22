// « Code et examens » : séries de code et examens blancs d'un prestataire (auto-école, éditeur), importés depuis
// un fichier JSON ou un lien, plus une démo intégrée. Communs à tous les profils du téléphone. Format : voir README.
import { APP } from "./contenu.js";
import { D, icone, officiels } from "./donnees.js";
import { aller } from "./nav.js";
import { idbMettre, idbSupprimer, idbTout } from "./stockage.js";
import { confirmer, demander, esc, graine, melanger, ouvrirFeuille, toast } from "./ui.js";

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

export async function carteCodes() {
  const packs = await listerPacks();
  return `<section class="carte carte-codes"><h2>Code et examens</h2>
    <p class="doux">Les séries de code et examens blancs de ton auto-école : importe son fichier ou ajoute le lien de son catalogue.</p>
    <div class="liste-lignes">${packs.map(pk => `<button class="element-liste" data-pack="${esc(pk.id)}"><div><b>${esc(pk.titre)}</b><div class="doux">${esc([pk.auteur, resume(pk)].filter(Boolean).join(". "))}</div></div></button>`).join("")}</div>
    <div class="duo"><label class="btn btn-plein">Importer un fichier<input type="file" accept=".json,application/json" hidden data-importer></label><button class="btn" data-lien>Ajouter un lien</button></div></section>`;
}

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
