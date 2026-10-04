"""
Évaluation : XGBoost vs baselines (naïve, dérive).

Répond scientifiquement à : « XGBoost apporte-t-il une amélioration par rapport à la naïve ? »
  1. score_relatif = MAE_xgb / MAE_naive  (<1 : mieux ; >=1 : pas d'amélioration)
  2. Test de Diebold-Mariano (correction de Harvey-Leybourne-Newbold, variance HAC
     à h-1 retards car les erreurs h-pas sont autocorrélées par construction)
  3. IC bootstrap par blocs mobiles du score_relatif
  4. Cohérence : walk-forward (5 fenêtres) ET test final hors échantillon

Les intervalles prédictifs sont de type « conformal split » : calibrés sur les
erreurs HORS ÉCHANTILLON, couverture empirique vérifiée sur le test final.
Ce sont des intervalles à couverture NOMINALE, pas des probabilités exactes.
"""
from __future__ import annotations

import json
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from . import config as cfg

MODELS = {
    "xgboost": ("pred_value_xgboost", "pred_return_xgboost"),
    "naive": ("pred_value_naive", "pred_return_naive"),
    "drift": ("pred_value_drift", "pred_return_drift"),
}


# --------------------------------------------------------------------------- #
# Métriques de base
# --------------------------------------------------------------------------- #
def metric_block(df: pd.DataFrame, model: str) -> dict:
    vcol, rcol = MODELS[model]
    a, p = df["actual_value"].to_numpy(), df[vcol].to_numpy()
    ra, rp = df["actual_return"].to_numpy(), df[rcol].to_numpy()
    ok = np.isfinite(p) & np.isfinite(rp)       # la baseline « dérive » peut être NaN en début de série
    a, p, ra, rp = a[ok], p[ok], ra[ok], rp[ok]
    err = p - a
    sse, sst = float(np.sum((rp - ra) ** 2)), float(np.sum((ra - ra.mean()) ** 2))
    sse_naive = float(np.sum(ra ** 2))
    both = (ra != 0) & (rp != 0)
    return {
        "n": int(len(a)),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mape_pct": float(100 * np.mean(np.abs(err) / np.abs(a))),
        "smape_pct": float(100 * np.mean(2 * np.abs(err) / (np.abs(a) + np.abs(p)))),
        "bias": float(np.mean(err)),                                # >0 : le modèle surestime
        "r2_level": float(1 - np.sum(err ** 2) / np.sum((a - a.mean()) ** 2)),  # GONFLÉ par la tendance : à ne pas utiliser seul
        "r2_return": float(1 - sse / sst) if sst > 0 else float("nan"),
        "r2_oos_vs_naive": float(1 - sse / sse_naive) if sse_naive > 0 else float("nan"),  # >0 : bat la naïve en MSE
        "directional_accuracy": float(np.mean(np.sign(rp[both]) == np.sign(ra[both]))) if both.sum() and model != "naive" else float("nan"),
    }


def all_models_metrics(df: pd.DataFrame) -> dict:
    out = {m: metric_block(df, m) for m in MODELS}
    for m in MODELS:
        out[m]["mae_ratio_vs_naive"] = out[m]["mae"] / out["naive"]["mae"]
        out[m]["rmse_ratio_vs_naive"] = out[m]["rmse"] / out["naive"]["rmse"]
    return out


