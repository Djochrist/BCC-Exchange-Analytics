# USD/CDF — analyses intégrées

Ce dossier contient les deux chaînes expérimentales utilisées pour le mémoire :

- `xgboost/` : prévision directe XGBoost pour h=5, 10 et 20 observations, avec variables passées, recherche d'hyperparamètres, validation walk-forward, test final, références naïve/dérive, test de Diebold-Mariano, bootstrap, intervalles et contrôle de fuite de données.
- `strategy/` : recherche empirique de stratégies issues de la série USD/CDF seule, avec EMA, RSI, momentum, MACD, volatilité, validation walk-forward et test final.

Le site public lit les synthèses présentes dans `data/analyses.json`. Les rapports détaillés, modèles, résultats CSV et figures restent archivés dans ces deux sous-projets afin de préserver la reproductibilité.

## Règle méthodologique

Le test final est séparé de la sélection. Une méthode n'est pas déclarée supérieure parce qu'elle fonctionne bien sur l'historique d'apprentissage : elle doit aussi améliorer la prévision hors échantillon par rapport à la référence naïve.

## Résultats de référence intégrés

- XGBoost : non retenu pour h=5, h=10 et h=20 dans l'expérience fournie.
- EMA 20/50 : retenue pour h=10 uniquement dans l'expérience fournie.
- h=5 et h=20 : référence naïve conservée.

Ces décisions correspondent à l'expérience archivée et peuvent changer après une nouvelle réestimation avec de nouvelles données BCC.
