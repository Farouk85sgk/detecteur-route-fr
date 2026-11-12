# Détecteur de panneaux et marquages au sol — code de la route français (YOLOv5, temps réel)

Application de détection **en direct** des panneaux de signalisation et des marquages au sol français, construite
sur le code de [YOLOv5](https://github.com/ultralytics/yolov5) (dossier `yolov5/`) et **entraînée sur de vraies
photos de routes françaises**.

**Version téléphone « Repère », sans installation : https://farouk85sgk.github.io/detecteur-route-fr/** :
détection en direct avec feux, piétons et cyclistes, trajets en photos, album, **685 questions de code en 57 séries**,
examens blancs, quiz sur de vraies photos, quête et profils (voir « Version téléphone » plus bas).

- **Un catalogue de 308 éléments** (`route_fr/classes.py`) : 285 panneaux, panonceaux et balises, désignés par leur
  code officiel, et 23 marquages au sol. La caméra en reconnaît **231** : 209 panneaux (dangers, priorités,
  interdictions, limitations de 5 à 130 km/h, stationnement et zones, obligations, fins, indications, services,
  signalisation temporaire, balises, panonceaux) et 22 marquages (lignes continue, discontinue, mixte, de
  dissuasion, de rive, STOP, cédez-le-passage, passage piétons, flèches, zébras, damier, vélo, BUS, zigzag, dents de
  requin...). Les 76 autres panneaux, trop rares sur les photos pour être appris, et la ligne d'effet des feux ont
  leur fiche dans l'album.
- **Deux étages** : YOLOv5n repère les marquages et tous les panneaux (une seule classe « panneau »), puis un
  classifieur YOLOv5n-cls dit de quel panneau il s'agit. Il regarde le panneau **et ce qui se trouve dessous** : il
  distingue ainsi un sens interdit d'un « sens interdit sauf vélos », un stationnement interdit d'une place réservée
  aux personnes handicapées, un cédez-le-passage de son annonce à 150 m. Il écarte les fausses détections et les
  panneaux hors catalogue (directions, publicités, dos de panneaux).
- **Temps réel** : lecture de la caméra dans un fil séparé (on traite toujours l'image la plus récente), modèles
  légers, export ONNX / OpenVINO / TensorRT possible.
- **Affichage pédagogique** : cadre et nom de chaque élément, **vitesse maximale en cours** (mémorisée à partir des
  panneaux B14, entrée/sortie d'agglomération, zones 30 et de rencontre, autoroute...), historique des derniers
  panneaux avec le **rappel du code de la route**, annonces vocales en option.
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

### Version téléphone : l'appli « Repère » (navigateur, sans installation)

Le dossier `docs/` contient une application complète qui fonctionne **directement dans le navigateur du
téléphone** : **https://farouk85sgk.github.io/detecteur-route-fr/**. Le calcul se fait sur l'appareil (ONNX Runtime
Web : carte graphique WebGPU si disponible, sinon processeur) et **rien n'est envoyé sur Internet** : profils,
photos, trajets et progression restent sur le téléphone. Sur Android ou iPhone, menu du navigateur →
« Ajouter à l'écran d'accueil » pour l'installer comme une appli.

- **Détection en direct** (caméra ou vidéo) : 209 panneaux et 22 marquages, plus **feux tricolores** (couleur lue,
  annonce du passage au vert), **piétons, cyclistes et deux-roues** avec leur distance approximative. Carte du
  dernier élément avec son explication, historique en pastilles, vitesse maximale en cours, lignes à gauche et à
  droite, annonces vocales (« Limitation à 50 », règle expliquée à voix haute), vibration. Pause : pincer pour
  zoomer, toucher un cadre pour ouvrir sa fiche. Mode paysage : la route à gauche, le panneau à droite.
- **Mes trajets** : une photo de la route à chaque élément repéré (cadres incrustés), avec l'heure, le moment de la
  vidéo et la position GPS (lien vers la carte) ; vidéo du trajet à enregistrer ou partager ; quiz du trajet.
- **Album** : 314 éléments rangés en 14 familles, avec les schémas officiels des panneaux ; en couleur une fois
  repérés sur la route, avec leur fiche (sens, bon réflexe, comment le reconnaître, ta photo).
- **Code de la route** : **685 questions originales en 57 séries**, classées selon les dix thèmes de l'examen
  (circulation, conducteur, route, autres usagers, notions diverses, premiers secours, prendre et quitter son
  véhicule, mécanique, sécurité, environnement), chacune avec son explication ; progression par thème, erreurs à
  revoir, et **examens blancs** de 40 questions réparties comme à l'épreuve (35 bonnes réponses pour réussir).
  Les **séries de l'auto-école** peuvent être importées (voir ci-dessous).
- **Quiz de signalisation** : dernier trajet, album, par famille, erreurs à revoir, examen des panneaux, et
  **« En situation réelle »** : de vraies photos de routes françaises où il faut reconnaître le panneau encadré.
- **La quête** : une carte avec une région par famille ; repérer 4 éléments de la famille sur la route ouvre le
  donjon de son gardien (10 questions, 3 cœurs, loupe et potion) ; chaque gardien vaincu donne un éclat du Panneau
  d'Or (14 régions). Quêtes du jour, panneau mystère, coffre, flamme des jours de suite, pépites, échoppe (objets et
  titres), niveaux, 19 badges, **classement** en 8 catégories entre les profils du téléphone et des amis ajoutés par code.
- **Profils** : plusieurs élèves sur un même téléphone, chacun avec ses réglages, sa couleur de fond (Auto, Blanc,
  Crème, Sauge, Bleu nuit), son album, ses trajets et sa progression.
- **Mes panneaux** : un panneau que l'appli ne connaît pas, ou qu'elle confond ? On le prend en photo, on dit ce
  que c'est, et l'appli le reconnaît ensuite (modèle d'empreintes `empreinte.onnx`).
- **Réglages** : ce qu'il faut détecter (famille par famille ou élément par élément), qualité d'analyse (Rapide,
  Équilibrée, Fine), photos, GPS, vidéo, paysage, sons, calcul sur plusieurs cœurs, et un diagnostic. **Sans réseau** :
  bouton « Tout préparer pour rouler sans réseau » (environ 55 Mo), puis l'appli fonctionne hors connexion.
- **Vitesse** : sans carte graphique utilisable, le calcul se répartit sur plusieurs cœurs du téléphone à partir
  de la deuxième ouverture de l'appli (le service worker fournit l'isolation de page nécessaire).

Mise en ligne (une seule fois) : sur la page GitHub du dépôt, **Settings** → **Pages** → Source « Deploy from a
branch », branche `main`, dossier `/docs` → **Save**. Le site se met ensuite à jour à chaque envoi sur GitHub.
Sur l'ordinateur : `python -m http.server --directory docs 8000` puis http://localhost:8000 (paramètre d'adresse
`?backend=wasm` si la carte graphique pose problème). Après un réentraînement : `python tools/export_web.py`.

