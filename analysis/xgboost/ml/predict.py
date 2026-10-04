"""
Prévision à partir des modèles déjà entraînés + génération de data/model.json.

Utilisable seul (sans ré-entraîner) :
    python -m ml.predict                       # utilise l'export défini dans config.py
    python -m ml.predict --input export.csv    # nouvelle donnée BCC, mêmes modèles

Les variables sont recalculées à partir de la série et SEULEMENT à partir de
la dernière observation connue ; la prévision est donc strictement hors échantillon.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from . import config as cfg
from . import features as F
from .evaluate import interval_half_width
from .prepare_data import prepare

log = logging.getLogger(__name__)


def load_regressor(h: int):
    from xgboost import XGBRegressor
    path = cfg.MODELS_DIR / f"xgboost_h{h}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} introuvable : lancez d'abord `python train_pipeline.py`.")
    m = XGBRegressor()
    m.load_model(str(path))
    return m


def forecast_from_series(series: pd.DataFrame, meta: dict) -> dict:
    """Prévision pour chaque horizon à partir de la dernière observation de `series`."""
    fs = meta["feature_set"]
    catalog = F.build_feature_catalog(series)
    usable = F.usable_rows(catalog, fs)
    row = usable.iloc[[-1]]
    if row.index[-1] != catalog.index[-1]:
        raise RuntimeError("La dernière observation n'a pas assez d'historique pour calculer les variables.")
    X = row[meta["feature_names"]]
    v0 = float(row["value"].iloc[0])
    sigma1 = float(row["rolling_std_20"].iloc[0])
    last_date = pd.Timestamp(row["date"].iloc[0])

    out = {}
    for h in cfg.HORIZONS:
        hm = meta["horizons"][f"h{h}"]
        pred_x = float(load_regressor(h).predict(X)[0] / cfg.TARGET_SCALE)
        selected = hm["selected_model"]
        pred = pred_x if selected == "xgboost" else 0.0
        sigma_h = sigma1 * np.sqrt(h)
        hw = float(interval_half_width(sigma_h, hm["calibration"][selected], hm["interval_method"]))
        target_date = np.busday_offset(last_date.date(), h, roll="forward")
        out[f"h{h}"] = {
            "value": round(v0 * (1 + pred), 2),
            "lower": round(v0 * (1 + pred - hw), 2),
            "upper": round(v0 * (1 + pred + hw), 2),
            "horizon_observations": h,
            "expected_return_pct": round(100 * pred, 4),
            "model_used": selected,
            "approx_target_date": str(target_date),
            "alternatives": {"xgboost": round(v0 * (1 + pred_x), 2), "naive": round(v0, 2)},
        }
    return {"last_date": last_date.strftime("%Y-%m-%d"), "last_value": v0, "forecast": out}


def build_model_json(series: pd.DataFrame, meta: dict, metrics_payload: dict, data_report: dict) -> dict:
    fc = forecast_from_series(series, meta)
    hz = metrics_payload["horizons"]
    from .evaluate import compact_metrics
    n_new = int((series["date"] > pd.Timestamp(meta["trained_through"])).sum())
    cov = {f"h{h}": hz[f"h{h}"]["intervals"]["coverage_on_holdout_calibrated_on_walk_forward"]
           [meta["horizons"][f"h{h}"]["selected_model"]][cfg.INTERVAL_METHOD]["empirical_coverage"] for h in cfg.HORIZONS}
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": "XGBoost",
        "target": cfg.TARGET_NAME,
        "last_observation": {"date": fc["last_date"], "value": fc["last_value"]},
        "selected_model": {f"h{h}": meta["horizons"][f"h{h}"]["selected_model"] for h in cfg.HORIZONS},
        "metrics": {f"h{h}": compact_metrics(hz[f"h{h}"]) for h in cfg.HORIZONS},
        "forecast": {k: {kk: vv for kk, vv in v.items()} for k, v in fc["forecast"].items()},
        # --- informations complémentaires (ignorables par le site) ---
        "interval": {
            "nominal_level": cfg.INTERVAL_LEVEL,
            "method": cfg.INTERVAL_METHOD,
            "empirical_coverage_on_holdout": cov,
            "note": ("Intervalles prédictifs de type conformal split calibrés sur les erreurs hors échantillon. "
                     "Couverture NOMINALE : ce ne sont pas des probabilités exactes."),
        },
        "horizons_note": "h est un nombre d'observations (jours ouvrés BCC), pas de jours calendaires. approx_target_date ignore les jours fériés.",
        "data": {
            "source_file": data_report.get("source", {}).get("path"),
            "n_observations_used": data_report["n_rows_clean"],
            "n_observations_excluded": data_report["n_rows_excluded"],
            "period": [data_report["date_min"], data_report["date_max"]],
        },
        "model_staleness": {"trained_through": meta["trained_through"], "new_observations_since_training": n_new},
        "disclaimer": "Prévision statistique indicative ; ne constitue pas un conseil financier.",
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Génère data/model.json à partir des modèles entraînés")
    ap.add_argument("--input", default=None)
    ap.add_argument("--date-column", default=None)
    ap.add_argument("--value-column", default=None)
    a = ap.parse_args()

    for p in (cfg.MODEL_META_PATH, cfg.REPORTS_DIR / "metrics.json"):
        if not p.exists():
            raise SystemExit(f"{p} introuvable : lancez d'abord `python train_pipeline.py`.")
    meta = json.loads(cfg.MODEL_META_PATH.read_text(encoding="utf-8"))
    metrics_payload = json.loads((cfg.REPORTS_DIR / "metrics.json").read_text(encoding="utf-8"))
    series, rep = prepare(a.input, a.date_column, a.value_column, save=False)
    model_json = build_model_json(series, meta, metrics_payload, rep)
    cfg.MODEL_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg.MODEL_JSON_PATH.write_text(json.dumps(model_json, indent=2, ensure_ascii=False), encoding="utf-8")
    last = model_json["last_observation"]
    print(f"Dernière observation : {last['date']}  {last['value']}")
    for k, v in model_json["forecast"].items():
        print(f"  {k:>3} [{v['model_used']:<7}] {v['value']:>9.2f}  [{v['lower']:.2f} ; {v['upper']:.2f}]")
    print("Écrit :", cfg.MODEL_JSON_PATH)


if __name__ == "__main__":
    main()
