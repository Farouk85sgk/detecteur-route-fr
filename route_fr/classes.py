"""Catalogue des éléments du code de la route français connus de l'application.

- PANNEAUX : panneaux, panonceaux et balises, identifiés par leur code officiel (IISR) : "AB4", "B14_50" (B14 à 50 km/h),
  "B6d_M6h" (panneau B6d complété du panonceau M6h)...
- MARQUAGES : marquages au sol reconnus par le détecteur.
- DETECTEUR : classes du réseau de détection (YOLOv5). Il ne distingue pas les panneaux entre eux : une seule classe
  « panneau », que le classifieur (second étage) identifie ensuite. Les deux dernières classes ne sont jamais prédites :
  elles servent, à l'entraînement, à délimiter des zones (voir tools/train_cpu_bf16.py). Ne pas modifier l'ordre sans
  réentraîner.
- CLASSES = PANNEAUX + MARQUAGES : l'indice dans cette liste est l'identifiant de classe utilisé par l'application.

Les panneaux de FICHES_SEULES et les marquages de MARQUAGES_FICHES ont une fiche (album, quiz) mais ne sont pas
reconnus par les modèles, faute de photos réelles en nombre suffisant ou parce qu'ils sont trop difficiles à voir.
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
    "service": ((200, 90, 60), "Service"),
    "temporaire": ((0, 215, 255), "Signalisation temporaire"),
    "panonceau": ((235, 235, 235), "Panonceau"),
    "balise": ((210, 160, 90), "Balise / repère"),
    "marquage": ((80, 230, 80), "Marquage au sol"),
}

# Familles de l'album et de la quête : identifiant -> (nom, catégorie par défaut)
FAMILLES = {
    "dangers": ("Dangers", "danger"),
    "priorites": ("Intersections et priorités", "priorite"),
    "interdictions": ("Interdictions", "interdiction"),
    "vitesses": ("Limitations de vitesse", "interdiction"),
    "zones": ("Stationnement et zones", "zone"),
    "obligations": ("Obligations", "obligation"),
    "fins": ("Fins d'interdiction et d'obligation", "fin"),
    "indications": ("Indications", "indication"),
    "services": ("Services", "service"),
    "temporaire": ("Signalisation temporaire", "temporaire"),
    "reperes": ("Agglomérations, balises et repères", "balise"),
    "panonceaux": ("Panonceaux", "panonceau"),
    "marquages": ("Marquages au sol", "marquage"),
}


@dataclass(frozen=True)
class RoadClass:
    code: str  # identifiant : code officiel du panneau, ou M_... pour un marquage
    nom: str  # libellé court affiché
    categorie: str
    explication: str  # ce que l'élément signifie
    vitesse: int | None = None  # nouvelle vitesse maximale en km/h (mémoire de limitation)
    voix: str | None = None  # annonce vocale (None = le nom)
    famille: str = ""
    reflexe: str = ""  # ce qu'il faut faire ; vide = même texte que l'explication


PANNEAUX: list[RoadClass] = []
_famille = ["", ""]


def _fam(ident):
    _famille[:] = [ident, FAMILLES[ident][1]]


def _p(code, nom, explication, reflexe="", voix=None, vitesse=None, cat=None):
    PANNEAUX.append(RoadClass(code, nom, cat or _famille[1], explication, vitesse, voix, _famille[0], reflexe))


# ----------------------------------------------------------------------------- dangers (A)
_fam("dangers")
_p("A1a", "Virage à droite", "Virage dangereux à droite.", "Ralentis avant d'entrer dans le virage, pas pendant, et garde bien ta droite.")
_p("A1b", "Virage à gauche", "Virage dangereux à gauche.", "Ralentis avant le virage et reste bien à droite : tu ne vois pas ce qui arrive en face.")
_p("A1c", "Virages, le premier à droite", "Succession de virages dont le premier est à droite.", "Adapte ta vitesse à toute la série de virages ; ne dépasse pas sans visibilité.")
_p("A1d", "Virages, le premier à gauche", "Succession de virages dont le premier est à gauche.", "Adapte ta vitesse à toute la série de virages ; ne dépasse pas sans visibilité.")
_p("A2a", "Cassis ou dos-d'âne", "Déformation de la chaussée : un creux (cassis) ou une bosse (dos-d'âne).", "Ralentis avant la déformation pour garder le contrôle et ménager la voiture.")
_p("A2b", "Ralentisseur", "Ralentisseur de type dos-d'âne.", "Ralentis franchement (souvent 30 km/h) pour passer le ralentisseur sans à-coup.", voix="Ralentisseur")
_p("A3", "Chaussée rétrécie", "La chaussée se rétrécit des deux côtés.", "Ralentis et serre à droite ; si la place manque, laisse passer celui qui arrive en face.")
_p("A3a", "Chaussée rétrécie par la droite", "La chaussée se rétrécit par la droite.", "Ralentis : tu vas devoir te décaler vers la gauche, sans gêner ceux qui arrivent en face.")
_p("A3b", "Chaussée rétrécie par la gauche", "La chaussée se rétrécit par la gauche.", "Ralentis et serre à droite : la place pour se croiser diminue.")
_p("A4", "Chaussée glissante", "Chaussée particulièrement glissante.", "Augmente les distances de sécurité ; évite les freinages et les coups de volant brusques.")
_p("A6", "Pont mobile", "Pont mobile : il peut se lever pour laisser passer les bateaux.", "Ralentis et sois prêt à t'arrêter devant le feu rouge clignotant ou la barrière.")
_p("A7", "Passage à niveau avec barrières", "Passage à niveau muni de barrières ou de demi-barrières.", "Ne t'engage jamais si les barrières se baissent ou si le feu rouge clignote ; ne t'arrête jamais sur les voies.", voix="Passage à niveau")
_p("A8", "Passage à niveau sans barrière", "Passage à niveau sans barrière ni demi-barrière.", "Pas de barrière : ralentis, regarde des deux côtés et écoute avant de traverser les voies.", voix="Passage à niveau sans barrière")
_p("A9", "Traversée de tramways", "Traversée de voies de tramways.", "Le tramway est prioritaire : ralentis, regarde des deux côtés et ne reste jamais sur les voies.", voix="Tramway")
_p("A13a", "Enfants", "Endroit fréquenté par les enfants (école, aire de jeux).", "Ralentis : un enfant peut surgir entre deux voitures.", voix="Attention enfants")
_p("A13b", "Passage pour piétons (annonce)", "Passage pour piétons à proximité.", "Prépare-toi à t'arrêter : le piéton qui traverse ou s'apprête à traverser est prioritaire.")
_p("A14", "Autres dangers", "Danger autre que ceux des panneaux habituels ; un panonceau peut en préciser la nature.", "Ralentis et redouble d'attention ; s'il y a un panonceau, il te dit quel est le danger.")
_p("A15a1", "Animaux domestiques (bovins)", "Passage d'animaux domestiques, ici du bétail.", "Ralentis : des bêtes peuvent traverser et la chaussée peut être salie ; n'utilise pas le klaxon près d'elles.")
_p("A15a2", "Animaux domestiques (ovins)", "Passage d'animaux domestiques, ici des moutons.", "Ralentis : un troupeau peut occuper toute la route ; avance au pas sans klaxonner.")
_p("A15b", "Animaux sauvages", "Passage d'animaux sauvages.", "Ralentis, surtout à l'aube et au crépuscule. Face à un animal, freine fort sans donner de coup de volant.")
_p("A15c", "Cavaliers", "Passage de cavaliers.", "Ralentis et dépasse au pas en t'écartant largement, sans klaxonner : un cheval peut faire un écart.")
_p("A16", "Descente dangereuse", "Descente dangereuse ; la pente est indiquée en pourcentage.", "Utilise le frein moteur en rétrogradant pour ne pas faire chauffer les freins.")
_p("A17", "Feux tricolores (annonce)", "Annonce de feux tricolores.", "Anticipe : le feu peut passer au rouge, prépare-toi à t'arrêter.", voix="Feux tricolores")
_p("A18", "Circulation à double sens", "La circulation se fait de nouveau dans les deux sens.", "La route redevient à double sens : serre à droite, attention aux véhicules en face.")
_p("A19", "Chute de pierres", "Risque de chute de pierres, ou présence de pierres sur la route.", "Ne t'arrête pas dans la zone ; surveille la chaussée et sois prêt à contourner une pierre.")
_p("A20", "Débouché sur un quai ou une berge", "La route débouche sur un quai ou une berge.", "Ralentis : la route finit au bord de l'eau, souvent sans protection.")
_p("A21", "Débouché de cyclistes", "Débouché de cyclistes venant de droite ou de gauche.", "Ralentis : des cyclistes peuvent couper la route, de droite comme de gauche.")
_p("A23", "Aire de danger aérien", "Traversée d'une aire de danger aérien : des avions volent à basse altitude.", "Ne te laisse pas surprendre par le bruit ou le passage d'un avion : garde ta trajectoire.")
_p("A24", "Vent latéral", "Vent latéral fréquent et violent.", "Tiens fermement le volant et ralentis, surtout en dépassant un camion ou en sortant d'un abri.")

# ----------------------------------------------------------------------------- intersections et priorités (AB)
_fam("priorites")
_p("AB1", "Priorité à droite", "Intersection où la priorité à droite s'applique.", "À cette intersection, cède le passage aux véhicules qui arrivent de ta droite.", voix="Priorité à droite")
_p("AB2", "Priorité ponctuelle", "Intersection avec une route dont les usagers doivent te céder le passage.", "Tu es prioritaire à la prochaine intersection seulement : reste attentif.", voix="Prioritaire à la prochaine intersection")
_p("AB3a", "Cédez le passage", "Cédez le passage à l'intersection.", "Ralentis, regarde et cède le passage ; arrête-toi seulement si quelqu'un arrive.", voix="Cédez le passage")
_p("AB3b", "Cédez le passage annoncé", "Annonce d'un cédez-le-passage, à la distance indiquée par le panonceau.", "Commence à ralentir : tu devras céder le passage à l'intersection annoncée.", voix="Cédez le passage annoncé")
_p("AB4", "STOP", "Arrêt obligatoire à l'intersection, puis cédez le passage.", "Arrêt complet à la ligne, roues immobiles, même si personne n'arrive ; puis cède le passage.", voix="Stop")
_p("AB5", "STOP annoncé", "Annonce d'un STOP, à la distance indiquée par le panonceau.", "Ralentis progressivement : tu devras marquer l'arrêt à l'intersection annoncée.", voix="Stop annoncé")
_p("AB6", "Route prioritaire", "Tu circules sur une route à caractère prioritaire.", "Tu es prioritaire aux intersections jusqu'au panneau de fin de route prioritaire.")
_p("AB7", "Fin de route prioritaire", "Fin du caractère prioritaire de la route.", "Fin de ta priorité : aux intersections suivantes, la priorité à droite revient, sauf autre signalisation.", voix="Fin de route prioritaire", cat="fin")
_p("AB25", "Giratoire", "Carrefour à sens giratoire.", "Cède le passage aux véhicules déjà sur l'anneau ; clignotant à droite pour sortir.", voix="Giratoire")
_p("B15", "Cédez au sens inverse", "Cédez le passage à la circulation venant en sens inverse.", "Dans le passage étroit, laisse d'abord passer les véhicules qui arrivent en face.", cat="interdiction")
_p("C18", "Prioritaire sur le sens inverse", "Priorité par rapport à la circulation venant en sens inverse.", "Tu passes en premier dans le passage étroit, mais reste prudent.", cat="indication")

# ----------------------------------------------------------------------------- interdictions (B)
_fam("interdictions")
_p("B0", "Circulation interdite", "Circulation interdite à tout véhicule, dans les deux sens.", "Aucun véhicule ne peut circuler, dans les deux sens ; les piétons peuvent passer.")
_p("B1", "Sens interdit", "Sens interdit à tout véhicule.", "Ne t'engage pas : la circulation vient en face (souvent une rue à sens unique).", voix="Sens interdit")
_p("B1_M9v", "Sens interdit sauf vélos", "Sens interdit, sauf pour les cyclistes : la rue est à double-sens cyclable.", "Ne t'engage pas ; des cyclistes peuvent y entrer, et tu en croiseras si tu prends cette rue dans le sens autorisé.", voix="Sens interdit sauf vélos")
_p("B1_M1", "Sens interdit annoncé", "Annonce d'un sens interdit, à la distance indiquée par le panonceau.", "Prépare ton changement d'itinéraire : tu ne pourras pas continuer tout droit.")
_p("B2a", "Interdit de tourner à gauche", "Interdiction de tourner à gauche à la prochaine intersection.")
_p("B2b", "Interdit de tourner à droite", "Interdiction de tourner à droite à la prochaine intersection.")
_p("B2c", "Demi-tour interdit", "Interdiction de faire demi-tour jusqu'à la prochaine intersection incluse.")
_p("B3", "Dépassement interdit", "Interdiction de dépasser les véhicules à moteur, sauf les deux-roues sans side-car.", "Reste derrière le véhicule qui te précède ; tu peux seulement dépasser un deux-roues.")
_p("B3a", "Dépassement interdit aux poids lourds", "Interdiction de dépasser pour les véhicules de transport de marchandises de plus de 3,5 tonnes.", "En voiture, tu n'es pas concerné ; attends-toi à des camions qui restent en file à droite.")
_p("B4", "Arrêt au poste de douane", "Arrêt obligatoire au poste de douane.", "Arrête-toi au poste et attends l'autorisation de repartir.")
_p("B5a", "Arrêt au poste de gendarmerie", "Arrêt obligatoire au poste de gendarmerie.", "Arrête-toi et suis les indications des gendarmes.")
_p("B5b", "Arrêt au poste de police", "Arrêt obligatoire au poste de police.", "Arrête-toi et suis les indications des policiers.")
_p("B5c", "Arrêt au péage", "Arrêt obligatoire au poste de péage.", "Ralentis, choisis ta voie selon ton moyen de paiement et arrête-toi à la barrière.")
_p("B7a", "Interdit aux véhicules à moteur sauf cyclomoteurs", "Accès interdit aux véhicules à moteur, à l'exception des cyclomoteurs.")
_p("B7b", "Interdit à tous les véhicules à moteur", "Accès interdit à tous les véhicules à moteur.", "Ne t'engage pas en voiture ; piétons et cyclistes peuvent passer.")
_p("B8", "Interdit aux véhicules de marchandises", "Accès interdit aux véhicules affectés au transport de marchandises.", "En voiture, tu peux passer. Camionnettes et camions sont interdits, sauf si un panonceau fixe un poids qu'ils ne dépassent pas.")
_p("B9a", "Interdit aux piétons", "Accès interdit aux piétons.")
_p("B9b", "Interdit aux cycles", "Accès interdit aux cycles.")
_p("B9c", "Interdit aux véhicules à traction animale", "Accès interdit aux véhicules à traction animale.")
_p("B9d", "Interdit aux véhicules agricoles", "Accès interdit aux véhicules agricoles à moteur.")
_p("B9e", "Interdit aux voitures à bras", "Accès interdit aux voitures à bras.")
_p("B9f", "Interdit aux transports en commun", "Accès interdit aux véhicules de transport en commun de personnes.")
_p("B9g", "Interdit aux cyclomoteurs", "Accès interdit aux cyclomoteurs.")
_p("B9h", "Interdit aux motos", "Accès interdit aux motocyclettes et motocyclettes légères.")
_p("B9i", "Interdit aux caravanes et remorques", "Accès interdit aux véhicules tractant une caravane ou une remorque de plus de 250 kg.")
_p("B10a", "Longueur limitée", "Accès interdit aux véhicules ou ensembles plus longs que la longueur indiquée.")
_p("B11", "Largeur limitée", "Accès interdit aux véhicules dont la largeur, chargement compris, dépasse le nombre indiqué.", "Vérifie que ton véhicule passe, rétroviseurs et chargement compris.")
_p("B12", "Hauteur limitée", "Accès interdit aux véhicules dont la hauteur, chargement compris, dépasse le nombre indiqué.", "Pense au coffre de toit, aux vélos sur le toit ou à la camionnette de location.")
_p("B13", "Poids limité", "Accès interdit aux véhicules dont le poids total autorisé en charge (PTAC, ou PTRA avec une remorque) dépasse le nombre indiqué.", "Compare avec le PTAC inscrit sur ta carte grise (case F.2), même si tu roules à vide.")
_p("B13a", "Poids par essieu limité", "Accès interdit aux véhicules pesant, sur un essieu, plus que le nombre indiqué.")
_p("B16", "Signaux sonores interdits", "Usage de l'avertisseur sonore interdit, sauf danger immédiat.", "N'utilise pas le klaxon, sauf pour éviter un accident.")
_p("B17", "Distance minimale entre véhicules", "Interdiction de circuler sans laisser, entre deux véhicules, au moins l'intervalle indiqué.", "Garde au moins la distance indiquée avec le véhicule qui te précède (souvent en tunnel).")
_p("B18a", "Interdit aux matières explosives", "Accès interdit aux véhicules transportant des produits explosifs ou facilement inflammables.")
_p("B18b", "Interdit aux produits polluant les eaux", "Accès interdit aux véhicules transportant des produits de nature à polluer les eaux.")
_p("B18c", "Interdit aux matières dangereuses", "Accès interdit aux véhicules transportant des matières dangereuses signalées.")
_p("B19", "Autre interdiction", "Interdiction dont la nature est écrite sur le panneau.", "Lis l'inscription : elle précise ce qui est interdit.")

# ----------------------------------------------------------------------------- limitations de vitesse
_fam("vitesses")
for _v in (5, 10, 15, 20, 30, 40, 45, 50, 60, 70, 80, 90, 100, 110, 130):
    _p(f"B14_{_v}", f"Limitation {_v} km/h", f"Vitesse limitée à {_v} km/h à partir de ce panneau.",
       f"Ne dépasse pas {_v} km/h à partir de ce panneau ; par mauvais temps, roule encore moins vite.", voix=f"Limitation à {_v}", vitesse=_v)
_p("B33", "Fin de limitation de vitesse", "Fin de la limitation de vitesse indiquée.", "Fin de la limitation : la vitesse maximale générale de la route s'applique de nouveau.", voix="Fin de limitation", cat="fin")
_p("C4a", "Vitesse conseillée", "Vitesse conseillée : ce n'est pas une obligation.", "Roule de préférence à cette vitesse si les conditions sont bonnes ; la limitation en vigueur reste la même.", cat="indication")
_p("C4b", "Fin de vitesse conseillée", "Fin de la vitesse conseillée.", cat="indication")

# ----------------------------------------------------------------------------- stationnement et zones
_fam("zones")
_p("B6a1", "Stationnement interdit", "Stationnement interdit du côté du panneau, jusqu'à la prochaine intersection.", "Stationnement interdit, mais un arrêt bref (pour déposer quelqu'un) reste possible.", cat="interdiction")
_p("B6a2", "Stationnement interdit du 1er au 15", "Stationnement interdit du 1er au 15 du mois.", "Du 1er au 15, gare-toi de l'autre côté de la rue.", cat="interdiction")
_p("B6a3", "Stationnement interdit du 16 au 31", "Stationnement interdit du 16 à la fin du mois.", "Du 16 à la fin du mois, gare-toi de l'autre côté de la rue.", cat="interdiction")
_p("B6d", "Arrêt et stationnement interdits", "Arrêt et stationnement interdits.", "Ni arrêt ni stationnement : tu ne peux même pas t'arrêter pour déposer quelqu'un.", cat="interdiction")
_p("B6d_M6h", "Place réservée aux personnes handicapées", "Arrêt et stationnement interdits, sauf pour les titulaires de la carte de stationnement pour personnes handicapées.", "Ne t'y arrête jamais, même une minute : c'est un stationnement très gênant, avec mise en fourrière possible.", cat="interdiction")
_p("B6d_M6a", "Arrêt interdit, mise en fourrière", "Arrêt et stationnement interdits : le véhicule en infraction peut être enlevé.", "Ne t'arrête pas ici : le stationnement y est gênant et la voiture peut partir en fourrière.", cat="interdiction")
_p("B6d_M6i", "Place réservée à la recharge électrique", "Arrêt et stationnement interdits, sauf pour les véhicules électriques pendant leur recharge.", "Ne t'y gare pas avec une voiture thermique, ni avec une électrique qui ne recharge pas.", cat="interdiction")
_p("B6d_M6j", "Place réservée à l'autopartage", "Arrêt et stationnement interdits, sauf pour les véhicules d'autopartage.", cat="interdiction")
_p("B6b1", "Zone à stationnement interdit", "Entrée d'une zone où le stationnement est interdit.", "Le stationnement est interdit dans toute la zone, jusqu'au panneau de sortie.")
_p("B6b2", "Zone à stationnement unilatéral alterné", "Entrée d'une zone à stationnement unilatéral à alternance semi-mensuelle.", "Du 1er au 15, gare-toi du côté des numéros impairs ; du 16 à la fin du mois, du côté des numéros pairs.")
_p("B6b3", "Zone bleue (disque)", "Entrée d'une zone à stationnement de durée limitée, contrôlée par disque.", "Place ton disque de stationnement derrière le pare-brise et respecte la durée autorisée.")
_p("B6b4", "Zone à stationnement payant", "Entrée d'une zone à stationnement payant.", "Paie ton stationnement à l'horodateur ou par téléphone dans toute la zone.")
_p("B6b5", "Zone à stationnement alterné à durée limitée", "Entrée d'une zone à stationnement unilatéral alterné et de durée limitée par disque.")
_p("B50a", "Sortie de zone à stationnement interdit", "Sortie de zone à stationnement interdit.", cat="fin")
_p("B50b", "Sortie de zone à stationnement alterné", "Sortie de zone à stationnement unilatéral à alternance semi-mensuelle.", cat="fin")
_p("B50c", "Sortie de zone bleue", "Sortie de zone à stationnement de durée limitée par disque.", cat="fin")
_p("B50d", "Sortie de zone à stationnement payant", "Sortie de zone à stationnement payant.", cat="fin")
_p("B50e", "Sortie de zone alternée à durée limitée", "Sortie de zone à stationnement unilatéral alterné et de durée limitée.", cat="fin")
_p("B30", "Zone 30", "Entrée d'une zone à vitesse limitée à 30 km/h.", "30 km/h maximum dans toute la zone, jusqu'au panneau de sortie ; attention aux vélos à contresens.", voix="Zone 30", vitesse=30)
_p("B51", "Fin de zone 30", "Sortie de la zone à vitesse limitée à 30 km/h.", "Sortie de la zone 30 : en agglomération, la limite redevient en général 50 km/h.", voix="Fin de zone 30", vitesse=50, cat="fin")
_p("B52", "Zone de rencontre", "Entrée d'une zone de rencontre : 20 km/h, les piétons sont prioritaires sur toute la chaussée.", "Roule à 20 km/h au plus et laisse la priorité aux piétons, où qu'ils soient sur la chaussée.", voix="Zone de rencontre", vitesse=20)
_p("B53", "Fin de zone de rencontre", "Sortie de la zone de rencontre.", "En agglomération, la limite redevient en général 50 km/h ; les piétons retrouvent les trottoirs.", vitesse=50, cat="fin")
_p("B54", "Aire piétonne", "Entrée d'une aire piétonne, réservée aux piétons.", "N'entre que si tu y es autorisé, au pas, en laissant toujours la priorité aux piétons.", voix="Aire piétonne")
_p("B55", "Fin d'aire piétonne", "Sortie de l'aire piétonne.", cat="fin")
_p("B56", "Zone à faibles émissions", "Entrée d'une zone à circulation restreinte : seuls les véhicules autorisés y circulent, le plus souvent selon leur vignette Crit'Air.", "Lis le panonceau : n'entre que si ton véhicule est autorisé (vignette Crit'Air, jours et heures indiqués).")
_p("B57", "Fin de zone à faibles émissions", "Sortie de la zone à circulation restreinte.", cat="fin")
_p("B58", "Zone à équipements d'hiver obligatoires", "Entrée d'une zone de montagne où pneus hiver ou chaînes sont obligatoires du 1er novembre au 31 mars.", "Du 1er novembre au 31 mars, roule avec des pneus hiver ou garde des chaînes ou chaussettes à bord.")
_p("B59", "Fin de zone à équipements d'hiver", "Sortie de la zone où les équipements d'hiver sont obligatoires.", cat="fin")
_p("C1a", "Parking", "Lieu aménagé pour le stationnement.", cat="indication")
_p("C1b", "Parking à durée limitée (disque)", "Lieu aménagé pour le stationnement gratuit à durée limitée, contrôlée par disque.", "Place ton disque de stationnement et respecte la durée autorisée.", cat="indication")
_p("C1c", "Parking payant", "Lieu aménagé pour le stationnement payant.", cat="indication")
_p("C1a_M4c", "Parking motos", "Stationnement réservé aux motos.", "Ne te gare pas en voiture sur ces places.", cat="indication")

# ----------------------------------------------------------------------------- obligations (B21 à B29)
_fam("obligations")
_p("B21-1", "Obligation de tourner à droite", "Obligation de tourner à droite avant le panneau.", "Tourne à droite avant le panneau, dans le sens de la flèche.")
_p("B21-2", "Obligation de tourner à gauche", "Obligation de tourner à gauche avant le panneau.", "Tourne à gauche avant le panneau, dans le sens de la flèche.")
_p("B21a1", "Contournement par la droite", "Contournement obligatoire de l'obstacle par la droite.", "Contourne l'îlot ou l'obstacle par la droite.")
_p("B21a2", "Contournement par la gauche", "Contournement obligatoire de l'obstacle par la gauche.", "Contourne l'îlot ou l'obstacle par la gauche.")
_p("B21b", "Tout droit obligatoire", "Direction obligatoire à la prochaine intersection : tout droit.", "À la prochaine intersection, tu dois continuer tout droit.")
_p("B21c1", "À droite obligatoire", "Direction obligatoire à la prochaine intersection : à droite.", "À la prochaine intersection, tu dois tourner à droite.")
_p("B21c2", "À gauche obligatoire", "Direction obligatoire à la prochaine intersection : à gauche.", "À la prochaine intersection, tu dois tourner à gauche.")
_p("B21d1", "Tout droit ou à droite", "Directions obligatoires à la prochaine intersection : tout droit ou à droite.", "À la prochaine intersection : tout droit ou à droite, mais pas à gauche.")
_p("B21d2", "Tout droit ou à gauche", "Directions obligatoires à la prochaine intersection : tout droit ou à gauche.", "À la prochaine intersection : tout droit ou à gauche, mais pas à droite.")
_p("B21e", "À droite ou à gauche", "Directions obligatoires à la prochaine intersection : à droite ou à gauche.", "À la prochaine intersection : à droite ou à gauche, pas tout droit.")
_p("B22a", "Piste cyclable obligatoire", "Piste ou bande cyclable obligatoire pour les cyclistes.", "Les voitures n'y circulent pas et ne s'y arrêtent pas ; vérifie-la avant de tourner.")
_p("B22b", "Chemin obligatoire pour piétons", "Chemin obligatoire pour les piétons.", "Chemin réservé aux piétons : les véhicules n'y circulent pas.")
_p("B22c", "Chemin obligatoire pour cavaliers", "Chemin obligatoire pour les cavaliers.")
_p("B25", "Vitesse minimale obligatoire", "Vitesse minimale obligatoire, sauf si les conditions imposent de rouler moins vite.", "Roule au moins à la vitesse indiquée si la circulation et la météo le permettent.")
_p("B26", "Chaînes à neige obligatoires", "Chaînes à neige obligatoires sur au moins deux roues motrices.", "Monte tes chaînes avant de continuer (les pneus hiver peuvent être admis si un panonceau le précise).", voix="Chaînes à neige obligatoires")
_p("B27a", "Voie réservée aux bus", "Voie réservée aux véhicules des services réguliers de transport en commun.", "N'y circule pas et ne t'y arrête pas : elle est réservée aux bus.")
_p("B27b", "Voie réservée aux tramways", "Voie réservée aux tramways.", "N'y circule pas et ne t'y arrête pas : elle est réservée aux tramways.")
_p("B29", "Autre obligation", "Obligation dont la nature est écrite sur le panneau (par exemple « Allumez vos feux »).", "Lis l'inscription : elle précise ce que tu dois faire.")

# ----------------------------------------------------------------------------- fins d'interdiction et d'obligation
_fam("fins")
_p("B31", "Fin de toutes les interdictions", "Fin de toutes les interdictions précédemment signalées aux véhicules en mouvement.", "Les interdictions signalées avant (vitesse, dépassement...) prennent fin : les règles générales s'appliquent.", voix="Fin des interdictions")
_p("B34", "Fin d'interdiction de dépasser", "Fin de l'interdiction de dépasser.", "Tu peux de nouveau dépasser, si la ligne au sol et la visibilité le permettent.")
_p("B34a", "Fin d'interdiction de dépasser (poids lourds)", "Fin de l'interdiction de dépasser pour les poids lourds.")
_p("B35", "Fin d'interdiction des signaux sonores", "Fin de l'interdiction d'utiliser l'avertisseur sonore.")
_p("B39", "Fin d'une autre interdiction", "Fin d'une interdiction dont la nature est écrite sur le panneau.")
_p("B40", "Fin de piste cyclable obligatoire", "Fin de la piste ou bande cyclable obligatoire.", "Les cyclistes rejoignent la chaussée : attends-toi à en voir s'insérer devant toi.")
_p("B41", "Fin de chemin pour piétons", "Fin du chemin obligatoire pour piétons.")
_p("B42", "Fin de chemin pour cavaliers", "Fin du chemin obligatoire pour cavaliers.")
_p("B43", "Fin de vitesse minimale", "Fin de la vitesse minimale obligatoire.")
_p("B44", "Fin d'obligation des chaînes", "Fin de l'obligation d'utiliser les chaînes à neige.")
_p("B45a", "Fin de voie réservée aux bus", "Fin de la voie réservée aux transports en commun.", "Les bus rejoignent la circulation générale : laisse-les s'insérer.")
_p("B45b", "Fin de voie réservée aux tramways", "Fin de la voie réservée aux tramways.")
_p("B49", "Fin d'une autre obligation", "Fin d'une obligation dont la nature est écrite sur le panneau.")

# ----------------------------------------------------------------------------- indications (C)
_fam("indications")
_p("C2", "Hôpital", "Hôpital ou clinique à proximité (ancien panneau, encore très répandu).", "Reste discret : évite le klaxon, et facilite le passage des ambulances.")
_p("C3", "Risque d'incendie", "Forêt facilement inflammable : risque d'incendie.", "Ne jette ni cigarette ni déchet ; ne fais pas de feu.")
_p("C5", "Station de taxis", "Station de taxis : arrêt et stationnement réservés aux taxis en service.", "Ne t'arrête pas sur les emplacements réservés aux taxis.")
_p("C6", "Arrêt d'autobus", "Arrêt d'autobus.", "Ne t'arrête pas et ne stationne pas sur l'emplacement du bus ; en ville, laisse le bus quitter son arrêt.")
_p("C8", "Emplacement d'arrêt d'urgence", "Emplacement d'arrêt d'urgence.", "Ne t'y arrête qu'en cas de panne ou d'urgence.")
_p("C9", "Station d'autopartage", "Station d'autopartage.", "Les emplacements sont réservés aux véhicules d'autopartage.")
_p("C12", "Sens unique", "Circulation à sens unique.", "Tous les véhicules circulent dans le même sens ; attention aux vélos autorisés à contresens.")
_p("C13a", "Impasse", "Impasse : la rue est sans issue.")
_p("C13b", "Impasse annoncée", "Présignalisation d'une impasse : une des branches de l'intersection est sans issue.")
_p("C13c", "Impasse avec issue pour piétons", "Impasse comportant une issue pour les piétons.")
_p("C13d", "Impasse avec issue pour piétons et cyclistes", "Impasse comportant une issue pour les piétons et les cyclistes.")
_p("C14", "Praticabilité d'une route", "Praticabilité d'une section de route (col ouvert ou fermé, équipements conseillés).", "Lis l'état de la route avant de t'engager, surtout en montagne l'hiver.")
_p("C20a", "Passage pour piétons", "Passage pour piétons.", "Le piéton qui s'engage ou montre qu'il va traverser est prioritaire : prépare-toi à t'arrêter.", voix="Passage piétons")
_p("C20b", "Traversée de voies de bus", "Traversée de voies réservées aux bus.", "Regarde des deux côtés : un bus peut arriver sur sa voie réservée.")
_p("C20c", "Traversée de tramways", "Traversée de voies de tramways.", "Le tramway est prioritaire : regarde des deux côtés et ne t'arrête pas sur les voies.", voix="Traversée de tramways")
_p("C23", "Stationnement réglementé pour caravanes", "Stationnement réglementé pour les caravanes et les autocaravanes.")
_p("C24a", "Double-sens cyclable", "Conditions particulières de circulation par voie : ici, les vélos circulent aussi dans l'autre sens, sur leur voie.", "Attends-toi à croiser des vélos venant en face ; ne mords pas sur leur voie, surtout en tournant.")
_p("C24b", "Voies affectées", "Voies affectées à l'approche d'une intersection.", "Place-toi tôt dans la voie qui correspond à ta direction.")
_p("C24c", "Conditions particulières sur la route abordée", "Conditions particulières de circulation sur la route ou la voie abordée.")
_p("C25a", "Limitations de vitesse en France", "Rappel, à la frontière, des limitations générales de vitesse en France.")
_p("C26a", "Voie de détresse à droite", "Voie de détresse à droite, pour les véhicules dont les freins ne répondent plus.", "N'y stationne jamais : elle sert à arrêter un véhicule sans freins dans une descente.")
_p("C26b", "Voie de détresse à gauche", "Voie de détresse à gauche.", "N'y stationne jamais : elle sert à arrêter un véhicule sans freins dans une descente.")
_p("C27", "Surélévation de chaussée", "Surélévation de chaussée : ralentisseur ou plateau.", "Ralentis franchement avant la surélévation.", voix="Ralentisseur")
_p("C28", "Réduction du nombre de voies", "Réduction du nombre de voies.", "Si ta voie disparaît, insère-toi sans forcer le passage ; sinon, laisse s'insérer ceux qui perdent leur voie, chacun son tour.")
_p("C29a", "Créneau de dépassement", "Présignalisation d'un créneau de dépassement ou d'une section à chaussées séparées.", "Attends le créneau pour dépasser en sécurité.")
_p("C30", "Fin de créneau de dépassement", "Fin du créneau de dépassement.", "Termine ton dépassement et rabats-toi : la route repasse à une voie par sens.")
_p("C50", "Indication diverse", "Indication écrite sur le panneau (par exemple « Arrêt autorisé sur trottoir »).")
_p("C51a", "Section à vitesse régulée", "Début d'une section où la vitesse maximale varie selon le trafic.", "Respecte la vitesse affichée sur les panneaux lumineux.")
_p("C62", "Borne de ticket de péage", "Présignalisation d'une borne de retrait de ticket de péage.", "Prends ton ticket à la borne : tu paieras à la sortie.")
_p("C64a", "Paiement auprès d'un péagiste", "Voie de péage avec paiement auprès d'un péagiste.")
_p("C64d", "Voie de télépéage", "Voie de péage réservée aux abonnés au télépéage.", "N'emprunte cette voie que si tu as un badge de télépéage.")
_p("C107", "Route à accès réglementé", "Route à accès réglementé (route pour automobiles).", "Interdite aux piétons, aux cyclistes, aux cyclomoteurs et aux tracteurs ; ni arrêt ni demi-tour.", voix="Route pour automobiles")
_p("C108", "Fin de route à accès réglementé", "Fin de la route à accès réglementé.", cat="fin")
_p("C111", "Tunnel", "Entrée d'un tunnel.", "Allume tes feux de croisement, enlève tes lunettes de soleil et garde tes distances.", voix="Tunnel")
_p("C112", "Fin de tunnel", "Sortie du tunnel.", cat="fin")
_p("C113", "Piste cyclable conseillée", "Piste ou bande cyclable conseillée, réservée aux cycles.", "N'y circule pas en voiture ; vérifie-la avant de tourner ou d'ouvrir ta portière.")
_p("C114", "Fin de piste cyclable conseillée", "Fin de la piste ou bande cyclable conseillée.", cat="fin")
_p("C115", "Voie verte", "Voie verte, réservée aux piétons et aux véhicules non motorisés.", "N'y circule pas avec un véhicule à moteur.")
_p("C116", "Fin de voie verte", "Fin de la voie verte.", cat="fin")
_p("C207", "Autoroute", "Début d'une section d'autoroute.", "130 km/h maximum par temps sec, 110 par temps de pluie, et jamais plus de 110 en apprentissage ou en permis probatoire ; ni piétons ni vélos, ni arrêt ni demi-tour.", voix="Autoroute", vitesse=130)
_p("C208", "Fin d'autoroute", "Fin de l'autoroute.", "Ralentis et réadapte ta conduite : les règles de la route ordinaire s'appliquent.", cat="fin")

# ----------------------------------------------------------------------------- services (CE)
_fam("services")
_p("CE1", "Poste de secours", "Poste de secours.")
_p("CE2a", "Poste d'appel d'urgence", "Poste d'appel d'urgence (borne SOS).", "En cas de panne ou d'accident, la borne te met en relation avec les secours et te localise.")
_p("CE2b", "Cabine téléphonique", "Cabine téléphonique publique.")
_p("CE3a", "Information touristique", "Informations relatives aux services ou aux activités touristiques.")
_p("CE3b", "Relais d'information service", "Panneau du relais d'information service.")
_p("CE4a", "Camping pour tentes", "Terrain de camping pour tentes.")
_p("CE4b", "Camping pour caravanes", "Terrain de camping pour caravanes et autocaravanes.")
_p("CE4c", "Camping tentes et caravanes", "Terrain de camping pour tentes, caravanes et autocaravanes.")
_p("CE5a", "Auberge de jeunesse", "Auberge de jeunesse.")
_p("CE5b", "Chambres d'hôtes ou gîte", "Chambres d'hôtes ou gîte.")
_p("CE6a", "Départ de randonnée pédestre", "Point de départ d'un itinéraire pédestre.")
_p("CE6b", "Départ de ski de fond", "Point de départ d'un circuit de ski de fond.")
_p("CE7", "Aire de pique-nique", "Emplacement pour pique-nique.")
_p("CE8", "Gare auto-train", "Gare auto-train.")
_p("CE9", "Parking sous vidéosurveillance", "Parc de stationnement sous vidéosurveillance.")
_p("CE10", "Embarcadère", "Embarcadère.")
_p("CE12", "Toilettes", "Toilettes ouvertes au public.")
_p("CE14", "Accessible aux personnes handicapées", "Installations accessibles aux personnes handicapées à mobilité réduite.")
_p("CE15a", "Station-service", "Poste de distribution de carburant.")
_p("CE15c", "Station-service avec GPL", "Poste de distribution de carburant assurant aussi le ravitaillement en GPL.")
_p("CE15i", "Borne de recharge électrique", "Poste de recharge pour véhicules électriques.")
_p("CE16", "Restaurant", "Restaurant.")
_p("CE17", "Hôtel", "Hôtel ou motel.")
_p("CE18", "Café", "Débit de boissons ou établissement proposant des collations.")
_p("CE19", "Mise à l'eau de bateaux", "Emplacement de mise à l'eau d'embarcations légères.")
_p("CE20a", "Téléphérique", "Gare de téléphérique.")
_p("CE20b", "Télésiège ou télécabine", "Point de départ d'un télésiège ou d'une télécabine.")
_p("CE21", "Point de vue", "Point de vue.")
_p("CE22", "Radio d'information routière", "Fréquence d'une radio dédiée aux informations sur la circulation.", "Règle l'autoradio avant de partir ou à l'arrêt, pas en conduisant.")
_p("CE23", "Jeux d'enfants", "Jeux d'enfants.")
_p("CE24", "Vidange pour camping-cars", "Station de vidange pour caravanes, autocaravanes et cars.")
_p("CE25", "Distributeur de billets", "Distributeur de billets de banque.")
_p("CE26", "Station de gonflage", "Station de gonflage des pneus.")
_p("CE28", "Poste de dépannage", "Poste de dépannage.")
_p("CE29", "Extincteur", "Moyen de lutte contre l'incendie.")
_p("CE30a", "Issue de secours à droite", "Issue de secours vers la droite.", "En cas d'incendie dans un tunnel, quitte ton véhicule et rejoins à pied l'issue de secours.")
_p("CE30b", "Issue de secours à gauche", "Issue de secours vers la gauche.", "En cas d'incendie dans un tunnel, quitte ton véhicule et rejoins à pied l'issue de secours.")
_p("CE50", "Service divers", "Installation ou service divers, précisé sur le panneau.")
_p("CE52", "Aire de covoiturage", "Parking de covoiturage.")

# ----------------------------------------------------------------------------- signalisation temporaire (fond jaune)
_fam("temporaire")
_p("AK2", "Cassis ou dos-d'âne (temporaire)", "Signalisation temporaire : déformation de la chaussée.", "Ralentis : la chaussée est déformée dans la zone de chantier.")
_p("AK3", "Chaussée rétrécie (temporaire)", "Signalisation temporaire : chaussée rétrécie.", "Ralentis et serre à droite : la zone de chantier réduit la largeur de la route.")
_p("AK4", "Chaussée glissante (temporaire)", "Signalisation temporaire : chaussée glissante.", "Ralentis et augmente tes distances : boue, gravillons ou enrobé frais.")
_p("AK5", "Travaux", "Signalisation temporaire : travaux.", "Ralentis et attends-toi à des ouvriers, des engins ou une voie neutralisée.", voix="Travaux")
_p("AK14", "Autres dangers (temporaire)", "Signalisation temporaire : danger particulier, parfois précisé par un panonceau.", "Ralentis et sois prêt à t'arrêter ; lis le panonceau s'il y en a un.")
_p("AK17", "Feux de chantier (annonce)", "Signalisation temporaire : annonce de feux réglant la circulation.", "Prépare-toi à t'arrêter au feu de chantier : la circulation est alternée.")
_p("AK22", "Projection de gravillons", "Signalisation temporaire : projection de gravillons.", "Ralentis et augmente les distances pour protéger ton pare-brise et celui des autres.")
_p("AK30", "Bouchon", "Signalisation temporaire : bouchon.", "Ralentis, allume tes feux de détresse à l'approche de la file et garde une marge devant toi.", voix="Bouchon")
_p("AK31", "Accident", "Signalisation temporaire : accident.", "Ralentis, ne t'arrête pas pour regarder et facilite le passage des secours.")
_p("AK32", "Brouillard ou fumées", "Signalisation temporaire : nappes de brouillard ou fumées épaisses.", "Ralentis, allume tes feux de croisement et de brouillard, augmente tes distances.")
_fam("interdictions")  # le B1j est un panneau permanent (créé en 2015) : rangé avec les interdictions, sans le déplacer dans la liste
_p("B1j", "Sens interdit sur fond jaune", "Sens interdit sur fond jaune vif, pour être mieux vu : on le trouve surtout au bout des bretelles de sortie d'autoroute et de voie rapide, pour éviter les contresens.", "Ne t'engage surtout pas : sur une bretelle de sortie, tu roulerais à contresens.", voix="Sens interdit")

# ----------------------------------------------------------------------------- agglomérations, balises et repères
_fam("reperes")
_p("EB10", "Entrée d'agglomération", "Entrée d'agglomération : la vitesse est limitée à 50 km/h, sauf indication contraire.", "50 km/h maximum sauf indication contraire ; klaxon seulement en cas de danger immédiat.", voix="Entrée d'agglomération", vitesse=50, cat="zone")
_p("EB20", "Sortie d'agglomération", "Sortie d'agglomération : fin des règles propres à l'agglomération.", "Fin de l'agglomération : la vitesse générale hors agglomération s'applique (souvent 80 km/h).", voix="Sortie d'agglomération", vitesse=80, cat="fin")
_p("J3", "Balise d'intersection", "Balise blanche à anneau rouge : elle signale une intersection hors agglomération.", "Une route débouche ici : ralentis et regarde si un véhicule s'apprête à sortir.")
_p("J5", "Balise de tête d'îlot", "Balise signalant la tête d'un îlot directionnel : passe du côté indiqué par la flèche.", "Contourne l'îlot du côté de la flèche.")
_p("J13", "Balise d'obstacle", "Balise à bandes obliques bleues et blanches : elle signale un obstacle tout proche du bord de la chaussée, comme un muret ou un petit pont.", "Écarte-toi de l'obstacle et ralentis si tu dois croiser un autre véhicule.")
_p("J10", "Balises de passage à niveau", "Balises annonçant un passage à niveau : trois, deux puis une barre rouge, tous les 50 m environ.", "Compte les barres : à la dernière balise, le passage à niveau est à une cinquantaine de mètres.")
_p("SR3", "Contrôle radar", "Zone où la vitesse est contrôlée par un radar automatique.", "Vérifie ta vitesse : elle est contrôlée, ici ou dans les kilomètres qui suivent.", voix="Contrôle radar", cat="indication")

# ----------------------------------------------------------------------------- panonceaux (M)
_fam("panonceaux")
_p("M1", "Panonceau de distance", "Distance entre le panneau et le début du danger ou de la prescription.", "Le danger ou la règle commence à la distance indiquée.")
_p("M2", "Panonceau d'étendue", "Longueur de la section concernée par le danger ou la prescription.", "Le danger ou la règle s'applique sur toute la longueur indiquée.")
_p("M3", "Panonceau de position", "Flèche indiquant la voie ou la direction concernée par le panneau.")
_p("M4a", "Panonceau : voitures", "Le panneau concerne les véhicules légers.")
_p("M4b", "Panonceau : transports en commun", "Le panneau concerne les véhicules de transport en commun.")
_p("M4c", "Panonceau : motos", "Le panneau concerne les motocyclettes.")
_p("M4d1", "Panonceau : vélos", "Le panneau concerne les cycles.")
_p("M4d2", "Panonceau : cyclomoteurs", "Le panneau concerne les cyclomoteurs.")
_p("M4f", "Panonceau : poids", "Le panneau concerne les véhicules dont le poids total autorisé en charge (PTAC) dépasse le nombre indiqué.")
_p("M4g", "Panonceau : transport de marchandises", "Le panneau concerne les véhicules de transport de marchandises.")
_p("M5", "Panonceau STOP à distance", "Annonce la distance à laquelle se trouve le STOP.", "Ralentis : tu devras marquer l'arrêt à la distance indiquée.")
_p("M6a", "Panonceau : mise en fourrière", "Stationnement gênant : le véhicule peut être mis en fourrière.")
_p("M6c", "Panonceau : durée limitée (disque)", "Stationnement à durée limitée, contrôlée par disque.")
_p("M6d", "Panonceau : stationnement payant", "Stationnement payant.")
_p("M6h", "Panonceau : sauf personnes handicapées", "Emplacement réservé aux titulaires de la carte de stationnement pour personnes handicapées.")
_p("M6i", "Panonceau : sauf recharge électrique", "Emplacement réservé aux véhicules électriques pendant leur recharge.")
_p("M6j", "Panonceau : sauf autopartage", "Emplacement réservé aux véhicules d'autopartage.")
_p("M7", "Panonceau schéma d'intersection", "Schéma de l'intersection : le trait épais montre la route prioritaire.", "Repère le trait épais : c'est la branche prioritaire de l'intersection.")
_p("M8", "Panonceau d'application", "Flèches indiquant où commence, continue ou finit la prescription (stationnement...).")
_p("M9a", "Panonceau : avion", "Précise le danger : passage d'avions à basse altitude.")
_p("M9c", "Panonceau « Cédez le passage »", "Rappelle l'obligation de céder le passage.")
_p("M9d", "Panonceau : passage surélevé", "Sous un panneau de passage pour piétons : le passage est surélevé, comme un ralentisseur.")
_p("M9e", "Panonceau SOS", "Poste d'appel d'urgence.")
_p("M9v", "Panonceau « Sauf vélos »", "L'interdiction ne s'applique pas aux cyclistes.", "Attends-toi à voir des vélos là où les autres véhicules sont interdits.")
_p("M9z", "Panonceau à inscription", "Indication écrite : « Rappel », « Verglas fréquent », « Sauf riverains »...", "Lis l'inscription : elle complète le panneau placé au-dessus.")
_p("M10", "Panonceau d'identification de route", "Numéro de la route (A, N, D, M...).")
_p("M11", "Panonceau de dérogation", "Catégories d'usagers autorisés malgré l'interdiction, ou horaires d'application.")
_p("M12d", "Cédez-le-passage cycliste : à droite", "Au feu, les cyclistes peuvent tourner à droite sans attendre le vert, en cédant le passage.", "Au feu rouge, un cycliste peut te passer à droite pour tourner : contrôle ton angle mort.")
_p("M12f", "Cédez-le-passage cycliste : tout droit", "Au feu, les cyclistes peuvent continuer tout droit sans attendre le vert, en cédant le passage.", "Au feu rouge, un cycliste peut continuer tout droit : il doit céder le passage, mais reste attentif.")
_p("M12fd", "Cédez-le-passage cycliste : tout droit ou à droite", "Au feu, les cyclistes peuvent continuer tout droit ou tourner à droite sans attendre le vert, en cédant le passage.")

# ----------------------------------------------------------------------------- marquages au sol
MARQUAGES = [
    RoadClass("M_passage_pietons", "Passage piétons (sol)", "marquage", "Bandes blanches : passage pour piétons.", famille="marquages",
              reflexe="Le piéton engagé ou qui s'apprête à traverser est prioritaire ; ne t'arrête pas sur les bandes.", voix="Passage piétons"),
    RoadClass("M_ligne_stop", "Ligne d'arrêt STOP", "marquage", "Large ligne blanche continue en travers de la voie : arrêt obligatoire.", famille="marquages",
              reflexe="Arrête-toi complètement juste avant la ligne, puis cède le passage."),
    RoadClass("M_ligne_cedez", "Ligne cédez-le-passage", "marquage", "Ligne de larges traits blancs en travers de la voie : cédez le passage.", famille="marquages",
              reflexe="Si tu dois céder le passage, arrête-toi avant cette ligne en pointillés."),
    RoadClass("M_stop_sol", "STOP au sol", "marquage", "Inscription STOP peinte sur la chaussée.", famille="marquages", reflexe="Prépare-toi à marquer l'arrêt complet à la ligne."),
    RoadClass("M_triangle_cedez", "Triangle cédez au sol", "marquage", "Triangle peint sur la chaussée : annonce d'un cédez-le-passage.", famille="marquages"),
    RoadClass("M_fleche_tout_droit", "Flèche tout droit", "marquage", "Flèche directionnelle : voie pour aller tout droit.", famille="marquages", reflexe="Choisis ta voie selon ta direction : cette voie va tout droit."),
    RoadClass("M_fleche_droite", "Flèche à droite", "marquage", "Flèche directionnelle : voie pour tourner à droite.", famille="marquages", reflexe="Choisis ta voie selon ta direction : cette voie tourne à droite."),
    RoadClass("M_fleche_gauche", "Flèche à gauche", "marquage", "Flèche directionnelle : voie pour tourner à gauche.", famille="marquages", reflexe="Choisis ta voie selon ta direction : cette voie tourne à gauche."),
    RoadClass("M_fleche_tout_droit_droite", "Flèche tout droit / droite", "marquage", "Flèche directionnelle : tout droit ou à droite.", famille="marquages"),
    RoadClass("M_fleche_tout_droit_gauche", "Flèche tout droit / gauche", "marquage", "Flèche directionnelle : tout droit ou à gauche.", famille="marquages"),
    RoadClass("M_fleche_rabattement", "Flèche de rabattement", "marquage", "Flèche oblique : la ligne va devenir continue.", famille="marquages",
              reflexe="Termine ton dépassement et rabats-toi à droite : la ligne continue arrive."),
    RoadClass("M_ligne_continue", "Ligne continue", "marquage", "Ligne continue : interdit de la franchir ou de la chevaucher.", famille="marquages"),
    RoadClass("M_ligne_discontinue", "Ligne discontinue", "marquage", "Ligne discontinue : franchissable pour dépasser ou changer de voie.", famille="marquages",
              reflexe="Tu peux la franchir pour dépasser ou tourner, si c'est sans danger."),
    RoadClass("M_ligne_mixte", "Ligne mixte", "marquage", "Ligne continue doublée d'une ligne discontinue.", famille="marquages", reflexe="Tu peux la franchir seulement si la partie discontinue est de ton côté."),
    RoadClass("M_zebras", "Zébras", "marquage", "Zone hachurée qui sépare ou guide les voies.", famille="marquages", reflexe="N'y circule pas et ne t'y arrête pas."),
    RoadClass("M_velo", "Marquage vélo", "marquage", "Pictogramme vélo : bande ou piste cyclable, sas pour cyclistes.", famille="marquages", reflexe="Espace pour les cyclistes : laisse-leur la place."),
    RoadClass("M_damier", "Damier", "marquage", "Damier : traversée d'une voie réservée aux bus.", famille="marquages", reflexe="Tu traverses un couloir réservé aux bus : regarde bien s'il en arrive."),
    RoadClass("M_dents_requin", "Dents de requin", "marquage", "Triangles blancs au sol : ralentisseur ou plateau surélevé.", famille="marquages", reflexe="Ralentisseur ou plateau tout proche : ralentis.", voix="Ralentisseur"),
    RoadClass("M_bus", "Voie de bus", "marquage", "Inscription BUS : voie réservée aux bus.", famille="marquages", reflexe="N'y circule pas et ne t'y arrête pas."),
    RoadClass("M_zigzag", "Zigzag d'arrêt de bus", "marquage", "Ligne jaune en zigzag : emplacement d'arrêt d'autobus.", famille="marquages", reflexe="Ni arrêt ni stationnement pour les autres véhicules."),
    RoadClass("M_ligne_dissuasion", "Ligne de dissuasion", "marquage", "Traits longs et rapprochés : dépassement déconseillé, sauf véhicule très lent.", famille="marquages",
              reflexe="Ne la franchis que pour dépasser un véhicule très lent (tracteur, cycliste)."),
    RoadClass("M_ligne_rive", "Ligne de rive", "marquage", "Ligne qui marque le bord de la chaussée.", famille="marquages", reflexe="Elle délimite le bord de la chaussée : ne roule pas dessus, sauf pour t'arrêter sur l'accotement."),
    RoadClass("M_ligne_feux", "Ligne d'effet des feux", "marquage", "Ligne de traits fins en travers de la voie : endroit où s'arrêter au feu rouge.", famille="marquages", reflexe="Au feu rouge ou orange, arrête-toi avant cette ligne."),
]

CLASSES = PANNEAUX + MARQUAGES
# Panneaux qui effacent la vitesse maximale gardée en mémoire sans en donner une nouvelle (fin de limitation, fin de toutes
# les interdictions, fin d'autoroute : la limite d'après dépend de la route)
FINS_VITESSE = ("B33", "B31", "C208")
NAMES = [c.code for c in CLASSES]
BY_CODE = {c.code: i for i, c in enumerate(CLASSES)}
SIGN_CODES = [c.code for c in PANNEAUX]
MARKING_CODES = [c.code for c in MARQUAGES]

# Marquages du catalogue que le détecteur n'apprend pas (fiche seulement) : la ligne d'effet des feux, trait trop fin
# pour être vu de loin, se confondait avec les lignes de STOP et de cédez-le-passage.
MARQUAGES_FICHES = {"M_ligne_feux"}

# Réseau de détection : « panneau », puis les marquages, puis deux classes techniques réservées à l'entraînement :
# « _ignorer » (zone douteuse : ni objet ni fond) et « _reel » (zone d'une vraie photo, où seuls les panneaux sont annotés)
DETECTEUR = ["panneau"] + [c for c in MARKING_CODES if c not in MARQUAGES_FICHES] + ["_ignorer", "_reel"]
DET_PANNEAU, DET_IGNORER, DET_REEL = 0, len(DETECTEUR) - 2, len(DETECTEUR) - 1
DET_MARQUAGE = {c: i for i, c in enumerate(DETECTEUR) if c.startswith("M_")}

# Fiches seulement (pas ou trop peu de photos réelles pour apprendre à les reconnaître)
FICHES_SEULES = {
    "B4", "B5a", "B5b", "B9c", "B9e", "B6b5", "B50b", "B50e", "B58", "B59", "B22c", "B25", "B35", "B39", "B42", "B43", "B44", "B45b", "B49", "C4b",
    "C9", "C13c", "C13d", "C14", "C24b", "C24c", "C25a", "C28", "C29a", "C30", "C50", "C51a", "C64a",
    "CE1", "CE2b", "CE3b", "CE4b", "CE6b", "CE8", "CE9", "CE10", "CE20a", "CE20b", "CE25", "CE26", "CE29", "CE30a", "CE30b", "CE50",
    "AK31", "AK32", "J10", "M1", "M2", "M3", "M4a", "M4b", "M4c", "M4d1", "M4d2", "M4f", "M4g", "M5", "M6a", "M6c", "M6d", "M6j",
    "M7", "M8", "M9a", "M9c", "M9d", "M9e", "M9z", "M10", "M11",
}
SIGNES_DETECTES = [c for c in SIGN_CODES if c not in FICHES_SEULES]  # classes du classifieur (plus « autre » et « fond »)


def code_affiche(code):
    """Code officiel à afficher : "B14_50" -> "B14", "B6d_M6h" -> "B6d + M6h"."""
    if code.startswith("B14_"):
        return "B14"
    return code.replace("_", " + ") if not code.startswith("M_") else ""


CODE_AFFICHE = {c.code: code_affiche(c.code) for c in CLASSES}
