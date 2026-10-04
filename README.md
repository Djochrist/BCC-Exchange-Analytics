# USD/CDF BCC — plateforme de visualisation et d'analyse prédictive

Plateforme web pour visualiser le cours USD/CDF publié par la Banque Centrale du Congo, conserver son historique et présenter les analyses expérimentales du mémoire.

## Données BCC : collecte automatique

Le projet ne dépend pas d'une mise à jour manuelle du CSV.

`python scripts/collect_bcc.py` consulte les pages quotidiennes officielles de la BCC sur une fenêtre récente (14 jours par défaut), récupère le **USD (cours moyen)**, réconcilie les dates et rejette les jours sans cotation. Aucun point n'est interpolé.

Le même historique est propagé vers les deux pipelines expérimentaux :

- `analysis/xgboost/data/raw/cours-de-change-quotidien.csv`
- `analysis/strategy/data/series_clean.csv`

La page web peut aussi interroger `api/bcc.js` lorsqu'elle est déployée sur Vercel afin d'afficher le dernier cours directement depuis la BCC. Le fichier JSON versionné reste la référence pour l'historique et la reproductibilité.

## Automatisation

### Mise à jour quotidienne

`.github/workflows/update-bcc.yml` s'exécute les jours ouvrables. Il :

1. collecte les nouvelles cotations BCC ;
2. actualise l'historique du site ;
3. synchronise les entrées des analyses ;
4. recalcule la prévision de référence affichée par le site ;
5. vérifie la cohérence puis commit les fichiers modifiés.

### Réestimation des analyses

`.github/workflows/retrain-analyses.yml` est séparé. Il réentraîne XGBoost et relance la recherche de stratégies techniques périodiquement. Cette séparation permet d'ajouter une nouvelle observation BCC sans modifier artificiellement une expérience historique déjà évaluée.

Pour tout refaire localement :

```bash
python scripts/update_site.py --days-back 14 --retrain
```

Pour une simple synchronisation :

```bash
python scripts/update_site.py --days-back 14
```

## Analyses incluses

`analysis/xgboost/` contient le pipeline XGBoost complet du projet initial : préparation, contrôle qualité, variables, recherche d'hyperparamètres, entraînement par horizon, walk-forward, test final, métriques, tests statistiques, bootstrap, intervalles, figures et contrôle de fuite.

`analysis/strategy/` contient la recherche de stratégies techniques : EMA, RSI, momentum, MACD, volatilité, recherche de paramètres, walk-forward, test final, prévisions conditionnelles et figures.

Les résultats sont résumés dans `data/analyses.json` et `data/model_comparison.csv`.

## Résultat de référence actuellement archivé

- XGBoost : non retenu face à la naïve pour h=5, h=10 et h=20.
- EMA 20/50 : retenue pour h=10 uniquement dans l'expérience archivée.
- Pour h=5 et h=20, la référence naïve reste déployée selon la règle de sélection.

Ces décisions peuvent évoluer après réestimation avec de nouvelles données BCC.

## Exécuter le site localement

```bash
python3 -m http.server 8000
```

Puis ouvrir `http://localhost:8000`.

Le site lit `data/usd-cdf.json`, `data/model.json` et `data/analyses.json`. `api/bcc.js` ne fonctionne que sur un environnement Vercel/Node qui expose cette fonction.

## Documentation scientifique

- `XGBOOST_DOCUMENTATION.md`
- `STRATEGY_DOCUMENTATION.md`
- `STRATEGY_METHODOLOGY.md`
- `AUTO_UPDATE_DOCUMENTATION.md`
- `analysis/xgboost/README.md`
- `analysis/strategy/DOCUMENTATION.md`
