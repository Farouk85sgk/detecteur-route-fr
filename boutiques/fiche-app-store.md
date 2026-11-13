# Fiche App Store : textes à copier

À coller dans App Store Connect. Les longueurs maximales sont celles demandées par Apple.

## Nom (30 caractères au plus)

```
Repère : code de la route
```

## Sous-titre (30 caractères au plus)

```
Panneaux reconnus en direct
```

## Texte promotionnel (170 caractères au plus)

```
Filme la route : panneaux, feux et marquages sont reconnus et expliqués en direct. Puis révise avec 685 questions de code, des examens blancs et une quête.
```

## Mots-clés (100 caractères au plus, séparés par des virgules)

```
permis,panneaux,signalisation,auto-école,conduite,examen,quiz,ETG,conduite accompagnée,révision
```

## Description

Reprends la « Description complète » de `fiche-google-play.md` : elle convient telle quelle.

## Réglages de la fiche

- Catégorie principale : Éducation. Catégorie secondaire : Références.
- Âge : 4+ (réponds « Aucun » à toutes les questions).
- Prix : gratuit.
- URL des règles de confidentialité : `https://TON-DOMAINE.fr/repere/confidentialite.html`
- URL d'assistance : l'adresse de ton site.
- Confidentialité de l'app : « Données non collectées ».
- Chiffrement : l'appli n'utilise que le HTTPS standard. Dans le projet, la clé `ITSAppUsesNonExemptEncryption` vaut `NO`.

## Images à fournir

| Demande d'Apple | Fichier |
|---|---|
| Icône, 1 024 × 1 024, sans transparence | `visuels/app-store-icone-1024.png` |
| Captures iPhone 6,9 pouces, 1 320 × 2 868 | les six images de `captures/app-store/`, dans l'ordre des numéros |

Limite l'appli à l'iPhone (décoche l'iPad dans Xcode) : sinon Apple demande aussi des captures iPad.

## Phrases d'autorisation (fichier Info.plist du projet)

Apple refuse une appli qui utilise la caméra sans dire pourquoi. Ces deux phrases se collent dans Xcode.

| Clé | Phrase |
|---|---|
| `NSCameraUsageDescription` | `La caméra filme la route pour reconnaître les panneaux. Les images restent sur ton iPhone.` |
| `NSLocationWhenInUseUsageDescription` | `Pour noter l'endroit où chaque panneau a été repéré pendant un trajet. C'est facultatif.` |

## Note pour l'équipe de validation d'Apple

À coller dans « Notes pour la vérification » (Apple travaille en anglais) :

```
Repère recognises French road signs, traffic lights and road markings on the device, using the camera and on-device machine learning. No image leaves the phone and the app works offline.

How to test without driving:
1. Open the app and tap "Lancer la caméra" (start camera).
2. Point the phone at a picture of a French road sign on another screen, for example a "STOP" sign or a "50" speed limit sign. The sign is framed, named aloud and explained.
3. Or tap "Tester sur une vidéo" (test on a video) and choose any dashcam video.

No account is needed. The app has no ads and no purchases. The in-game currency ("pépites") is earned by playing and cannot be bought.
```
