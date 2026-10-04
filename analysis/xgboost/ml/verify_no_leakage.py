"""
Vérifie PAR LE CODE que le pipeline n'utilise aucune donnée future.

    python -m ml.verify_no_leakage            # sur la série réelle (data/processed ou export)
    python -m ml.verify_no_leakage --input export.csv

Contrôles :
  1. Invariance par troncature : les variables en t calculées sur la série COMPLÈTE sont
     identiques à celles calculées sur la série COUPÉE en t (le futur n'existe pas).
  2. Invariance par perturbation : on remplace tout le futur (après t) par du bruit ;
     les variables en t ne bougent pas.
  3. Alignement de la cible : return_h[t] = value[t+h]/value[t]-1, et aucune colonne
     « cible » n'est dans les variables.
  4. Découpages : dans le pool de développement, la cible de chaque échantillon est
     connue AVANT le début du test final ; dans chaque pli walk-forward, la cible de
     chaque échantillon d'entraînement est connue AVANT la 1re origine de validation ;
     indices strictement croissants (aucun mélange).
  5. Analyse statique : aucun train_test_split / shuffle / KFold dans le code.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg
from . import features as F
from . import train_xgboost as T
from .prepare_data import prepare

TARGET_COLS = {"return_h", "target_value", "target_date"}


def _sample_positions(n: int, k: int, seed: int = 0) -> list[int]:
    rng = np.random.default_rng(seed)
    pos = set(rng.choice(np.arange(cfg.WARMUP_ROWS + 5, n), size=min(k, n - cfg.WARMUP_ROWS - 5), replace=False).tolist())
    pos.update({cfg.WARMUP_ROWS + 1, n - 1, n - 2})
    return sorted(pos)


def check_truncation_and_perturbation(series: pd.DataFrame, n_points: int = 40) -> list[tuple[str, bool, str]]:
    full = F.build_feature_catalog(series)
    feat_cols = [c for c in full.columns if c not in ("date",)]
    results = []
    bad_trunc, bad_pert = [], []
    rng = np.random.default_rng(123)
    for t in _sample_positions(len(series), n_points):
        cut = F.build_feature_catalog(series.iloc[: t + 1])
        a, b = full.iloc[t][feat_cols].astype(float), cut.iloc[t][feat_cols].astype(float)
        if not np.allclose(a.to_numpy(), b.to_numpy(), rtol=1e-9, atol=1e-12, equal_nan=True):
            bad_trunc.append(int(t))
        # perturbation : futur remplacé par du bruit multiplicatif
        fut = series.copy()
        fut.loc[fut.index > fut.index[t], "value"] *= rng.uniform(0.3, 3.0, size=len(fut) - t - 1)
        pert = F.build_feature_catalog(fut)
        c = pert.iloc[t][feat_cols].astype(float)
        if not np.allclose(a.to_numpy(), c.to_numpy(), rtol=1e-9, atol=1e-12, equal_nan=True):
            bad_pert.append(int(t))
    results.append(("Invariance par troncature (variables en t == variables sur série coupée en t)", not bad_trunc,
                    f"{len(_sample_positions(len(series), n_points))} dates testées" + (f" ; ÉCHECS aux positions {bad_trunc[:5]}" if bad_trunc else "")))
    results.append(("Invariance par perturbation du futur (variables en t inchangées si le futur est remplacé par du bruit)", not bad_pert,
                    "OK" if not bad_pert else f"ÉCHECS aux positions {bad_pert[:5]}"))
    return results


def check_targets(series: pd.DataFrame) -> list[tuple[str, bool, str]]:
    out = []
    cat = F.build_feature_catalog(series)
    for fs in ("scale_free", "levels"):
        leaked = TARGET_COLS & set(F.feature_columns(fs))
        out.append((f"Aucune colonne cible dans les variables ({fs})", not leaked, str(leaked) if leaked else "OK"))
    for h in cfg.HORIZONS:
        ds = F.build_horizon_dataset(cat, h, cfg.FEATURE_SET)
        m = ds["meta"]
        pos = m["row"].to_numpy()
        v = series["value"].to_numpy()
        exp = v[pos + h] / v[pos] - 1.0
        ok_ret = np.allclose(ds["y"].to_numpy(), exp, rtol=1e-12, atol=1e-15)
        ok_date = (m["target_date"].to_numpy() == series["date"].to_numpy()[pos + h]).all()
        out.append((f"Cible h={h} : return = value[t+{h}]/value[t]-1 et date cible = date[t+{h}]", bool(ok_ret and ok_date), "OK"))
        out.append((f"Dernière observation sans cible (réservée à la prévision réelle) h={h}", int(m['row'].max()) == len(series) - 1 - h, "OK"))
    return out


def check_splits(series: pd.DataFrame) -> list[tuple[str, bool, str]]:
    out = []
    cat = F.build_feature_catalog(series)
    t0 = T.test_start_row(cat, cfg.FEATURE_SET)
    for h in cfg.HORIZONS:
        ds = F.build_horizon_dataset(cat, h, cfg.FEATURE_SET)
        sp = T.split_dev_test(ds, h, t0)
        row = ds["meta"]["row"].to_numpy()
        dev_target_row = row[sp["dev_idx"]] + h
        ok1 = bool(dev_target_row.max() < t0 <= row[sp["test_idx"]].min())
        ok2 = bool(np.all(np.diff(sp["dev_idx"]) > 0) and np.all(np.diff(sp["test_idx"]) > 0) and sp["dev_idx"].max() < sp["test_idx"].min())
        out.append((f"h={h} : pool dev/test chronologiques, cible dev (max ligne {int(dev_target_row.max())}) < début test (ligne {t0})", ok1 and ok2, "OK"))

        dev_rows = row[sp["dev_idx"]]
        ok3, ok4, info = True, True, []
        for k, (tr, va) in enumerate(T.walk_forward_splits(len(sp["dev_idx"]), h), start=1):
            ok3 &= bool(dev_rows[tr].max() + h < dev_rows[va].min())      # cible train connue avant 1re origine de validation
            ok4 &= bool(np.all(np.diff(tr) > 0) and np.all(np.diff(va) > 0) and tr.max() < va.min())
            info.append(f"pli{k}: train≤{int(dev_rows[tr].max())}→cible≤{int(dev_rows[tr].max()) + h} < val≥{int(dev_rows[va].min())}")
        out.append((f"h={h} : walk-forward sans chevauchement de cibles (purge gap=h)", ok3, "; ".join(info)))
        out.append((f"h={h} : walk-forward chronologique (aucun mélange)", ok4, "OK"))
    return out


def check_static_code() -> list[tuple[str, bool, str]]:
    bad = []
    pat = re.compile(r"train_test_split|shuffle\s*=\s*True|\bKFold\b|\bStratifiedKFold\b|ShuffleSplit|cross_val_score\(")
    for p in Path(__file__).parent.glob("*.py"):
        if p.name == "verify_no_leakage.py":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            if pat.search(code):
                bad.append(f"{p.name}:{i}: {line.strip()}")
    return [("Analyse statique : aucun train_test_split / shuffle=True / KFold dans ml/*.py", not bad, "OK" if not bad else "; ".join(bad))]


def run_all(series: pd.DataFrame, n_points: int = 40) -> list[tuple[str, bool, str]]:
    return (check_truncation_and_perturbation(series, n_points) + check_targets(series)
            + check_splits(series) + check_static_code())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None)
    ap.add_argument("--date-column", default=None)
    ap.add_argument("--value-column", default=None)
    a = ap.parse_args()
    series, _ = prepare(a.input, a.date_column, a.value_column, save=False)
    res = run_all(series)
    print("\nVÉRIFICATION D'ABSENCE DE FUITE DE DONNÉES FUTURES\n" + "=" * 60)
    for name, ok, detail in res:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}\n       {detail}")
    n_fail = sum(not ok for _, ok, _ in res)
    print("=" * 60 + f"\n{len(res) - n_fail}/{len(res)} contrôles réussis")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
