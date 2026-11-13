# Publier Repère sur Google Play et sur l'App Store

Ce dossier contient tout ce que les deux boutiques demandent, sauf ce que toi seul peux faire : ouvrir les comptes,
payer les frais, signer et envoyer l'appli.

| Fichier | À quoi il sert |
|---|---|
| `fiche-google-play.md` | Textes à coller dans la console Google Play, réponses aux questionnaires |
| `fiche-app-store.md` | Textes à coller dans App Store Connect, phrases d'autorisation, note pour Apple |
| `captures/google-play/` | Six captures d'écran, 1 080 × 1 920 |
| `captures/app-store/` | Six captures d'écran, 1 320 × 2 868 (iPhone 6,9 pouces) |
| `visuels/` | Icône 512 et bandeau 1 024 × 500 pour Google, icône 1 024 pour Apple |
| `android/assetlinks.modele.json` | Modèle du fichier qui relie ton site à l'appli Android |
| `android/twa-manifest.modele.json` | Réglages pour l'outil Bubblewrap (seulement si un développeur t'aide) |

## Trois choses à savoir avant de commencer

1. **Le plus simple existe déjà.** Depuis ton site, Chrome propose « Installer l'appli » : Repère s'installe sur le
   téléphone, avec son icône, et marche sans réseau. C'est gratuit et immédiat. Les boutiques servent surtout à être
   trouvé par des inconnus.
2. **Google Play : compte 25 dollars, payés une fois. App Store : 99 dollars par an, et il faut un Mac.**
3. **Une question de licence est à régler avant de publier** (voir « La licence » plus bas). Lis ce passage d'abord.

## Étape commune : préparer le site

1. Mets la dernière version (zip 3.1.0 ou plus récent) sur Hostinger, dans le dossier `repere`, comme d'habitude.
2. Le site doit s'ouvrir en `https://`. C'est le cas chez Hostinger quand le certificat SSL est activé.
3. Ouvre `https://TON-DOMAINE.fr/repere/confidentialite.html`. Deux lignes sont « à compléter » : le nom de l'éditeur
   et l'adresse e-mail de contact. Donne-les moi et je les écris, ou modifie le fichier `confidentialite.html`.
   Les deux boutiques exigent cette page.

Partout dans ce dossier, remplace `TON-DOMAINE.fr` par ton vrai nom de domaine.

## Google Play, pas à pas

L'appli Android est une « enveloppe » qui ouvre ton site en plein écran, sans barre d'adresse (Google appelle ça une
Trusted Web Activity). Tu n'as rien à programmer : le site PWABuilder fabrique l'enveloppe.

**1. Ouvre un compte développeur** sur `play.google.com/console`. Deux choix :

- *Compte personnel.* Rapide à ouvrir. Mais Google impose alors un essai fermé : 12 testeurs au moins, inscrits
  pendant 14 jours d'affilée, avant d'avoir le droit de publier pour tout le monde. Tes élèves peuvent être ces testeurs.
- *Compte d'organisation* (au nom de l'auto-école). Il faut un numéro D-U-N-S, gratuit mais long à obtenir. D'après
  plusieurs guides, ce type de compte n'est pas soumis à la règle des 12 testeurs ; vérifie-le dans la console.

**2. Fabrique le paquet Android.**

1. Va sur `pwabuilder.com`, colle l'adresse `https://TON-DOMAINE.fr/repere/` et lance l'analyse.
2. Choisis « Package for stores », puis « Android ».
3. Remplis : identifiant du paquet `fr.tondomaine.repere` (il ne pourra plus changer), nom « Repère : code de la
   route », nom court « Repère », version `3.1.0`, code de version `1`.
4. Laisse PWABuilder créer une nouvelle clé de signature, puis télécharge le zip.
5. **Garde ce zip en lieu sûr, en double.** Il contient la clé de signature et ses mots de passe. Sans elle, tu ne
   pourras plus jamais mettre l'appli à jour.

Le zip contient un fichier `.aab` (pour Google Play), un fichier `.apk` (pour essayer sur ton téléphone) et un fichier
`assetlinks.json`.

**3. Relie le site à l'appli.** Sans ce lien, l'appli affiche une barre d'adresse en haut.

1. Sur Hostinger, à la **racine** du site (dossier `public_html`, pas dans `repere`), crée un dossier `.well-known`.
2. Mets-y le fichier `assetlinks.json` donné par PWABuilder.
3. Vérifie : `https://TON-DOMAINE.fr/.well-known/assetlinks.json` doit s'afficher dans le navigateur.
4. Après le premier envoi à Google : dans la console, « Intégrité de l'appli », copie l'empreinte SHA-256 de la *clé de
   signature de l'appli* et ajoute-la dans `assetlinks.json` (le modèle `android/assetlinks.modele.json` montre où).
   Google signe lui-même l'appli avec cette clé : c'est l'oubli le plus fréquent.

**4. Crée l'appli dans la console.**

1. « Créer une application » : nom, langue française, application, gratuite.
2. Colle les textes de `fiche-google-play.md`, ajoute l'icône, le bandeau et les six captures.
3. Réponds aux questionnaires (les réponses sont dans la fiche).
4. Dans « Tests », crée un test interne, envoie le fichier `.aab`, ajoute ton adresse comme testeur, installe et essaie.
   Vérifie surtout : pas de barre d'adresse, la caméra démarre, l'appli marche en mode avion après « Tout préparer pour
   rouler sans réseau ».
5. Compte personnel : crée ensuite le test fermé, invite 12 testeurs, attends 14 jours, puis demande l'accès à la
   production.