**Sur son propre site (Hostinger, o2switch, OVH...)** : `python tools/zip_hebergement.py --sortie repere-hostinger.zip`
fabrique un zip d'environ 32 Mo qui contient un seul dossier, `repere`. On l'importe dans le dossier `public_html`
du site avec le gestionnaire de fichiers de l'hébergeur, on l'extrait, et l'appli répond à l'adresse
`https://votre-domaine/repere/` sans toucher au reste du site (il faut une adresse en **https**, sinon le
téléphone refuse la caméra). Le zip contient un fichier `LISEZ-MOI.txt` qui détaille la marche à suivre, et un
`.htaccess` pour que les mises à jour arrivent tout de suite sur les téléphones.

**Banque de questions intégrée.** Les questions sont écrites dans des fichiers texte faciles à relire et à
corriger, un par série (`data/series/questions/L01.txt`...), la lettre donnant le thème de l'examen :

```
# Titre de la série
? Texte de la question
- mauvaise réponse
+ bonne réponse (plusieurs lignes « + » si plusieurs bonnes réponses)
! Explication affichée après la réponse
@ sous-thème | difficulté de 1 à 3 | code d'un panneau à afficher (facultatif)
```

`python tools/construire_series.py` vérifie chaque question et produit `docs/series/banque.json`. Ces questions sont
originales, rédigées d'après le code de la route en vigueur en 2026 ; les règles récentes (inter-files, grand excès
de vitesse, stupéfiants, trottinettes...) ont été vérifiées sur des sources officielles. Elles ne remplacent pas les
séries officielles : faites-les relire par un enseignant, et corrigez toute erreur dans le fichier concerné.

