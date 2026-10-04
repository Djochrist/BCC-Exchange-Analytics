# Documentation méthodologique — USD/CDF Strategy Analysis

## 1. Objectif scientifique

L'objectif est de vérifier, directement sur la série temporelle USD/CDF, si des règles de décision inspirées de l'analyse technique permettent d'améliorer la prévision par rapport à une référence extrêmement simple : conserver la dernière valeur observée.

Le projet ne part donc pas de l'hypothèse que « trader = prédire parfaitement ». Il teste l'hypothèse plus prudente suivante : **certaines configurations observables à la date `t` pourraient être associées à une distribution différente des variations futures à horizon `h`.**

Les horizons étudiés sont : 5, 10 et 20 observations.

## 2. Données

Entrée attendue : deux colonnes équivalentes à `date` et `value`, où `value` représente le cours USD/CDF selon la convention `1 USD = X CDF`.

Le projet utilise par défaut `data/series_clean.csv`, provenant de la série nettoyée du projet initial. Les observations exclues du nettoyage initial sont conservées à titre documentaire dans `data/excluded_observations.csv`.

Aucune valeur future n'est fabriquée pour rendre la série plus régulière.

## 3. Variables techniques

### Moyennes mobiles

Les EMA 5, 10, 20, 30, 50 et 100 sont calculées. La relation entre deux EMA est exprimée sous forme relative :

`gap = EMA_fast / EMA_slow - 1`

L'emploi d'un écart relatif est préférable à une différence brute en CDF car le niveau du taux change fortement sur la période 2017-2026.

### RSI

Les RSI 7, 14 et 21 sont calculés selon une moyenne exponentielle des gains et pertes. Le RSI sert ici de mesure de momentum relatif et non de règle universelle « surachat = vente ».

### Momentum

Les variations sur 5, 10 et 20 observations sont calculées :

`momentum_n(t) = value(t) / value(t-n) - 1`

### MACD

Le projet calcule EMA12, EMA26, ligne de signal EMA9 et histogramme MACD.

### Volatilité

Les écarts-types roulants des rendements sont calculés pour plusieurs fenêtres. Ils servent principalement à décrire le régime de volatilité et à éviter d'interpréter identiquement une configuration dans une période calme et une période de forte dispersion.

### Position dans la plage récente

La position de la valeur actuelle dans la plage des 20 dernières observations est mesurée par :

`(value - minimum20) / (maximum20 - minimum20)`

## 4. Construction des stratégies

### 4.1 Stratégie MA

Un signal haussier est produit lorsque `EMA_fast` dépasse `EMA_slow` d'une bande minimale. Un signal baissier apparaît lorsque l'écart est inférieur à la bande négative. Entre les deux, le signal est neutre.

### 4.2 Stratégie MA + RSI

La tendance doit être confirmée par un RSI élevé dans le régime haussier ou faible dans le régime baissier.

Cette règle est testée empiriquement. Le projet ne suppose pas à l'avance que RSI > 70 implique nécessairement une baisse.

### 4.3 Stratégie tendance + momentum

Le signal exige une tendance cohérente avec le signe du momentum récent.

### 4.4 Stratégie combinée

Quatre composantes votent :

- écart EMA ;
- momentum ;
- RSI ;
- histogramme MACD.

Le signal final est donné lorsqu'un seuil de votes minimum est atteint.

## 5. Transformation d'un signal en prévision numérique

Une difficulté importante apparaît : une règle technique fournit naturellement une direction, mais pas nécessairement une valeur future en CDF.

Pour résoudre cela sans modèle d'IA supplémentaire, l'espérance conditionnelle est estimée sur les données d'entraînement :

`E[rendement_h | signal = s]`

Le projet utilise la médiane lorsque suffisamment d'observations existent, sinon la moyenne, avec une limitation robuste de l'amplitude basée sur la distribution d'entraînement.

Ainsi, si le signal actuel est `+1`, la prévision n'est pas une valeur arbitrairement choisie : elle correspond au comportement historique observé sous des configurations comparables dans le seul échantillon disponible pour l'entraînement.

## 6. Absence de fuite de données

Le point le plus important est temporel.

Pour une validation donnée :

- les indicateurs à la date `t` utilisent uniquement les valeurs disponibles jusqu'à `t` ;
- les paramètres de la stratégie sont choisis uniquement avec la partie développement ;
- l'estimation conditionnelle du rendement est recalculée sur l'entraînement de chaque pli ;
- une purge de `h` observations sépare entraînement et validation ;
- le test final n'est jamais utilisé pour choisir les paramètres.

