# Entraînement SMC

Application mobile pour s'entraîner à repérer à l'œil nu une stratégie Smart Money Concepts sur de **vraies bougies 15 minutes de l'or et du forex** : XAUUSD, EURUSD et GBPUSD.

Le graphique s'arrête sur une **bougie de retournement**, juste après un retour du prix dans une zone (order block, FVG, Fibonacci). C'est le moment où tu entrerais en réel. Tu peux regarder la tendance de fond en **1 h** et en **4 h**, puis tu choisis **Achat** ou **Vente**. Les bougies suivantes défilent :
- +2R si le take-profit est touché en premier ;
- −1R si c'est le stop.

L'analyse de la stratégie s'affiche ensuite sur le graphique.

Tes statistiques restent enregistrées sur ton téléphone : série en cours, meilleure série, taux de réussite, total en R, résultats par marché.

- **385 situations réelles**, de février 2024 à octobre 2026 : 155 sur l'or, 113 sur EURUSD, 117 sur GBPUSD.
- Fonctionne **hors ligne** une fois installée.
- Aucun compte, aucune donnée envoyée.

## Installer l'application sur ton téléphone

L'application se publie gratuitement avec GitHub Pages, puis s'installe depuis le navigateur comme une vraie app (icône sur l'écran d'accueil, plein écran).

### 1. Activer GitHub Pages (une seule fois)

1. Sur GitHub, ouvre ce dépôt, puis **Settings → Pages**.
2. Dans **Build and deployment**, choisis **Source : Deploy from a branch**.
3. Choisis la branche **main** et le dossier **/ (root)**, puis **Save**.
4. Après une à deux minutes, l'adresse s'affiche, du type `https://<ton-compte>.github.io/entrainement-trading/`.

### 2. L'installer

- **iPhone (Safari)** : ouvre l'adresse, touche le bouton **Partager**, puis **Sur l'écran d'accueil**.
- **Android (Chrome)** : ouvre l'adresse, touche le menu **⋮**, puis **Installer l'application** (ou **Ajouter à l'écran d'accueil**).

### Tester sur ordinateur

```bash
python3 -m http.server 8000
```

Puis ouvre http://localhost:8000.

## Comment sont créées les situations

Les bougies 1 minute viennent de HistData.com (données gratuites), regroupées en 15 minutes. Les situations sont détectées automatiquement par `outils/smc.py` :

| Élément | Règle |
|---|---|
| Tendance 4 h | Prix au-dessus de l'EMA 200 en 4 h et dernier plus haut 4 h cassé (l'inverse pour la vente) |
| Points de swing | Plus haut ou plus bas des 3 bougies avant et des 3 après |
| Prise de liquidité | Une mèche passe sous un plus bas récent puis le prix reclôture au-dessus dans les 3 bougies |
| BOS | Clôture au-dessus du dernier plus haut de swing |
| Order block | Dernière bougie baissière avant l'impulsion |
| Impulsion | Au moins une bougie dont le corps fait plus de 1,5 fois la moyenne des 20 précédentes |
| FVG | Bas de la bougie 3 au-dessus du haut de la bougie 1, qui touche ou chevauche l'order block, jamais retesté |
| Zone | Partie commune du FVG et de la zone Fibonacci 0,618–0,705 |
| Entrée | Clôture d'une bougie au-delà du plus haut (achat) ou du plus bas (vente) de la précédente, dans les 6 bougies après le retour dans la zone |
| Stop | Au-delà de l'order block, avec une marge de 0,3 × ATR(14) |
| Take-profit | 2 fois la distance du stop |

Pour avoir assez de situations, l'application mélange quatre variantes : avec ou sans prise de liquidité, avec ou sans zone Fibonacci. L'écran de résultat indique laquelle tu viens de voir.

### Régénérer les situations

Il faut Python 3 avec `pandas` et `numpy`.

```bash
python3 outils/telecharger_donnees.py
```

```bash
python3 outils/generer_scenarios.py
```

Après une régénération, change le nom du cache dans `sw.js` (par exemple `entrainement-smc-v3`) pour que les téléphones téléchargent la nouvelle version.

## Fichiers

| Fichier | Rôle |
|---|---|
| `index.html`, `style.css` | Interface |
| `app.js` | Déroulement du jeu et statistiques |
| `chart.js` | Dessin des bougies et des zones |
| `scenarios.js` | Les situations (généré) |
| `sw.js`, `manifest.webmanifest`, `icons/` | Installation et fonctionnement hors ligne |
| `outils/` | Téléchargement des bougies et détection des situations |
