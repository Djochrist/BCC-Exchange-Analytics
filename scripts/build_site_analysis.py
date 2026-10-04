#!/usr/bin/env python3
"""Refresh the site's analysis snapshot without retraining the experiments."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
XGB = ROOT / "analysis" / "xgboost"
STR = ROOT / "analysis" / "strategy"
OUT = DATA / "analyses.json"

def main() -> None:
    series = json.loads((DATA / "usd-cdf.json").read_text(encoding="utf-8"))["series"]
    df = pd.DataFrame(series)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"])
    df = df.sort_values("date").reset_index(drop=True)

    from importlib.util import spec_from_file_location, module_from_spec
    ind_path = STR / "src" / "indicators.py"
    spec = spec_from_file_location("usdcdf_indicators", ind_path)
    mod = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    tech = mod.build_indicators(df[["date", "value"]].copy()).iloc[-1]

    def num(v):
        return None if pd.isna(v) else float(v)

    xgb_path = XGB / "ml" / "reports" / "metrics.json"
    xgb_model_path = XGB / "data" / "model.json"
    strat_path = STR / "data" / "reports" / "model.json"
    xgb_metrics = json.loads(xgb_path.read_text(encoding="utf-8")) if xgb_path.exists() else {}
    xgb_model = json.loads(xgb_model_path.read_text(encoding="utf-8")) if xgb_model_path.exists() else {}
    strategy_model = json.loads(strat_path.read_text(encoding="utf-8")) if strat_path.exists() else {}

    xgb_h = {}
    for h in [5, 10, 20]:
        item = xgb_metrics.get("horizons", {}).get(f"h{h}", {})
        holdout = item.get("holdout", {})
        models = holdout.get("models", {})
        wf = item.get("walk_forward", {}).get("score_relatif_mean")
        xgb_h[f"h{h}"] = {
            "walk_forward_ratio": wf,
            "test_ratio": holdout.get("score_relatif"),
            "mae_xgboost": models.get("xgboost", {}).get("mae"),
            "mae_naive": models.get("naive", {}).get("mae"),
            "rmse_xgboost": models.get("xgboost", {}).get("rmse"),
            "rmse_naive": models.get("naive", {}).get("rmse"),
            "directional_accuracy": models.get("xgboost", {}).get("directional_accuracy"),
            "selected_model": item.get("selection", {}).get("selected_model", "naive"),
            "verdict": item.get("selection", {}).get("verdict"),
            "test_period": holdout.get("period"),
        }

    strategy_h = {}
    sm = strategy_model.get("strategies", {})
    summary_rows = []
    summary_path = STR / "data" / "reports" / "summary.csv"
    if summary_path.exists():
        summary_rows = pd.read_csv(summary_path).to_dict("records")
    for h in [5, 10, 20]:
        row = sm.get(f"h{h}", {})
        sr = next((r for r in summary_rows if int(r.get("horizon", 0)) == h), {})
        strategy_h[f"h{h}"] = {
            "strategy": row.get("strategy"),
            "params": row.get("params"),
            "wf_ratio": sr.get("wf_mae_ratio"),
            "test_ratio": row.get("holdout", {}).get("mae_ratio", sr.get("holdout_mae_ratio")),
            "directional_accuracy": row.get("holdout", {}).get("directional_accuracy", sr.get("holdout_directional_accuracy")),
            "signal_coverage": row.get("holdout", {}).get("signal_coverage", sr.get("holdout_signal_coverage")),
            "selected_model": row.get("selected_model", sr.get("selected_model", "naive")),
        }

    generated_xgb = xgb_metrics.get("generated_at") or xgb_model.get("generated_at")
    generated_str = strategy_model.get("generated_at")
    def age_obs(model_last):
        if not model_last:
            return None
        try:
            return max(0, len(df) - int(df.index[df["date"] == pd.to_datetime(model_last)].tolist()[0]) - 1)
        except Exception:
            return None

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "current_series": {
            "source": "Banque Centrale du Congo",
            "observations": len(df),
            "start": df.iloc[0]["date"].strftime("%Y-%m-%d"),
            "last_observation": {"date": df.iloc[-1]["date"].strftime("%Y-%m-%d"), "value": num(df.iloc[-1]["value"])}
        },
        "technical_snapshot": {
            "ema_20": num(tech.get("ema_20")),
            "ema_50": num(tech.get("ema_50")),
            "ema_gap_20_50": num(tech.get("ema_gap_20_50")),
            "rsi_14": num(tech.get("rsi_14")),
            "momentum_10_pct": num(tech.get("ret_10") * 100 if "ret_10" in tech else None),
            "momentum_20_pct": num(tech.get("ret_20") * 100 if "ret_20" in tech else None),
            "macd": num(tech.get("macd")),
            "macd_hist": num(tech.get("macd_hist")),
            "volatility_20_pct": num(tech.get("vol_20") * 100 if "vol_20" in tech else None),
            "range_position_20": num(tech.get("range_pos_20")),
            "ema_signal": int(tech.get("ema_signal", 0)) if pd.notna(tech.get("ema_signal", 0)) else 0,
        },
        "xgboost": {
            "generated_at": generated_xgb,
            "trained_through": xgb_metrics.get("data", {}).get("date_max"),
            "new_observations_since_training": age_obs(xgb_metrics.get("data", {}).get("date_max")),
            "last_observation": xgb_model.get("last_observation"),
            "selected_model": {k: v.get("selected_model", "naive") for k, v in xgb_h.items()},
            "metrics": xgb_h,
            "features_top": {},
        },
        "strategy": {
            "generated_at": generated_str,
            "trained_through": strategy_model.get("last_observation", {}).get("date"),
            "new_observations_since_training": age_obs(strategy_model.get("last_observation", {}).get("date")),
            "summary": strategy_h,
            "forecast": strategy_model.get("forecast", {}),
        },
        "data_source": {
            "official_url": "https://www.bcc.cd/statistiques/secteur-exterieur/cours-de-change",
            "daily_page_pattern": "https://www.bcc.cd/marche-des-changes/cours-de-change/{YYYY-MM-DD}",
            "collection": "automatique via scripts/collect_bcc.py + GitHub Actions",
        },
    }
    # Restore a compact top-feature table from the existing archived report.
    fi_path = XGB / "ml" / "reports" / "feature_importance.csv"
    if fi_path.exists():
        fi = pd.read_csv(fi_path)
        for h in [5,10,20]:
            sub = fi[fi.get("horizon", h) == h] if "horizon" in fi.columns else fi
            cols = [c for c in ["feature", "perm_importance_mae_cdf", "perm_rank"] if c in sub.columns]
            if cols:
                payload["xgboost"]["features_top"][f"h{h}"] = sub.sort_values(cols[-1]).head(6)[cols].to_dict("records")

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"[DONE] synthèse analyses mise à jour: {OUT}")

if __name__ == "__main__":
    main()
