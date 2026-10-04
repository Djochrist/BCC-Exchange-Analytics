#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.indicators import build_indicators
from src.search import search
from src.backtest import holdout_evaluate
from src.report import plot_price, plot_scores, write_json

HORIZONS = [5, 10, 20]
TEST_FRACTION = 0.20
WF_SPLITS = 5
WF_TEST_SIZE = 120


def make_folds(dev_end: int, horizon: int) -> list[tuple[int,int,int,int]]:
    usable_end = dev_end - horizon
    total = WF_SPLITS * WF_TEST_SIZE
    if usable_end <= total + 100:
        raise ValueError("Pas assez d'observations pour le walk-forward.")
    first_test_start = usable_end - total
    folds = []
    for i in range(WF_SPLITS):
        va0 = first_test_start + i * WF_TEST_SIZE
        va1 = va0 + WF_TEST_SIZE
        tr1 = va0 - horizon
        folds.append((0, tr1, va0, va1))
    return folds


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = next((c for c in ["date", "Date", "DATE"] if c in df.columns), None)
    value_col = next((c for c in ["value", "USD/CDF", "usd_cdf", "Value"] if c in df.columns), None)
    if date_col is None or value_col is None:
        raise ValueError(f"Colonnes introuvables dans {path}: {df.columns.tolist()}")
    out = df[[date_col, value_col]].copy()
    out.columns = ["date", "value"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)
    if (out["value"] <= 0).any():
        raise ValueError("Le taux USD/CDF doit être strictement positif.")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Recherche et validation de stratégies techniques pour la série USD/CDF.")
    ap.add_argument("--input", default=str(ROOT / "data" / "series_clean.csv"))
    ap.add_argument("--candidate-limit", type=int, default=360, help="Nombre maximal de candidats, échantillonné de façon stratifiée (défaut: 360). Mettre 945 pour explorer toute la grille.")
    args = ap.parse_args()

    reports = ROOT / "data" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    plots = ROOT / "plots"
    plots.mkdir(parents=True, exist_ok=True)

    df0 = load_data(Path(args.input))
    df = build_indicators(df0)
    dev_end = int(round(len(df) * (1 - TEST_FRACTION)))
    test_start_date = df.iloc[dev_end]["date"]

    all_results = {}
    deployment = {}
    top_rows = []

    for h in HORIZONS:
        folds = make_folds(dev_end, h)
        res = search(df, h, folds, args.candidate_limit)
        res.to_csv(reports / f"strategy_search_h{h}.csv", index=False)
        all_results[h] = res

        best = res.iloc[0]
        strategy = str(best["strategy"])
        param_keys = {
            "ma": ["fast", "slow", "neutral_band"],
            "ma_rsi": ["fast", "slow", "rsi_period", "rsi_bull", "rsi_bear", "neutral_band"],
            "trend_momentum": ["fast", "slow", "mom_window", "neutral_band"],
            "combo": ["fast", "slow", "rsi_period", "mom_window", "rsi_bull", "rsi_bear", "score_threshold"],
        }[strategy]
        params = {k: (int(best[k]) if isinstance(best[k], (np.integer, int)) else float(best[k])) for k in param_keys}
        holdout_frame, hm, expected = holdout_evaluate(df, h, strategy, params, dev_end)
        holdout_frame.to_csv(reports / f"holdout_predictions_h{h}.csv", index=False)

        # Déploiement : stratégie si elle bat la naïve en walk-forward ET en holdout.
        selected = strategy if best["mae_ratio_mean"] < 1.0 and hm["mae_ratio"] < 1.0 else "naive"
        top_rows.append({
            "horizon": h,
            "strategy": strategy,
            "params": json.dumps(params, ensure_ascii=False),
            "wf_mae_ratio": float(best["mae_ratio_mean"]),
            "wf_directional_accuracy": float(best["directional_accuracy_mean"]),
            "holdout_mae_ratio": float(hm["mae_ratio"]),
            "holdout_directional_accuracy": float(hm["directional_accuracy"]),
            "holdout_signal_coverage": float(hm["signal_coverage"]),
            "selected_model": selected,
        })
        deployment[h] = {"strategy": strategy, "params": params, "expected_returns": expected, "holdout": hm, "selected_model": selected}

    summary = pd.DataFrame(top_rows)
    summary.to_csv(reports / "summary.csv", index=False)
    plot_price(df0, plots / "series_usdcdf.png")
    plot_scores(all_results, plots / "strategy_scores.png")

    # Prévision actuelle avec les paramètres sélectionnés, entraînée sur toutes les observations connues.
    latest = df.iloc[-1]
    forecasts = {}
    for h in HORIZONS:
        d = deployment[h]
        from src.strategies import generate_signal_row
        from src.backtest import fit_signal_expectation, add_signal, target_return
        s_all = add_signal(df, d["strategy"], d["params"])
        expected = fit_signal_expectation(df, s_all, h)
        signal = int(generate_signal_row(latest, d["strategy"], d["params"]))
        pred_ret = expected.get(signal, 0.0) if d["selected_model"] != "naive" else 0.0
        value = float(latest["value"] * (1 + pred_ret))
        # Intervalle robuste = quantiles des erreurs de retour observées sur tout l'historique,
        # conditionnés au même signal; ces quantiles restent descriptifs, pas une garantie.
        y_all = target_return(df, h)
        tmp = pd.DataFrame({"signal": s_all, "y": y_all}).dropna()
        vals = tmp.loc[tmp["signal"] == signal, "y"]
        if len(vals) < 30:
            vals = tmp["y"]
        lo, hi = vals.quantile([0.10, 0.90])
        forecasts[f"h{h}"] = {
            "value": value,
            "lower": float(latest["value"] * (1 + lo)),
            "upper": float(latest["value"] * (1 + hi)),
            "signal": signal,
            "strategy": d["strategy"],
            "model_used": d["selected_model"],
            "expected_return": float(pred_ret),
        }

    payload = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "model": "strategy_search_walk_forward",
        "target": "USD/CDF",
        "last_observation": {"date": latest["date"].strftime("%Y-%m-%d"), "value": float(latest["value"])},
        "test_start": test_start_date.strftime("%Y-%m-%d"),
        "selected_model": {f"h{h}": deployment[h]["selected_model"] for h in HORIZONS},
        "strategies": {f"h{h}": deployment[h] for h in HORIZONS},
        "forecast": forecasts,
        "disclaimer": "Les signaux techniques ne garantissent pas une évolution future. La sélection est validée hors échantillon et peut changer avec de nouvelles données.",
    }
    write_json(payload, reports / "model.json")

    print("=" * 96)
    print(f"USD/CDF — RECHERCHE DE STRATÉGIES | {len(df0)} observations | test final à partir du {test_start_date.date()}")
    print("=" * 96)
    print(summary.to_string(index=False))
    print("\nPrévisions actuelles:")
    for h in HORIZONS:
        f = forecasts[f"h{h}"]
        print(f"h={h}: {f['value']:.2f} [{f['lower']:.2f}; {f['upper']:.2f}] | signal={f['signal']:+d} | {f['strategy']} | utilisé={f['model_used']}")


if __name__ == "__main__":
    main()
