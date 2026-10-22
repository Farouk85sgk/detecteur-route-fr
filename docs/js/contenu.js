// Contenus pédagogiques et règles du jeu : familles, fiches, carte de la quête, quêtes du jour, badges, niveaux.
// Les 87 éléments détectés par le modèle viennent de classes.json (route_fr/classes.py) ; les feux et usagers
// (détectés par le YOLOv5 COCO d'origine) sont définis ici.

export const APP = {
  nom: "Repère",
  slogan: "Le code de la route, en direct.",
  accroche: "Filme ta route : panneaux, feux, marquages, piétons et cyclistes sont reconnus et expliqués en direct.",
  depot: "https://github.com/Farouk85sgk/detecteur-route-fr",
  version: "2.0",
};

// Éléments ajoutés à ceux du modèle (indices 87 et suivants)
export const EXTRAS = [
  { code: "F_rouge", nom: "Feu rouge", categorie: "feu", explication: "Feu rouge : arrêt obligatoire avant la ligne d'arrêt.", voix: "Feu rouge" },
  { code: "F_orange", nom: "Feu orange", categorie: "feu", explication: "Feu jaune fixe : arrêt, sauf si l'arrêt ne peut plus se faire sans danger.", voix: "Feu orange" },
  { code: "F_vert", nom: "Feu vert", categorie: "feu", explication: "Feu vert : passage autorisé, sans risquer de bloquer le carrefour.", voix: "Feu vert" },
  { code: "U_pieton", nom: "Piéton", categorie: "usager", explication: "Piéton : céder le passage s'il traverse ou s'apprête à traverser.", voix: "Piéton" },
  { code: "U_cycliste", nom: "Cycliste", categorie: "usager", explication: "Cycliste : le dépasser en laissant 1 m en ville, 1,50 m hors agglomération.", voix: "Cycliste" },
  { code: "U_deux_roues", nom: "Deux-roues motorisé", categorie: "usager", explication: "Moto ou scooter : attention aux angles morts.", voix: "Deux-roues" },
];

