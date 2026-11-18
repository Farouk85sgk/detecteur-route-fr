# Vraies photos de marquages au sol, annotées

Le détecteur a d'abord appris les marquages au sol sur des images de synthèse seulement. Mesuré sur de vraies rues,
il n'en trouvait que 16 %. Ce dossier contient les annotations d'un jeu de vraies photos de rues françaises, qui sert
à le mesurer honnêtement et à l'entraîner.

## Source et licence des photos

Les photos viennent de [Panoramax](https://panoramax.ign.fr), instance de l'IGN, sous
[Licence Ouverte 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence/) (Etalab). Chaque ligne de `meta.jsonl`
donne l'identifiant de la photo, son auteur (producteur Panoramax), sa date, sa licence, sa position et le lien vers
la photo d'origine. Les images ne sont pas copiées ici : on les retélécharge à partir des identifiants.

## Contenu

Un dossier par région de collecte (`paris`, `sud`, `nord-2`…) :

- `meta.jsonl` : une ligne par vue annotée (attribution, voir plus haut) ;
- `annots/<identifiant>.json` : les marquages de la vue, en coordonnées de la vue de 1 280 × 720 points :
  `[{"classe": "M_velo", "box": [x1, y1, x2, y2]}, ...]`. Les classes sont celles du détecteur
  (`route_fr/classes.py`, liste `DETECTEUR`). `_ignorer` marque une zone à ne pas compter (marquage illisible, ou
  ambigu).

La vue est une vue « conducteur » : pour une photo à 360°, la vue vers l'avant reprojetée (champ horizontal 82°,
caméra inclinée de 12° vers le bas) ; pour une photo ordinaire, la partie basse de l'image ramenée à 1 280 points de
large.

## Refaire les images

```bash
python tools/marquages_reels.py refaire --dossier data/marquages_reels/paris --annotees
```

Les vues sont écrites dans `data/marquages_reels/paris/vues/` (ce dossier n'est pas suivi par git). Ensuite :

```bash
# mesurer un détecteur sur une ou plusieurs régions
python tools/marquages_reels.py bilan weights/route_fr_yolov5n.pt actuel --dossiers data/marquages_reels/sud
# fabriquer un jeu d'entraînement YOLO (fenêtres de 416 points)
python tools/marquages_reels.py exporte --dossiers data/marquages_reels/paris ... --vers datasets/marquages_reels --partie train
```

## Comment les annotations ont été faites

Des agents ont parcouru les vues, encadré chaque marquage lisible (le cadre est ensuite resserré automatiquement sur
la peinture), puis un contrôle indépendant a relu les cadres, corrigé les erreurs et retiré les vues douteuses.
Les régions de la première vague (`paris`, `lyon-grenoble`, `ouest`, `nord-est`, `sud`, `idf-banlieue`) ont été
contrôlées ainsi ; la région `sud` est tenue à l'écart de l'entraînement et ne sert qu'à mesurer.
