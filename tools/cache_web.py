"""Cache des fichiers lourds de la version web (docs/), utilisé par tools/export_web.py et tools/zip_hebergement.py.
Bibliothèque standard seulement : le zip pour l'hébergeur doit pouvoir se fabriquer avec le Python du système, sans
torch, onnx ni YOLOv5 (importés par export_web.py)."""

import hashlib
import json
import re

LOURDS = (".onnx", ".wasm", ".mjs", ".png", ".jpg", ".woff2")  # mêmes fichiers que la fonction lourd() de docs/sw.js


def version_cache(web):
    """Donne au cache des fichiers lourds (modèles, icônes, photos du quiz, polices), dans sw.js, un nom tiré de leur
    contenu : dès que l'un d'eux change, les téléphones qui ont déjà l'appli passent à un nouveau cache.
    Écrit aussi docs/lourds.json, l'empreinte de chaque fichier : à la mise à jour, le service worker reprend de
    l'ancien cache les fichiers inchangés et ne retélécharge que ceux qui ont changé."""
    # (les captures d'écran du manifeste, docs/captures, ne servent qu'à la fenêtre d'installation : pas besoin hors ligne)
    fichiers = {f.relative_to(web).as_posix(): hashlib.sha1(f.read_bytes()).hexdigest()[:16] for f in sorted(web.rglob("*"))
                if f.is_file() and f.suffix in LOURDS and "captures" not in f.relative_to(web).parts}
    (web / "lourds.json").write_text(json.dumps({"fichiers": fichiers}, separators=(",", ":")), encoding="utf-8")
    nom = f"repere-lourds-{hashlib.sha1(json.dumps(fichiers, sort_keys=True).encode()).hexdigest()[:8]}"
    sw = web / "sw.js"
    js, n = re.subn(r'LOURDS = "repere-lourds-[^"]*"', f'LOURDS = "{nom}"', sw.read_text(encoding="utf-8"))
    if n != 1:
        raise SystemExit("sw.js : nom du cache des fichiers lourds introuvable")
    sw.write_text(js, encoding="utf-8")
    return nom
