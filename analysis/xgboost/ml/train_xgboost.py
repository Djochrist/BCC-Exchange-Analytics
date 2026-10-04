"""
Entraînement XGBoost par horizon (prévision DIRECTE : un modèle par h).

Schéma temporel (jamais aléatoire) pour chaque horizon h :

  |<------------- pool de développement ------------>|<-h->|<---- test final ---->|
  | train ......................................... |purge| origines t >= T0      |
  
  - T0 : début du test final = dernières TEST_FRACTION des observations utilisables.
  - Un échantillon d'entraînement t n'est gardé que si t+h < T0 (sa cible est
    connue avant T0) -> aucun chevauchement de cible avec le test.
  - Walk-forward (fenêtre extensible) à l'intérieur du pool, avec gap=h entre
    entraînement et validation -> même garantie dans chaque pli.
  - La recherche d'hyperparamètres n'utilise QUE le pool de développement.
  - Le test final n'est vu qu'UNE fois, après le choix des hyperparamètres.
"""
from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import ParameterSampler, TimeSeriesSplit

from . import config as cfg
from . import features as F

log = logging.getLogger(__name__)

DEFAULT_PARAMS = {  # candidat « raisonnable » toujours évalué en premier
    "n_estimators": 200, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8,
    "colsample_bytree": 0.8, "min_child_weight": 10, "reg_alpha": 0.01, "reg_lambda": 10.0,
    "objective": "reg:squarederror",
}


# --------------------------------------------------------------------------- #
# Modèle
# --------------------------------------------------------------------------- #
def make_regressor(params: dict):
    from xgboost import XGBRegressor  # import tardif : message d'erreur clair si absent
    return XGBRegressor(tree_method="hist", random_state=cfg.RANDOM_STATE, n_jobs=cfg.N_JOBS, verbosity=0, **params)


def fit_predict_returns(params: dict, X_train: pd.DataFrame, y_train: pd.Series, X_eval: pd.DataFrame):
    """Entraîne sur (X_train,y_train) et prédit des rendements en décimal."""
    model = make_regressor(params)
    model.fit(X_train, y_train.to_numpy() * cfg.TARGET_SCALE)
    return model, model.predict(X_eval) / cfg.TARGET_SCALE


# --------------------------------------------------------------------------- #
# Découpage chronologique
# --------------------------------------------------------------------------- #
def test_start_row(catalog: pd.DataFrame, feature_set: str) -> int:
    """Position (dans la série) de la 1re origine du test final. Identique pour tous les horizons."""
    usable = F.usable_rows(catalog, feature_set)
    rows = np.asarray(usable.index)
    return int(rows[int(round(len(rows) * (1.0 - cfg.TEST_FRACTION)))])


def split_dev_test(ds: dict, h: int, t0_row: int) -> dict:
    """Sépare pool de développement (cible connue avant T0) et test final (origine >= T0)."""
    row = ds["meta"]["row"].to_numpy()
    dev = row + h < t0_row         # cible t+h strictement avant T0
    test = row >= t0_row
    return {"dev_idx": np.flatnonzero(dev), "test_idx": np.flatnonzero(test)}


