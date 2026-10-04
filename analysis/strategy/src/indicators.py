from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss > 0)), 0.0)
    return out


def build_indicators(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["ret_1"] = x["value"].pct_change()
    x["ret_3"] = x["value"].pct_change(3)
    x["ret_5"] = x["value"].pct_change(5)
    x["ret_10"] = x["value"].pct_change(10)
    x["ret_20"] = x["value"].pct_change(20)

    for w in [5, 10, 20, 30, 50, 100]:
        x[f"ma_{w}"] = x["value"].rolling(w).mean()
        x[f"ema_{w}"] = x["value"].ewm(span=w, adjust=False, min_periods=w).mean()
        x[f"vol_{w}"] = x["ret_1"].rolling(w).std()

    x["rsi_7"] = rsi(x["value"], 7)
    x["rsi_14"] = rsi(x["value"], 14)
    x["rsi_21"] = rsi(x["value"], 21)

    ema12 = x["value"].ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = x["value"].ewm(span=26, adjust=False, min_periods=26).mean()
    x["macd"] = ema12 - ema26
    x["macd_signal"] = x["macd"].ewm(span=9, adjust=False, min_periods=9).mean()
    x["macd_hist"] = x["macd"] - x["macd_signal"]

    x["high_10"] = x["value"].rolling(10).max()
    x["low_10"] = x["value"].rolling(10).min()
    x["high_20"] = x["value"].rolling(20).max()
    x["low_20"] = x["value"].rolling(20).min()
    x["high_30"] = x["value"].rolling(30).max()
    x["low_30"] = x["value"].rolling(30).min()
    x["range_pos_20"] = (x["value"] - x["low_20"]) / (x["high_20"] - x["low_20"]).replace(0, np.nan)

    # Données strictement disponibles à t. Les seuils absolus sont évités autant que possible.
    x["ma_gap_5_20"] = x["ma_5"] / x["ma_20"] - 1
    x["ma_gap_10_30"] = x["ma_10"] / x["ma_30"] - 1
    x["ema_gap_20_50"] = x["ema_20"] / x["ema_50"] - 1
    x["ema_slope_20"] = x["ema_20"].pct_change(5)
    x["vol_ratio_10_30"] = x["vol_10"] / x["vol_30"].replace(0, np.nan)
    return x


def feature_vector(row: pd.Series, fast: int, slow: int, rsi_period: int) -> dict[str, float]:
    return {
        "trend": float(row[f"ema_{fast}"] / row[f"ema_{slow}"] - 1),
        "momentum_10": float(row["ret_10"]),
        "momentum_20": float(row["ret_20"]),
        "rsi": float(row[f"rsi_{rsi_period}"]),
        "macd_norm": float(row["macd"] / row["value"]),
        "macd_hist_norm": float(row["macd_hist"] / row["value"]),
        "range_pos": float(row["range_pos_20"]),
        "vol": float(row["vol_20"]),
    }
