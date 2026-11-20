// « Passer l'examen » : l'essentiel sur le vrai examen du code (épreuve théorique générale, ETG), à lire en deux minutes
// (500 mots environ : avant d'ajouter une phrase, en retirer une).
// Du texte seulement, écrit ici : la page ne charge rien et s'affiche donc sans réseau (seuls les liens du bas en demandent).
// Chaque phrase s'appuie sur une fiche officielle (Service-Public, Légifrance, Sécurité routière) ou sur les sites des
// opérateurs agréés, d'après la recherche du 19 novembre 2026. Ce qui n'est pas sûr est dit comme tel : le temps par
// question et le délai du résultat viennent des opérateurs, les âges de Service-Public (un ancien texte disait 17 ans),
// et pour une pièce d'identité périmée le texte officiel et les centres ne disent pas la même chose. Après un échec,
// les opérateurs écrivent qu'aucun délai n'est imposé et des sites de préparation parlent de 48 heures : la page donne
// ce qui est vrai dans les deux cas, 2 jours au moins (résultat après 24 heures, inscription la veille). Laissés de côté,
// faute de source sûre ou de place : nombre de questions par thème, gratuité du NEPH, délai pour avoir une place,
// changement de date (propre à chaque opérateur), peines en cas de fraude, taux de réussite exact (49 ou 51 % en 2025
// selon les sources : la page dit « environ une sur deux »), détail des dispenses pour qui a déjà un permis moto.
// Après une réforme, corriger le texte ici et changer la date en bas de page.
import { ICONES } from "./ui.js";

// Une section : son titre, puis des lignes « l'essentiel en gras, le détail dessous » (lire les gras suffit pour retenir
// le principal). Les opérateurs sont cités par ordre alphabétique : l'appli n'en recommande aucun.
// \u00a0 : espace qui ne doit pas être coupée en bout de ligne (voir insec, plus bas).
const SECTIONS = [
  ["L'examen en bref", [
    ["40 questions, 35 bonnes réponses pour réussir", "Les questions sont tirées au sort : ton voisin n'a pas les mêmes. Plusieurs bonnes réponses ? L'écran le signale."],
    ["Sur une tablette, avec un casque", "Chaque question est lue dans le casque, avec une photo ou une vidéo."],
    ["Environ 30 minutes, sans retour en arrière", "En général 20 secondes par question, d'après les opérateurs."],
  ]],
  ["Avant : ton numéro NEPH et l'inscription", [
    ["Âge minimum : 15 ans en conduite accompagnée, 16 ans sinon", "D'après Service-Public."],
    ["Il te faut un numéro NEPH", "C'est ton numéro de dossier de permis (12 chiffres). Sans lui, pas de réservation."],
    ["Demande-le sur le site officiel de l'ANTS (France\u00a0Titres)", "Ton auto-école peut aussi le faire. Compte 2 semaines en moyenne, parfois plus. Inutile de payer un site privé."],
    ["Les pièces à fournir", "Pièce d'identité, justificatif de domicile, photo d'identité. Avant 21 ans : ASSR\u00a02 ou ASR (ou une déclaration sur l'honneur si tu l'as perdue). Français de 17 à 24 ans : justificatif JDC. Mineur : pièce d'identité de ton représentant légal."],
    ["Ensuite seulement, tu t'inscris à l'examen", "Par ton auto-école, ou toi-même, en candidat libre : même examen, même prix."],
  ]],
  ["Où le passer et combien ça coûte", [
    ["Chez l'un des cinq opérateurs agréés par l'État", "Par ordre alphabétique : Bureau\u00a0Veritas, Dekra, La\u00a0Poste, Pearson\u00a0VUE, SGS. Tu réserves et tu paies sur le site de l'opérateur ; ta convocation arrive par e-mail."],
    ["30 € par passage, le même prix partout", ""],
    ["Inscris-toi au plus tard la veille", "Depuis le 1er juillet 2026, plus d'inscription le jour même."],
  ]],
  ["Le jour\u00a0J", [
    ["Ta convocation (papier ou téléphone) et ta pièce d'identité", "L'original de ta carte d'identité ou de ton passeport : photocopie, photo sur ton téléphone et carte Vitale sont refusées. Pièce périmée ? Vérifie auprès de ton centre."],
    ["Arrive 15 à 20 minutes en avance", "En retard, tu n'entres pas et tu perds tes 30 €."],
    ["Téléphone éteint et rangé", "Interdit aussi : parler, utiliser un document, porter tes propres écouteurs. Sinon, exclusion immédiate."],
  ]],
  ["Le résultat", [
    ["Jamais le jour même", "Au plus tôt 24 heures après. Les opérateurs annoncent 48 à 72 heures au plus."],
    ["Par e-mail et dans ton espace candidat", "Regarde aussi tes courriers indésirables. Si ton auto-école t'a inscrit, c'est souvent elle qui le reçoit."],
  ]],
  ["Si tu échoues", [
    ["Tu peux te réinscrire dès que tu as ton résultat", "Compte au moins 2 jours avant de repasser : l'inscription se fait la veille. Aucune limite au nombre d'essais."],
    ["Chaque essai coûte de nouveau 30 €", "Environ une épreuve sur deux est réussie : mieux vaut s'y présenter prêt."],
  ]],
  ["Après le code", [
    ["Ton code est valable 5 ans", "Il faut réussir la conduite dans ce délai. Sinon, tu repasses le code. Tu le gardes si tu changes d'auto-école."],
    ["Conduite : autant d'essais qu'il le faut", "La limite de 5 passages n'existe plus."],
    ["Épreuve de conduite : à partir de 17 ans", ""],
  ]],
  ["Cas particuliers", [
    ["Sourd ou malentendant, « dys », français mal maîtrisé", "Des séances adaptées existent : contacte à l'avance le bureau de l'éducation routière (BER) de ton département. Français mal maîtrisé : signale-le dès ta demande à l'ANTS."],
    ["Tu as déjà un autre permis ?", "Selon sa catégorie et sa date, tu peux être dispensé du code. Le permis AM, lui, ne dispense pas. Pour les autres, vérifie sur Service-Public."],
  ]],
];