**Séries de code de l'auto-école** (page « Code de la route ») : un fichier JSON importé depuis le
téléphone ou par un lien `https://` (le serveur doit autoriser CORS). Une question a 2 à 6 choix ; `bonnes` donne la
ou les bonnes réponses (à partir de 0) ; l'image est soit un panneau de l'appli (`panneau`, code de
`route_fr/classes.py`), soit une adresse `https://` ou une image `data:` ; `type` vaut `serie` ou `examen`
(examen : 20 s par question, corrigé à la fin).

```json
{
  "titre": "Auto-école du Centre : séries de code",
  "auteur": "Auto-école du Centre",
  "series": [
    { "titre": "Série 1", "type": "serie", "questions": [
      { "question": "Que signifie ce panneau ?", "panneau": "AB4",
        "choix": ["Arrêt obligatoire", "Cédez le passage", "Sens interdit"], "bonnes": [0],
        "explication": "STOP : arrêt complet à la ligne, puis céder le passage." },
      { "question": "Quelles affirmations sont vraies ?", "image": "https://exemple.fr/photo.jpg",
        "choix": ["Je peux dépasser", "Je dois ralentir", "Je cède le passage"], "bonnes": [1, 2] }
    ]}
  ]
}
```

### Aller plus vite

| Matériel | Conseil |
|---|---|
| Processeur seul | modèle ONNX (choisi par défaut s'il est présent), `--taille 512` ou `416` |
| Processeur Intel | `python yolov5/export.py --weights weights/route_fr_yolov5n.pt --include openvino --img 384 640` puis `--poids weights/route_fr_yolov5n_openvino_model --taille 384 640` |
| GPU NVIDIA | `--appareil 0 --demi` (ou export TensorRT : `--include engine --device 0`) |
| Mac Apple Silicon | `--appareil mps` |

## 3. Comment les modèles ont été entraînés

### De vraies photos de routes françaises

[Panoramax](https://panoramax.fr) est le géocommun de photos de rues porté par l'IGN et OpenStreetMap France. Son
instance IGN publie, sous **Licence Ouverte 2.0**, des millions de photos de routes où les panneaux ont été repérés
et identifiés par des modèles automatiques (code du panneau et boîte englobante). Le projet s'en sert ainsi :

1. `tools/panoramax_index.py` interroge l'API pour chaque code de panneau (`data/panoramax_codes.txt`) et note les
   photos qui le contiennent : 338 000 photos indexées.
2. `tools/panoramax_telecharge.py` en choisit jusqu'à 200 par panneau (les plus rares d'abord, séquences et auteurs
   variés) et télécharge **26 000 vues** : un morceau des photos à 360° autour du panneau, ou la photo entière des
   caméras ordinaires.
3. `tools/panoramax_dataset.py` en tire les données du **détecteur** (recadrages ramenés à l'échelle d'un téléphone,
   les panneaux en une seule classe « panneau ») et les **vignettes du classifieur** (chaque panneau à pleine
   définition avec son décor), en gardant pour la validation des zones géographiques entières.

Les étiquettes viennent de modèles automatiques : elles sont filtrées (confiance élevée) et les cas douteux ne sont
ni des exemples ni des contre-exemples (zones « _ignorer »). Les marquages au sol de ces photos ne sont pas
annotés : une zone « _reel » demande à l'entraînement de n'y corriger le réseau que s'il voit un panneau là où il
n'y en a pas, jamais s'il y voit un marquage (`tools/train_cpu_bf16.py`).

### Des images synthétiques pour les marquages et les cas rares

Les marquages au sol s'apprennent sur des images **synthétiques, mais sur de vraies images de route** :

1. **Fonds réels** : 9 888 images de conduite [comma10k](https://github.com/commaai/comma10k) (licence MIT) avec
   leur segmentation (chaussée, véhicules, capot). `synth/prepare_backgrounds.py` estime l'horizon et la position
   des voies, efface les marquages américains et écarte les images contenant d'autres peintures au sol.
2. **Marquages français** (`synth/markings.py`) dessinés dans le repère de la route puis projetés en perspective
   (lignes T1, T2, T3, mixtes, de rive, STOP, cédez-le-passage, effet des feux, flèches, zébras...), avec usure,
   éclairage de la chaussée et occultation par les véhicules.
3. **Panneaux** dessinés en vectoriel (`route_fr/signs_svg.py`), placés en 3D au bord de la route sur poteau, avec
   décoloration, reflets, flou, feuillage et leurres (dos de panneaux, plaques de rue, publicités).

Le détecteur YOLOv5n part du modèle précédent et s'entraîne sur les deux sources à la fois, **sans miroir
horizontal** (il inverserait droite / gauche et les textes) et avec une variation de teinte réduite (la couleur
porte le sens du panneau).

### Le classifieur de panneaux

`tools/train_classifieur.py` entraîne un YOLOv5n-cls à 211 sorties : les 209 panneaux reconnus, « autre » (panneau
hors catalogue) et « fond » (fausse détection). Il voit un carré autour de la boîte détectée, prolongé vers le bas
(64 x 96 px) pour lire le panonceau. À l'entraînement, le cadrage est décalé au hasard et l'image dégradée
(panneau lointain de quelques pixels, flou, bruit, contre-jour, compression). Un second tour ajoute à « fond » et à
« autre » ce que le détecteur propose à tort sur les photos d'entraînement (`tools/miner_rejets.py`).

**Étiquettes contrôlées à l'œil.** Le modèle automatique qui a annoté les photos se trompe de façon répétée sur
certains panneaux : il prend le logo d'une enseigne pour une limitation à 100, un schéma de giratoire pour un
panonceau « sauf vélos », une fenêtre pour une station-service, un piéton portant un sac en bandoulière pour une
fin d'interdiction... `tools/planche_classe.py` affiche toutes les vignettes d'une classe, numérotées ; les
erreurs repérées sont notées dans `data/panoramax_corrections.txt` (**2 048 vignettes corrigées dans 45 classes**)
et `tools/corriger_vignettes.py` les applique : un faux panneau devient un exemple de la classe « autre », un cas
ambigu est retiré. Le troisième tour d'entraînement part de ces vignettes corrigées. Les photos du quiz
« En situation réelle » (`tools/photos_quiz.py`) ont été vérifiées une à une de la même façon.

### Résultats mesurés

Toutes les mesures portent sur les **1 542 photos de validation** : de vraies routes françaises, dans des zones
géographiques que les modèles n'ont jamais vues à l'entraînement.

**Le détecteur** trouve-t-il les panneaux, quel que soit leur type ? (1 973 panneaux annotés, seuil 0,25,
`tools/evaluer_detecteur.py`)

| Détecteur | AP50 | Précision | Rappel | Rappel : moins de 10 px | 10 à 20 px | plus de 20 px |
|---|---|---|---|---|---|---|
| version précédente | 0,645 | 0,79 | 0,56 | 0,14 | 0,38 | 0,69 |
| après la première phase d'entraînement | 0,841 | 0,70 | 0,83 | 0,22 | 0,72 | 0,95 |
| **version livrée** | **0,902** | 0,77 | **0,88** | 0,39 | 0,81 | 0,97 |

La version précédente manquait presque un panneau sur deux sur ces photos ; la version livrée en trouve près de
neuf sur dix, et 97 % de ceux qui mesurent plus de 20 pixels.

**Les marquages au sol** sont mesurés sur 800 images synthétiques de validation : AP50 moyenne de 0,83 pour les
22 marquages, dont 18 au-dessus de 0,82 (passage piétons 0,92, flèches 0,86 à 0,97, lignes continues et
discontinues 0,83 et 0,85, zébras 0,91, damier 0,86). Quatre restent en retrait : la ligne de rive (0,75), les
dents de requin (0,73) et surtout les deux lignes fines en travers de la voie, **ligne d'arrêt STOP (0,32) et
ligne de cédez-le-passage (0,34)**, encore peu fiables. Le mot « STOP » peint au sol (0,90) et le triangle de
cédez-le-passage (0,95) sont, eux, bien reconnus.

**Le classifieur** (troisième tour, vignettes corrigées) donne le bon type pour **93,3 % des vignettes en moyenne
par panneau** (94,1 % toutes vignettes confondues) sur 2 330 vraies vignettes de validation ; le tour précédent
était à 92,9 % sur les mêmes vignettes. Il rejette maintenant 57 % des panneaux hors catalogue, contre 22 %.

**La chaîne complète**, comme dans l'appli (détecteur, puis classifieur, seuil des panneaux à 0,455 ;
`tools/evaluer_chaine.py`), sur les 1 811 panneaux du catalogue annotés dans ces photos :

| Modèles | Trouvés et bien nommés | Confusions | Fausses annonces | Annonces justes |
|---|---|---|---|---|
| détecteur de la première phase + classifieur du deuxième tour | 77,0 % | 95 | 150 | 85,1 % |
| détecteur livré + classifieur du deuxième tour | 80,9 % | 105 | 145 | 85,4 % |
| **détecteur livré + classifieur du troisième tour (version livrée)** | **80,8 %** | **88** | **137** | **86,7 %** |

Selon la taille du panneau dans l'image : 91 % au-dessus de 24 px, 79 % entre 12 et 24 px, 41 % en dessous de
12 px. Ces chiffres valent pour **une seule photo** ; en roulant, le panneau grossit d'image en image et l'appli
attend de le voir plusieurs fois de suite avant de l'annoncer. Le seuil règle le compromis entre oublis et erreurs :

| Seuil des panneaux | Trouvés et bien nommés | Confusions | Fausses annonces | Annonces justes |
|---|---|---|---|---|
| 0,35 | 82,6 % | 103 | 169 | 84,6 % |
| **0,455 (appli)** | **80,8 %** | **88** | **137** | **86,7 %** |
| 0,55 | 78,8 % | 64 | 107 | 89,3 % |
| 0,70 | 72,9 % | 37 | 62 | 93,0 % |

Les panneaux les moins bien reconnus (cinq à dix exemples chacun dans ces photos) sont la chaussée rétrécie A3, le
panonceau M6h, la limitation de hauteur B12 et la balise J3 ; les confusions les plus fréquentes touchent des
panneaux qui se ressemblent (AB3a / AB3b, B6a1 / B6a2, B50c / B50d).

**Dans le navigateur**, sur une vidéo d'essai faite de dix vraies scènes, les dix panneaux attendus sont annoncés,
ainsi que trois autres réellement présents dans les images (une balise J3, une limitation de hauteur, un 110 sur
un panneau d'autoroute) ; aucune annonce de panneau n'est fausse. Sur un seul cœur de processeur, sans carte
graphique, l'analyse y prend environ 130 ms par image (machine d'essai).

## 4. Améliorer les modèles avec vos propres vidéos

Filmez vos trajets habituels (caméra embarquée ou téléphone sur support), puis :

```bash
# 1) extraire une image par seconde
python tools/extraire_images.py mes_videos/*.mp4 --sortie mes_donnees/images --intervalle 1
# 2) pré-annoter avec le modèle actuel (fichiers .txt au format YOLO + classes.txt)
python tools/pre_annoter.py mes_donnees/images
```

3. Corrigez les annotations dans un outil gratuit acceptant le format YOLO : **Label Studio**, **CVAT**,
   **Roboflow** ou **LabelImg** (ajoutez les objets oubliés, supprimez les erreurs). Les classes sont celles du
   détecteur : `panneau` pour tous les panneaux, puis les marquages. Placez ensuite les `.txt` dans
   `mes_donnees/labels/` (même nom que l'image).
4. Créez `data/mes_donnees.yaml` en reprenant `data/route_fr.yaml` et en ajoutant votre dossier à `train`.
5. Réentraînez à partir du modèle actuel :

```bash
# Avec un GPU NVIDIA
python yolov5/train.py --data data/mes_donnees.yaml --weights weights/route_fr_yolov5n.pt --hyp data/hyp_route_fr.yaml --img 640 --epochs 30 --batch 32
# Sur processeur Intel récent (précision mixte bfloat16, ~2,4x plus rapide qu'en float32)
python tools/train_cpu_bf16.py --data data/mes_donnees.yaml --weights weights/route_fr_yolov5n.pt --hyp data/hyp_route_fr.yaml --img 640 --epochs 30 --batch 32
```

Le meilleur modèle est écrit dans `yolov5/runs/train/exp*/weights/best.pt` ; copiez-le dans `weights/`, puis
`python tools/export_web.py` pour la version web. (Les zones « _ignorer » et « _reel » ne sont prises en compte que
par `tools/train_cpu_bf16.py`.)

**Classifieur** : ajoutez vos vignettes de panneaux dans `datasets/vignettes/train/<code>/` (image carrée avec le
panneau au centre et du décor autour ; la boîte du panneau, en millièmes du côté, termine le nom du fichier :
`..._x1_y1_x2_y2.jpg`), puis `python tools/train_classifieur.py`. Dans l'appli web, « Mes panneaux » permet aussi
d'apprendre un panneau à partir d'une seule photo, sans réentraînement.

**Ajouter un panneau au catalogue** : une ligne dans `route_fr/classes.py` (et son code retiré de `FICHES_SEULES`
s'il doit être reconnu), son icône (`tools/make_icons.py`), des vignettes d'exemple, puis réentraîner le
classifieur. Le détecteur, lui, n'a pas besoin d'être réentraîné : il cherche « un panneau », quel qu'il soit.

## 5. Tout régénérer

```bash
pip install cairosvg
# --- vraies photos (Panoramax, instance IGN) : index, téléchargement (≈ 13 Go), jeux de données ---
python tools/panoramax_index.py --codes data/panoramax_codes.txt --out datasets_src/panoramax
python tools/panoramax_telecharge.py --index datasets_src/panoramax --out datasets_src/panoramax --par-code 200
python tools/panoramax_dataset.py --vues datasets_src/panoramax --out datasets --vignettes
# --- images synthétiques : fonds comma10k (≈ 6,5 Go, https://github.com/commaai/comma10k, dossiers imgs/ et masks/) ---
python synth/prepare_backgrounds.py --src <dossier comma10k converti> --out datasets_src/fonds
python synth/find_real_stops.py --fonds datasets_src/fonds
python synth/generate.py --fonds datasets_src/fonds --out datasets/route_fr --train 14000 --val 800
python synth/generate_crops.py --fonds datasets_src/fonds --out datasets/vignettes_synth --par-classe 400
# --- entraînements ---
python tools/train_cpu_bf16.py --data data/route_fr.yaml --weights weights/route_fr_yolov5n.pt --hyp data/hyp_route_fr.yaml --img 416 --epochs 10 --batch 32
python tools/evaluer_detecteur.py --poids weights/route_fr_yolov5n.pt --images datasets/reel/images/val datasets/route_fr/images/val
python tools/train_classifieur.py --data datasets/vignettes datasets/vignettes_synth
python tools/miner_rejets.py && python tools/train_classifieur.py --data datasets/vignettes datasets/vignettes_synth --epochs 4 --lr 5e-4
# étiquettes corrigées à l'œil, puis troisième tour du classifieur et mesure de la chaîne complète
python tools/corriger_vignettes.py --data datasets/vignettes --corrections data/panoramax_corrections.txt --reel datasets/reel --vues datasets_src/panoramax
python tools/train_classifieur.py --data datasets/vignettes datasets/vignettes_synth --depart weights/panneaux_cls.pt --epochs 6 --lr 8e-4
python tools/evaluer_chaine.py --poids weights/route_fr_yolov5n.pt --classifieur weights/panneaux_cls.pt
# --- appli ---
python tools/make_icons.py --commons datasets_src/commons   # icônes (schémas officiels de Wikimedia Commons)
python tools/construire_series.py                           # banque de questions du code
python tools/photos_quiz.py --vues datasets_src/panoramax --classifieur weights/panneaux_cls.pt   # quiz « En situation réelle »
python tools/export_web.py                                  # détecteur ONNX, catalogue, icônes et crédits de la version web
python tools/zip_hebergement.py --sortie repere-hostinger.zip   # zip de l'appli pour un hébergeur (dossier « repere »)
# « Mes panneaux » (version web) : panneaux-identités, puis modèle d'empreintes -> docs/empreinte.onnx
python synth/generate_identites.py --fonds datasets_src/fonds --out datasets/empreintes
python tools/train_empreinte.py --data datasets/empreintes
```

## 6. Organisation

```
app.py                  application temps réel
route_fr/classes.py     catalogue : panneaux et marquages, libellés, rappels du code, effets sur la vitesse
route_fr/panoramax.py   correspondance entre les annotations Panoramax et le catalogue
route_fr/detector.py    inférence YOLOv5 (DetectMultiBackend : .pt, .onnx, OpenVINO, TensorRT...)
route_fr/classifier.py  second étage : classifieur de panneaux (vignette 64 x 96 : panneau et panonceau)
route_fr/tracker.py     stabilisation temporelle (suivi IoU, vote de classe, lissage)
route_fr/hud.py         affichage (cadres, vitesse en cours, historique, explications)
route_fr/video.py       capture threadée (webcam, fichier, flux réseau, écran)
route_fr/signs_svg.py   dessins vectoriels des panneaux (images synthétiques)
route_fr/icones/        icônes de l'application et leurs crédits
synth/                  génération des images synthétiques
tools/                  données réelles (panoramax_*.py), entraînements (train_cpu_bf16.py, train_classifieur.py,
                        train_empreinte.py), évaluation, icônes, banque de questions, photos du quiz, export web
data/                   configuration des entraînements, codes Panoramax, crédits des schémas, questions du code
docs/                   appli web « Repère » publiée par GitHub Pages : index.html, css/, js/ (moteur.js détection,
                        camera.js, quiz.js, series.js, quete.js, album.js...), modèles ONNX, icônes, séries, polices
weights/                modèles entraînés
yolov5/                 code YOLOv5 (ultralytics/yolov5, commit af08ba1, non modifié)
```

## Licences et sources

- YOLOv5 : AGPL-3.0 (Ultralytics). Ce projet, qui en dérive, est distribué sous la même licence (`LICENSE`).
- **Photos d'entraînement et photos du quiz « En situation réelle »** : contributeurs de
  [Panoramax](https://panoramax.fr), instance IGN, **Licence Ouverte 2.0 (Etalab)**. Les photos du quiz portent le nom
  de leur auteur dans l'appli ; la liste complète est dans `docs/series/photos.json`. Les étiquettes de panneaux de
  ces photos proviennent des modèles de détection et de classification de Panoramax.
- **Icônes des panneaux** : schémas de Wikimedia Commons (Roulex 45 et autres auteurs), sous licences CC BY-SA 3.0 ou
  4.0, CC BY 4.0, CC0 ou domaine public selon le schéma : détail dans `route_fr/icones/CREDITS.md` (page
  `credits.html` de l'appli). Les icônes dérivées restent sous la licence de leur schéma d'origine.
- Images comma10k (entraînement uniquement, non incluses) : MIT. Polices DejaVu : licence libre Bitstream Vera /
  DejaVu (`route_fr/fonts/LICENSE`). Polices de la version web Bricolage Grotesque et Overpass : licence OFL
  (`docs/polices/LICENSE.txt`). ONNX Runtime Web (chargé par la version web) : MIT. Détection des piétons, vélos,
  motos et feux : YOLOv5n COCO d'origine (Ultralytics, AGPL-3.0).
- Questions du code de la route (`data/series/questions/`) : rédigées pour ce projet, même licence que le projet.
