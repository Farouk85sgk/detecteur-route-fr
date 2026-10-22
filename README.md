# Détecteur de panneaux et marquages au sol — code de la route français (YOLOv5, temps réel)

Application de détection **en direct** des panneaux de signalisation et des marquages au sol français, construite
sur le code de [YOLOv5](https://github.com/ultralytics/yolov5) (dossier `yolov5/`).

**Version téléphone, sans installation : https://farouk85sgk.github.io/detecteur-route-fr/** (voir
« Version téléphone » plus bas).

- **87 classes** : 67 panneaux (danger, priorité, interdiction, obligation, fin, zones, agglomération, indication)
  et 20 marquages au sol (lignes continue / discontinue / mixte, ligne STOP, ligne cédez-le-passage, passage piétons,
  flèches, zébras, damier, vélo, BUS, zigzag, dents de requin...). Liste complète dans `route_fr/classes.py`.
- **Temps réel** : lecture de la caméra dans un fil séparé (on traite toujours l'image la plus récente), modèle
  YOLOv5n léger, export ONNX / OpenVINO / TensorRT possible. Mesuré : **40 ms par image (≈ 25 images/s)** pour une
  vidéo 1280 × 720 sur un processeur 4 cœurs, sans carte graphique (détection + classifieur + affichage).
- **Affichage pédagogique** : cadre et nom de chaque élément, **vitesse maximale en cours** (mémorisée à partir des
  panneaux B14, entrée/sortie d'agglomération, zone 30, autoroute...), historique des derniers panneaux avec le
  **rappel du code de la route**, annonces vocales en option.
- **Deux étages** : YOLOv5n repère panneaux et marquages, puis un classifieur YOLOv5n-cls relit chaque panneau
  détecté (vignette 64 × 64) pour fixer sa classe exacte (chiffre de la limitation, sens des flèches...). Il écarte
  aussi les leurres (dos de panneaux, panneaux de direction, publicités) et les panneaux hors liste (limitations de
  poids ou de hauteur, vitesse minimale...), qui ne sont donc jamais pris pour une limitation de vitesse.
- **Stabilisation** : un objet n'est affiché qu'après 2 détections consécutives (moins de fausses alertes), les
  cadres sont lissés et la classe est votée sur plusieurs images (pas de clignotement 50 ↔ 30).

> ⚠️ Outil d'aide pédagogique : il ne remplace ni l'attention du conducteur ni la signalisation réelle. En voiture,
> le téléphone ou l'écran doit être fixé sur un support et ne doit pas être manipulé par le conducteur.

---

## 1. Installation

Python 3.9 à 3.13 (Windows, macOS ou Linux).

**Récupérer le projet** : sur https://github.com/Farouk85sgk/detecteur-route-fr, bouton vert **Code** →
**Download ZIP**, puis décompresser. Ou avec Git : `git clone https://github.com/Farouk85sgk/detecteur-route-fr.git`

**Le plus simple** : sous Windows, double-cliquez sur `installer_windows.bat` puis sur `lancer_windows.bat`
(webcam). Sous macOS / Linux : `bash installer.sh` puis `bash lancer.sh`. À la main :

```bash
cd detecteur-route-fr
python -m venv .venv
# Windows : .venv\Scripts\activate      macOS / Linux : source .venv/bin/activate
pip install -r requirements.txt
```

Avec une carte graphique NVIDIA, installez d'abord PyTorch avec CUDA (https://pytorch.org/get-started/locally/).

## 2. Lancer la détection

```bash
python app.py                                   # webcam n°0
python app.py --source 1                        # autre caméra (caméra USB, caméra embarquée...)
python app.py --source trajet.mp4               # vidéo, lue à sa vitesse réelle comme en direct
python app.py --source http://192.168.1.20:8080/video   # téléphone Android (appli « IP Webcam ») ou caméra IP
python app.py --source rtsp://...               # caméra de surveillance / dashcam Wi-Fi
python app.py --source ecran                    # capture de l'écran (pip install mss), ex. vidéo YouTube
python app.py --voix                            # annonces vocales (pip install pyttsx3)
```

| Touche | Action |
|---|---|
| `Q` / `Échap` | quitter |
| `Espace` | pause |
| `S` | capture d'écran (`capture_*.jpg`) |
| `R` | démarrer / arrêter l'enregistrement vidéo (`enregistrement_*.mp4`) |
| `M` | afficher / masquer les marquages au sol |
| `P` | afficher / masquer le panneau latéral |
| `+` / `-` | augmenter / baisser le seuil de confiance |

Options utiles : `--conf 0.4` (moins de fausses détections), `--taille 512` (plus rapide), `--appareil 0` (GPU),
`--demi` (FP16 sur GPU), `--sans-marquages`, `--min-hits 3`, `--enregistrer sortie.mp4 --sans-affichage`
(traitement d'une vidéo sans fenêtre), `--journal lecon.csv` (liste horodatée des panneaux et marquages
rencontrés, à ouvrir dans Excel pour le débriefing d'une leçon). `python app.py -h` liste toutes les options.

### Utiliser un téléphone comme caméra

1. Installez **IP Webcam** (Android) ou **DroidCam** (Android / iPhone), téléphone et ordinateur sur le même Wi-Fi.
2. Lancez le serveur vidéo dans l'appli, puis `python app.py --source http://<adresse-du-téléphone>:8080/video`.

### Version téléphone (navigateur, sans installation)

Le dossier `docs/` contient la même détection fonctionnant **directement dans le navigateur du téléphone**
(caméra arrière, calcul sur l'appareil avec ONNX Runtime Web : WebGPU si disponible, sinon WebAssembly ;
aucune image n'est envoyée sur Internet). Fonctions : cadres, vitesse en cours, dernier panneau avec son
explication, annonces vocales (bouton « Voix »), plein écran, analyse d'une vidéo enregistrée.

- **Sur le téléphone** : ouvrir **https://farouk85sgk.github.io/detecteur-route-fr/** et autoriser la caméra
  (le navigateur ne donne accès à la caméra qu'en HTTPS, ce que fournit GitHub Pages).
- **Mise en ligne, une seule fois** : sur la page GitHub du dépôt, onglet **Settings** → **Pages** → *Build and
  deployment* : Source « Deploy from a branch », branche `main`, dossier `/docs` → **Save**. Le site est en ligne
  une à deux minutes plus tard et se met à jour à chaque envoi sur GitHub (gratuit pour un dépôt public).
- **Sur l'ordinateur** : `python -m http.server --directory docs 8000` puis ouvrir http://localhost:8000
- Paramètres d'adresse : `?taille=512` (plus rapide), `?backend=wasm` (si la carte graphique pose problème).
- Après un réentraînement : `python tools/export_web.py` met à jour `docs/` (modèles ONNX, classes, icônes).

### Aller plus vite

| Matériel | Conseil |
|---|---|
| Processeur seul | modèle ONNX (choisi par défaut s'il est présent), `--taille 512` ou `416` |
| Processeur Intel | `python yolov5/export.py --weights weights/route_fr_yolov5n.pt --include openvino --img 384 640` puis `--poids weights/route_fr_yolov5n_openvino_model --taille 384 640` |
| GPU NVIDIA | `--appareil 0 --demi` (ou export TensorRT : `--include engine --device 0`) |
| Mac Apple Silicon | `--appareil mps` |

## 3. Comment le modèle a été entraîné

Aucun jeu de données public de panneaux **et** marquages français n'étant disponible, le jeu d'entraînement est
**synthétique, mais sur de vraies images de route** :

1. **Fonds réels** : 9 888 images de conduite [comma10k](https://github.com/commaai/comma10k) (licence MIT) avec
   leur segmentation (chaussée, véhicules, capot). `synth/prepare_backgrounds.py` estime l'horizon et la position
   des voies, efface les marquages américains et écarte les images contenant d'autres peintures au sol.
2. **Marquages français** (`synth/markings.py`) dessinés dans le repère de la route puis projetés en perspective
   (lignes T1, T2, T3, mixtes, STOP, cédez-le-passage, flèches, zébras...), avec usure, éclairage de la chaussée et
   occultation par les véhicules.
3. **Panneaux français** (`route_fr/signs_svg.py`) dessinés en vectoriel d'après l'IISR et les affiches ENPC, placés
   en 3D au bord de la route sur poteau (taille réelle, distance, orientation), avec décoloration, reflets, flou,
   feuillage, panonceaux et leurres non annotés (dos de panneaux, panneaux de direction, plaques de rue...).
4. Les **vrais panneaux STOP** des images américaines (identiques au AB4 français) sont repérés avec le YOLOv5
   d'origine (COCO) et annotés AB4 (`synth/find_real_stops.py`). Les 28 STOP de face confirmés à l'œil servent
   aussi d'exemples réels au classifieur.
5. Entraînement YOLOv5n (pré-entraîné COCO), **sans miroir horizontal** (il inverserait droite / gauche et les
   textes) et avec une variation de teinte réduite (la couleur porte le sens du panneau).
6. Classifieur de panneaux YOLOv5n-cls (pré-entraîné ImageNet) sur 118 000 vignettes (synthétiques, plus 420 vignettes de vrais STOP)
   (`synth/generate_crops.py`) : 67 panneaux + « autre panneau » + « fond », avec perspective, flou, basse
   résolution (panneaux lointains), éclairage et feuillage.

### Résultats mesurés

Validation synthétique (1 500 images jamais vues, fonds réels distincts de l'entraînement ; une détection compte si
la classe exacte est trouvée avec un recouvrement IoU > 0,5, seuil de confiance par défaut) :

| | Rappel | Précision |
|---|---|---|
| Marquages au sol (3 762) | 80,5 % | 82,0 % |
| Panneaux (3 090), détecteur seul | 42,8 % | 70,7 % |
| **Panneaux, détecteur + classifieur** | **86,3 %** | **92,2 %** |

Rappel des panneaux selon leur taille à l'image (échelle 640 px) : 95 % au-delà de 32 px, 93 % de 16 à 32 px, 67 %
en dessous de 16 px (panneaux lointains, qui grossissent à l'approche). Classifieur seul : 98 % de bonnes réponses
sur ses vignettes de validation.

Tests sur de vraies images :
- **Photo de l'affiche ENPC « Signalisation routière »** (vrais panneaux imprimés, reflets) : 87 panneaux détectés,
  dont environ 60 correctement identifiés, et une seule limitation de vitesse lue (la bonne). La majorité des
  erreurs portent sur des panneaux absents de la liste des 67 classes.
- **300 vraies images de route** (américaines, donc sans panneau français), image par image : 9 fausses détections
  de panneaux (3 % des images), surtout des panneaux propres aux États-Unis. En direct, l'exigence de 2 détections
  consécutives et d'une taille minimale en élimine une partie.

**Limite importante** : ces mesures portent sur des images synthétiques ; les performances sur de vraies routes
françaises n'ont pas pu être mesurées (aucune image réelle annotée disponible). Le modèle fourni est une **base de
départ** : pour une utilisation sérieuse, affinez-le avec quelques centaines d'images réelles annotées (section
suivante) — c'est le levier le plus efficace.

## 4. Améliorer le modèle avec vos propres vidéos (recommandé)

Filmez vos trajets habituels (caméra embarquée ou téléphone sur support), puis :

```bash
# 1) extraire une image par seconde
python tools/extraire_images.py mes_videos/*.mp4 --sortie mes_donnees/images --intervalle 1
# 2) pré-annoter avec le modèle actuel (fichiers .txt au format YOLO + classes.txt)
python tools/pre_annoter.py mes_donnees/images
```

3. Corrigez les annotations dans un outil gratuit acceptant le format YOLO : **Label Studio**, **CVAT**,
   **Roboflow** ou **LabelImg** (ajoutez les objets oubliés, supprimez les erreurs). Placez ensuite les `.txt` dans
   `mes_donnees/labels/` (même nom que l'image).
4. Créez `data/mes_donnees.yaml` en reprenant `data/route_fr.yaml`, avec par exemple
   `train: [/chemin/datasets/route_fr/images/train, /chemin/mes_donnees/images]`.
5. Réentraînez à partir du modèle actuel :

```bash
# Avec un GPU NVIDIA
python yolov5/train.py --data data/mes_donnees.yaml --weights weights/route_fr_yolov5n.pt --hyp data/hyp_route_fr.yaml --img 640 --epochs 50 --batch 32
# Sur processeur Intel récent (précision mixte bfloat16, ~2,4x plus rapide qu'en float32)
python tools/train_cpu_bf16.py --data data/mes_donnees.yaml --weights weights/route_fr_yolov5n.pt --hyp data/hyp_route_fr.yaml --img 640 --epochs 50 --batch 32
```

Le meilleur modèle est écrit dans `yolov5/runs/train/exp*/weights/best.pt` ; copiez-le dans `weights/`.

Classifieur de panneaux (dossiers d'images par classe, voir `synth/generate_crops.py`) : vous pouvez y ajouter vos
propres vignettes de panneaux réels (`datasets/panneaux_cls/train/<code>/`), puis

```bash
python tools/train_cpu_bf16.py --classifieur --model weights/panneaux_cls.pt --data datasets/panneaux_cls --img 64 --epochs 10 --batch-size 128
```
Export ONNX (utilisé par défaut par l'application, plus rapide sur processeur) :

```bash
python yolov5/export.py --weights weights/route_fr_yolov5n.pt --include onnx --dynamic --img 640
python yolov5/export.py --weights weights/panneaux_cls.pt --include onnx --dynamic --img 64
```

Ajouter un panneau : une entrée dans `route_fr/classes.py` (à la fin de la liste), son dessin dans
`route_fr/signs_svg.py`, puis régénérer les données et réentraîner.

## 5. Régénérer le jeu de données synthétique

```bash
pip install cairosvg
# images comma10k (≈ 6,5 Go) : https://github.com/commaai/comma10k, dossiers imgs/ et masks/
python synth/prepare_backgrounds.py --src <dossier comma10k converti> --out datasets_src/fonds
python synth/find_real_stops.py --fonds datasets_src/fonds
python synth/generate.py --fonds datasets_src/fonds --out datasets/route_fr --train 24000 --val 1500
python synth/generate_crops.py --fonds datasets_src/fonds --out datasets/panneaux_cls --par-classe 1500
python tools/make_icons.py          # icônes du panneau latéral
```

## 6. Organisation

```
app.py                  application temps réel
route_fr/classes.py     classes, libellés, rappels du code de la route, effets sur la vitesse
route_fr/detector.py    inférence YOLOv5 (DetectMultiBackend : .pt, .onnx, OpenVINO, TensorRT...)
route_fr/classifier.py  second étage : classifieur de panneaux sur vignettes
route_fr/tracker.py     stabilisation temporelle (suivi IoU, vote de classe, lissage)
route_fr/hud.py         affichage (cadres, vitesse en cours, historique, explications)
route_fr/video.py       capture threadée (webcam, fichier, flux réseau, écran)
route_fr/signs_svg.py   dessins vectoriels des panneaux
synth/                  génération du jeu de données synthétique
tools/                  entraînement CPU bf16, extraction d'images, pré-annotation, icônes, export web
docs/                   version web (navigateur du téléphone), publiée par GitHub Pages
weights/                modèles entraînés
yolov5/                 code YOLOv5 (ultralytics/yolov5, commit af08ba1, non modifié)
```

## Licences

- YOLOv5 : AGPL-3.0 (Ultralytics). Ce projet, qui en dérive, est distribué sous la même licence (`LICENSE`).
- Images comma10k (entraînement uniquement, non incluses) : MIT. Polices DejaVu : licence libre Bitstream Vera /
  DejaVu (`route_fr/fonts/LICENSE`). ONNX Runtime Web (chargé par la version web) : MIT.
