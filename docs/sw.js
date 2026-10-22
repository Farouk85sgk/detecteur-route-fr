// Service worker : l'appli s'installe sur le téléphone et fonctionne sans réseau.
// « Avec réseau » : pages et scripts vérifiés en ligne à chaque ouverture (mises à jour), modèles en cache.
// « Sans réseau » : tout est servi depuis le téléphone, aucune requête.
const VERSION = "repere-2.0.0";
const COEUR = `${VERSION}-coeur`, LOURDS = "repere-lourds-v1";
const ORT = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
const FICHIERS = ["./", "index.html", "manifest.webmanifest", "favicon.svg", "icone-192.png", "icone-512.png", "css/app.css", "classes.json", "classifieur.json", "empreinte.json",
  ...["accueil", "album", "app", "camera", "contenu", "donnees", "mespanneaux", "moteur", "nav", "progression", "quete", "quiz", "reglages", "series", "stockage", "trajets", "ui"].map(m => `js/${m}.js`),
  ...["bricolage-grotesque-latin-600", "bricolage-grotesque-latin-700", "bricolage-grotesque-latin-800", "overpass-latin-400", "overpass-latin-600", "overpass-latin-700"].map(f => `polices/${f}-normal.woff2`)];
const MODELES = ["modele.onnx", "classifieur.onnx", "usagers.onnx", "empreinte.onnx", `${ORT}ort.webgpu.min.js`, `${ORT}ort-wasm-simd-threaded.jsep.mjs`, `${ORT}ort-wasm-simd-threaded.jsep.wasm`];
let mode = null;

self.addEventListener("install", e => e.waitUntil(caches.open(COEUR).then(c => c.addAll(FICHIERS)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== COEUR && k !== LOURDS && k.startsWith("repere-")) await caches.delete(k);
  await self.clients.claim();
})()));

async function lireMode() {
  if (mode) return mode;
  const r = await (await caches.open(COEUR)).match("__mode");
  return (mode = r ? await r.text() : "avec");
}

self.addEventListener("message", e => {
  if (e.data?.type === "mode") { mode = e.data.mode === "sans" ? "sans" : "avec"; e.waitUntil(caches.open(COEUR).then(c => c.put("__mode", new Response(mode)))); }
  if (e.data?.type === "tout-preparer") e.waitUntil((async () => {
    const c = await caches.open(LOURDS);
    const res = await Promise.allSettled(MODELES.map(async u => { if (!(await c.match(u))) { const r = await fetch(u, { mode: "cors" }); if (!r.ok) throw new Error(u); await c.put(u, r); } }));
    const icones = await (await fetch("classes.json")).json().catch(() => []);
    const ci = await caches.open(COEUR);
    await Promise.allSettled([...icones.map(x => `icones/${x.code}.png`), ...["F_rouge", "F_orange", "F_vert", "U_pieton", "U_cycliste", "U_deux_roues"].map(c2 => `icones/${c2}.png`)].map(u => ci.add(u)));
    e.source?.postMessage({ type: "pret", ok: res.every(r => r.status === "fulfilled") });
  })());
});

const lourd = url => /\.(onnx|wasm|mjs|png|woff2)$/.test(url.pathname) || url.href.startsWith(ORT);

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin && !url.href.startsWith(ORT)) return;
  e.respondWith((async () => {
    const m = await lireMode();
    const cache = await caches.open(lourd(url) ? LOURDS : COEUR);
    const enCache = await cache.match(req, { ignoreSearch: url.origin === location.origin && req.mode === "navigate" });
    if (enCache && (m === "sans" || lourd(url))) return enCache;
    try {
      const rep = await fetch(req);
      if (rep.ok && (rep.type === "basic" || rep.type === "cors")) cache.put(req, rep.clone());
      return rep;
    } catch (err) {
      if (enCache) return enCache;
      if (req.mode === "navigate") return (await caches.match("index.html")) || Response.error();
      throw err;
    }
  })());
});