// Familles : album, quiz, carte de la quête (une région par famille) et filtres de détection
export const FAMILLES = [
  {
    id: "dangers", nom: "Dangers", icone: "A1a", region: "Les Gorges du Danger", gardien: "le Dragon des Lacets",
    forme: "Triangle à bordure rouge, pointe en haut : il annonce un danger, en général 150 m avant hors agglomération et 50 m avant en agglomération.",
    codes: ["A1a", "A1b", "A1c", "A1d", "A2b", "A3", "A4", "A7", "A8", "A13a", "A13b", "A14", "A15b", "A16", "A17", "A18", "A21"],
  },
  {
    id: "priorites", nom: "Intersections et priorités", icone: "AB1", region: "La Croisée des Chemins", gardien: "la Chouette du Carrefour",
    forme: "Triangles, octogone STOP, losange jaune ou panneaux de passage étroit : ils disent qui passe en premier.",
    codes: ["AB1", "AB2", "AB25", "AB3a", "AB4", "AB6", "AB7", "B15", "C18"],
  },
  {
    id: "interdictions", nom: "Interdictions", icone: "B1", region: "Le Fort Écarlate", gardien: "le Golem Interdit",
    forme: "Disque à bordure rouge : il interdit quelque chose à partir du panneau.",
    codes: ["B0", "B1", "B2a", "B2b", "B2c", "B3", "B8", "B9a", "B9b"],
  },
  {
    id: "vitesses", nom: "Limitations de vitesse", icone: "B14_50", region: "Le Circuit des Compteurs", gardien: "le Lièvre Chronomètre",
    forme: "Disque à bordure rouge avec un nombre : la vitesse maximale autorisée, en km/h.",
    codes: ["B14_30", "B14_50", "B14_70", "B14_80", "B14_90", "B14_110", "B14_130"],
  },
  {
    id: "zones", nom: "Stationnement et zones", icone: "B6a1", region: "Le Bourg Paisible", gardien: "le Veilleur du Bourg",
    forme: "Disque bleu à bordure rouge pour l'arrêt et le stationnement ; panneaux d'entrée pour les zones et les agglomérations.",
    codes: ["B6a1", "B6d", "B30", "EB10"],
  },
  {
    id: "obligations", nom: "Obligations", icone: "B21d1", region: "L'Archipel des Flèches", gardien: "la Sirène Bleue",
    forme: "Disque bleu à pictogramme blanc : il oblige (direction à suivre, voie réservée).",
    codes: ["B21b", "B21d1", "B21d2", "B21c1", "B21c2", "B21e", "B21a1", "B21a2", "B22a", "B22b"],
  },
  {
    id: "fins", nom: "Fins d'interdiction et de zone", icone: "B31", region: "La Porte de la Liberté", gardien: "le Passeur des Bornes",
    forme: "Panneau blanc barré d'une bande noire ou grise : fin d'une interdiction, d'une zone ou de l'agglomération.",
    codes: ["B31", "B33", "B34", "B51", "EB20"],
  },
  {
    id: "indications", nom: "Indications", icone: "C12", region: "La Baie des Repères", gardien: "le Phare Bleu",
    forme: "Carré ou rectangle bleu : il informe (parking, sens unique, passage piétons, autoroute...).",
    codes: ["C1a", "C12", "C13a", "C20a", "C107", "C207"],
  },
  {
    id: "marquages", nom: "Marquages au sol", icone: "M_ligne_discontinue", region: "Les Lignes Blanches", gardien: "le Serpent de Craie",
    forme: "Peinture blanche sur la chaussée (jaune pour les travaux et certains arrêts) : lignes, flèches, passages, symboles.",
    codes: ["M_passage_pietons", "M_ligne_stop", "M_ligne_cedez", "M_stop_sol", "M_triangle_cedez", "M_fleche_tout_droit", "M_fleche_droite", "M_fleche_gauche",
      "M_fleche_tout_droit_droite", "M_fleche_tout_droit_gauche", "M_fleche_rabattement", "M_ligne_continue", "M_ligne_discontinue", "M_ligne_mixte", "M_zebras",
      "M_velo", "M_damier", "M_dents_requin", "M_bus", "M_zigzag"],
  },
  {
    id: "feux", nom: "Feux et usagers", icone: "F_rouge", region: "La Ville Lumière", gardien: "le Cyclope Tricolore",
    forme: "Feux tricolores, et usagers à protéger : piétons, cyclistes, deux-roues.",
    codes: ["F_rouge", "F_orange", "F_vert", "U_pieton", "U_cycliste", "U_deux_roues"],
  },
];