Le test final sert uniquement à répondre à la question : **la stratégie choisie sur le passé continue-t-elle à fonctionner sur une période réellement inconnue ?**

## 7. Pourquoi la comparaison avec la naïve est indispensable

Pour une série de change, une stratégie sophistiquée peut donner l'impression de prévoir correctement tout en ne battant pas une règle triviale consistant à reprendre la dernière valeur.

C'est pourquoi le projet rapporte systématiquement :

`score relatif = MAE stratégie / MAE naïve`

Interprétation :

- `< 1` : amélioration par rapport à la naïve ;
- `= 1` : pas d'amélioration ;
- `> 1` : stratégie moins précise.

Cette comparaison est plus informative qu'un simple score de précision directionnelle.

## 8. Critère de sélection

La recherche interne privilégie les candidats qui réduisent le MAE relatif moyen en walk-forward, tout en tenant compte de la capacité directionnelle et de la couverture des signaux.

Le test final n'est pas utilisé dans cette optimisation.

Pour le déploiement, la règle est encore plus stricte : la stratégie n'est retenue que si elle bat la naïve sur les deux niveaux de validation : walk-forward et test final.

Sinon le JSON de déploiement indique `naive`.

## 9. Lecture des résultats

Le fichier `summary.csv` doit être lu horizon par horizon.

Exemple conceptuel :

- walk-forward < 1 et test final < 1 : stratégie potentiellement déployable ;
- walk-forward < 1 mais test final > 1 : signe d'instabilité / overfitting possible ;
- walk-forward > 1 et test final < 1 : amélioration ponctuelle, mais absence de robustesse démontrée ;
- tous les ratios > 1 : la stratégie ne justifie pas son usage face à la naïve.

La précision directionnelle doit également être examinée. Une stratégie peut avoir une bonne direction sans améliorer le niveau prévu, notamment lorsque l'amplitude des erreurs reste importante.

## 10. Interprétation des intervalles

Les bornes du fichier `model.json` sont construites à partir de quantiles historiques des rendements correspondant au même signal lorsque suffisamment d'observations sont disponibles. Elles constituent un repère empirique.

Elles ne doivent pas être présentées comme une garantie probabiliste exacte.

## 11. Utilisation dans le mémoire

Le chapitre expérimental peut comparer trois approches :

1. naïve ;
2. stratégie technique sélectionnée ;
3. XGBoost.

La question devient alors non pas « quelle méthode est la plus complexe ? », mais :

**quelle méthode fournit la meilleure prévision hors échantillon du taux USD/CDF et dans quelles conditions ?**

Cette formulation est méthodologiquement plus solide.

## 12. Limites

La stratégie ne doit pas être qualifiée de « parfaite ». Les indicateurs techniques sont des transformations de la même série et ne créent pas d'information externe.

Une performance passée peut disparaître lorsque le régime économique change. Une stratégie peut aussi être sensible au choix des horizons, au nombre de paramètres testés et à la taille effective des épisodes comparables.

La bonne pratique consiste donc à privilégier la robustesse hors échantillon et à réévaluer le système lorsque de nouvelles observations BCC sont ajoutées.

## 13. Résultat de référence obtenu sur la série fournie

Une recherche stratifiée de 360 candidats a été exécutée sur la série fournie, avec 5 plis walk-forward pour chaque horizon et un test final séparé à partir du 9 octobre 2024.

| Horizon | Meilleure famille | Paramètres | Ratio MAE WF | Ratio MAE test | Sélection |
|---|---|---|---:|---:|---|
| 5 | MA | EMA 20 / EMA 50, bande 0,3 % | 1,015 | 0,998 | naïve |
| 10 | MA | EMA 20 / EMA 50, bande 0,3 % | 0,977 | 0,999 | MA |
| 20 | MA | EMA 20 / EMA 50, bande 0,3 % | 0,924 | 1,006 | naïve |

Ce résultat est particulièrement utile pour le mémoire : la règle EMA 20/50 présente une forte précision directionnelle en walk-forward, mais son avantage sur la prévision du niveau reste faible et n'est pas stable pour tous les horizons. Le protocole refuse donc de transformer automatiquement cette règle en « meilleure stratégie » pour h=5 et h=20.

La prochaine étape scientifique, avec une série BCC mise à jour, consiste à vérifier si ce comportement reste stable et à comparer directement cette stratégie aux références naïves et au modèle XGBoost du projet précédent.
