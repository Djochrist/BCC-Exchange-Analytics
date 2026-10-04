from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import walk_forward_evaluate


@dataclass(frozen=True)
class Candidate:
    strategy: str
    params: dict


def candidates() -> list[Candidate]:
    out = []
    fasts = [5, 10, 20]
    slows = [30, 50, 100]
    for fast, slow in itertools.product(fasts, slows):
        if fast >= slow:
            continue
        for band in [0.001, 0.003, 0.005]:
            out.append(Candidate("ma", {"fast": fast, "slow": slow, "neutral_band": band}))
    for fast, slow, rp, rb, rs, band in itertools.product(
        [5, 10, 20], [30, 50, 100], [7, 14, 21], [55, 60], [45, 40], [0.001, 0.003]
    ):
        if fast >= slow:
            continue
        out.append(Candidate("ma_rsi", {"fast": fast, "slow": slow, "rsi_period": rp, "rsi_bull": rb, "rsi_bear": rs, "neutral_band": band}))
    for fast, slow, mw, band in itertools.product([5, 10, 20], [30, 50, 100], [5, 10, 20], [0.001, 0.003]):
        if fast >= slow:
            continue
        out.append(Candidate("trend_momentum", {"fast": fast, "slow": slow, "mom_window": mw, "neutral_band": band}))
    for fast, slow, rp, mw, rb, rs, st in itertools.product(
        [5, 10, 20], [30, 50, 100], [7, 14, 21], [5, 10, 20], [55, 60], [45, 40], [2, 3]
    ):
        if fast >= slow:
            continue
        out.append(Candidate("combo", {"fast": fast, "slow": slow, "rsi_period": rp, "mom_window": mw, "rsi_bull": rb, "rsi_bear": rs, "score_threshold": st}))
    return out


def composite(summary: dict) -> float:
    # Critère principal: battre la naïve sur le niveau. Secondaire: direction et couverture.
    ratio_penalty = min(max(summary["mae_ratio_mean"] - 1.0, -0.5), 1.0)
    dir_bonus = max(summary["directional_accuracy_mean"] - 0.5, -0.25)
    coverage_penalty = abs(summary["signal_coverage_mean"] - 0.6) * 0.05
    return ratio_penalty - 0.50 * dir_bonus + coverage_penalty


def search(df: pd.DataFrame, horizon: int, folds: list[tuple[int,int,int,int]], limit: int | None = None) -> pd.DataFrame:
    rows = []
    cand = candidates()
    if limit and limit < len(cand):
        # Échantillonnage stratifié et déterministe : toutes les familles restent représentées.
        groups = {}
        for c in cand:
            groups.setdefault(c.strategy, []).append(c)
        rng = np.random.default_rng(20261004 + horizon)
        per = max(1, limit // len(groups))
        chosen = []
        for name in sorted(groups):
            g = groups[name]
            k = min(per, len(g))
            idx = rng.choice(len(g), size=k, replace=False)
            chosen.extend(g[int(i)] for i in idx)
        if len(chosen) < limit:
            rest = [c for c in cand if c not in chosen]
            idx = rng.choice(len(rest), size=limit-len(chosen), replace=False)
            chosen.extend(rest[int(i)] for i in idx)
        cand = chosen
    for i, c in enumerate(cand, start=1):
        wf, s = walk_forward_evaluate(df, horizon, c.strategy, c.params, folds)
        rows.append({"candidate": i, "strategy": c.strategy, **c.params, **s, "composite": composite(s)})
    res = pd.DataFrame(rows).sort_values(["composite", "mae_ratio_mean", "directional_accuracy_mean"], ascending=[True, True, False]).reset_index(drop=True)
    return res
