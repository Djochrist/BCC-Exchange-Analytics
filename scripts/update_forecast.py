#!/usr/bin/env python3
"""Update the USD/CDF series from official BCC daily pages and rebuild forecasts.

The public website stays static. This script is intended for GitHub Actions (or a
local cron) and writes data/usd-cdf.json + data/model.json.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "usd-cdf.json"
MODEL_PATH = ROOT / "data" / "model.json"
BCC_DAY_URL = "https://www.bcc.cd/marche-des-changes/cours-de-change/{date}"

HORIZONS = (5, 10, 20)
MAX_HORIZON = max(HORIZONS)
MODEL_NAMES = ("naive", "drift", "holt_damped", "arima_011", "arima_110", "arima_111", "blend_naive_arima110")
USER_AGENT = "USD-CDF-BCC/1.0 (+https://www.bcc.cd/)"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_day(day: date, timeout: int = 20) -> tuple[str, float] | None:
    """Fetch one BCC daily page and extract the USD mean rate."""
    url = BCC_DAY_URL.format(date=day.isoformat())
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"[BCC] {day}: unavailable ({exc})")
        return None

    # The daily BCC page exposes: USD (cours moyen) <value>.
    match = re.search(
        r"USD\s*\(cours moyen\)\s*</[^>]+>\s*([0-9][0-9\s.,]*)",
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        # Fallback for plain-text/minified HTML variants.
        match = re.search(
            r"USD\s*\(cours moyen\)\s*[^0-9]{0,100}([0-9][0-9\s.,]*)",
            re.sub(r"<[^>]+>", " ", html),
            flags=re.IGNORECASE,
        )
    if not match:
        print(f"[BCC] {day}: USD mean not found")
        return None

    raw = match.group(1).strip().replace(" ", "")
    # BCC pages may use either a comma or a dot as decimal separator.
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    if not 500 <= value <= 10000:
        print(f"[BCC] {day}: suspicious value {value}")
        return None
    return day.isoformat(), round(value, 6)


def update_series(days_back: int = 14) -> tuple[dict, int]:
    payload = load_json(DATA_PATH)
    series = list(payload.get("series", []))
    known = {item["date"]: float(item["value"]) for item in series}
    latest = max((date.fromisoformat(x) for x in known), default=date(2017, 1, 1))
    today = datetime.now(timezone.utc).date()

    # Re-check a short window so a BCC publication arriving late is picked up.
    start = max(latest + timedelta(days=1), today - timedelta(days=days_back))
    cursor = start
    added = 0
    while cursor <= today:
        result = fetch_day(cursor)
        if result:
            d, value = result
            if d not in known or not math.isclose(known[d], value, rel_tol=0, abs_tol=1e-9):
                known[d] = value
                added += 1
        cursor += timedelta(days=1)

    merged = [{"date": d, "value": known[d]} for d in sorted(known)]
    payload["series"] = merged
    payload["observations"] = len(merged)
    payload["period"] = {"start": merged[0]["date"], "end": merged[-1]["date"]}
    payload["snapshotNote"] = (
        "Série mise à jour automatiquement à partir des pages quotidiennes officielles de la "
        "Banque Centrale du Congo. Le pipeline vérifie régulièrement les nouvelles observations."
    )
    save_json(DATA_PATH, payload)
    return payload, added


def naive_forecast(y: np.ndarray, horizon: int) -> np.ndarray:
    return np.repeat(y[-1], horizon)


def drift_forecast(y: np.ndarray, horizon: int) -> np.ndarray:
    if len(y) < 2:
        return naive_forecast(y, horizon)
    slope = (y[-1] - y[0]) / (len(y) - 1)
    return y[-1] + slope * np.arange(1, horizon + 1)


def fit_model(name: str, y: np.ndarray):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if name == "naive":
            return None
        if name == "drift":
            return None
        if name == "blend_naive_arima110":
            return ARIMA(y, order=(1, 1, 0), trend=None, enforce_stationarity=False, enforce_invertibility=False).fit()
        if name == "holt_damped":
            return ExponentialSmoothing(
                y,
                trend="add",
                damped_trend=True,
                seasonal=None,
                initialization_method="estimated",
            ).fit(optimized=True)
        order = {
            "arima_011": (0, 1, 1),
            "arima_110": (1, 1, 0),
            "arima_111": (1, 1, 1),
        }[name]
        return ARIMA(y, order=order, trend=None, enforce_stationarity=False, enforce_invertibility=False).fit()


def forecast_model(name: str, y: np.ndarray, horizon: int, fitted=None) -> np.ndarray:
    if name == "naive":
        return naive_forecast(y, horizon)
    if name == "drift":
        return drift_forecast(y, horizon)
    if name == "blend_naive_arima110":
        if fitted is None:
            fitted = fit_model("arima_110", y)
        arima = np.asarray(fitted.forecast(horizon), dtype=float)
        naive = naive_forecast(y, horizon)
        return 0.25 * arima + 0.75 * naive
    if fitted is None:
        fitted = fit_model(name, y)
    return np.asarray(fitted.forecast(horizon), dtype=float)


def residual_scale(name: str, y: np.ndarray, fitted=None) -> float:
    if name in {"naive", "drift"}:
        diffs = np.diff(y)
        return float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 1.0
    if name == "blend_naive_arima110":
        if fitted is None:
            fitted = fit_model(name, y)
        try:
            arima_in = np.asarray(fitted.predict(start=1, end=len(y)-1), dtype=float)
            blend_in = 0.25 * arima_in + 0.75 * y[:-1]
            residuals = y[1:] - blend_in
        except Exception:
            residuals = np.diff(y)
        residuals = np.asarray(residuals, dtype=float)
        return float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 1.0
    if fitted is None:
        fitted = fit_model(name, y)
    residuals = np.asarray(getattr(fitted, "resid", []), dtype=float)
    residuals = residuals[np.isfinite(residuals)]
    if len(residuals) < 2:
        residuals = np.diff(y)
    return float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 1.0


def evaluate_models(y: np.ndarray) -> tuple[dict, str]:
    """Rolling-origin validation over the final part of the series.

    Scores are ratios against the naive benchmark for the user-facing horizons
    5, 10 and 20. A score below 1 means better than naive on average.
    """
    max_h = MAX_HORIZON
    min_train = max(250, min(730, len(y) - max_h - 20))
    final_origin = len(y) - max_h
    start_origin = max(min_train, final_origin - 440)
    origins = np.unique(np.linspace(start_origin, final_origin, 12, dtype=int))

    raw: dict[str, dict[str, list[float]]] = {
        name: {str(h): [] for h in HORIZONS} for name in MODEL_NAMES
    }
    failures: dict[str, int] = {name: 0 for name in MODEL_NAMES}

    for origin in origins:
        train = y[max(0, origin - 730):origin]
        actual = y[origin:origin + max_h]
        naive = naive_forecast(train, max_h)
        for h in HORIZONS:
            base = float(np.mean(np.abs(actual[:h] - naive[:h]))) or 1.0
            for name in MODEL_NAMES:
                try:
                    fitted = fit_model(name, train)
                    pred = forecast_model(name, train, h, fitted=fitted)
                    err = float(np.mean(np.abs(actual[:h] - pred[:h])))
                    raw[name][str(h)].append(err / base)
                except Exception:
                    failures[name] += 1

    results = {}
    for name in MODEL_NAMES:
        ratios = {h: (float(np.mean(raw[name][str(h)])) if raw[name][str(h)] else None) for h in HORIZONS}
        usable = [v for v in ratios.values() if v is not None and np.isfinite(v)]
        results[name] = {
            "relative_mae": {str(k): (round(v, 4) if v is not None else None) for k, v in ratios.items()},
            "score": round(float(np.mean(usable)), 4) if usable else None,
            "failed_fits": failures[name],
        }

    valid = [(name, r["score"]) for name, r in results.items() if r["score"] is not None]
    selected = min(valid, key=lambda item: item[1])[0] if valid else "naive"
    return results, selected


def build_forecast(payload: dict) -> dict:
    series = payload["series"]
    y = np.asarray([float(x["value"]) for x in series], dtype=float)
    if len(y) < 100:
        raise RuntimeError("Pas assez d'observations pour entraîner le modèle.")

    validation, selected = evaluate_models(y)
    train = y[-730:] if len(y) > 730 else y
    fitted = fit_model(selected, train)
    forecast = forecast_model(selected, train, MAX_HORIZON, fitted=fitted)
    scale = residual_scale(selected, train, fitted=fitted)

    items = []
    z80, z95 = 1.2815515655, 1.9599639845
    for h, value in enumerate(forecast, start=1):
        width = scale * math.sqrt(h)
        items.append(
            {
                "horizon": h,
                "value": round(float(value), 6),
                "lower80": round(float(value - z80 * width), 6),
                "upper80": round(float(value + z80 * width), 6),
                "lower95": round(float(value - z95 * width), 6),
                "upper95": round(float(value + z95 * width), 6),
            }
        )

    return {
        "model": selected,
        "method": {
            "naive": "Dernière valeur",
            "drift": "Dérive",
            "holt_damped": "Holt à tendance amortie",
            "arima_011": "ARIMA(0,1,1)",
            "arima_110": "ARIMA(1,1,0)",
            "arima_111": "ARIMA(1,1,1)",
            "blend_naive_arima110": "Prévision combinée",
        }[selected],
        "sample_observations": len(y),
        "train_window": len(train),
        "last_date": series[-1]["date"],
        "last_value": round(float(y[-1]), 6),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "validation": {
            "method": "rolling-origin",
            "horizons": list(HORIZONS),
            "origins": 12,
            "selection_rule": "meilleure moyenne du MAE relatif à la référence naïve",
            "models": validation,
        },
        "forecast": items,
        "note": (
            "Prévision recalculée automatiquement à partir de la dernière série disponible. "
            "La performance reste évaluée hors échantillon par validation chronologique. "
            "Une prévision ne constitue pas une garantie sur le taux futur."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fetch", action="store_true", help="ne pas interroger la BCC")
    parser.add_argument("--days-back", type=int, default=14)
    parser.add_argument("--force-model", action="store_true", help="recalculer le modèle même sans nouvelle observation")
    args = parser.parse_args()

    if args.no_fetch:
        payload = load_json(DATA_PATH)
        added = 0
    else:
        payload, added = update_series(days_back=max(7, args.days_back))

    if not args.force_model and not args.no_fetch and added == 0 and MODEL_PATH.exists():
        print("[DONE] aucune nouvelle cotation BCC; modèle conservé")
        return 0

    model = build_forecast(payload)
    save_json(MODEL_PATH, model)
    print(f"[DONE] observations={len(payload['series'])} added={added} selected={model['model']}")
    print(f"[DONE] last={model['last_date']} value={model['last_value']}")
    print(f"[DONE] score={model['validation']['models'][model['model']]['score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
