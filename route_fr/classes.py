"""Classes détectées : panneaux (codes de l'IISR) et marquages au sol du code de la route français.

L'ordre de CLASSES définit les indices du modèle YOLOv5 : ne pas le modifier sans réentraîner.
"""

from __future__ import annotations

from dataclasses import dataclass

# Catégories : couleur BGR du cadre affiché (OpenCV) et libellé
CATEGORIES = {
    "danger": ((40, 40, 220), "Danger"),
    "priorite": ((0, 200, 255), "Priorité"),
    "interdiction": ((60, 60, 230), "Interdiction"),
    "fin": ((150, 150, 150), "Fin de prescription"),
    "obligation": ((200, 110, 20), "Obligation"),
    "zone": ((230, 230, 230), "Zone / agglomération"),
    "indication": ((220, 140, 40), "Indication"),
    "marquage": ((80, 230, 80), "Marquage au sol"),
}


@dataclass(frozen=True)
class RoadClass:
    code: str  # nom de la classe dans le modèle
    nom: str  # libellé court affiché
    categorie: str
    explication: str  # rappel du code de la route
    vitesse: int | None = None  # nouvelle vitesse maximale en km/h (mémoire de limitation)
    voix: str | None = None  # annonce vocale (None = pas d'annonce)


CLASSES = [
    # --- Panneaux de danger (A) ---
    RoadClass("A1a", "Virage à droite", "danger", "Virage dangereux à droite : ralentir avant le virage."),
    RoadClass("A1b", "Virage à gauche", "danger", "Virage dangereux à gauche : ralentir avant le virage."),
    RoadClass("A1c", "Virages, 1er à droite", "danger", "Succession de virages dont le premier est à droite."),
    RoadClass("A1d", "Virages, 1er à gauche", "danger", "Succession de virages dont le premier est à gauche."),
    RoadClass("A2b", "Ralentisseur", "danger", "Ralentisseur de type dos-d'âne : ralentir.", voix="Ralentisseur"),
    RoadClass("A3", "Chaussée rétrécie", "danger", "La chaussée se rétrécit (A3, A3a, A3b) : ralentir et serrer à droite."),
    RoadClass("A4", "Chaussée glissante", "danger", "Chaussée particulièrement glissante : vitesse réduite, pas de freinage brusque."),
    RoadClass("A7", "Passage à niveau avec barrières", "danger", "Passage à niveau muni de barrières : ralentir, ne jamais s'engager si les feux clignotent.", voix="Passage à niveau"),
    RoadClass("A8", "Passage à niveau sans barrières", "danger", "Passage à niveau sans barrière : s'assurer qu'aucun train n'arrive avant de traverser.", voix="Passage à niveau sans barrière"),
    RoadClass("A13a", "Enfants", "danger", "Endroit fréquenté par les enfants (école, jeux) : ralentir.", voix="Attention enfants"),
    RoadClass("A13b", "Annonce passage piétons", "danger", "Passage pour piétons proche : ralentir, être prêt à céder le passage."),
    RoadClass("A14", "Autres dangers", "danger", "Danger précisé par un panonceau : redoubler de prudence."),
    RoadClass("A15b", "Animaux sauvages", "danger", "Passage d'animaux sauvages, surtout à l'aube et au crépuscule."),
    RoadClass("A16", "Descente dangereuse", "danger", "Descente dangereuse : utiliser le frein moteur (rapport inférieur)."),
    RoadClass("A17", "Feux tricolores", "danger", "Annonce de feux tricolores : se préparer à s'arrêter.", voix="Feux tricolores"),
    RoadClass("A18", "Double sens", "danger", "La circulation redevient à double sens : serrer à droite."),
    RoadClass("A21", "Débouché de cyclistes", "danger", "Des cyclistes peuvent surgir de droite ou de gauche."),
    # --- Intersection et priorité (AB) ---
    RoadClass("AB1", "Priorité à droite", "priorite", "Intersection : céder le passage aux véhicules venant de droite.", voix="Priorité à droite"),
    RoadClass("AB2", "Route non prioritaire", "priorite", "Prochaine intersection : vous êtes prioritaire sur la route adjacente."),
    RoadClass("AB25", "Giratoire", "priorite", "Carrefour à sens giratoire : céder le passage aux véhicules sur l'anneau.", voix="Giratoire"),
    RoadClass("AB3a", "Cédez le passage", "priorite", "Céder le passage aux usagers de la route abordée, s'arrêter si nécessaire.", voix="Cédez le passage"),
    RoadClass("AB4", "STOP", "priorite", "Arrêt obligatoire à la ligne, puis céder le passage.", voix="Stop"),
    RoadClass("AB6", "Route prioritaire", "priorite", "Vous êtes prioritaire aux intersections jusqu'au panneau de fin."),
    RoadClass("AB7", "Fin de route prioritaire", "fin", "Fin de priorité : la priorité à droite s'applique de nouveau.", voix="Fin de route prioritaire"),
    # --- Interdiction (B) ---
    RoadClass("B0", "Circulation interdite", "interdiction", "Circulation interdite à tout véhicule dans les deux sens."),
    RoadClass("B1", "Sens interdit", "interdiction", "Sens interdit à tout véhicule : ne pas s'engager.", voix="Sens interdit"),
    RoadClass("B2a", "Interdit de tourner à gauche", "interdiction", "Interdiction de tourner à gauche à la prochaine intersection."),
    RoadClass("B2b", "Interdit de tourner à droite", "interdiction", "Interdiction de tourner à droite à la prochaine intersection."),
    RoadClass("B2c", "Demi-tour interdit", "interdiction", "Interdiction de faire demi-tour jusqu'à la prochaine intersection incluse."),
    RoadClass("B3", "Dépassement interdit", "interdiction", "Interdiction de dépasser les véhicules à moteur (sauf deux-roues sans side-car).", voix="Dépassement interdit"),
    RoadClass("B6a1", "Stationnement interdit", "interdiction", "Stationnement interdit (l'arrêt reste autorisé)."),
    RoadClass("B6d", "Arrêt et stationnement interdits", "interdiction", "Arrêt et stationnement interdits."),
    RoadClass("B8", "Interdit aux poids lourds", "interdiction", "Accès interdit aux véhicules de transport de marchandises."),
    RoadClass("B9a", "Interdit aux piétons", "interdiction", "Accès interdit aux piétons."),
    RoadClass("B9b", "Interdit aux cycles", "interdiction", "Accès interdit aux cycles."),
    RoadClass("B15", "Cédez au sens inverse", "interdiction", "Passage étroit : céder le passage aux véhicules venant en sens inverse.", voix="Cédez le passage au sens inverse"),
    RoadClass("B14_30", "Limitation 30 km/h", "interdiction", "Vitesse maximale autorisée : 30 km/h.", vitesse=30, voix="Limitation 30"),
    RoadClass("B14_50", "Limitation 50 km/h", "interdiction", "Vitesse maximale autorisée : 50 km/h.", vitesse=50, voix="Limitation 50"),
    RoadClass("B14_70", "Limitation 70 km/h", "interdiction", "Vitesse maximale autorisée : 70 km/h.", vitesse=70, voix="Limitation 70"),
    RoadClass("B14_80", "Limitation 80 km/h", "interdiction", "Vitesse maximale autorisée : 80 km/h.", vitesse=80, voix="Limitation 80"),
    RoadClass("B14_90", "Limitation 90 km/h", "interdiction", "Vitesse maximale autorisée : 90 km/h.", vitesse=90, voix="Limitation 90"),
    RoadClass("B14_110", "Limitation 110 km/h", "interdiction", "Vitesse maximale autorisée : 110 km/h.", vitesse=110, voix="Limitation 110"),
    RoadClass("B14_130", "Limitation 130 km/h", "interdiction", "Vitesse maximale autorisée : 130 km/h.", vitesse=130, voix="Limitation 130"),
    # --- Fin d'interdiction ---
    RoadClass("B31", "Fin des interdictions", "fin", "Fin de toutes les interdictions signalées aux véhicules en mouvement."),
    RoadClass("B33", "Fin de limitation", "fin", "Fin de la limitation : retour à la vitesse maximale générale de la route.", voix="Fin de limitation"),
    RoadClass("B34", "Fin d'interdiction de dépasser", "fin", "Le dépassement est de nouveau autorisé (si la manœuvre est sans danger)."),
    # --- Obligation (B21, B22) ---
    RoadClass("B21b", "Tout droit obligatoire", "obligation", "Direction obligatoire à la prochaine intersection : tout droit."),
    RoadClass("B21d1", "Obligation à droite", "obligation", "Obligation de tourner à droite (B21-1 avant le panneau, B21c1 à la prochaine intersection)."),
    RoadClass("B21d2", "Obligation à gauche", "obligation", "Obligation de tourner à gauche (B21-2 avant le panneau, B21c2 à la prochaine intersection)."),
    RoadClass("B21c1", "Tout droit ou à droite", "obligation", "Directions obligatoires : tout droit ou à droite."),
    RoadClass("B21c2", "Tout droit ou à gauche", "obligation", "Directions obligatoires : tout droit ou à gauche."),
    RoadClass("B21e", "À droite ou à gauche", "obligation", "Directions obligatoires : à droite ou à gauche."),
    RoadClass("B21a1", "Contournement par la droite", "obligation", "Contournement obligatoire par la droite."),
    RoadClass("B21a2", "Contournement par la gauche", "obligation", "Contournement obligatoire par la gauche."),
    RoadClass("B22a", "Piste cyclable obligatoire", "obligation", "Piste ou bande obligatoire pour les cycles, interdite aux autres véhicules."),
    RoadClass("B22b", "Chemin piétons obligatoire", "obligation", "Chemin obligatoire pour piétons."),
    # --- Zones et agglomération ---
    RoadClass("B30", "Zone 30", "zone", "Entrée de zone 30 : vitesse limitée à 30 km/h dans toute la zone.", vitesse=30, voix="Zone 30"),
    RoadClass("B51", "Fin de zone 30", "fin", "Sortie de zone 30 : retour à 50 km/h en agglomération.", vitesse=50, voix="Fin de zone 30"),
    RoadClass("EB10", "Entrée d'agglomération", "zone", "Entrée d'agglomération : 50 km/h sauf indication contraire.", vitesse=50, voix="Agglomération, 50"),
    RoadClass("EB20", "Sortie d'agglomération", "fin", "Sortie d'agglomération : 80 km/h en général (90 si la route le permet).", vitesse=80, voix="Sortie d'agglomération"),
    # --- Indication (C) ---
    RoadClass("C1a", "Parking", "indication", "Lieu aménagé pour le stationnement."),
    RoadClass("C12", "Sens unique", "indication", "Circulation à sens unique."),
    RoadClass("C13a", "Impasse", "indication", "Impasse : voie sans issue."),
    RoadClass("C18", "Prioritaire sur le sens inverse", "indication", "Passage étroit : vous êtes prioritaire sur les véhicules venant en sens inverse."),
    RoadClass("C20a", "Passage pour piétons", "indication", "Passage piétons : céder le passage aux piétons engagés ou s'apprêtant à traverser."),
    RoadClass("C107", "Route pour automobiles", "indication", "Route à accès réglementé : interdite aux piétons, cycles et véhicules lents."),
    RoadClass("C207", "Autoroute", "indication", "Début d'autoroute : 130 km/h (110 km/h par temps de pluie).", vitesse=130, voix="Autoroute"),
    # --- Marquages au sol ---
    RoadClass("M_passage_pietons", "Passage piétons (sol)", "marquage", "Céder le passage aux piétons qui traversent ou s'apprêtent à le faire.", voix="Passage piéton"),
    RoadClass("M_ligne_stop", "Ligne d'arrêt STOP", "marquage", "Ligne continue transversale : arrêt complet obligatoire à cette ligne."),
    RoadClass("M_ligne_cedez", "Ligne cédez-le-passage", "marquage", "Ligne discontinue transversale : céder le passage, s'arrêter si nécessaire."),
    RoadClass("M_stop_sol", "STOP au sol", "marquage", "Annonce d'un STOP : se préparer à marquer l'arrêt."),
    RoadClass("M_triangle_cedez", "Triangle cédez au sol", "marquage", "Annonce d'un cédez-le-passage."),
    RoadClass("M_fleche_tout_droit", "Flèche tout droit", "marquage", "Voie de sélection : tout droit."),
    RoadClass("M_fleche_droite", "Flèche à droite", "marquage", "Voie de sélection : tourner à droite."),
    RoadClass("M_fleche_gauche", "Flèche à gauche", "marquage", "Voie de sélection : tourner à gauche."),
    RoadClass("M_fleche_tout_droit_droite", "Flèche tout droit / droite", "marquage", "Voie de sélection : tout droit ou à droite."),
    RoadClass("M_fleche_tout_droit_gauche", "Flèche tout droit / gauche", "marquage", "Voie de sélection : tout droit ou à gauche."),
    RoadClass("M_fleche_rabattement", "Flèche de rabattement", "marquage", "Annonce une ligne continue ou une réduction de voies : se rabattre à droite.", voix="Rabattez-vous"),
    RoadClass("M_ligne_continue", "Ligne continue", "marquage", "Interdiction de franchir ou de chevaucher la ligne."),
    RoadClass("M_ligne_discontinue", "Ligne discontinue", "marquage", "Franchissable pour dépasser ou changer de voie, si sans danger."),
    RoadClass("M_ligne_mixte", "Ligne mixte", "marquage", "Franchissable uniquement du côté de la ligne discontinue."),
    RoadClass("M_zebras", "Zébras", "marquage", "Zone hachurée : interdiction d'y circuler, de s'y arrêter ou d'y stationner."),
    RoadClass("M_velo", "Marquage vélo", "marquage", "Bande ou piste cyclable, ou sas vélo : réservé aux cycles."),
    RoadClass("M_damier", "Damier", "marquage", "Damier : traversée d'une voie réservée aux bus."),
    RoadClass("M_dents_requin", "Dents de requin", "marquage", "Triangles au sol : ralentisseur à proximité, ralentir.", voix="Ralentisseur"),
    RoadClass("M_bus", "Voie de bus", "marquage", "Voie réservée aux bus : interdite aux autres véhicules."),
    RoadClass("M_zigzag", "Zigzag d'arrêt de bus", "marquage", "Arrêt d'autobus : arrêt et stationnement interdits aux autres véhicules."),
]

NAMES = [c.code for c in CLASSES]
BY_CODE = {c.code: i for i, c in enumerate(CLASSES)}
SIGN_CODES = [c.code for c in CLASSES if c.categorie != "marquage"]
MARKING_CODES = [c.code for c in CLASSES if c.categorie == "marquage"]

# Codes officiels (IISR) affichés, quand ils diffèrent de l'identifiant interne de la classe (gardé pour les modèles)
CODE_AFFICHE = {"B21d1": "B21c1", "B21d2": "B21c2", "B21c1": "B21d1", "B21c2": "B21d2"}
