// Contenus pédagogiques et règles du jeu : familles, carte de la quête, quêtes du jour, badges, niveaux.
// Les panneaux et marquages (nom, sens, bon réflexe) viennent de catalogue.json, produit à partir de
// route_fr/classes.py ; les feux et usagers (détectés par le YOLOv5 COCO d'origine) sont définis ici.

export const APP = {
  nom: "Repère",
  slogan: "Le code de la route, en direct.",
  accroche: "Filme ta route : panneaux, feux, marquages, piétons et cyclistes sont reconnus et expliqués en direct.",
  depot: "https://github.com/Farouk85sgk/detecteur-route-fr",
  version: "3.0.3",
};

// Éléments ajoutés à ceux du catalogue
export const EXTRAS = [
  { code: "F_rouge", nom: "Feu rouge", categorie: "feu", explication: "Feu rouge : arrêt obligatoire avant la ligne d'arrêt.", voix: "Feu rouge" },
  { code: "F_orange", nom: "Feu orange", categorie: "feu", explication: "Feu jaune fixe : arrêt, sauf si l'arrêt ne peut plus se faire sans danger.", voix: "Feu orange" },
  { code: "F_vert", nom: "Feu vert", categorie: "feu", explication: "Feu vert : passage autorisé, sans risquer de bloquer le carrefour.", voix: "Feu vert" },
  { code: "U_pieton", nom: "Piéton", categorie: "usager", explication: "Piéton : céder le passage s'il traverse ou s'apprête à traverser.", voix: "Piéton" },
  { code: "U_cycliste", nom: "Cycliste", categorie: "usager", explication: "Cycliste : le dépasser en laissant 1 m en ville, 1,50 m hors agglomération.", voix: "Cycliste" },
  { code: "U_deux_roues", nom: "Deux-roues motorisé", categorie: "usager", explication: "Moto ou scooter : attention aux angles morts.", voix: "Deux-roues" },
];

// Familles : album, quiz, carte de la quête (une région par famille, dans cet ordre) et filtres de détection.
// Les éléments de chaque famille (f.codes) sont ceux du catalogue qui la désignent ; ceux de « feux » sont les EXTRAS.
export const FAMILLES = [
  {
    id: "dangers", nom: "Dangers", icone: "A1a", region: "Les Gorges du Danger", gardien: "le Dragon des Lacets",
    forme: "Triangle à bordure rouge, pointe en haut : il annonce un danger, en général 150 m avant hors agglomération et 50 m avant en agglomération.",
  },
  {
    id: "priorites", nom: "Intersections et priorités", icone: "AB1", region: "La Croisée des Chemins", gardien: "la Chouette du Carrefour",
    forme: "Triangles, octogone STOP, losange jaune ou panneaux de passage étroit : ils disent qui passe en premier.",
  },
  {
    id: "interdictions", nom: "Interdictions", icone: "B1", region: "Le Fort Écarlate", gardien: "le Golem Interdit",
    forme: "Disque à bordure rouge : il interdit quelque chose à partir du panneau.",
  },
  {
    id: "vitesses", nom: "Limitations de vitesse", icone: "B14_50", region: "Le Circuit des Compteurs", gardien: "le Lièvre Chronomètre",
    forme: "Disque à bordure rouge avec un nombre : la vitesse maximale autorisée, en km/h. Carré bleu : une vitesse seulement conseillée.",
  },
  {
    id: "zones", nom: "Stationnement et zones", icone: "B6a1", region: "Le Bourg Paisible", gardien: "le Veilleur du Bourg",
    forme: "Disque bleu à bordure rouge pour l'arrêt et le stationnement ; grands panneaux rectangulaires à l'entrée et à la sortie des zones.",
  },
  {
    id: "obligations", nom: "Obligations", icone: "B21c1", region: "L'Archipel des Flèches", gardien: "la Sirène Bleue",
    forme: "Disque bleu à pictogramme blanc : il oblige (direction à suivre, voie réservée, équipement).",
  },
  {
    id: "fins", nom: "Fins d'interdiction et d'obligation", icone: "B31", region: "La Porte de la Liberté", gardien: "le Passeur des Bornes",
    forme: "Panneau barré d'une bande noire, grise ou rouge : fin d'une interdiction ou d'une obligation.",
  },
  {
    id: "indications", nom: "Indications", icone: "C12", region: "La Baie des Repères", gardien: "le Phare Bleu",
    forme: "Carré ou rectangle bleu : il informe (sens unique, impasse, passage piétons, tunnel, autoroute...).",
  },
  {
    id: "marquages", nom: "Marquages au sol", icone: "M_ligne_discontinue", region: "Les Lignes Blanches", gardien: "le Serpent de Craie",
    forme: "Peinture blanche sur la chaussée (jaune pour les travaux et certains arrêts) : lignes, flèches, passages, symboles.",
  },
  {
    id: "feux", nom: "Feux et usagers", icone: "F_rouge", region: "La Ville Lumière", gardien: "le Cyclope Tricolore",
    forme: "Feux tricolores, et usagers à protéger : piétons, cyclistes, deux-roues.",
  },
  {
    id: "temporaire", nom: "Signalisation temporaire", icone: "AK5", region: "Le Chantier Jaune", gardien: "le Titan des Travaux",
    forme: "Fond jaune : signalisation temporaire (chantier, déviation, accident). Elle l'emporte sur la signalisation permanente.",
  },
  {
    id: "services", nom: "Services", icone: "CE15a", region: "Le Relais des Voyageurs", gardien: "l'Aubergiste aux Mille Clés",
    forme: "Carré bleu à pictogramme noir sur fond blanc : un service à proximité (carburant, restauration, secours, hébergement...).",
  },
  {
    id: "reperes", nom: "Agglomérations, balises et repères", icone: "EB10", region: "Les Bornes du Royaume", gardien: "le Géant des Balises",
    forme: "Panneaux au nom des agglomérations et balises blanches, rouges ou bleues qui jalonnent la route et signalent ses points particuliers.",
  },
  {
    id: "panonceaux", nom: "Panonceaux", icone: "M9v", region: "La Tour des Panonceaux", gardien: "le Scribe Minuscule",
    forme: "Petit rectangle placé sous un panneau : il en précise la portée (distance, étendue, usagers concernés, exceptions).",
  },
];

