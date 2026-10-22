// Profils (localStorage) et données lourdes (IndexedDB : photos des trajets, panneaux appris, séries importées).
// Tout reste sur le téléphone.
import { COULEURS_PROFIL } from "./contenu.js";

const CLE = "repere.v1";
export const S = { etat: null };

function profilVide(nom, couleur) {
  return {
    id: "p" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), nom, couleur, cree: Date.now(), fond: "sauge",
    reglages: {
      voix: true, vibration: true, lireLimitations: true, expliquer: false, photos: true, gps: true, video: false, paysage: false, sons: true,
      qualite: "auto", debug: false, familles: {}, exclus: [], reseau: "avec",
    },
    xp: 0, pepites: 0, coeurs: 3, coeursMaj: Date.now(), objets: { loupe: 1, potion: 1, bouclier: 0 }, titres: [], titre: null,
    album: {}, trajets: [], examens: [], gardiens: {}, badges: {}, amis: [], aRevoir: {},
    stats: { series: 0, reponses: 0, justes: 0, parfaits: 0, donjons: 0, minutes: 0, photos: 0, familles: 0, mysteres: 0 },
    flamme: { jours: 0, record: 0, dernier: null }, jour: null,
  };
}

// complète un profil enregistré par une version plus ancienne de l'appli
function completer(p) {
  const v = profilVide(p.nom, p.couleur);
  for (const k of Object.keys(v)) {
    if (p[k] === undefined) p[k] = v[k];
    else if (v[k] && typeof v[k] === "object" && !Array.isArray(v[k]) && k !== "album" && k !== "gardiens" && k !== "badges" && k !== "aRevoir")
      for (const kk of Object.keys(v[k])) if (p[k][kk] === undefined) p[k][kk] = v[k][kk];
  }
  return p;
}

export function charger() {
  try { S.etat = JSON.parse(localStorage.getItem(CLE)); } catch { S.etat = null; }
  if (!S.etat?.profils || !Object.keys(S.etat.profils).length) {
    const p = profilVide("Mon profil", COULEURS_PROFIL[0]);
    S.etat = { actif: p.id, profils: { [p.id]: p } };
  }
  Object.values(S.etat.profils).forEach(completer);
  if (!S.etat.profils[S.etat.actif]) S.etat.actif = Object.keys(S.etat.profils)[0];
  sauver();
}

export const profil = () => S.etat.profils[S.etat.actif];
export const profils = () => Object.values(S.etat.profils).sort((a, b) => a.cree - b.cree);

let attente = null;
export function sauver() {
  clearTimeout(attente);
  attente = setTimeout(() => {
    try { localStorage.setItem(CLE, JSON.stringify(S.etat)); } catch (e) { console.warn("Enregistrement impossible", e); }
  }, 60);
}
addEventListener("pagehide", () => { clearTimeout(attente); try { localStorage.setItem(CLE, JSON.stringify(S.etat)); } catch { /* plein */ } });

export function ajouterProfil(nom) {
  const n = profils().length;
  const p = profilVide(nom, COULEURS_PROFIL[n % COULEURS_PROFIL.length]);
  S.etat.profils[p.id] = p;
  S.etat.actif = p.id;
  sauver();
  return p;
}
export function changerProfil(id) { if (S.etat.profils[id]) { S.etat.actif = id; sauver(); } }
export function renommer(id, nom) { if (S.etat.profils[id] && nom) { S.etat.profils[id].nom = nom.slice(0, 40); sauver(); } }
export async function supprimerProfil(id) {
  delete S.etat.profils[id];
  if (!Object.keys(S.etat.profils).length) { const p = profilVide("Mon profil", COULEURS_PROFIL[0]); S.etat.profils[p.id] = p; }
  if (!S.etat.profils[S.etat.actif]) S.etat.actif = profils()[0].id;
  sauver();
  await idbSupprimerPrefixe("photos", id + "/");
  for (const { cle, valeur } of await idbTout("appris")) if (valeur.profil === id) await idbSupprimer("appris", cle);
}
export async function effacerHistorique(p) {
  for (const t of p.trajets) await idbSupprimerPrefixe("photos", `${p.id}/${t.id}/`);
  for (const a of Object.values(p.album)) delete a.photo;
  p.trajets = [];
  sauver();
}

// ---------- IndexedDB ----------
let base = null;
function db() {
  base ??= new Promise((ok, ko) => {
    const r = indexedDB.open("repere", 1);
    r.onupgradeneeded = () => { for (const s of ["photos", "appris", "series"]) r.result.createObjectStore(s); };
    r.onsuccess = () => ok(r.result);
    r.onerror = () => ko(r.error);
  });
  return base;
}
async function tx(store, mode, fn) {
  try {
    const d = await db();
    return await new Promise((ok, ko) => {
      const t = d.transaction(store, mode), s = t.objectStore(store);
      const r = fn(s);
      t.oncomplete = () => ok(r?.result);
      t.onerror = () => ko(t.error);
    });
  } catch (e) { console.warn("IndexedDB", e); return undefined; }
}
export const idbMettre = (store, cle, valeur) => tx(store, "readwrite", s => s.put(valeur, cle));
export const idbLire = (store, cle) => tx(store, "readonly", s => s.get(cle));
export const idbSupprimer = (store, cle) => tx(store, "readwrite", s => s.delete(cle));
export async function idbTout(store, prefixe = "") {
  try {
    const d = await db();
    return await new Promise((ok, ko) => {
      const out = [];
      const range = prefixe ? IDBKeyRange.bound(prefixe, prefixe + "￿") : undefined;
      const r = d.transaction(store).objectStore(store).openCursor(range);
      r.onsuccess = () => { const c = r.result; if (c) { out.push({ cle: c.key, valeur: c.value }); c.continue(); } else ok(out); };
      r.onerror = () => ko(r.error);
    });
  } catch { return []; }
}
export async function idbSupprimerPrefixe(store, prefixe) {
  return tx(store, "readwrite", s => s.delete(IDBKeyRange.bound(prefixe, prefixe + "￿")));
}
