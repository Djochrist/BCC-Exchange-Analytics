"""
Construction des variables et des cibles.

RÈGLE ABSOLUE : la variable de la ligne t n'utilise que value[0..t].
  - lags      : shift(+k)               -> passé strict
  - rolling   : fenêtres terminant en t -> (center=False, par défaut)
  - cible     : shift(-h)               -> UNIQUEMENT dans make_target(), jamais dans les features
Cette propriété est vérifiée automatiquement par `ml/verify_no_leakage.py`.

Horizons : h est un nombre d'OBSERVATIONS (la série n'est pas à pas régulier).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg


# --------------------------------------------------------------------------- #
# Catalogue complet des variables (toutes backward-looking)
# --------------------------------------------------------------------------- #
def _rolling_slope(x: np.ndarray) -> float:
    """Pente OLS de x sur 0..k-1 (unité : CDF par observation)."""
    k = len(x)
    t = np.arange(k, dtype=float)
    tc = t - t.mean()
    return float((tc * (x - x.mean())).sum() / (tc ** 2).sum())


def build_feature_catalog(series: pd.DataFrame) -> pd.DataFrame:
    """
    series : colonnes ['date', 'value'], triée chronologiquement.
    Retourne un DataFrame indexé comme `series` avec TOUTES les variables.
    """
    s = series.reset_index(drop=True)
    v = s["value"].astype(float)
    out = pd.DataFrame({"date": s["date"], "value": v})
    ret1 = v.pct_change()  # rendement sur 1 observation, connu en t

    # --- retards (niveaux) et version sans échelle ------------------------- #
    for k in cfg.LAGS:
        out[f"lag_{k}"] = v.shift(k)
        out[f"lag_{k}_rel"] = v.shift(k) / v - 1.0

    # --- variations passées (déjà relatives) -------------------------------- #
    for k in cfg.VARIATION_WINDOWS:
        out[f"variation_{k}"] = v / v.shift(k) - 1.0

    # --- moyennes mobiles --------------------------------------------------- #
    for k in cfg.ROLLING_WINDOWS:
        m = v.rolling(k, min_periods=k).mean()
        out[f"rolling_mean_{k}"] = m
        out[f"rolling_mean_{k}_rel"] = m / v - 1.0

    # --- volatilité --------------------------------------------------------- #
    # rolling_std_k       : écart-type des rendements 1-obs sur k obs (sans échelle)
    # rolling_std_k_level : écart-type du niveau en CDF (version « brute »)
    for k in cfg.STD_WINDOWS:
        out[f"rolling_std_{k}"] = ret1.rolling(k, min_periods=k).std()
        out[f"rolling_std_{k}_level"] = v.rolling(k, min_periods=k).std()
    # rolling_std_20 est aussi utilisé pour normaliser les intervalles ; garantir sa présence
    if "rolling_std_20" not in out:
        out["rolling_std_20"] = ret1.rolling(20, min_periods=20).std()

    # --- tendance ------------------------------------------------------------ #
    # trend_k       : pente OLS sur k obs. divisée par le niveau courant (relatif / obs.)
    # trend_k_level : pente OLS en CDF / obs.
    for k in cfg.TREND_WINDOWS:
        slope = v.rolling(k, min_periods=k).apply(_rolling_slope, raw=True)
        out[f"trend_{k}_level"] = slope
        out[f"trend_{k}"] = slope / v

    # --- calendrier & irrégularité ------------------------------------------ #
    d = pd.to_datetime(s["date"])
    out["day_of_week"] = d.dt.dayofweek.astype(int)
    out["month"] = d.dt.month.astype(int)
    out["quarter"] = d.dt.quarter.astype(int)
    out["days_since_previous_observation"] = d.diff().dt.days

    # --- référence « dérive » (2e baseline), uniquement passé --------------- #
    out["drift_ratio"] = v / v.shift(cfg.DRIFT_WINDOW)
    return out


# --------------------------------------------------------------------------- #
# Jeux de variables
# --------------------------------------------------------------------------- #
_CALENDAR = ["day_of_week", "month", "quarter", "days_since_previous_observation"]


def feature_columns(feature_set: str) -> list[str]:
    if feature_set == "scale_free":
        return (
            [f"lag_{k}_rel" for k in cfg.LAGS]
            + [f"variation_{k}" for k in cfg.VARIATION_WINDOWS]
            + [f"rolling_mean_{k}_rel" for k in cfg.ROLLING_WINDOWS]
            + [f"rolling_std_{k}" for k in cfg.STD_WINDOWS]
            + [f"trend_{k}" for k in cfg.TREND_WINDOWS]
            + _CALENDAR
        )
    if feature_set == "levels":
        return (
            [f"lag_{k}" for k in cfg.LAGS]
            + [f"variation_{k}" for k in cfg.VARIATION_WINDOWS]
            + [f"rolling_mean_{k}" for k in cfg.ROLLING_WINDOWS]
            + [f"rolling_std_{k}_level" for k in cfg.STD_WINDOWS]
            + [f"trend_{k}_level" for k in cfg.TREND_WINDOWS]
            + _CALENDAR
        )
    raise ValueError(f"feature_set inconnu : {feature_set!r} (attendu: 'scale_free' ou 'levels')")


# --------------------------------------------------------------------------- #
# Cibles
# --------------------------------------------------------------------------- #
def make_target(catalog: pd.DataFrame, h: int) -> pd.DataFrame:
    """
    Ajoute, pour l'horizon h (en observations) :
      return_h       = value[t+h]/value[t] - 1      (cible)
      target_date    = date[t+h]
      target_value   = value[t+h]
    Les h dernières lignes n'ont pas de cible (NaN) : elles servent à la prévision réelle.
    """
    out = catalog.copy()
    out["return_h"] = out["value"].shift(-h) / out["value"] - 1.0
    out["target_date"] = out["date"].shift(-h)
    out["target_value"] = out["value"].shift(-h)
    return out


def usable_rows(catalog: pd.DataFrame, feature_set: str) -> pd.DataFrame:
    """Retire les lignes de mise en route (fenêtres incomplètes). Ne supprime rien d'autre."""
    # drift_ratio (60 obs) n'est exigé que pour la baseline : on ne coupe que sur les features.
    must = feature_columns(feature_set) + ["rolling_std_20"]
    mask = catalog[must].notna().all(axis=1)
    return catalog[mask]


