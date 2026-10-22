// « Mes panneaux » : l'utilisateur photographie un panneau que l'appli ne connaît pas (ou qu'elle confond) et dit
// ce que c'est. L'appli garde l'empreinte de ce panneau (modèle empreinte.onnx) et le reconnaît ensuite sur la route.
import { D, definirAppris, estPanneau, icone, officiels } from "./donnees.js";
import { verifierBadges } from "./progression.js";
import { idbMettre, idbSupprimer, idbTout, profil, sauver } from "./stockage.js";
import { $, ICONES, confirmer, esc, ouvrirFeuille, fermerFeuille, toast } from "./ui.js";

let urls = [];

// panneaux appris du profil -> éléments supplémentaires et références pour le moteur
export async function chargerAppris(moteur, p = profil()) {
  urls.forEach(u => URL.revokeObjectURL(u)); urls = [];
  const liste = (await idbTout("appris")).map(x => x.valeur).filter(a => a.profil === p.id).sort((a, b) => a.cree - b.cree);
  for (const a of liste) { a.vignetteUrl = URL.createObjectURL(a.vignette); urls.push(a.vignetteUrl); }
  definirAppris(liste);
  const refs = [];
  for (const a of liste) {
    const it = a.code && D.parCode[a.code] && D.parCode[a.code].index < D.nbOfficiels ? D.parCode[a.code] : D.parCode[`perso_${a.id}`];
    if (it) for (const e of a.emb) refs.push({ index: it.index, emb: Float32Array.from(e), correction: !!a.code });
  }
  moteur.configurer({ appris: refs });
  return liste;
}

export function carteMesPanneaux(liste) {
  return `<section class="carte"><h2>Mes panneaux</h2>
    <p class="doux">Un panneau que l'appli ne connaît pas, ou qu'elle confond ? Prends-le en photo et dis ce que c'est : la prochaine fois, elle le reconnaîtra.</p>
    <div class="duo"><label class="btn btn-plein">Prendre une photo<input type="file" accept="image/*" capture="environment" hidden data-apprendre></label>
      <label class="btn">Choisir une image<input type="file" accept="image/*" hidden data-apprendre></label></div>
    ${liste.length ? `<div class="mes-panneaux-liste">${liste.map(a => `<button data-appris="${esc(a.id)}"><img src="${esc(a.vignetteUrl)}" alt="">${esc(a.nom)}</button>`).join("")}</div>` : ""}</section>`;
}

export function brancherMesPanneaux(zone, moteur, apres) {
  zone.addEventListener("change", e => {
    if (!e.target.matches("[data-apprendre]")) return;
    const f = e.target.files[0];
    e.target.value = "";
    if (f) apprendre(f, moteur, apres);
  });
  zone.addEventListener("click", async e => {
    const b = e.target.closest("[data-appris]");
    if (!b) return;
    const a = (await idbTout("appris")).map(x => x.valeur).find(x => x.id === b.dataset.appris);
    if (!a) return;
    const corps = ouvrirFeuille(a.nom, `<img class="fiche-photo" src="${esc(URL.createObjectURL(a.vignette))}" alt="" style="max-width:220px;margin:0 auto">
      <p class="doux">${a.code ? `Panneau connu (${esc(D.parCode[a.code]?.nom || a.code)}) : l'appli s'en servira pour corriger ses confusions.` : "Panneau ajouté par toi : il apparaît dans ton album, rubrique « Mes panneaux »."}</p>
      <button class="btn btn-danger" data-suppr>Oublier ce panneau</button>`);
    corps.onclick = async ev => {
      if (!ev.target.closest("[data-suppr]") || !(await confirmer(`Oublier « ${a.nom} » ?`))) return;
      await idbSupprimer("appris", a.id);
      fermerFeuille();
      await chargerAppris(moteur);
      apres();
    };
  });
}

async function apprendre(fichier, moteur, apres) {
  const corps = ouvrirFeuille("Apprendre un panneau", `<p class="doux etape">Analyse de la photo…</p>`);
  try {
    if (!moteur.pret) { $(".etape", corps).textContent = "Chargement du détecteur…"; await moteur.charger(); }
    const bmp = await createImageBitmap(fichier, { imageOrientation: "from-image" });
    const k = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
    const cv = document.createElement("canvas");
    cv.width = Math.round(bmp.width * k); cv.height = Math.round(bmp.height * k);
    cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
    const candidats = await moteur.panneauxPhoto(cv, cv.width, cv.height);
    choisirZone(corps, cv, candidats, moteur, apres);
  } catch (e) {
    console.error(e);
    corps.innerHTML = `<p>Impossible d'analyser cette image : ${esc(e.message || e)}</p>`;
  }
}

