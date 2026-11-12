// Service worker : l'appli s'installe sur le téléphone et fonctionne sans réseau.
// « Avec réseau » : pages et scripts vérifiés en ligne à chaque ouverture (mises à jour), modèles en cache.
// « Sans réseau » : tout est servi depuis le téléphone, aucune requête.
// Il ajoute aussi aux pages les en-têtes d'isolation (COOP / COEP) que l'hébergement ne fournit pas : le navigateur
// autorise alors le calcul sur plusieurs cœurs (WebAssembly multi-fils), deux à trois fois plus rapide sans carte graphique.
const VERSION = "repere-3.0.0";
const COEUR = `${VERSION}-coeur`, LOURDS = "repere-lourds-b202a7ae";
const ORT = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
const EXTRAS = ["F_rouge", "F_orange", "F_vert", "U_pieton", "U_cycliste", "U_deux_roues"];
const FICHIERS = ["./", "index.html", "manifest.webmanifest", "favicon.svg", "icone-192.png", "icone-512.png", "css/app.css", "catalogue.json", "panneaux.json", "empreinte.json",
  "series/banque.json", "series/photos.json", "credits.html",
  ...["accueil", "album", "app", "camera", "contenu", "donnees", "mespanneaux", "moteur", "nav", "progression", "quete", "quiz", "reglages", "series", "stockage", "trajets", "ui"].map(m => `js/${m}.js`),
  ...["bricolage-grotesque-latin-600", "bricolage-grotesque-latin-700", "bricolage-grotesque-latin-800", "overpass-latin-400", "overpass-latin-600", "overpass-latin-700"].map(f => `polices/${f}-normal.woff2`)];
const MODELES = ["detecteur.onnx", "panneaux.onnx", "usagers.onnx", "empreinte.onnx", `${ORT}ort.webgpu.min.js`, `${ORT}ort-wasm-simd-threaded.jsep.mjs`, `${ORT}ort-wasm-simd-threaded.jsep.wasm`];
let mode = null, coep = null;

self.addEventListener("install", e => e.waitUntil(caches.open(COEUR).then(c => c.addAll(FICHIERS)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil((async () => {
  const garde = {};  // réglages mémorisés par la version précédente
  for (const k of await caches.keys()) if (k !== COEUR && k.endsWith("-coeur")) for (const cle of ["__mode", "__coep"]) garde[cle] ??= await (await caches.open(k)).match(cle);
  const c = await caches.open(COEUR);
  for (const [cle, rep] of Object.entries(garde)) if (rep && !(await c.match(cle))) await c.put(cle, rep);
  for (const k of await caches.keys()) if (k !== COEUR && k !== LOURDS && k.startsWith("repere-")) await caches.delete(k);
  await self.clients.claim();
})()));

async function reglage(cle, defaut) {
  const r = await (await caches.open(COEUR)).match(cle);
  return r ? await r.text() : defaut;
}
const memoriser = (cle, valeur) => caches.open(COEUR).then(c => c.put(cle, new Response(valeur)));

self.addEventListener("message", e => {
  if (e.data?.type === "mode") { mode = e.data.mode === "sans" ? "sans" : "avec"; e.waitUntil(memoriser("__mode", mode)); }
  if (e.data?.type === "isolation") { coep = ["require-corp", "credentialless"].includes(e.data.coep) ? e.data.coep : "non"; e.waitUntil(memoriser("__coep", coep)); }
  if (e.data?.type === "tout-preparer") e.waitUntil((async () => {
    const c = await caches.open(LOURDS);
    const res = await Promise.allSettled(MODELES.map(async u => { if (!(await c.match(u))) { const r = await fetch(u, { mode: "cors" }); if (!r.ok) throw new Error(u); await c.put(u, r); } }));
    const catalogue = await (await fetch("catalogue.json")).json().catch(() => ({ items: [] }));
    const photos = await (await fetch("series/photos.json")).json().catch(() => ({ photos: [] }));
    const images = [...[...catalogue.items.map(x => x.code), ...EXTRAS].map(code => `icones/${code}.png`), ...photos.photos.map(ph => `series/photos/${ph.f}`)];
    await Promise.allSettled(images.map(async u => { if (!(await c.match(u))) await c.add(u); }));
    e.source?.postMessage({ type: "pret", ok: res.every(r => r.status === "fulfilled") });
  })());
});

const lourd = url => /\.(onnx|wasm|mjs|png|jpg|woff2)$/.test(url.pathname) || url.href.startsWith(ORT);

// page servie avec les en-têtes d'isolation (si l'appli les a demandés pour ce navigateur)
async function isoler(rep) {
  coep ??= await reglage("__coep", "non");
  if (coep === "non" || !rep || rep.status === 0 || rep.type === "opaque") return rep;
  const h = new Headers(rep.headers);
  h.set("Cross-Origin-Opener-Policy", "same-origin");
  h.set("Cross-Origin-Embedder-Policy", coep);
  return new Response(rep.body, { status: rep.status, statusText: rep.statusText, headers: h });
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin && !url.href.startsWith(ORT)) return;
  const page = req.mode === "navigate";
  e.respondWith((async () => {
    mode ??= await reglage("__mode", "avec");
    const cache = await caches.open(lourd(url) ? LOURDS : COEUR);
    const enCache = await cache.match(req, { ignoreSearch: url.origin === location.origin && page });
    const rendre = rep => page ? isoler(rep) : rep;
    if (enCache && (mode === "sans" || lourd(url))) return rendre(enCache);
    try {
      const rep = await fetch(req);
      if (rep.ok && (rep.type === "basic" || rep.type === "cors")) cache.put(req, rep.clone());
      return rendre(rep);
    } catch (err) {
      if (enCache) return rendre(enCache);
      if (page) return rendre((await caches.match("index.html")) || Response.error());
      throw err;
    }
  })());
});