def walk_forward_splits(n_dev: int, h: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Fenêtre extensible, gap=h (purge des cibles chevauchantes)."""
    need = cfg.WF_N_SPLITS * cfg.WF_TEST_SIZE + h
    if n_dev < need + 200:
        raise ValueError(f"Pas assez d'observations pour le walk-forward (n_dev={n_dev}, requis>={need + 200}). "
                         "Réduisez WF_N_SPLITS ou WF_TEST_SIZE dans config.py.")
    tscv = TimeSeriesSplit(n_splits=cfg.WF_N_SPLITS, test_size=cfg.WF_TEST_SIZE, gap=h)
    return list(tscv.split(np.arange(n_dev)))


# --------------------------------------------------------------------------- #
# Utilitaires de prédictions
# --------------------------------------------------------------------------- #
def make_pred_frame(meta: pd.DataFrame, y: pd.Series, pred_ret: np.ndarray, h: int, split: str, fold: int) -> pd.DataFrame:
    v = meta["value"].to_numpy()
    out = pd.DataFrame({
        "horizon": h, "split": split, "fold": fold,
        "origin_date": meta["date"].dt.strftime("%Y-%m-%d").to_numpy(),
        "target_date": meta["target_date"].dt.strftime("%Y-%m-%d").to_numpy(),
        "value_origin": v,
        "actual_value": meta["target_value"].to_numpy(),
        "actual_return": y.to_numpy(),
        "pred_return_xgboost": pred_ret,
        "pred_value_xgboost": v * (1.0 + pred_ret),
        "pred_return_naive": 0.0,
        "pred_value_naive": v,
    })
    drift = F.drift_baseline_return(meta["drift_ratio"].to_numpy(), h)
    out["pred_return_drift"] = drift
    out["pred_value_drift"] = v * (1.0 + drift)
    out["sigma_h"] = meta["rolling_std_20"].to_numpy() * np.sqrt(h)  # volatilité locale connue en t
    return out


def _fold_relative_score(y_true: np.ndarray, y_pred: np.ndarray, v0: np.ndarray) -> tuple[float, float, float]:
    """(MAE_xgb, MAE_naive, ratio) en NIVEAU (CDF). Naïve = rendement nul."""
    mae_x = float(np.mean(np.abs(v0 * (y_pred - y_true))))
    mae_n = float(np.mean(np.abs(v0 * y_true)))
    return mae_x, mae_n, mae_x / mae_n if mae_n > 0 else np.inf


# --------------------------------------------------------------------------- #
# Recherche d'hyperparamètres (aléatoire, walk-forward, pool de développement seulement)
# --------------------------------------------------------------------------- #
def tune_horizon(X_dev: pd.DataFrame, y_dev: pd.Series, meta_dev: pd.DataFrame, h: int,
                 n_iter: int, progress=None) -> tuple[dict, pd.DataFrame]:
    """
    Critère de sélection : moyenne sur les plis de MAE_xgb / MAE_naive (niveau).
    On optimise donc directement la question posée (« mieux que la naïve ? »).
    """
    splits = walk_forward_splits(len(X_dev), h)
    candidates = [DEFAULT_PARAMS] + list(ParameterSampler(cfg.PARAM_SPACE, n_iter=n_iter, random_state=cfg.RANDOM_STATE + h))
    rows = []
    for i, params in enumerate(candidates):
        ratios, maes = [], []
        for tr, va in splits:
            _, pred = fit_predict_returns(params, X_dev.iloc[tr], y_dev.iloc[tr], X_dev.iloc[va])
            mx, mn, r = _fold_relative_score(y_dev.iloc[va].to_numpy(), pred, meta_dev["value"].iloc[va].to_numpy())
            ratios.append(r)
            maes.append(mx)
        rows.append({"candidate": i, "is_default": i == 0, "cv_score_relatif_mean": float(np.mean(ratios)),
                     "cv_score_relatif_std": float(np.std(ratios)), "cv_mae_mean": float(np.mean(maes)),
                     **{f"fold{j + 1}_score": r for j, r in enumerate(ratios)}, **params})
        if progress:
            progress(i + 1, len(candidates))
    res = pd.DataFrame(rows).sort_values("cv_score_relatif_mean").reset_index(drop=True)
    best_row = res.iloc[0]
    best = {k: (best_row[k].item() if hasattr(best_row[k], "item") else best_row[k]) for k in cfg.PARAM_SPACE}
    return best, res


def walk_forward_oof(params: dict, X_dev, y_dev, meta_dev, h: int) -> pd.DataFrame:
    """Prédictions hors échantillon de chaque pli walk-forward avec les hyperparamètres choisis."""
    frames = []
    for k, (tr, va) in enumerate(walk_forward_splits(len(X_dev), h), start=1):
        _, pred = fit_predict_returns(params, X_dev.iloc[tr], y_dev.iloc[tr], X_dev.iloc[va])
        f = make_pred_frame(meta_dev.iloc[va], y_dev.iloc[va], pred, h, f"walk_forward_{k}", k)
        f["train_start"] = meta_dev["date"].iloc[tr[0]].strftime("%Y-%m-%d")
        f["train_end"] = meta_dev["date"].iloc[tr[-1]].strftime("%Y-%m-%d")
        f["train_size"] = len(tr)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- #
# Entraînement complet d'un horizon
# --------------------------------------------------------------------------- #
def train_horizon(catalog: pd.DataFrame, h: int, feature_set: str, t0_row: int, n_iter: int, verbose: bool = True) -> dict:
    t_start = time.time()
    ds = F.build_horizon_dataset(catalog, h, feature_set)
    sp = split_dev_test(ds, h, t0_row)
    d, t = sp["dev_idx"], sp["test_idx"]
    X_dev, y_dev, m_dev = ds["X"].iloc[d].reset_index(drop=True), ds["y"].iloc[d].reset_index(drop=True), ds["meta"].iloc[d].reset_index(drop=True)
    X_te, y_te, m_te = ds["X"].iloc[t].reset_index(drop=True), ds["y"].iloc[t].reset_index(drop=True), ds["meta"].iloc[t].reset_index(drop=True)

    if len(t) < 30:
        raise ValueError(f"Test final trop petit pour h={h} ({len(t)} échantillons).")

    def progress(i, n):
        if verbose and (i == n or i % 10 == 0):
            print(f"    h={h:>2} recherche d'hyperparamètres : {i}/{n}", flush=True)

    # 1) recherche d'hyperparamètres : pool de développement uniquement
    best, search = tune_horizon(X_dev, y_dev, m_dev, h, n_iter, progress)

    # 2) prédictions walk-forward hors échantillon avec les meilleurs paramètres
    wf = walk_forward_oof(best, X_dev, y_dev, m_dev, h)

    # 3) modèle « développement » -> évalué UNE fois sur le test final
    model_dev, pred_te = fit_predict_returns(best, X_dev, y_dev, X_te)
    holdout = make_pred_frame(m_te, y_te, pred_te, h, "holdout", 0)
    holdout["train_start"] = m_dev["date"].iloc[0].strftime("%Y-%m-%d")
    holdout["train_end"] = m_dev["date"].iloc[-1].strftime("%Y-%m-%d")
    holdout["train_size"] = len(X_dev)

    # 4) modèle final (déploiement) : toutes les cibles connues, mêmes hyperparamètres
    model_final = make_regressor(best)
    model_final.fit(ds["X"], ds["y"].to_numpy() * cfg.TARGET_SCALE)

    return {
        "h": h, "feature_set": feature_set, "feature_names": ds["feature_names"], "best_params": best,
        "search": search, "walk_forward": wf, "holdout": holdout,
        "model_dev": model_dev, "model_final": model_final,
        "X_test": X_te, "y_test": y_te, "meta_test": m_te,
        "forecast_row": ds["forecast_row"],
        "n_dev": len(X_dev), "n_test": len(X_te), "n_all_labeled": len(ds["X"]),
        "dev_period": (m_dev["date"].iloc[0], m_dev["target_date"].iloc[-1]),
        "test_period": (m_te["date"].iloc[0], m_te["target_date"].iloc[-1]),
        "seconds": time.time() - t_start,
    }


def train_all(catalog: pd.DataFrame, feature_set: str | None = None, n_iter: int | None = None, verbose: bool = True) -> dict:
    fs = feature_set or cfg.FEATURE_SET
    n_iter = n_iter or cfg.N_ITER_SEARCH
    t0 = test_start_row(catalog, fs)
    if verbose:
        print(f"  Début du test final : {catalog['date'].iloc[t0].date()} (ligne {t0}/{len(catalog)}) | variables: {fs}")
    return {h: train_horizon(catalog, h, fs, t0, n_iter, verbose) for h in cfg.HORIZONS}


def save_models(results: dict) -> None:
    cfg.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for h, r in results.items():
        r["model_final"].save_model(str(cfg.MODELS_DIR / f"xgboost_h{h}.json"))