// Bon réflexe : ce qu'il faut faire en voyant l'élément
export const REFLEXES = {
  A1a: "Ralentis avant d'entrer dans le virage, pas pendant, et garde bien ta droite.",
  A1b: "Ralentis avant le virage et reste bien à droite : tu ne vois pas ce qui arrive en face.",
  A1c: "Adapte ta vitesse à toute la série de virages ; ne dépasse pas sans visibilité.",
  A1d: "Adapte ta vitesse à toute la série de virages ; ne dépasse pas sans visibilité.",
  A2b: "Ralentis franchement (souvent 30 km/h) pour passer le ralentisseur sans à-coup.",
  A3: "Ralentis et serre à droite ; si la place manque, laisse passer celui qui arrive en face.",
  A4: "Augmente les distances de sécurité ; évite les freinages et les coups de volant brusques.",
  A7: "Ne t'engage jamais si les barrières se baissent ou si le feu rouge clignote ; ne t'arrête jamais sur les voies.",
  A8: "Pas de barrière : ralentis, regarde des deux côtés et écoute avant de traverser les voies.",
  A13a: "Ralentis : un enfant peut surgir entre deux voitures.",
  A13b: "Prépare-toi à t'arrêter : le piéton qui traverse ou s'apprête à traverser est prioritaire.",
  A14: "Lis le panonceau qui précise le danger, et ralentis.",
  A15b: "Ralentis, surtout à l'aube et au crépuscule. Face à un animal, freine fort sans donner de coup de volant.",
  A16: "Utilise le frein moteur en rétrogradant pour ne pas faire chauffer les freins.",
  A17: "Anticipe : le feu peut passer au rouge, prépare-toi à t'arrêter.",
  A18: "La route redevient à double sens : serre à droite, attention aux véhicules en face.",
  A21: "Ralentis : des cyclistes peuvent couper la route, de droite comme de gauche.",
  AB1: "À cette intersection, cède le passage aux véhicules qui arrivent de ta droite.",
  AB2: "Tu es prioritaire à la prochaine intersection seulement : reste attentif.",
  AB25: "Cède le passage aux véhicules déjà sur l'anneau ; clignotant à droite pour sortir.",
  AB3a: "Ralentis, regarde et cède le passage ; arrête-toi seulement si quelqu'un arrive.",
  AB4: "Arrêt complet à la ligne, roues immobiles, même si personne n'arrive ; puis cède le passage.",
  AB6: "Tu es prioritaire aux intersections jusqu'au panneau de fin de route prioritaire.",
  AB7: "Fin de ta priorité : aux intersections suivantes, la priorité à droite revient, sauf autre signalisation.",
  B15: "Dans le passage étroit, laisse d'abord passer les véhicules qui arrivent en face.",
  C18: "Tu passes en premier dans le passage étroit, mais reste prudent.",
  B0: "Aucun véhicule ne peut circuler, dans les deux sens ; les piétons peuvent passer.",
  B1: "Ne t'engage pas : la circulation vient en face (souvent une rue à sens unique).",
  B2a: "Interdit de tourner à gauche à la prochaine intersection.",
  B2b: "Interdit de tourner à droite à la prochaine intersection.",
  B2c: "Pas de demi-tour jusqu'à la prochaine intersection incluse.",
  B3: "Interdit de dépasser les véhicules à moteur, sauf les deux-roues sans side-car.",
  B8: "Interdit aux véhicules de transport de marchandises ; un panonceau peut préciser le poids.",
  B9a: "Interdit aux piétons : ils doivent passer ailleurs.",
  B9b: "Interdit aux cyclistes : ils doivent prendre un autre itinéraire.",
  B6a1: "Stationnement interdit, mais un arrêt bref (pour déposer quelqu'un) reste possible.",
  B6d: "Ni arrêt ni stationnement : tu ne peux même pas t'arrêter pour déposer quelqu'un.",
  B30: "30 km/h maximum dans toute la zone, jusqu'au panneau de sortie ; attention aux vélos à contresens.",
  EB10: "50 km/h maximum sauf indication contraire ; klaxon seulement en cas de danger immédiat.",
  B21b: "À la prochaine intersection, tu dois continuer tout droit.",
  B21d1: "Tu dois aller à droite, dans le sens indiqué par la flèche.",
  B21d2: "Tu dois aller à gauche, dans le sens indiqué par la flèche.",
  B21c1: "À la prochaine intersection : tout droit ou à droite, mais pas à gauche.",
  B21c2: "À la prochaine intersection : tout droit ou à gauche, mais pas à droite.",
  B21e: "À la prochaine intersection : à droite ou à gauche, pas tout droit.",
  B21a1: "Contourne l'obstacle par la droite.",
  B21a2: "Contourne l'obstacle par la gauche.",
  B22a: "Piste ou bande obligatoire pour les cyclistes : les voitures n'y circulent pas.",
  B22b: "Chemin réservé aux piétons : les véhicules n'y circulent pas.",
  B31: "Fin de toutes les interdictions signalées pour les véhicules en mouvement (vitesse, dépassement...).",
  B33: "Fin de la limitation : la vitesse maximale générale de la route s'applique de nouveau.",
  B34: "Tu peux de nouveau dépasser, si la ligne au sol et la visibilité le permettent.",
  B51: "Sortie de la zone 30 : en agglomération, la limite redevient en général 50 km/h.",
  EB20: "Fin de l'agglomération : la vitesse générale hors agglomération s'applique (souvent 80 km/h).",
  C1a: "Parking : lieu aménagé pour stationner.",
  C12: "Sens unique : tous les véhicules circulent dans le même sens ; attention aux vélos autorisés à contresens.",
  C13a: "Impasse : pas d'issue au bout de la rue.",
  C20a: "Le piéton qui s'engage ou montre qu'il va traverser est prioritaire : prépare-toi à t'arrêter.",
  C107: "Route pour automobiles : interdite aux piétons, aux cyclistes, aux cyclomoteurs et aux tracteurs.",
  C207: "Autoroute : 130 km/h maximum par temps sec, 110 km/h par temps de pluie ; ni piétons ni vélos.",
  M_passage_pietons: "Le piéton engagé ou qui s'apprête à traverser est prioritaire ; ne t'arrête pas sur les bandes.",
  M_ligne_stop: "Arrête-toi complètement juste avant la ligne, puis cède le passage.",
  M_ligne_cedez: "Si tu dois céder le passage, arrête-toi avant cette ligne en pointillés.",
  M_stop_sol: "STOP au sol : prépare-toi à marquer l'arrêt complet à la ligne.",
  M_triangle_cedez: "Triangle au sol : annonce d'un cédez-le-passage.",
  M_fleche_tout_droit: "Choisis ta voie selon ta direction : cette voie va tout droit.",
  M_fleche_droite: "Choisis ta voie selon ta direction : cette voie tourne à droite.",
  M_fleche_gauche: "Choisis ta voie selon ta direction : cette voie tourne à gauche.",
  M_fleche_tout_droit_droite: "Cette voie va tout droit ou à droite.",
  M_fleche_tout_droit_gauche: "Cette voie va tout droit ou à gauche.",
  M_fleche_rabattement: "La ligne va devenir continue : termine ton dépassement et rabats-toi à droite.",
  M_ligne_continue: "Interdit de la franchir ou de la chevaucher.",
  M_ligne_discontinue: "Tu peux la franchir pour dépasser ou tourner, si c'est sans danger.",
  M_ligne_mixte: "Tu peux la franchir seulement si la partie discontinue est de ton côté.",
  M_zebras: "Zone hachurée : n'y circule pas et ne t'y arrête pas ; elle sépare ou guide les voies.",
  M_velo: "Espace pour les cyclistes : laisse-leur la place.",
  M_damier: "Tu traverses un couloir réservé aux bus : regarde bien s'il en arrive.",
  M_dents_requin: "Ralentisseur ou plateau tout proche : ralentis.",
  M_bus: "Voie réservée aux bus : n'y circule pas et ne t'y arrête pas.",
  M_zigzag: "Arrêt de bus : ni arrêt ni stationnement pour les autres véhicules.",
  F_rouge: "Arrête-toi avant la ligne d'arrêt et attends le vert.",
  F_orange: "Arrête-toi, sauf si tu es trop près pour freiner sans danger.",
  F_vert: "Passe, à condition de ne pas risquer de rester bloqué dans le carrefour ; regarde les piétons en tournant.",
  U_pieton: "Ralentis et sois prêt à t'arrêter : un piéton peut traverser à tout moment.",
  U_cycliste: "Pour le dépasser, laisse au moins 1 m en ville et 1,50 m hors agglomération.",
  U_deux_roues: "Vérifie tes rétroviseurs et tes angles morts avant de changer de voie ou de tourner.",
};
for (const v of [30, 50, 70, 80, 90, 110, 130]) REFLEXES[`B14_${v}`] = `Ne dépasse pas ${v} km/h à partir de ce panneau ; par mauvais temps, roule encore moins vite.`;

// Questions « vitesse » : vitesse maximale certaine après le panneau (par temps sec)
export const VITESSE_APRES = { B14_30: 30, B14_50: 50, B14_70: 70, B14_80: 80, B14_90: 90, B14_110: 110, B14_130: 130, B30: 30, EB10: 50, C207: 130 };

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
  { id: "famille", nom: "Famille complète", texte: "Complète une famille de l'album." },
  { id: "serie1", nom: "Première série", texte: "Termine une série de code." },
  { id: "parfait", nom: "Sans faute", texte: "Réussis une série sans aucune erreur." },
  { id: "justes100", nom: "Cent bonnes réponses", texte: "Donne 100 bonnes réponses aux quiz." },
  { id: "gardien1", nom: "Premier éclat", texte: "Bats un premier gardien." },
  { id: "gardien5", nom: "Cinq éclats", texte: "Bats cinq gardiens." },
  { id: "examen", nom: "Examen réussi", texte: "Obtiens au moins 35/40 à un examen blanc." },
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
