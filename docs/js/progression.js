// Progression du joueur : XP et niveaux, pépites, cœurs, album, quêtes du jour, panneau mystère, flamme (jours de
// suite), gardiens de la carte, badges et statistiques du classement.
import { BADGES, FAMILLES, NOMS_NIVEAUX, QUETE, QUETES_DU_JOUR } from "./contenu.js";
import { D, itemsFamille, officiels } from "./donnees.js";
import { profil, profils, sauver } from "./stockage.js";
import { graine, jourCle, melanger, son, toast, vibrer } from "./ui.js";

export const PROG = { notifier: (texte, badge) => toast(texte, badge) };
const dire = (texte, badge) => PROG.notifier(texte, badge);

// ---------- niveaux ----------
export const xpNiveau = n => 50 * n * (n - 1);
export function niveau(xp) {
  let n = 1;
  while (xp >= xpNiveau(n + 1)) n++;
  return { n, nom: NOMS_NIVEAUX[Math.min(n, NOMS_NIVEAUX.length) - 1], debut: xpNiveau(n), fin: xpNiveau(n + 1), reste: xpNiveau(n + 1) - xp };
}
export function gagner(p, { xp = 0, pepites = 0 } = {}) {
  const avant = niveau(p.xp).n;
  p.xp += xp;
  p.pepites += pepites;
  const apres = niveau(p.xp);
  if (apres.n > avant) { dire(`Niveau ${apres.n} : ${apres.nom} !`, "Bravo"); son("victoire", p.reglages.sons); }
  sauver();
}

// ---------- cœurs (donjons) : un cœur revient toutes les 20 minutes ----------
export function majCoeurs(p) {
  const pas = QUETE.minutesParCoeur * 60000;
  if (p.coeurs >= QUETE.coeursMax) { p.coeursMaj = Date.now(); return; }
  const gagnes = Math.floor((Date.now() - p.coeursMaj) / pas);
  if (gagnes > 0) { p.coeurs = Math.min(QUETE.coeursMax, p.coeurs + gagnes); p.coeursMaj += gagnes * pas; sauver(); }
}
export const minutesProchainCoeur = p => Math.max(1, Math.ceil((p.coeursMaj + QUETE.minutesParCoeur * 60000 - Date.now()) / 60000));

// ---------- album ----------
export const nbAlbum = p => Object.keys(p.album).filter(c => D.parCode[c] && D.parCode[c].index < D.nbOfficiels).length;
export const vuFamille = (p, id) => itemsFamille(id).filter(it => p.album[it.code]).length;
export function noterAlbum(p, code, quand = Date.now()) {
  const neuf = !p.album[code];
  const a = p.album[code] ??= { premier: quand, vu: 0 };
  a.vu++;
  a.dernier = quand;
  if (neuf && D.parCode[code]?.index < D.nbOfficiels) {
    gagner(p, { xp: 20, pepites: 10 });
    const f = FAMILLES.find(f => f.codes.includes(code));
    if (f && vuFamille(p, f.id) === f.codes.length) dire(`Famille complète : ${f.nom}`, "+50 💎"), gagner(p, { pepites: 50 });
  } else gagner(p, { xp: 2 });
  return neuf;
}

// ---------- journée : quêtes du jour, panneau mystère, coffre, flamme ----------
export function assurerJour(p) {
  const jour = jourCle();
  if (p.jour?.date === jour) return p.jour;
  const r = graine(p.id + jour);
  const route = melanger(QUETES_DU_JOUR.filter(q => q.type === "route"), r);
  const quiz = melanger(QUETES_DU_JOUR.filter(q => q.type === "quiz"), r);
  const choix = [route[0], quiz[0], melanger([...route.slice(1), ...quiz.slice(1)], r)[0]];
  // panneau mystère : de préférence un élément encore absent de l'album, dans une famille déjà ouverte sur la carte
  const ouvertes = new Set(FAMILLES.filter((f, i) => etatRegion(p, i).etat !== "bloquee").map(f => f.id));
  let pool = officiels().filter(it => !p.album[it.code] && ouvertes.has(it.famille));
  if (!pool.length) pool = officiels().filter(it => !p.album[it.code]);
  if (!pool.length) pool = officiels();
  const mystere = pool[Math.floor(r() * pool.length)];
  p.jour = { date: jour, quetes: choix.map(q => ({ id: q.id, avance: 0 })), coffre: false, mystere: mystere.code, trouve: false };
  sauver();
  return p.jour;
}
export const queteDef = id => QUETES_DU_JOUR.find(q => q.id === id);
export const nbQuetesFaites = p => assurerJour(p).quetes.filter(q => q.avance >= queteDef(q.id).but).length;