// Bon réflexe des feux et usagers (celui des panneaux et marquages est dans le catalogue)
export const REFLEXES = {
  F_rouge: "Arrête-toi avant la ligne d'arrêt et attends le vert.",
  F_orange: "Arrête-toi, sauf si tu es trop près pour freiner sans danger.",
  F_vert: "Passe, à condition de ne pas risquer de rester bloqué dans le carrefour ; regarde les piétons en tournant.",
  U_pieton: "Ralentis et sois prêt à t'arrêter : un piéton peut traverser à tout moment.",
  U_cycliste: "Pour le dépasser, laisse au moins 1 m en ville et 1,50 m hors agglomération.",
  U_deux_roues: "Vérifie tes rétroviseurs et tes angles morts avant de changer de voie ou de tourner.",
};

// Questions « vitesse » : vitesse maximale certaine après le panneau (par temps sec)
export const VITESSE_APRES = { B30: 30, B52: 20, EB10: 50, C207: 130 };
for (const v of [20, 30, 50, 70, 80, 90, 110, 130]) VITESSE_APRES[`B14_${v}`] = v;

// La quête : réunir les éclats du Panneau d'Or, un par gardien vaincu
export const QUETE = {
  titre: "La quête du Panneau d'Or",
  reperages: 4,  // éléments différents de la famille à repérer sur la route avant d'affronter le gardien
  questionsDonjon: 10,
  coeursMax: 3,
  minutesParCoeur: 20,
  recompenseGardien: 50,
};

export const QUETES_DU_JOUR = [
  { id: "trajet5", type: "route", texte: "Fais un trajet d'au moins 5 minutes", but: 1, gain: 20 },
  { id: "reperer5", type: "route", texte: "Repère 5 éléments sur la route", but: 5, gain: 20 },
  { id: "nouveau", type: "route", texte: "Ajoute un élément nouveau à ton album", but: 1, gain: 30 },
  { id: "serie", type: "quiz", texte: "Fais une série de code", but: 1, gain: 20 },
  { id: "justes10", type: "quiz", texte: "Donne 10 bonnes réponses", but: 10, gain: 20 },
  { id: "sansfaute", type: "quiz", texte: "Réussis une série sans faute", but: 1, gain: 30 },
  { id: "famille", type: "quiz", texte: "Révise une famille de panneaux", but: 1, gain: 20 },
];

export const OBJETS = [
  { id: "loupe", nom: "Loupe", texte: "Au donjon : retire deux mauvaises réponses.", prix: 30, icone: "loupe" },
  { id: "potion", nom: "Potion de cœur", texte: "Au donjon : rend un cœur perdu.", prix: 40, icone: "potion" },
  { id: "bouclier", nom: "Bouclier de série", texte: "Garde ta série de jours si tu oublies une journée.", prix: 60, icone: "bouclier" },
];

