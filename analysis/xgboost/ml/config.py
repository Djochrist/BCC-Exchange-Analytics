"""
Configuration centrale du pipeline USD/CDF.

Tout ce qui est un choix méthodologique (horizons, découpage, recherche
d'hyperparamètres, seuils de détection d'anomalies, intervalles) est ici,
pour qu'aucun « nombre magique » ne soit enfoui dans le code.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Chemins
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
ML_DIR = ROOT / "ml"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ML_DIR / "models"
REPORTS_DIR = ML_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# Fichier consommé par le site web
MODEL_JSON_PATH = DATA_DIR / "model.json"

# Entrée par défaut. Surchargeable : `--input` en CLI ou variable USDCDF_INPUT.
DEFAULT_INPUT = Path(os.environ.get("USDCDF_INPUT", RAW_DIR / "cours-de-change-quotidien.csv"))

CLEAN_SERIES_PATH = PROCESSED_DIR / "series_clean.csv"
EXCLUDED_PATH = PROCESSED_DIR / "excluded_observations.csv"
DATA_QUALITY_REPORT = REPORTS_DIR / "data_quality.json"
MODEL_META_PATH = MODELS_DIR / "meta.json"

# --------------------------------------------------------------------------- #
# Lecture des données (export BCC CSV/JSON)
# --------------------------------------------------------------------------- #
# Colonnes testées, dans l'ordre, si --date-column / --value-column ne sont pas
# fournis. NB : "X_clean" n'est volontairement PAS dans la liste : c'est une
# colonne interpolée (donc des valeurs non observées). Pour l'utiliser, il faut
# la demander explicitement avec --value-column X_clean.
DATE_COLUMN_CANDIDATES = ["date", "Date", "DATE", "jour", "Jour"]
VALUE_COLUMN_CANDIDATES = ["USD/CDF", "usd_cdf", "USDCDF", "value", "Value", "X", "taux", "cours"]
DATE_DAYFIRST = False          # True si l'export BCC est au format JJ/MM/AAAA
TARGET_NAME = "USD/CDF"

# --------------------------------------------------------------------------- #
# Qualité des données
# --------------------------------------------------------------------------- #
# Détection des « excursions réversibles » : un bloc de 1 à ANOMALY_MAX_BLOCK
# observations consécutives qui s'écarte d'au moins ANOMALY_EXCURSION de la
# dernière valeur avant le bloc, ALORS QUE la première valeur après le bloc
# revient à moins de ANOMALY_REVERT_TOL de cette même référence.
# Un vrai mouvement de marché ne revient pas à son niveau initial en 1-5 jours
# avec un écart de >10 % : c'est la signature d'une erreur de saisie/export.
ANOMALY_MAX_BLOCK = 5
ANOMALY_EXCURSION = 0.10
ANOMALY_REVERT_TOL = 0.02
# "exclude" : les observations flaggées sont retirées de la série (jamais
#             remplacées ni interpolées) et listées dans excluded_observations.csv
# "keep"    : on les garde (à vos risques ; elles dominent alors RMSE/MAE)
ANOMALY_POLICY = "exclude"
# Au-delà de ce nombre de jours calendaires entre deux observations : alerte.
GAP_WARNING_DAYS = 7
# Rendements « extrêmes » (information seulement, jamais supprimés) : |z| robuste
EXTREME_RETURN_Z = 8.0
# Si la dernière observation s'écarte de plus de ce seuil de la précédente,
# on alerte (elle ne peut pas être validée par le test de réversion).
LAST_OBS_ALERT = 0.05

# --------------------------------------------------------------------------- #
# Prévision
# --------------------------------------------------------------------------- #
# Horizons exprimés en NOMBRE D'OBSERVATIONS (pas en jours calendaires).
HORIZONS = [5, 10, 20]
ROLLING_WINDOWS = [3, 5, 10, 20, 30]
LAGS = [1, 2, 3, 5, 7, 10, 14, 20, 30]
VARIATION_WINDOWS = [1, 3, 5, 10, 20]
STD_WINDOWS = [5, 10, 20, 30]
TREND_WINDOWS = [5, 10, 20, 30]
WARMUP_ROWS = 30               # lag_30 / rolling_30 / trend_30 exigent 30 obs. passées
DRIFT_WINDOW = 60              # baseline « dérive » (2e référence, en plus de la naïve)

# "scale_free" : variables sans échelle (rapports au niveau courant). Recommandé :
#                les arbres ne savent pas extrapoler un niveau jamais vu (le taux
#                passe de ~1 200 à ~2 800 CDF sur la période).
# "levels"     : variables en niveau brut, telles que listées dans la demande
#                (lag_k, rolling_mean_k en CDF). Utilisé pour l'ablation.
FEATURE_SET = "scale_free"
ABLATION_FEATURE_SET = "levels"

# --------------------------------------------------------------------------- #
# Validation temporelle
# --------------------------------------------------------------------------- #
TEST_FRACTION = 0.15           # dernière portion chronologique = test final hors échantillon
WF_N_SPLITS = 5                # fenêtres de validation walk-forward (expanding window)
WF_TEST_SIZE = 150             # taille de chaque fenêtre de validation (observations)
# gap (purge) = h : un échantillon d'entraînement t a pour cible t+h ; on retire
# donc les h dernières lignes avant chaque fenêtre de validation pour qu'aucune
# cible d'entraînement ne recouvre la période de validation.

# --------------------------------------------------------------------------- #
# XGBoost / recherche d'hyperparamètres
# --------------------------------------------------------------------------- #
RANDOM_STATE = 42
N_ITER_SEARCH = 30             # tirages aléatoires par horizon
N_JOBS = -1
TARGET_SCALE = 100.0           # la cible interne est en % (return*100) pour que
                               # reg_alpha/reg_lambda aient un effet cohérent
PARAM_SPACE = {
    "n_estimators": [100, 200, 300, 500],
    "max_depth": [2, 3, 4, 5],
    "learning_rate": [0.01, 0.02, 0.05, 0.1],
    "subsample": [0.6, 0.8, 1.0],
    "colsample_bytree": [0.5, 0.7, 0.9, 1.0],
    "min_child_weight": [1, 5, 10, 20, 50],
    "reg_alpha": [0.0, 0.001, 0.01, 0.1],
    "reg_lambda": [1.0, 5.0, 10.0, 50.0],
    "objective": ["reg:squarederror", "reg:absoluteerror"],
}

# --------------------------------------------------------------------------- #
# Évaluation / sélection
# --------------------------------------------------------------------------- #
BOOTSTRAP_N = 2000
BOOTSTRAP_CI = 0.90
DM_ALPHA = 0.10                # seuil du test de Diebold-Mariano
# Règle de sélection par horizon : XGBoost n'est retenu que si
# score_relatif < 1 en walk-forward ET sur le test final.
# Si True, il faut en plus que le test de Diebold-Mariano soit significatif.
REQUIRE_SIGNIFICANCE = False
PERMUTATION_REPEATS = 10

# --------------------------------------------------------------------------- #
# Intervalles prédictifs (conformal split, calibré sur erreurs hors échantillon)
# --------------------------------------------------------------------------- #
INTERVAL_LEVEL = 0.90          # couverture NOMINALE visée (pas une probabilité exacte)
# "conformal_normalized" : écart normalisé par la volatilité locale connue en t
# "conformal_absolute"   : écart absolu constant (ne s'adapte pas à la volatilité)
INTERVAL_METHOD = "conformal_normalized"
SIGMA_FLOOR_QUANTILE = 0.10    # plancher de volatilité pour éviter des bandes nulles