function majFlamme(p) {
  const f = p.flamme, jour = jourCle();
  if (f.dernier === jour) return;
  const hier = jourCle(Date.now() - 86400000);
  if (f.dernier === hier || f.jours === 0) f.jours += 1;
  else {
    // jours oubliés : un bouclier par jour manqué protège la série
    const manques = Math.round((new Date(jour) - new Date(f.dernier)) / 86400000) - 1;
    if (manques > 0 && p.objets.bouclier >= manques) { p.objets.bouclier -= manques; f.jours += 1; dire(`Bouclier utilisé : ta flamme est sauvée`, `${manques} jour${manques > 1 ? "s" : ""}`); }
    else f.jours = 1;
  }
  f.dernier = jour;
  f.record = Math.max(f.record, f.jours);
  dire(`${f.jours} jour${f.jours > 1 ? "s" : ""} de suite`, "🔥");
}

// Événements de jeu : avancent les quêtes du jour. types : trajet (minutes), repere, nouveau, serie, juste, sansfaute, famille
export function evenement(type, n = 1, p = profil()) {
  const j = assurerJour(p);
  for (const q of j.quetes) {
    const def = queteDef(q.id);
    const concerne = { trajet5: type === "trajet" && n >= 5, reperer5: type === "repere", nouveau: type === "nouveau", serie: type === "serie",
      justes10: type === "juste", sansfaute: type === "sansfaute", famille: type === "famille" }[q.id];
    if (!concerne || q.avance >= def.but) continue;
    q.avance = Math.min(def.but, q.avance + (q.id === "trajet5" ? 1 : n));
    if (q.avance >= def.but) {
      gagner(p, { pepites: def.gain, xp: 15 });
      dire(`Quête du jour : ${def.texte}`, `+${def.gain} 💎`);
      son("piece", p.reglages.sons);
      majFlamme(p);
    }
  }
  verifierBadges(p);
  sauver();
}

export function ouvrirCoffre(p) {
  const j = assurerJour(p);
  if (j.coffre || nbQuetesFaites(p) < 3) return null;
  j.coffre = true;
  const r = Math.random();
  const lot = r < 0.6 ? { pepites: 30 + Math.floor(Math.random() * 4) * 10 } : { objet: ["loupe", "potion", "bouclier"][Math.floor(Math.random() * 3)] };
  if (lot.pepites) gagner(p, { pepites: lot.pepites, xp: 20 });
  else { p.objets[lot.objet] = (p.objets[lot.objet] || 0) + 1; gagner(p, { xp: 20 }); }
  sauver();
  return lot;
}

export function verifierMystere(p, code) {
  const j = assurerJour(p);
  if (j.trouve || j.mystere !== code) return false;
  j.trouve = true;
  p.stats.mysteres++;
  gagner(p, { pepites: 40, xp: 30 });
  dire(`Panneau mystère trouvé : ${D.parCode[code].nom}`, "+40 💎");
  son("victoire", p.reglages.sons);
  vibrer([80, 60, 80], p.reglages.vibration);
  verifierBadges(p);
  return true;
}