# --------------------------------------------------------------------------- #
# Tests statistiques
# --------------------------------------------------------------------------- #
def diebold_mariano(e1: np.ndarray, e2: np.ndarray, h: int, power: int = 1) -> dict:
    """
    H0 : même précision. d_t = |e1|^p - |e2|^p. Statistique < 0 => le modèle 1 (xgboost) est meilleur.
    Variance de long terme de Bartlett avec h-1 retards ; correction HLN ; loi de Student(T-1).
    """
    d = np.abs(e1) ** power - np.abs(e2) ** power
    T = len(d)
    dbar = d.mean()
    dc = d - dbar
    lrv = float(np.sum(dc * dc) / T)
    for k in range(1, h):
        gk = float(np.sum(dc[k:] * dc[:-k]) / T)
        lrv += 2.0 * (1.0 - k / h) * gk
    lrv = max(lrv, 1e-18)
    dm = dbar / np.sqrt(lrv / T)
    hln = np.sqrt(max((T + 1 - 2 * h + h * (h - 1) / T) / T, 1e-12))
    dm_adj = dm * hln
    return {
        "statistic": float(dm_adj),
        "p_value_two_sided": float(2 * (1 - stats.t.cdf(abs(dm_adj), T - 1))),
        "p_value_xgb_better_one_sided": float(stats.t.cdf(dm_adj, T - 1)),
        "mean_loss_diff": float(dbar),
        "n": int(T),
    }


