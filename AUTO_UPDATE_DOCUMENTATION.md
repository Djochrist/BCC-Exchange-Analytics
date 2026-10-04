# Mise à jour automatique des données BCC

## Principe

Le site utilise deux mécanismes complémentaires.

### 1. Historique : synchronisation automatique

Le script `scripts/collect_bcc.py` consulte les pages quotidiennes officielles de la Banque Centrale du Congo selon le motif :

`https://www.bcc.cd/marche-des-changes/cours-de-change/{YYYY-MM-DD}`

Il recontrôle une fenêtre récente de 14 jours afin de récupérer les publications tardives et les éventuelles corrections de la BCC. Les jours sans cotation sont ignorés. Aucune interpolation n'est réalisée.

Les données synchronisées sont enregistrées dans :

- `data/usd-cdf.json` pour le site ;
- `analysis/xgboost/data/raw/cours-de-change-quotidien.csv` pour le pipeline XGBoost ;
- `analysis/strategy/data/series_clean.csv` pour l'analyse technique.

### 2. Dernier cours : consultation directe

Sur Vercel, `api/bcc.js` interroge directement la page officielle BCC au chargement du site. Lorsque cette requête réussit, la dernière cotation est affichée immédiatement, même si le dépôt n'a pas encore reçu le prochain commit automatique.

Cette couche sert à afficher le cours courant. Elle ne remplace pas l'historique versionné utilisé pour les analyses du mémoire.

## Automatisation GitHub Actions

`.github/workflows/update-bcc.yml` s'exécute les jours ouvrables à 06:15 UTC. Il collecte les nouvelles cotations, rafraîchit `data/model.json` et `data/analyses.json`, vérifie la cohérence puis publie les changements dans le dépôt.

`.github/workflows/retrain-analyses.yml` est séparé : il réestime périodiquement XGBoost et la recherche de stratégies techniques. Cette séparation évite de mélanger une simple nouvelle observation BCC avec un réentraînement qui modifierait l'expérience scientifique à chaque visite.

## Pourquoi cette séparation est importante pour le mémoire

Une nouvelle cotation peut être ajoutée sans modifier rétroactivement les métriques d'un test historique déjà réalisé. Le site peut donc montrer une donnée actuelle tout en conservant une trace de la date jusqu'à laquelle chaque expérience XGBoost ou stratégie a été entraînée.

Avant une nouvelle expérience scientifique, le chercheur peut lancer :

```bash
python scripts/update_site.py --days-back 14 --retrain
```

Le protocole XGBoost et le protocole de recherche de stratégies restent documentés dans `analysis/xgboost/README.md` et `analysis/strategy/DOCUMENTATION.md`.

## Source institutionnelle

La Banque Centrale du Congo publie les cours officiels quotidiens et présente une série historique depuis janvier 2017 dans sa rubrique « Cours de change ». La page statistique décrit aussi le flux officiel utilisé pour les données courantes.