// ---------- carte de la quête : une région par famille ----------
export function etatRegion(p, i) {
  const f = FAMILLES[i];
  const besoin = Math.min(QUETE.reperages, f.codes.length);
  const vus = vuFamille(p, f.id);
  if (p.gardiens[f.id]) return { etat: "vaincue", vus, besoin };
  if (i > 0 && !p.gardiens[FAMILLES[i - 1].id]) return { etat: "bloquee", vus, besoin };
  if (vus < besoin) return { etat: "reperage", vus, besoin };
  return { etat: "gardien", vus, besoin };
}
export const regionCourante = p => { const i = FAMILLES.findIndex((f, k) => etatRegion(p, k).etat !== "vaincue"); return i < 0 ? FAMILLES.length - 1 : i; };
export const nbEclats = p => FAMILLES.filter(f => p.gardiens[f.id]).length;

// ---------- badges ----------
const CONDITIONS = {
  trajet1: p => p.trajets.length > 0,
  album10: p => nbAlbum(p) >= 10, album25: p => nbAlbum(p) >= 25, album50: p => nbAlbum(p) >= 50,
  famille: p => FAMILLES.some(f => vuFamille(p, f.id) === f.codes.length),
  serie1: p => p.stats.series > 0, parfait: p => p.stats.parfaits > 0, justes100: p => p.stats.justes >= 100,
  gardien1: p => nbEclats(p) >= 1, gardien5: p => nbEclats(p) >= 5,
  examen: p => p.examens.some(e => e.score >= 35),
  flamme3: p => p.flamme.record >= 3, flamme7: p => p.flamme.record >= 7,
  mystere: p => p.stats.mysteres > 0, photos20: p => p.stats.photos >= 20, prof: p => (p.stats.appris || 0) > 0,
};
export function verifierBadges(p = profil()) {
  for (const b of BADGES) {
    if (!p.badges[b.id] && CONDITIONS[b.id]?.(p)) {
      p.badges[b.id] = Date.now();
      gagner(p, { xp: 25 });
      dire(`Badge obtenu : ${b.nom}`, "🏅");
    }
  }
}
export const nbBadges = p => BADGES.filter(b => p.badges[b.id]).length;

// ---------- classement (8 catégories) ----------
export function statsClassement(p) {
  const rep = p.stats.reponses, ok = p.stats.justes;
  return {
    explorateur: nbAlbum(p),
    batisseur: (p.stats.appris || 0) + Object.values(p.album).filter(a => a.photo).length,
    erudit: rep >= 10 ? Math.round(100 * ok / rep) : 0,
    marathonien: p.stats.series,
    examen: Math.max(0, ...p.examens.map(e => e.score)),
    routier: Math.round(p.stats.minutes),
    flamme: p.flamme.record,
    conquerant: nbEclats(p),
  };
}
export function participants(p) {
  const moi = profils().map(x => ({ id: x.id, nom: x.nom, couleur: x.couleur, titre: x.titre, stats: statsClassement(x), toi: x.id === p.id }));
  const amis = (p.amis || []).map(a => ({ ...a, ami: true }));
  return [...moi, ...amis];
}

// Code ami : statistiques compressées dans un texte à copier (rien n'est envoyé sur Internet)
export function codeAmi(p) {
  const s = statsClassement(p);
  const donnees = { i: p.id, n: p.nom, c: p.couleur, t: p.titre, s: Object.values(s), d: Date.now() };
  return "REPERE-" + btoa(unescape(encodeURIComponent(JSON.stringify(donnees)))).replace(/=+$/, "");
}
export function lireCodeAmi(code) {
  try {
    const brut = code.trim().replace(/^REPERE-/, "");
    const d = JSON.parse(decodeURIComponent(escape(atob(brut))));
    const cles = ["explorateur", "batisseur", "erudit", "marathonien", "examen", "routier", "flamme", "conquerant"];
    if (!d.i || !Array.isArray(d.s) || d.s.length !== 8) return null;
    return { id: String(d.i).slice(0, 40), nom: String(d.n || "Ami").slice(0, 40), couleur: /^#[0-9a-f]{6}$/i.test(d.c) ? d.c : "#5b6475",
      titre: typeof d.t === "string" ? d.t.slice(0, 40) : null, stats: Object.fromEntries(cles.map((k, j) => [k, Math.max(0, Math.min(1e6, Number(d.s[j]) || 0))])), date: Number(d.d) || Date.now() };
  } catch { return null; }
}
