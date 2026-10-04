from __future__ import annotations

import numpy as np
import pandas as pd


def signal_ma(row: pd.Series, fast: int, slow: int, neutral_band: float) -> int:
    gap = row[f"ema_{fast}"] / row[f"ema_{slow}"] - 1
    if gap > neutral_band:
        return 1
    if gap < -neutral_band:
        return -1
    return 0


def signal_ma_rsi(row: pd.Series, fast: int, slow: int, rsi_period: int, rsi_bull: float, rsi_bear: float, neutral_band: float) -> int:
    gap = row[f"ema_{fast}"] / row[f"ema_{slow}"] - 1
    r = row[f"rsi_{rsi_period}"]
    if not np.isfinite(gap) or not np.isfinite(r):
        return 0
    if gap > neutral_band and r >= rsi_bull:
        return 1
    if gap < -neutral_band and r <= rsi_bear:
        return -1
    return 0


def signal_trend_momentum(row: pd.Series, fast: int, slow: int, mom_window: int, neutral_band: float) -> int:
    gap = row[f"ema_{fast}"] / row[f"ema_{slow}"] - 1
    mom = row[f"ret_{mom_window}"]
    if not np.isfinite(gap) or not np.isfinite(mom):
        return 0
    if gap > neutral_band and mom > 0:
        return 1
    if gap < -neutral_band and mom < 0:
        return -1
    return 0


def signal_combo(row: pd.Series, fast: int, slow: int, rsi_period: int, mom_window: int, rsi_bull: float, rsi_bear: float, score_threshold: int) -> int:
    gap = row[f"ema_{fast}"] / row[f"ema_{slow}"] - 1
    mom = row[f"ret_{mom_window}"]
    r = row[f"rsi_{rsi_period}"]
    macd_hist = row["macd_hist"]
    values = [gap, mom, r, macd_hist]
    if not all(np.isfinite(v) for v in values):
        return 0
    score = (1 if gap > 0 else -1 if gap < 0 else 0) + (1 if mom > 0 else -1 if mom < 0 else 0)
    score += 1 if r >= rsi_bull else -1 if r <= rsi_bear else 0
    score += 1 if macd_hist > 0 else -1 if macd_hist < 0 else 0
    return 1 if score >= score_threshold else -1 if score <= -score_threshold else 0


def add_signal(df: pd.DataFrame, strategy: str, params: dict) -> pd.Series:
    # Vectorisé : indispensable pour la recherche de paramètres.
    gap = df[f"ema_{params['fast']}"] / df[f"ema_{params['slow']}"] - 1
    if strategy == "ma":
        s = np.where(gap > params["neutral_band"], 1, np.where(gap < -params["neutral_band"], -1, 0))
    elif strategy == "ma_rsi":
        r = df[f"rsi_{params['rsi_period']}"]
        s = np.where((gap > params["neutral_band"]) & (r >= params["rsi_bull"]), 1,
                     np.where((gap < -params["neutral_band"]) & (r <= params["rsi_bear"]), -1, 0))
    elif strategy == "trend_momentum":
        mom = df[f"ret_{params['mom_window']}"]
        s = np.where((gap > params["neutral_band"]) & (mom > 0), 1,
                     np.where((gap < -params["neutral_band"]) & (mom < 0), -1, 0))
    elif strategy == "combo":
        r = df[f"rsi_{params['rsi_period']}"]
        mom = df[f"ret_{params['mom_window']}"]
        score = np.zeros(len(df), dtype=int)
        score += np.where(gap > 0, 1, np.where(gap < 0, -1, 0))
        score += np.where(mom > 0, 1, np.where(mom < 0, -1, 0))
        score += np.where(r >= params["rsi_bull"], 1, np.where(r <= params["rsi_bear"], -1, 0))
        score += np.where(df["macd_hist"] > 0, 1, np.where(df["macd_hist"] < 0, -1, 0))
        s = np.where(score >= params["score_threshold"], 1, np.where(score <= -params["score_threshold"], -1, 0))
    else:
        raise ValueError(f"Stratégie inconnue: {strategy}")
    s = pd.Series(s, index=df.index, dtype=float)
    return s.where(gap.notna(), 0.0)

def generate_signal_row(row: pd.Series, strategy: str, params: dict) -> int:
    if strategy == "ma":
        return signal_ma(row, params["fast"], params["slow"], params["neutral_band"])
    if strategy == "ma_rsi":
        return signal_ma_rsi(row, params["fast"], params["slow"], params["rsi_period"], params["rsi_bull"], params["rsi_bear"], params["neutral_band"])
    if strategy == "trend_momentum":
        return signal_trend_momentum(row, params["fast"], params["slow"], params["mom_window"], params["neutral_band"])
    if strategy == "combo":
        return signal_combo(row, params["fast"], params["slow"], params["rsi_period"], params["mom_window"], params["rsi_bull"], params["rsi_bear"], params["score_threshold"])
    raise ValueError(f"Stratégie inconnue: {strategy}")
