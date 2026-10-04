# USD/CDF — prévision XGBoost directe (h = 5, 10, 20 observations)

## Ce que le pipeline fait (et ne fait pas)

- Un modèle XGBoost **par horizon** (prévision directe), cible `return_h = value[t+h]/value[t] − 1`,
  niveau reconstruit par `value[t] × (1 + return_h_prédit)`.
- Validation **uniquement chronologique** : test final = dernière portion de la série (jamais vue
  pendant le réglage) + walk-forward à fenêtre extensible (5 plis) avec **purge de h observations**
  (les cibles de h pas se chevauchent ; sans purge, l'entraînement « verrait » la période de validation).
- Référence naïve (`value[t+h] = value[t]`) + 2ᵉ référence « dérive » ; score relatif
  `MAE_XGBoost / MAE_naïve`, test de Diebold-Mariano (HLN, variance HAC) et IC bootstrap par blocs.
- **XGBoost n'est déployé pour un horizon que s'il bat la naïve** (score < 1 en walk-forward ET en test final).
  Sinon `selected_model` vaut `"naive"` pour cet horizon dans `model.json`.
- Aucune donnée inventée, interpolée ou modifiée. 9 observations manifestement erronées sont
  **exclues** (jamais remplacées) et listées dans `data/processed/excluded_observations.csv`.

## Arborescence

```
train_pipeline.py            point d'entrée unique (toute la chaîne)
requirements.txt
ml/
  config.py                  TOUS les choix méthodologiques (horizons, découpage, recherche, seuils, intervalles)
  prepare_data.py            lecture CSV/JSON BCC, contrôles qualité, exclusion des erreurs de données
  features.py                variables (passé strict) + cibles par horizon
  train_xgboost.py           découpages temporels, recherche aléatoire d'hyperparamètres, entraînement
  evaluate.py                métriques, tests statistiques, intervalles conformes, importances, graphiques
  predict.py                 prévision depuis les modèles sauvegardés + génération de data/model.json
  verify_no_leakage.py       preuve par le code qu'aucune donnée future n'est utilisée
  models/                    xgboost_h5.json, xgboost_h10.json, xgboost_h20.json, meta.json   (générés)
  reports/                   metrics.json, metrics.csv, validation_predictions.csv,
                             feature_importance.csv, hyperparameter_search.csv,
                             data_quality.json, figures/*.png                                  (générés)
data/
  raw/                       export BCC (déposez ici le nouveau fichier)
  processed/                 series_clean.csv, excluded_observations.csv
  model.json                 fichier consommé par le site                                      (généré)
tests/test_no_leakage.py     même vérification, sous pytest
```

## Commandes

```bash
# 1) Installer (Ubuntu, Python >= 3.10)
cd usdcdf_ml
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Entraîner (toute la chaîne ; quelques minutes sur CPU standard avec 30 candidats/horizon)
python train_pipeline.py
#    variantes : --quick (test rapide du code) | --n-iter 60 | --ablation (compare variables « niveaux bruts »)
#                --input data/raw/export_bcc.csv --value-column "USD/CDF"

# 3) Inspecter les performances
column -s, -t < ml/reports/metrics.csv | less -S
python -c "import json;d=json.load(open('ml/reports/metrics.json'));[print(h,e['holdout']['score_relatif'],e['selection']['verdict']) for h,e in d['horizons'].items()]"
ls ml/reports/figures/        # pred_vs_actual_h*.png, errors_h*.png, relative_score_h*.png,
                              # comparison_naive_vs_xgboost.png, feature_importance.png, series_overview.png

# 4) Régénérer la prévision SANS ré-entraîner (ex. après ajout de nouvelles observations)
python -m ml.predict --input data/raw/cours-de-change-quotidien.csv

# 5) Vérifier l'absence de données futures
python -m ml.verify_no_leakage      # 20 contrôles ; code retour 1 si un seul échoue
python -m pytest -q

# 6) Intégrer dans le site : copier data/model.json (ex. vers public/data/model.json)
```

## Lire `model.json` côté site

Clés exigées : `generated_at`, `model`, `target`, `last_observation`, `selected_model`, `metrics`,
`forecast.{h5,h10,h20}.{value,lower,upper}`. Clés additionnelles (ignorables) : `model_used`,
`approx_target_date`, `alternatives`, `interval`, `model_staleness`, `disclaimer`.

```js
const m = await (await fetch('/data/model.json', { cache: 'no-cache' })).json();
for (const h of ['h5', 'h10', 'h20']) {
  const f = m.forecast[h];
  console.log(h, f.value, `[${f.lower} ; ${f.upper}]`, 'modèle:', m.selected_model[h], m.metrics[h].verdict);
}
```

À afficher honnêtement : (1) `selected_model` — si `naive`, ne pas présenter la valeur comme « prédiction IA » ;
(2) l'intervalle est **nominal** (`interval.nominal_level`) ; la couverture réellement observée sur le test est
dans `interval.empirical_coverage_on_holdout` ; (3) `h` = nombre d'observations, pas de jours ;
(4) `model_staleness.new_observations_since_training` pour savoir quand ré-entraîner.

## Utiliser un export BCC

Déposer le fichier dans `data/raw/` puis `python train_pipeline.py --input data/raw/<fichier>`.
Formats acceptés : CSV (`,` `;` tab, BOM), JSON (liste d'objets, `{"data":[...]}` ou `{date: valeur}`).
Colonnes détectées automatiquement (`config.py`) ou imposées avec `--date-column` / `--value-column`.
Dates en JJ/MM/AAAA : mettre `DATE_DAYFIRST = True`. Doublons de date avec valeurs différentes :
le pipeline s'arrête et vous le dit (il ne choisit pas à votre place).

## Limites à connaître

- La colonne `X_clean` du fichier « nettoyé » contient des valeurs interpolées : elle n'est jamais utilisée par défaut.
- Les 20 dernières cibles n'existent pas encore : elles ne servent qu'à la prévision réelle.
- La série contient des régimes très différents (volatilité quotidienne ≈ 0,03 % en 2021-22, ≈ 2 % en 2023,
  chute d'environ 25 % entre sept. et oct. 2025). Une évaluation unique sur ce test final est donc dominée par peu d'épisodes ;
  c'est pourquoi les 5 plis walk-forward sont rapportés en plus du test final.
- Les variables « niveaux bruts » (`lag_k`, `rolling_mean_k` en CDF) sont disponibles (`--ablation`) mais le modèle principal
  utilise les versions sans échelle : un arbre ne sait pas extrapoler des niveaux jamais vus (1 200 → 2 800 CDF).
