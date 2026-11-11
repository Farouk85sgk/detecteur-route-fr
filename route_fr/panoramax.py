"""Correspondance entre les annotations de panneaux de Panoramax (clé « osm|traffic_sign ») et le catalogue.

Les annotations viennent de modèles automatiques : « FR:B14[50] », « FR:B6d;FR:M6h » (panneau + panonceau dans la même
boîte), noms génériques (« stop », « maxspeed »...) ou simplement « yes » (panneau non identifié).
"""

from route_fr.classes import SIGN_CODES, SIGNES_DETECTES

ALIAS = {"AB3": "AB3a", "AB3v": "AB3a", "B45": "B45a", "B6D": "B6d", "CE2e": "CE2a", "CE15g": "CE15a", "CE15h": "CE15a"}
ASSEMBLAGES = {
    ("B21", "1"): "B21-1", ("B21", "2"): "B21-2", ("B6d", "M6h"): "B6d_M6h", ("B6d", "M6a"): "B6d_M6a", ("B6d", "M6i"): "B6d_M6i",
    ("B6d", "M6j"): "B6d_M6j", ("B1", "M9v"): "B1_M9v", ("B1", "M1"): "B1_M1", ("C1a", "M4c"): "C1a_M4c",
}  # fmt: skip
GENERIQUES = {
    "maxspeed", "no_entry", "stop", "no_parking", "maxweightrating", "city_limit", "no_left_turn", "no_right_turn", "maxheight",
    "hazard", "give_way", "signal_ahead", "stop_ahead", "yield_ahead", "maxwidth", "no_u_turn",
}  # fmt: skip
BRUITES = {"Z", "C50", "C9"}  # étiquettes fourre-tout du modèle d'origine : jamais une classe


def _un(code):
    code = ALIAS.get(code, code)
    if code.startswith("B14[") and code[4:-1].isdigit():
        return f"B14_{code[4:-1]}"
    if code.startswith("B33["):
        return "B33"
    return code


def code_catalogue(brut):
    """(nature, code) d'une annotation Panoramax :
    - ("classe", code)  : panneau du catalogue reconnu par le classifieur ;
    - ("autre", None)   : un vrai panneau, mais hors des classes reconnues (ou étiquette peu fiable) ;
    - ("panneau", None) : un vrai panneau de type inconnu (nom générique) : utile au détecteur seulement ;
    - ("inconnu", None) : objet non identifié (« yes ») : ni exemple ni contre-exemple."""
    if brut in GENERIQUES:
        return "panneau", None
    parts = [_un(p[3:]) for p in brut.split(";") if p.startswith("FR:")]
    if not parts:
        return "inconnu", None
    code = parts[0] if len(parts) == 1 else ASSEMBLAGES.get(tuple(parts))
    if len(parts) == 2 and parts[1].lower() == "m9[rappel]":
        return "panneau", None  # panneau + panonceau « Rappel » dans la même boîte
    if code in SIGNES_DETECTES and code not in BRUITES:
        return "classe", code
    return ("autre", None) if code in SIGN_CODES or len(parts) == 1 else ("panneau", None)