// Liens vers les sites officiels seulement (aucun vers un opérateur : leurs pages d'inscription sont sur la fiche Service-Public).
const SOURCES = [
  ["Passer le code", "Service-Public, fiche\u00a0F33694", "https://www.service-public.gouv.fr/particuliers/vosdroits/F33694"],
  ["Demander son numéro NEPH", "Service-Public, démarche\u00a0R49186", "https://www.service-public.gouv.fr/particuliers/vosdroits/R49186"],
  ["Permis\u00a0B : âge et pièces à fournir", "Service-Public, fiche\u00a0F2828", "https://www.service-public.gouv.fr/particuliers/vosdroits/F2828"],
  ["Handicap, troubles « dys », traduction", "Service-Public, fiche\u00a0F2842", "https://www.service-public.gouv.fr/particuliers/vosdroits/F2842"],
  ["Les règles de l'examen", "Légifrance, arrêté du 16 avril 2026", "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053974673"],
];

// Sur un petit écran, pas de « : », de « € » ni de guillemet seul en début de ligne ; un nombre reste avec le mot qui le
// suit (« 30 € », « 5 ans ») et un mot à trait d'union n'est pas coupé (« lis-les »). Ces groupes sont mis dans un <span>
// qui ne se coupe pas, plutôt que liés par des espaces insécables : le texte affiché garde ses espaces ordinaires
// (recherche dans la page, copier-coller).
function insec(texte) {
  const groupes = [];
  for (const mot of texte.split(" ")) {
    const g = groupes[groupes.length - 1];
    if (g && (/^[:;?!»€%]/.test(mot) || /[«\d]$/.test(g[g.length - 1]))) g.push(mot); else groupes.push([mot]);
  }
  return groupes.map(g => g.join(" ")).map(t => /[ \u00a0-]/.test(t) ? `<span style="white-space:nowrap">${t.replace(/\u00a0/g, " ")}</span>` : t).join(" ");
}
// Titre plus petit que celui des cartes de l'accueil (1,85 rem) : le plus long tient en deux lignes sur un écran de 320 points.
const carte = (titre, corps) => `<section class="carte"><h2 style="font-size:1.45rem">${insec(titre)}</h2>${corps}</section>`;
const ligne = ([gras, detail]) => `<div><b>${insec(gras)}</b>${detail ? `<div class="doux">${insec(detail)}</div>` : ""}</div>`;

export function pageExamen(zone) {
  zone.innerHTML = `<div class="page"><div class="entete"><h1>Passer l'examen</h1><button class="btn-rond" data-nav="#/codes" aria-label="Fermer">${ICONES.fermer}</button></div>
    <p class="sous-titre">L'essentiel sur le vrai examen du code (épreuve théorique générale, ou ETG), en deux minutes.</p>
    <div class="contenu">
      ${SECTIONS.map(([titre, lignes]) => carte(titre, `<div class="liste-lignes">${lignes.map(l => `<div class="element-liste">${ligne(l)}</div>`).join("")}</div>`)).join("")}
      ${carte("Sources officielles", `<p class="doux">${insec("Ces liens ouvrent les sites officiels : il faut du réseau.")}</p>
        <div class="liste-lignes">${SOURCES.map(([titre, site, url]) => `<a class="element-liste" href="${url}" target="_blank" rel="noopener" style="text-decoration:none">${ligne([titre, site])}
          ${ICONES.chevron.replace("<svg", '<svg class="chevron" style="transform:rotate(-90deg)"')}</a>`).join("")}</div>
        <p class="doux petit">${insec("Vérifié le 19 novembre 2026. Les règles peuvent changer : en cas de doute, c'est le site officiel qui a raison.")}</p>`)}
    </div></div>`;
}
