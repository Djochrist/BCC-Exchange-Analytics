import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.indicators import build_indicators


def test_indicators_have_expected_columns():
    df = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=120), "value": range(100, 220)})
    x = build_indicators(df)
    for col in ["ema_5", "ema_50", "rsi_14", "macd", "ret_20", "range_pos_20"]:
        assert col in x.columns
