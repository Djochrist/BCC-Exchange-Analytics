from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_price(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(df["date"], df["value"], linewidth=1.8)
    ax.set_title("Évolution du taux USD/CDF")
    ax.set_xlabel("Date")
    ax.set_ylabel("CDF pour 1 USD")
    fig.tight_layout()
    fig.savefig(out, dpi=220)
    plt.close(fig)


def plot_scores(search_results: dict[int,pd.DataFrame], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    rows = []
    for h, r in search_results.items():
        top = r.head(10).copy()
        top["horizon"] = h
        rows.append(top[["horizon", "mae_ratio_mean", "directional_accuracy_mean"]])
    d = pd.concat(rows, ignore_index=True)
    for h, g in d.groupby("horizon"):
        g = g.sort_values("mae_ratio_mean").reset_index(drop=True)
        ax.plot(range(1, len(g) + 1), g["mae_ratio_mean"], marker="o", label=f"h={h}")
    ax.axhline(1.0, linestyle="--", linewidth=1)
    ax.set_xlabel("Rang des 10 meilleurs candidats")
    ax.set_ylabel("MAE walk-forward / MAE naïve")
    ax.set_title("Robustesse des meilleures stratégies")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=220)
    plt.close(fig)


def write_json(payload: dict, path: Path) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
