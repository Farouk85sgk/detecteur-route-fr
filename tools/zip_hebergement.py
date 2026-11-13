"""Fabrique un fichier .zip de l'appli web « Repère », prêt à déposer chez un hébergeur (Hostinger, o2switch, OVH...).

Le zip contient un seul dossier (« repere » par défaut). Une fois extrait dans le dossier public du site
(public_html), l'appli répond à l'adresse https://votre-domaine/repere/ sans toucher au reste du site.
Deux fichiers sont ajoutés au contenu de docs/ :
- .htaccess : types des fichiers et consignes de cache (les mises à jour de l'appli arrivent tout de suite) ;
- LISEZ-MOI.txt : la marche à suivre, pas à pas.

    python tools/zip_hebergement.py --sortie repere-hostinger.zip
"""

import argparse
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HTACCESS = """# Appli « Repère » : réglages pour l'hébergeur (Apache / LiteSpeed)
AddType application/manifest+json .webmanifest
AddType application/wasm .wasm
AddType application/octet-stream .onnx
AddType text/javascript .js .mjs
AddType font/woff2 .woff2
AddDefaultCharset utf-8

<IfModule mod_headers.c>
  # pages, scripts et données : toujours vérifiés auprès du serveur, pour que les mises à jour arrivent tout de suite
  <FilesMatch "\\.(html|js|css|json|webmanifest)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
</IfModule>
"""

LISEZ_MOI = """REPÈRE : mettre l'appli sur votre site, puis sur votre téléphone
================================================================

1) Sur Hostinger
   - Ouvrez hPanel, puis « Sites web » et « Gestionnaire de fichiers ».
   - Entrez dans le dossier « public_html ».
   - Importez le fichier zip, puis faites un clic droit dessus et choisissez « Extraire »
     (extraire dans public_html). Un dossier « {dossier} » apparaît.
   - Vérifiez que le certificat SSL du site est actif (adresse en https) : sans https,
     le téléphone refuse d'ouvrir la caméra.

   L'appli est alors à l'adresse :  https://VOTRE-DOMAINE/{dossier}/
   Le reste de votre site n'est pas modifié.
   (L'adresse suit les dossiers : si, après l'extraction, l'appli se trouve dans
   public_html/{dossier}/{dossier}, l'adresse devient https://VOTRE-DOMAINE/{dossier}/{dossier}/ .)

2) Sur le téléphone (Android, par exemple Xiaomi)
   - Ouvrez cette adresse avec Chrome.
   - Touchez le menu (les trois points en haut à droite), puis « Ajouter à l'écran d'accueil »
     ou « Installer l'application ». L'icône « Repère » apparaît avec vos autres applis.
   - Sur un Xiaomi, si l'icône n'apparaît pas : Paramètres > Applications > Gérer les applications
     > Chrome > Autres autorisations, puis activez « Raccourcis sur l'écran d'accueil » et recommencez.
   - Au premier lancement de la caméra, acceptez l'autorisation « Caméra »
     (et « Position » si vous voulez la carte de vos trajets).

3) Pour rouler sans réseau
   - Dans l'appli, sur l'accueil, touchez « Tout préparer pour rouler sans réseau »
     pendant que vous êtes en Wi-Fi : les modèles et les images sont copiés sur le téléphone.

4) Mettre à jour plus tard
   - Supprimez le dossier « {dossier} » dans public_html, puis importez et extrayez le nouveau zip.
   - Le téléphone prend la nouvelle version à l'ouverture suivante avec du réseau
     (à la deuxième ouverture si l'appli est réglée sur « sans réseau »).
     Le numéro de version est écrit en bas des Réglages de l'appli.
     Les profils et la progression restent sur le téléphone.

Rien n'est envoyé sur Internet par l'appli : photos, trajets et profils restent sur le téléphone.
Au premier chargement, le moteur de calcul (ONNX Runtime) est téléchargé depuis cdn.jsdelivr.net.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default=str(ROOT / "repere-hostinger.zip"))
    ap.add_argument("--dossier", default="repere", help="nom du dossier créé à l'extraction (et fin de l'adresse)")
    a = ap.parse_args()
    from tools.export_web import version_cache

    web = ROOT / "docs"
    cache = version_cache(web)  # le nom du cache suit le contenu des modèles, icônes et photos
    fichiers = sorted(f for f in web.rglob("*") if f.is_file())
    maintenant = time.localtime()[:6]

    # Droits écrits dans le zip : 644 pour les fichiers, 755 pour les dossiers. Certains hébergeurs les appliquent à
    # l'extraction ; avec des droits plus stricts, le serveur web ne peut pas lire .htaccess et répond « 403 Forbidden ».
    def fichier(z, nom, donnees, date, compression=zipfile.ZIP_DEFLATED):
        info = zipfile.ZipInfo(nom, date_time=date)
        info.external_attr = 0o100644 << 16
        info.compress_type = compression
        z.writestr(info, donnees, compresslevel=6)

    with zipfile.ZipFile(a.sortie, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        dossiers = {p.relative_to(web).as_posix() for f in fichiers for p in f.parents if web in p.parents}
        for d in [a.dossier] + sorted(f"{a.dossier}/{d}" for d in dossiers):
            info = zipfile.ZipInfo(d + "/", date_time=maintenant)
            info.external_attr = (0o40755 << 16) | 0x10
            z.writestr(info, b"")
        for f in fichiers:
            deja_compresse = f.suffix in (".png", ".jpg", ".woff2")
            date = time.localtime(f.stat().st_mtime)[:6]
            fichier(z, f"{a.dossier}/{f.relative_to(web).as_posix()}", f.read_bytes(), date, zipfile.ZIP_STORED if deja_compresse else zipfile.ZIP_DEFLATED)
        fichier(z, f"{a.dossier}/.htaccess", HTACCESS, maintenant)
        fichier(z, f"{a.dossier}/LISEZ-MOI.txt", "\ufeff" + LISEZ_MOI.format(dossier=a.dossier), maintenant)  # marque UTF-8 : accents corrects dans le Bloc-notes
    taille = Path(a.sortie).stat().st_size / 1e6
    print(f"{a.sortie} : {len(fichiers) + 2} fichiers, {taille:.1f} Mo (dossier « {a.dossier} », cache {cache})")


if __name__ == "__main__":
    main()