def build_horizon_dataset(catalog: pd.DataFrame, h: int, feature_set: str) -> dict:
    """
    Construit le jeu (X, y, meta) pour l'horizon h.
    Retourne un dict avec :
      X       : DataFrame des variables (lignes avec cible disponible)
      y       : rendement futur en DÉCIMAL
      meta    : date, value, target_date, target_value, row (position dans la série), sigma, drift_ratio
      forecast_row : DataFrame 1 ligne (dernière observation) pour la prévision réelle
    """
    full = make_target(catalog, h)
    full = full.assign(row=np.arange(len(full)))
    full = usable_rows(full, feature_set)
    labeled = full[full["return_h"].notna()]
    cols = feature_columns(feature_set)
    meta_cols = ["row", "date", "value", "target_date", "target_value", "rolling_std_20", "drift_ratio"]
    return {
        "X": labeled[cols].reset_index(drop=True),
        "y": labeled["return_h"].reset_index(drop=True),
        "meta": labeled[meta_cols].reset_index(drop=True),
        "forecast_row": full.iloc[[-1]][cols + meta_cols[:3] + ["rolling_std_20", "drift_ratio"]].reset_index(drop=True),
        "feature_names": cols,
    }


def drift_baseline_return(drift_ratio: pd.Series | np.ndarray, h: int) -> np.ndarray:
    """Baseline « dérive » : prolonge la tendance des DRIFT_WINDOW dernières obs. sur h obs."""
    r = np.asarray(drift_ratio, dtype=float)
    return r ** (h / cfg.DRIFT_WINDOW) - 1.0