function choisirZone(corps, cv, candidats, moteur, apres) {
  const W = cv.width, H = cv.height;
  let choisi = candidats[0] ? { box: candidats[0].box, devine: candidats[0].devine } : null;
  let taille = 0.22;
  const pct = b => `left:${100 * b[0] / W}%;top:${100 * b[1] / H}%;width:${100 * (b[2] - b[0]) / W}%;height:${100 * (b[3] - b[1]) / H}%`;
  corps.innerHTML = `<p>${candidats.length ? "Touche le panneau à apprendre (cadre vert)." : "Aucun panneau trouvé automatiquement : touche le panneau sur la photo."}</p>
    <div class="choix-zone"><img src="${cv.toDataURL("image/jpeg", 0.85)}" alt="Photo">${candidats.map((c, i) => `<div class="boite" data-i="${i}" style="${pct(c.box)}"></div>`).join("")}<div class="boite manuelle cache"></div></div>
    <label class="doux reglage-taille ${candidats.length ? "cache" : ""}">Taille du cadre <input type="range" min="0.06" max="0.6" step="0.01" value="${taille}" style="width:100%"></label>
    <h3>Qu'est-ce que c'est ?</h3>
    <div class="recherche">${ICONES.recherche}<input class="champ" placeholder="Chercher un panneau connu…" data-q></div>
    <div class="liste-choix" role="listbox">
      <button data-code="" aria-pressed="false"><span style="font-size:1.6rem;text-align:center">＋</span><span>Un autre panneau (nouveau)</span></button>
      ${officiels().filter(estPanneau).map(it => `<button data-code="${esc(it.code)}" aria-pressed="false"><img src="${esc(icone(it))}" alt="" loading="lazy"><span>${esc(it.nom)}</span></button>`).join("")}</div>
    <input class="champ nom-nouveau cache" maxlength="40" placeholder="Nom du panneau (ex. : Chaînes à neige obligatoires)">
    <input class="champ explication-nouveau cache" maxlength="160" placeholder="Ce qu'il signifie (facultatif)">
    <button class="btn btn-plein btn-grand" data-enregistrer disabled>Apprendre ce panneau</button>`;
  const zone = $(".choix-zone", corps), manuelle = $(".boite.manuelle", corps);
  let code = null;
  const marquer = () => {
    corps.querySelectorAll(".boite[data-i]").forEach(b => b.classList.toggle("choisie", choisi && candidats[+b.dataset.i]?.box === choisi.box));
    $("[data-enregistrer]", corps).disabled = !(choisi && (code || (code === "" && $(".nom-nouveau", corps).value.trim())));
  };
  const choisirCode = c => {
    code = c;
    corps.querySelectorAll(".liste-choix button").forEach(b => b.setAttribute("aria-pressed", b.dataset.code === c));
    $(".nom-nouveau", corps).classList.toggle("cache", c !== ""); $(".explication-nouveau", corps).classList.toggle("cache", c !== "");
    marquer();
  };
  if (choisi?.devine != null) choisirCode(D.items[choisi.devine].code);
  zone.onclick = e => {
    const b = e.target.closest(".boite[data-i]");
    if (b) { choisi = { box: candidats[+b.dataset.i].box, devine: candidats[+b.dataset.i].devine }; manuelle.classList.add("cache"); if (choisi.devine != null && code == null) choisirCode(D.items[choisi.devine].code); return marquer(); }
    const r = zone.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * W, y = (e.clientY - r.top) / r.height * H;
    const s = taille * Math.min(W, H);
    choisi = { box: [Math.max(0, x - s / 2), Math.max(0, y - s / 2), Math.min(W, x + s / 2), Math.min(H, y + s / 2)], manuel: [x, y] };
    manuelle.setAttribute("style", pct(choisi.box)); manuelle.classList.remove("cache", "choisie"); manuelle.classList.add("choisie");
    $(".reglage-taille", corps).classList.remove("cache");
    marquer();
  };
  $(".reglage-taille input", corps).oninput = e => {
    taille = +e.target.value;
    if (choisi?.manuel) { const [x, y] = choisi.manuel, s = taille * Math.min(W, H); choisi.box = [Math.max(0, x - s / 2), Math.max(0, y - s / 2), Math.min(W, x + s / 2), Math.min(H, y + s / 2)]; manuelle.setAttribute("style", pct(choisi.box)); }
  };
  corps.querySelector(".liste-choix").onclick = e => { const b = e.target.closest("[data-code]"); if (b) choisirCode(b.dataset.code); };
  $("[data-q]", corps).oninput = e => {
    const q = e.target.value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    corps.querySelectorAll(".liste-choix button[data-code]").forEach(b => { if (b.dataset.code) b.classList.toggle("cache", !!q && !b.textContent.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().includes(q)); });
  };
  $(".nom-nouveau", corps).oninput = marquer;
  $("[data-enregistrer]", corps).onclick = async e => {
    e.target.disabled = true; e.target.textContent = "Apprentissage…";
    const p = profil(), emb = await moteur.empreinteDe(cv, choisi.box);
    if (!emb.length) { toast("Le modèle d'empreintes n'a pas pu être chargé (réseau ?)"); e.target.disabled = false; e.target.textContent = "Apprendre ce panneau"; return; }
    const [x1, y1, x2, y2] = choisi.box, s = Math.max(x2 - x1, y2 - y1) * 1.15, cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
    const vg = Object.assign(document.createElement("canvas"), { width: 128, height: 128 });
    vg.getContext("2d").drawImage(cv, cx - s / 2, cy - s / 2, s, s, 0, 0, 128, 128);
    const vignette = await new Promise(ok => vg.toBlob(ok, "image/jpeg", 0.85));
    const connu = code ? D.parCode[code] : null;
    const a = { id: "a" + Date.now().toString(36), profil: p.id, code: connu?.code || null, nom: connu?.nom || $(".nom-nouveau", corps).value.trim(),
      explication: connu ? null : $(".explication-nouveau", corps).value.trim() || null, emb, vignette, cree: Date.now() };
    await idbMettre("appris", a.id, a);
    p.stats.appris = (p.stats.appris || 0) + 1;
    verifierBadges(p); sauver();
    await chargerAppris(moteur);
    fermerFeuille();
    toast(`Appris : ${a.nom}`, "✓");
    apres();
  };
}
