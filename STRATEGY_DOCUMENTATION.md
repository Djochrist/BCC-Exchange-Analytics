# USD/CDF — recherche de stratégie prédictive basée sur la série elle-même

Ce projet complète le pipeline XGBoost précédent. Son objectif n'est pas de chercher un modèle d'IA plus complexe, mais de déterminer si **la dynamique historique de la série USD/CDF** contient des signaux exploitables à partir d'indicateurs techniques classiques : moyennes mobiles, RSI, momentum, MACD, position dans une plage récente et volatilité.

Le projet cherche plusieurs familles de stratégies, les évalue avec une validation chronologique walk-forward, puis conserve séparément un test final qui n'intervient pas dans le choix des paramètres.

## Principe

Pour une origine `t` et un horizon `h` :

`rendement_h(t) = USD_CDF(t+h) / USD_CDF(t) - 1`

Une stratégie produit un signal connu à `t` :

- `+1` : scénario haussier ;
- `0` : neutre ;
- `-1` : scénario baissier.

La valeur prévue est ensuite obtenue par une estimation **conditionnelle au signal**, calculée uniquement sur les observations d'entraînement. Cela évite de transformer artificiellement une règle de trading en prévision numérique.

## Familles testées

1. `ma` : tendance par croisement / écart entre deux EMA.
2. `ma_rsi` : tendance + confirmation RSI.
3. `trend_momentum` : tendance + momentum.
4. `combo` : vote combiné tendance + momentum + RSI + MACD.

Les paramètres explorés sont volontairement limités à des valeurs économiquement lisibles. Le script n'optimise pas chaque nombre possible, afin de réduire le risque d'overfitting.

## Validation

La série est séparée en deux blocs :

- développement : 80 % de la série ;
- test final : 20 %, conservé pour l'évaluation finale.

Sur le développement, chaque horizon utilise 5 plis walk-forward avec une purge de `h` observations entre apprentissage et validation. Le test final reste totalement hors sélection.

La référence principale est la prévision naïve :

`USD_CDF(t+h) = USD_CDF(t)`

Une stratégie n'est déclarée **sélectionnée pour le déploiement** que si elle bat la naïve à la fois :

- sur le walk-forward ;
- sur le test final.

Sinon `selected_model = naive`, même si une stratégie possède une bonne direction sur une partie des données. C'est volontairement conservateur.

## Métriques

Le rapport contient notamment :

- MAE en niveau CDF ;
- ratio `MAE stratégie / MAE naïve` ;
- RMSE et son ratio ;
- précision directionnelle ;
- couverture des signaux non neutres ;
- résultats par pli ;
- meilleurs paramètres par horizon.

Un ratio MAE < 1 signifie que la stratégie fait mieux que la prévision naïve pour cette métrique. La précision directionnelle mesure séparément la capacité à anticiper le signe du mouvement.

## Installation

```bash
cd usdcdf_strategy_analysis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Exécution

```bash
python run_strategy.py
```

Pour un essai rapide :

```bash
python run_strategy.py --candidate-limit 120
```

Par défaut, la recherche utilise 360 candidats échantillonnés de façon stratifiée, en conservant les quatre familles de stratégies. Pour explorer toute la grille actuelle, utiliser `--candidate-limit 945`.

Avec un nouveau fichier :

```bash
python run_strategy.py --input data/series_clean.csv
```

## Sorties

`data/reports/summary.csv` contient un résumé par horizon.

`data/reports/strategy_search_h5.csv`, `strategy_search_h10.csv`, `strategy_search_h20.csv` contiennent les résultats de la recherche.

`data/reports/holdout_predictions_h*.csv` contient les prédictions du test final.

`data/reports/model.json` est le fichier prévu pour une consommation par le site web.

`plots/series_usdcdf.png` représente la série.

`plots/strategy_scores.png` compare les meilleurs candidats.

## Important pour le mémoire

Il ne faut pas écrire que la stratégie est « parfaite » simplement parce qu'elle obtient un bon score historique. La conclusion scientifique doit être formulée en termes de **robustesse hors échantillon**, de comparaison avec la naïve et de stabilité entre périodes.

Le résultat le plus intéressant peut être qu'aucune stratégie ne bat systématiquement la naïve. Ce résultat est lui-même exploitable dans le mémoire : il montre que la seule série historique du taux USD/CDF peut contenir une information directionnelle sans pour autant permettre une prévision précise et stable du niveau futur.