export const TITRES = [
  { id: "vigie", nom: "Vigie", prix: 100 },
  { id: "pilote", nom: "Pilote averti", prix: 250 },
  { id: "legende", nom: "Légende du code", prix: 500 },
];

// Niveau n atteint à 50 n (n - 1) XP
export const NOMS_NIVEAUX = ["Piéton curieux", "Passager attentif", "Apprenti du code", "Jeune conducteur", "Conducteur averti", "As du rétroviseur",
  "Pilote du code", "Expert de la route", "Maître du code", "Légende de la route"];

export const BADGES = [
  { id: "trajet1", nom: "Premier trajet", texte: "Termine un premier trajet filmé." },
  { id: "album10", nom: "Œil de lynx", texte: "Repère 10 éléments différents." },
  { id: "album25", nom: "Collectionneur", texte: "Repère 25 éléments différents." },
  { id: "album50", nom: "Encyclopédie", texte: "Repère 50 éléments différents." },
  { id: "album100", nom: "Mémoire d'éléphant", texte: "Repère 100 éléments différents." },
  { id: "famille", nom: "Famille complète", texte: "Complète une famille de l'album." },
  { id: "serie1", nom: "Première série", texte: "Termine une série de code." },
  { id: "parfait", nom: "Sans faute", texte: "Réussis une série sans aucune erreur." },
  { id: "justes100", nom: "Cent bonnes réponses", texte: "Donne 100 bonnes réponses aux quiz." },
  { id: "gardien1", nom: "Premier éclat", texte: "Bats un premier gardien." },
  { id: "gardien5", nom: "Cinq éclats", texte: "Bats cinq gardiens." },
  { id: "examen", nom: "Examen réussi", texte: "Obtiens au moins 35/40 à un examen blanc." },
  { id: "code100", nom: "Bûcheur du code", texte: "Réussis 100 questions différentes des séries de code." },
  { id: "theme", nom: "Thème maîtrisé", texte: "Réussis toutes les questions d'un thème du code." },
  { id: "flamme3", nom: "Trois jours de suite", texte: "Accomplis une quête du jour 3 jours de suite." },
  { id: "flamme7", nom: "Une semaine de suite", texte: "Accomplis une quête du jour 7 jours de suite." },
  { id: "mystere", nom: "Détective", texte: "Trouve le panneau mystère du jour." },
  { id: "photos20", nom: "Photographe", texte: "Garde 20 photos de tes trajets." },
  { id: "prof", nom: "Professeur", texte: "Apprends un panneau à l'appli." },
];

// Classement : 8 catégories (profils du téléphone et amis ajoutés par leur code)
export const CATEGORIES_CLASSEMENT = [
  { id: "explorateur", nom: "L'explorateur", texte: "le plus d'éléments différents trouvés sur la route", unite: n => `${n} élément${n > 1 ? "s" : ""}` },
  { id: "batisseur", nom: "Le bâtisseur", texte: "le plus de panneaux appris à l'appli ou gardés en photo", unite: n => `${n} panneau${n > 1 ? "x" : ""}` },
  { id: "erudit", nom: "L'érudit", texte: "la meilleure réussite aux quiz et aux donjons (10 réponses au moins)", unite: n => `${n} %` },
  { id: "marathonien", nom: "Le marathonien", texte: "le plus de séries de code", unite: n => `${n} série${n > 1 ? "s" : ""}` },
  { id: "examen", nom: "Le champion d'examen", texte: "le meilleur examen blanc", unite: n => `${n}/40` },
  { id: "routier", nom: "Le routier", texte: "le plus de temps de route filmé", unite: n => `${n} min` },
  { id: "flamme", nom: "La flamme", texte: "la plus longue série de jours", unite: n => `${n} jour${n > 1 ? "s" : ""}` },
  { id: "conquerant", nom: "Le conquérant", texte: "le plus de gardiens vaincus", unite: n => `${n} gardien${n > 1 ? "s" : ""}` },
];

export const COULEURS_PROFIL = ["#2453d6", "#e0262b", "#22a04b", "#8a3ffc", "#f07d19", "#0e9aa7", "#d6337a", "#5b6475"];
export const FONDS = [
  { id: "auto", nom: "Auto" }, { id: "blanc", nom: "Blanc" }, { id: "creme", nom: "Crème" }, { id: "sauge", nom: "Sauge" }, { id: "nuit", nom: "Bleu nuit" },
];