6. Envoie en production. La première validation de Google prend de quelques jours à une semaine.

**Mises à jour.** Le contenu de l'appli vient de ton site : quand tu mets un nouveau zip sur Hostinger, l'appli du
Play Store se met à jour toute seule. Tu ne renvoies un paquet à Google que si le nom, l'icône ou les exigences de
Google changent. Si la console refuse un paquet pour « niveau d'API cible trop ancien », refais-le sur PWABuilder.

## App Store, pas à pas

**Avant de payer quoi que ce soit, fais deux essais.**

1. Ouvre le site sur un iPhone, dans Safari, et lance la caméra. Je n'ai pas pu essayer l'appli sur iPhone : elle a été
   mise au point et testée sur Android (Chrome). Si la détection ne démarre pas ou est trop lente, il faut d'abord
   corriger cela.
2. Lis « Le risque de refus » ci-dessous.

**Ce qu'il faut.** Un compte Apple Developer (99 dollars par an), un Mac récent avec Xcode (gratuit), un iPhone.
Sans Mac, il existe des services de Mac à distance, ou un développeur peut le faire pour toi en une demi-journée.

**Les étapes.**

1. Sur `pwabuilder.com`, analyse `https://TON-DOMAINE.fr/repere/`, choisis « Package for stores », puis « iOS ».
   Identifiant : `fr.tondomaine.repere`. Télécharge le projet.
2. Ouvre le projet dans Xcode sur le Mac. Choisis ton équipe (ton compte développeur) pour la signature.
3. Dans le fichier `Info.plist`, ajoute les deux phrases d'autorisation de `fiche-app-store.md` (caméra et position).
   Sans la phrase sur la caméra, l'appli se ferme au lancement de la détection.
4. Remplace l'icône par `visuels/app-store-icone-1024.png`. Décoche l'iPad.
5. Essaie sur ton iPhone : caméra, voix, mode avion.
6. Dans Xcode : « Product », « Archive », puis « Distribute App » pour envoyer à App Store Connect.
7. Sur `appstoreconnect.apple.com` : crée la fiche avec les textes de `fiche-app-store.md`, les six captures,
   l'adresse de la page de confidentialité, la note pour la validation. Propose d'abord l'appli à quelques testeurs
   avec TestFlight, puis envoie-la en validation.

**Le risque de refus.** La règle 4.2 d'Apple dit qu'une appli doit offrir plus qu'un site web mis dans une boîte.
Apple refuse souvent les enveloppes de sites. Repère a de bons arguments : reconnaissance par la caméra faite sur
l'appareil, fonctionnement sans réseau, voix. La note pour la validation les met en avant. Mais un refus reste
possible, et dans ce cas il faudrait ajouter des fonctions propres à l'iPhone. Rien ne garantit l'acceptation.

## La licence : à régler avant de publier

Le détecteur a été entraîné avec YOLOv5, un logiciel de la société Ultralytics publié sous licence AGPL-3.0.
Cette licence demande que tout ce qui en dérive soit publié sous la même licence, code source compris.
Ultralytics considère que les modèles entraînés avec son logiciel en font partie.

- **Aujourd'hui, c'est respecté** : le code de Repère est public sur GitHub, sous licence AGPL-3.0, et l'appli donne
  le lien vers ce code.
- **Sur Google Play**, une appli libre et gratuite peut être publiée ainsi. Garde le dépôt public et le lien dans l'appli.
- **Sur l'App Store**, c'est moins clair : les conditions d'Apple ajoutent des restrictions que les licences de cette
  famille n'acceptent pas toujours. Des applis sous licence GPL ont déjà été retirées pour cette raison.
- **Si un jour l'appli devient payante, ou si tu ne veux plus publier le code**, il faut acheter une licence
  « Enterprise » à Ultralytics, ou réentraîner le détecteur avec un outil sous licence plus souple.

Je ne suis pas juriste. Avant une publication sur l'App Store ou une version payante, demande un avis à quelqu'un
dont c'est le métier, ou écris à Ultralytics.

## Ce que je n'ai pas pu vérifier

- Je n'ai pas de compte développeur ni de Mac : aucun paquet n'a été envoyé à Google ou à Apple. Les étapes ci-dessus
  suivent la documentation et des guides récents, pas un essai réel.
- Les pages d'aide de Google n'étaient pas accessibles depuis mon poste. Les tailles d'images et la règle des
  12 testeurs viennent de résultats de recherche qui les citent ; la console te les redonne au moment de remplir.
- L'appli n'a pas été essayée sur iPhone.
- Les boutiques changent leurs règles souvent. Si un écran ne ressemble pas à ce guide, c'est la console qui a raison.

## Sources

- [Google Play : exigences de test pour les nouveaux comptes personnels](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en)
- [Google Play : images de la fiche](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en)
- [Chrome : Trusted Web Activity, notions Android pour les développeurs web](https://developer.chrome.com/docs/android/trusted-web-activity/android-for-web-devs)
- [Apple : règles de validation de l'App Store (règles 4.2 et 5.1.1)](https://developer.apple.com/app-store/review/guidelines/)
- [Tailles des captures d'écran de l'App Store en 2026](https://studio.adalo.com/blog/app-store-screenshot-sizes-2026)
- [Publier une PWA sur Google Play : liste de contrôle 2026](https://spacenexus.us/blog/play-store-launch-checklist-pwa-twa-android)
- [La règle des 12 testeurs de Google Play](https://www.choicely.com/blog/google-play-12-tester-rule)
- [Règle 4.2 et applis qui enveloppent un site](https://www.mobiloud.com/blog/app-store-review-guidelines-webview-wrapper)
