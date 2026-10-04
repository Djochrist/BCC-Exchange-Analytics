from __future__ import annotations

import numpy as np
import pandas as pd

from .strategies import add_signal


def target_return(df: pd.DataFrame, horizon: int) -> pd.Series:
    return df["value"].shift(-horizon) / df["value"] - 1


def fit_signal_expectation(train: pd.DataFrame, signal: pd.Series, horizon: int) -> dict[int, float]:
    y = target_return(train, horizon)
    d = pd.DataFrame({"signal": signal, "y": y}).dropna()
    out: dict[int, float] = {}
    for s in (-1, 0, 1):
        vals = d.loc[d["signal"] == s, "y"]
        if len(vals) >= 20:
            out[s] = float(vals.median())
        elif len(vals) > 0:
            out[s] = float(vals.mean())
        else:
            out[s] = 0.0
    # Ne pas laisser l'estimation conditionnelle devenir extrême sur un petit historique.
    cap = float(d["y"].abs().quantile(0.90)) if len(d) else 0.0
    cap = max(cap, 1e-6)
    for s in out:
        out[s] = float(np.clip(out[s], -cap, cap))
    return out


def predict_from_signal(df_eval: pd.DataFrame, signal: pd.Series, expected: dict[int, float]) -> np.ndarray:
    return np.array([expected.get(int(s), 0.0) for s in signal], dtype=float)


def directional_accuracy(y: np.ndarray, pred: np.ndarray) -> float:
    ysign = np.sign(y)
    psign = np.sign(pred)
    # Un signal neutre n'est pas compté comme correct par défaut.
    mask = psign != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(ysign[mask] == psign[mask]))


def metrics(v0: np.ndarray, y: np.ndarray, pred_ret: np.ndarray, signal: np.ndarray) -> dict:
    actual = v0 * (1 + y)
    pred = v0 * (1 + pred_ret)
    naive = v0
    mae = float(np.mean(np.abs(pred - actual)))
    mae_naive = float(np.mean(np.abs(naive - actual)))
    rmse = float(np.sqrt(np.mean((pred - actual) ** 2)))
    rmse_naive = float(np.sqrt(np.mean((naive - actual) ** 2)))
    da = directional_accuracy(y, pred_ret)
    coverage = float(np.mean(signal != 0))
    return {
        "mae": mae,
        "mae_naive": mae_naive,
        "mae_ratio": mae / mae_naive if mae_naive > 0 else float("inf"),
        "rmse": rmse,
        "rmse_naive": rmse_naive,
        "rmse_ratio": rmse / rmse_naive if rmse_naive > 0 else float("inf"),
        "directional_accuracy": da,
        "signal_coverage": coverage,
        "n": int(len(y)),
    }


def walk_forward_evaluate(df: pd.DataFrame, horizon: int, strategy: str, params: dict, folds: list[tuple[int,int,int,int]]) -> tuple[pd.DataFrame, dict]:
    all_rows = []
    for fold, (tr0, tr1, va0, va1) in enumerate(folds, start=1):
        train = df.iloc[tr0:tr1].copy()
        valid = df.iloc[va0:va1].copy()
        s_train = add_signal(train, strategy, params)
        expected = fit_signal_expectation(train, s_train, horizon)
        s_valid = add_signal(valid, strategy, params)
        pred_ret = predict_from_signal(valid, s_valid, expected)
        y = target_return(valid, horizon).to_numpy()
        # Retirer les dernières origines sans cible.
        mask = np.isfinite(y)
        y = y[mask]
        v0 = valid["value"].to_numpy()[mask]
        s = s_valid.to_numpy()[mask]
        pr = pred_ret[mask]
        m = metrics(v0, y, pr, s)
        m.update({"fold": fold, "train_end": train["date"].iloc[-1].strftime("%Y-%m-%d"), "valid_start": valid["date"].iloc[0].strftime("%Y-%m-%d"), "valid_end": valid["date"].iloc[-1].strftime("%Y-%m-%d")})
        all_rows.append(m)
    f = pd.DataFrame(all_rows)
    summary = {
        "mae_ratio_mean": float(f["mae_ratio"].mean()),
        "mae_ratio_median": float(f["mae_ratio"].median()),
        "directional_accuracy_mean": float(f["directional_accuracy"].mean()),
        "signal_coverage_mean": float(f["signal_coverage"].mean()),
    }
    return f, summary


def holdout_evaluate(df: pd.DataFrame, horizon: int, strategy: str, params: dict, dev_end: int) -> tuple[pd.DataFrame, dict, dict[int,float]]:
    train = df.iloc[:dev_end].copy()
    test = df.iloc[dev_end:].copy()
    s_train = add_signal(train, strategy, params)
    expected = fit_signal_expectation(train, s_train, horizon)
    s_test = add_signal(test, strategy, params)
    pred_ret = predict_from_signal(test, s_test, expected)
    y = target_return(test, horizon).to_numpy()
    mask = np.isfinite(y)
    meta = test.loc[mask, ["date", "value"]].copy().reset_index(drop=True)
    v0 = meta["value"].to_numpy()
    yy = y[mask]
    ss = s_test.to_numpy()[mask]
    pp = pred_ret[mask]
    m = metrics(v0, yy, pp, ss)
    out = meta.copy()
    out["actual_value"] = v0 * (1 + yy)
    out["pred_value"] = v0 * (1 + pp)
    out["actual_return"] = yy
    out["pred_return"] = pp
    out["signal"] = ss.astype(int)
    return out, m, expected