def block_bootstrap_ratio(abs_err_x: np.ndarray, abs_err_n: np.ndarray, block: int, n_boot: int, ci: float, seed: int) -> dict:
    """IC du ratio MAE_xgb/MAE_naive par blocs mobiles (préserve l'autocorrélation des erreurs)."""
    rng = np.random.default_rng(seed)
    n = len(abs_err_x)
    L = max(2, min(block, n))
    nb = int(np.ceil(n / L))
    starts = rng.integers(0, n - L + 1, size=(n_boot, nb))
    idx = (starts[:, :, None] + np.arange(L)[None, None, :]).reshape(n_boot, -1)[:, :n]
    ratios = abs_err_x[idx].mean(axis=1) / abs_err_n[idx].mean(axis=1)
    lo, hi = np.quantile(ratios, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return {"ci_level": ci, "lower": float(lo), "upper": float(hi), "block_length": int(L), "n_boot": int(n_boot),
            "prob_ratio_below_1": float(np.mean(ratios < 1.0))}


# --------------------------------------------------------------------------- #
# Intervalles prédictifs (conformal split)
# --------------------------------------------------------------------------- #
def conformal_quantile(scores: np.ndarray, level: float) -> float:
    n = len(scores)
    k = min(int(np.ceil((n + 1) * level)), n)
    return float(np.sort(scores)[k - 1])


def calibrate_interval(ret_true: np.ndarray, ret_pred: np.ndarray, sigma: np.ndarray, level: float) -> dict:
    res = np.abs(ret_true - ret_pred)
    floor = float(np.nanquantile(sigma, cfg.SIGMA_FLOOR_QUANTILE))
    return {"n_calibration": int(len(res)), "level_nominal": level, "q_abs": conformal_quantile(res, level),
            "sigma_floor": floor, "q_norm": conformal_quantile(res / np.maximum(sigma, floor), level)}


def interval_half_width(sigma: np.ndarray | float, calib: dict, method: str) -> np.ndarray | float:
    if method == "conformal_absolute":
        return calib["q_abs"] + 0.0 * np.asarray(sigma)
    if method == "conformal_normalized":
        return calib["q_norm"] * np.maximum(sigma, calib["sigma_floor"])
    raise ValueError(method)


def coverage_and_width(df: pd.DataFrame, model: str, calib: dict, method: str) -> dict:
    rcol = MODELS[model][1]
    pr, sig = df[rcol].to_numpy(), df["sigma_h"].to_numpy()
    hw = interval_half_width(sig, calib, method)
    lo, up = pr - hw, pr + hw
    ra = df["actual_return"].to_numpy()
    v0 = df["value_origin"].to_numpy()
    return {"empirical_coverage": float(np.mean((ra >= lo) & (ra <= up))),
            "mean_width_cdf": float(np.mean(v0 * (up - lo))), "n": int(len(df))}


# --------------------------------------------------------------------------- #
# Évaluation d'un horizon
# --------------------------------------------------------------------------- #
def evaluate_horizon(r: dict) -> dict:
    h, wf, ho = r["h"], r["walk_forward"], r["holdout"]

    # Walk-forward : par pli + poolé
    folds = []
    for k, g in wf.groupby("fold"):
        m = all_models_metrics(g)
        folds.append({"fold": int(k), "validation_start": g["origin_date"].iloc[0], "validation_end": g["target_date"].iloc[-1],
                      "train_start": g["train_start"].iloc[0], "train_end": g["train_end"].iloc[0], "train_size": int(g["train_size"].iloc[0]),
                      "n": int(len(g)), "mae_xgboost": m["xgboost"]["mae"], "mae_naive": m["naive"]["mae"],
                      "score_relatif": m["xgboost"]["mae_ratio_vs_naive"]})
    wf_pooled = all_models_metrics(wf)
    fold_scores = np.array([f["score_relatif"] for f in folds])

    # Test final
    ho_m = all_models_metrics(ho)
    ex = (ho["pred_value_xgboost"] - ho["actual_value"]).to_numpy()
    en = (ho["pred_value_naive"] - ho["actual_value"]).to_numpy()
    dm_abs = diebold_mariano(ex, en, h, power=1)
    dm_sq = diebold_mariano(ex, en, h, power=2)
    boot = block_bootstrap_ratio(np.abs(ex), np.abs(en), block=max(h, 10), n_boot=cfg.BOOTSTRAP_N,
                                 ci=cfg.BOOTSTRAP_CI, seed=cfg.RANDOM_STATE + h)

    # Intervalles : calibrage sur walk-forward (dev), vérification sur test final
    calib_dev = {}
    interval_check = {}
    for model in ("xgboost", "naive"):
        rcol = MODELS[model][1]
        calib_dev[model] = calibrate_interval(wf["actual_return"].to_numpy(), wf[rcol].to_numpy(), wf["sigma_h"].to_numpy(), cfg.INTERVAL_LEVEL)
        interval_check[model] = {meth: coverage_and_width(ho, model, calib_dev[model], meth)
                                 for meth in ("conformal_normalized", "conformal_absolute")}
    # Calibrage de déploiement : toutes les erreurs hors échantillon (walk-forward + test final)
    both = pd.concat([wf, ho], ignore_index=True)
    calib_deploy = {m: calibrate_interval(both["actual_return"].to_numpy(), both[MODELS[m][1]].to_numpy(),
                                          both["sigma_h"].to_numpy(), cfg.INTERVAL_LEVEL) for m in ("xgboost", "naive")}

    # Décision de sélection (règle fixée à l'avance dans config.py)
    s_test, s_wf = ho_m["xgboost"]["mae_ratio_vs_naive"], float(fold_scores.mean())
    significant = dm_abs["p_value_xgb_better_one_sided"] < cfg.DM_ALPHA
    better = (s_test < 1.0) and (s_wf < 1.0) and (significant or not cfg.REQUIRE_SIGNIFICANCE)
    selected = "xgboost" if better else "naive"
    if s_test < 1 and s_wf < 1:
        verdict = ("Amélioration par rapport à la naïve, statistiquement significative." if significant
                   else "Amélioration par rapport à la naïve, mais NON significative statistiquement.")
    elif s_test < 1 or s_wf < 1:
        verdict = "Résultats contradictoires (walk-forward et test final divergent) : pas d'amélioration démontrée."
    else:
        verdict = "XGBoost n'apporte pas d'amélioration par rapport à la prévision naïve."
    if selected == "naive":
        verdict += " Le modèle déployé pour cet horizon est la prévision naïve."

    return {
        "horizon_observations": h,
        "feature_set": r["feature_set"],
        "best_hyperparameters": r["best_params"],
        "samples": {"n_development": r["n_dev"], "n_test": r["n_test"], "n_all_labeled": r["n_all_labeled"],
                    "development_period": [str(r["dev_period"][0].date()), str(r["dev_period"][1].date())],
                    "test_period": [str(r["test_period"][0].date()), str(r["test_period"][1].date())]},
        "walk_forward": {"folds": folds, "score_relatif_mean": s_wf, "score_relatif_std": float(fold_scores.std()),
                         "n_folds_better_than_naive": int((fold_scores < 1).sum()), "pooled": wf_pooled},
        "holdout": {"models": ho_m, "score_relatif": s_test,
                    "score_relatif_rmse": ho_m["xgboost"]["rmse_ratio_vs_naive"],
                    "diebold_mariano_mae": dm_abs, "diebold_mariano_mse": dm_sq,
                    "bootstrap_mae_ratio": boot},
        "intervals": {"nominal_level": cfg.INTERVAL_LEVEL, "method_deployed": cfg.INTERVAL_METHOD,
                      "coverage_on_holdout_calibrated_on_walk_forward": interval_check,
                      "calibration_deploy": calib_deploy},
        "selection": {"selected_model": selected, "verdict": verdict, "statistically_significant": bool(significant),
                      "rule": ("xgboost si score_relatif<1 en walk-forward ET en test final"
                               + (" ET Diebold-Mariano significatif" if cfg.REQUIRE_SIGNIFICANCE else ""))},
    }


# --------------------------------------------------------------------------- #
# Importance des variables
# --------------------------------------------------------------------------- #
def _gain(model, names: list[str]) -> np.ndarray:
    sc = model.get_booster().get_score(importance_type="gain")
    g = np.array([sc.get(n, 0.0) for n in names], dtype=float)
    return g / g.sum() if g.sum() > 0 else g


def permutation_importance_mae(model, X: pd.DataFrame, y: pd.Series, v0: np.ndarray, seed: int) -> pd.DataFrame:
    """
    Hausse de MAE (niveau, CDF) quand on permute UNE variable du jeu de TEST.
    Ce mélange porte sur les valeurs d'une colonne pour mesurer son utilité ; il ne
    crée aucune séparation train/test aléatoire.
    """
    rng = np.random.default_rng(seed)
    def mae(Xe):
        return float(np.mean(np.abs(v0 * (model.predict(Xe) / cfg.TARGET_SCALE - y.to_numpy()))))
    base = mae(X)
    rows = []
    for c in X.columns:
        deltas = []
        for _ in range(cfg.PERMUTATION_REPEATS):
            Xp = X.copy()
            Xp[c] = rng.permutation(Xp[c].to_numpy())
            deltas.append(mae(Xp) - base)
        rows.append({"feature": c, "perm_importance_mae_cdf": float(np.mean(deltas)), "perm_importance_std": float(np.std(deltas))})
    return pd.DataFrame(rows)


def feature_importance_table(results: dict) -> pd.DataFrame:
    frames = []
    for h, r in results.items():
        names = r["feature_names"]
        perm = permutation_importance_mae(r["model_dev"], r["X_test"], r["y_test"], r["meta_test"]["value"].to_numpy(), cfg.RANDOM_STATE + h)
        t = pd.DataFrame({"horizon": h, "feature": names,
                          "gain_importance_dev_model": _gain(r["model_dev"], names),
                          "gain_importance_final_model": _gain(r["model_final"], names)})
        t = t.merge(perm, on="feature")
        t["perm_rank"] = t["perm_importance_mae_cdf"].rank(ascending=False, method="min").astype(int)
        frames.append(t.sort_values("gain_importance_dev_model", ascending=False))
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- #
# Tables et rapports
# --------------------------------------------------------------------------- #
def metrics_csv(ev: dict) -> pd.DataFrame:
    rows = []
    for hk, e in ev.items():
        for split, blocks in (("holdout", e["holdout"]["models"]), ("walk_forward_pooled", e["walk_forward"]["pooled"])):
            for model, m in blocks.items():
                rows.append({"horizon": e["horizon_observations"], "split": split, "model": model, **m})
    return pd.DataFrame(rows)


def compact_metrics(e: dict) -> dict:
    """Version courte pour data/model.json."""
    m = e["holdout"]["models"]
    return {
        "evaluation": "test final hors échantillon (dernière portion chronologique)",
        "test_period": e["samples"]["test_period"], "n_test": e["samples"]["n_test"],
        "mae_xgboost": m["xgboost"]["mae"], "mae_naive": m["naive"]["mae"],
        "rmse_xgboost": m["xgboost"]["rmse"], "rmse_naive": m["naive"]["rmse"],
        "smape_pct_xgboost": m["xgboost"]["smape_pct"], "smape_pct_naive": m["naive"]["smape_pct"],
        "bias_xgboost": m["xgboost"]["bias"], "bias_naive": m["naive"]["bias"],
        "r2_oos_vs_naive": m["xgboost"]["r2_oos_vs_naive"],
        "score_relatif": e["holdout"]["score_relatif"],
        "score_relatif_walk_forward_mean": e["walk_forward"]["score_relatif_mean"],
        "diebold_mariano_p_one_sided": e["holdout"]["diebold_mariano_mae"]["p_value_xgb_better_one_sided"],
        "bootstrap_ratio_ci": [e["holdout"]["bootstrap_mae_ratio"]["lower"], e["holdout"]["bootstrap_mae_ratio"]["upper"]],
        "interval_empirical_coverage_holdout": e["intervals"]["coverage_on_holdout_calibrated_on_walk_forward"][e["selection"]["selected_model"]][cfg.INTERVAL_METHOD]["empirical_coverage"],
        "verdict": e["selection"]["verdict"],
    }


def write_reports(results: dict, ev: dict, fi: pd.DataFrame, data_report: dict) -> None:
    cfg.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": cfg.TARGET_NAME, "model": "XGBoost",
        "protocol": {
            "horizons_unit": "observations (pas des jours calendaires)",
            "target": "return_h = value[t+h]/value[t]-1 (prévision directe, un modèle par horizon)",
            "split": f"chronologique ; test final = dernières {cfg.TEST_FRACTION:.0%} des observations utilisables",
            "walk_forward": f"fenêtre extensible, {cfg.WF_N_SPLITS} plis de {cfg.WF_TEST_SIZE} obs., gap=h",
            "hyperparameter_search": f"{cfg.N_ITER_SEARCH}+1 candidats aléatoires, critère = MAE_xgb/MAE_naive moyen en walk-forward, pool de développement seulement",
            "baselines": {"naive": "value[t+h] = value[t]", "drift": f"tendance des {cfg.DRIFT_WINDOW} dernières observations prolongée"},
            "random_shuffle_used": False,
        },
        "data": {k: data_report[k] for k in ("n_rows_input", "n_rows_clean", "n_rows_excluded", "date_min", "date_max")},
        "horizons": ev,
    }
    (cfg.REPORTS_DIR / "metrics.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    metrics_csv(ev).to_csv(cfg.REPORTS_DIR / "metrics.csv", index=False)
    pd.concat([pd.concat([r["walk_forward"], r["holdout"]], ignore_index=True) for r in results.values()], ignore_index=True)\
        .to_csv(cfg.REPORTS_DIR / "validation_predictions.csv", index=False)
    fi.to_csv(cfg.REPORTS_DIR / "feature_importance.csv", index=False)
    pd.concat([r["search"].assign(horizon=h) for h, r in results.items()], ignore_index=True)\
        .to_csv(cfg.REPORTS_DIR / "hyperparameter_search.csv", index=False)


# --------------------------------------------------------------------------- #
# Graphiques
# --------------------------------------------------------------------------- #
def make_figures(results: dict, ev: dict, fi: pd.DataFrame, series: pd.DataFrame, excluded_dates: list[str], t0_date) -> None:
    cfg.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3})

    # 0) série + anomalies + début du test
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(series["date"], series["value"], lw=1, label="USD/CDF (série utilisée)")
    ax.axvline(t0_date, color="crimson", ls="--", label="début du test final")
    for i, d in enumerate(excluded_dates):
        ax.axvline(pd.Timestamp(d), color="orange", alpha=0.5, lw=0.8, label="obs. exclue (erreur de données)" if i == 0 else None)
    ax.set_title("Série USD/CDF, test final et observations exclues"); ax.legend(); fig.tight_layout()
    fig.savefig(cfg.FIGURES_DIR / "series_overview.png"); plt.close(fig)

    for h, r in results.items():
        ho = r["holdout"]; d = pd.to_datetime(ho["target_date"])
        # 1) prédictions vs réel (test final)
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(d, ho["actual_value"], color="black", lw=1.2, label="réel")
        ax.plot(d, ho["pred_value_xgboost"], lw=1, label="XGBoost")
        ax.plot(d, ho["pred_value_naive"], lw=1, ls="--", label="naïve")
        ax.set_title(f"h={h} : prévisions vs réel — test final (date cible)"); ax.set_ylabel("CDF pour 1 USD"); ax.legend(); fig.tight_layout()
        fig.savefig(cfg.FIGURES_DIR / f"pred_vs_actual_h{h}.png"); plt.close(fig)

        # 2) erreurs
        ex = ho["pred_value_xgboost"] - ho["actual_value"]; en = ho["pred_value_naive"] - ho["actual_value"]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        axes[0].plot(d, ex, lw=0.9, label="erreur XGBoost"); axes[0].plot(d, en, lw=0.9, label="erreur naïve", alpha=0.7)
        axes[0].axhline(0, color="black", lw=0.6); axes[0].set_title(f"h={h} : erreurs (prévu − réel)"); axes[0].legend()
        axes[1].plot(d, np.cumsum(np.abs(en) - np.abs(ex)), color="green")
        axes[1].axhline(0, color="black", lw=0.6)
        axes[1].set_title("Gain cumulé |err naïve| − |err XGB|  (>0 : XGB meilleur)")
        fig.tight_layout(); fig.savefig(cfg.FIGURES_DIR / f"errors_h{h}.png"); plt.close(fig)

        # 3) score relatif par pli
        folds = ev[f"h{h}"]["walk_forward"]["folds"]
        fig, ax = plt.subplots(figsize=(6, 3.6))
        labels = [f"pli {f['fold']}" for f in folds] + ["test final"]
        vals = [f["score_relatif"] for f in folds] + [ev[f"h{h}"]["holdout"]["score_relatif"]]
        ax.bar(labels, vals, color=["#4c72b0"] * len(folds) + ["#c44e52"]); ax.axhline(1, color="black", ls="--")
        ax.set_title(f"h={h} : score relatif MAE_xgb/MAE_naïve (<1 = mieux)"); fig.tight_layout()
        fig.savefig(cfg.FIGURES_DIR / f"relative_score_h{h}.png"); plt.close(fig)

    # 4) comparaison naïve vs XGBoost (MAE test final, 3 horizons)
    fig, ax = plt.subplots(figsize=(7, 4))
    hs = list(results.keys()); x = np.arange(len(hs)); w = 0.27
    for j, m in enumerate(("naive", "xgboost", "drift")):
        ax.bar(x + (j - 1) * w, [ev[f"h{h}"]["holdout"]["models"][m]["mae"] for h in hs], w, label=m)
    ax.set_xticks(x); ax.set_xticklabels([f"h={h}" for h in hs]); ax.set_ylabel("MAE (CDF)")
    ax.set_title("MAE sur le test final : naïve vs XGBoost vs dérive"); ax.legend(); fig.tight_layout()
    fig.savefig(cfg.FIGURES_DIR / "comparison_naive_vs_xgboost.png"); plt.close(fig)

    # 5) importances
    fig, axes = plt.subplots(len(hs), 2, figsize=(11, 3.2 * len(hs)))
    axes = np.atleast_2d(axes)
    for i, h in enumerate(hs):
        t = fi[fi["horizon"] == h]
        a = t.nlargest(12, "gain_importance_dev_model").iloc[::-1]
        axes[i, 0].barh(a["feature"], a["gain_importance_dev_model"]); axes[i, 0].set_title(f"h={h} : importance (gain XGBoost)")
        b = t.nlargest(12, "perm_importance_mae_cdf").iloc[::-1]
        axes[i, 1].barh(b["feature"], b["perm_importance_mae_cdf"], xerr=b["perm_importance_std"])
        axes[i, 1].set_title(f"h={h} : permutation (Δ MAE CDF, test)")
    fig.tight_layout(); fig.savefig(cfg.FIGURES_DIR / "feature_importance.png"); plt.close(fig)
