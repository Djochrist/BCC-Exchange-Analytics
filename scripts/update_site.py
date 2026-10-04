#!/usr/bin/env python3
"""Daily site refresh: collect BCC data and refresh lightweight site metadata.

Use --retrain when a full experimental re-estimation is desired. Daily updates
normally keep the archived XGBoost/strategy experiments unchanged and expose
their training date so staleness is visible rather than silently mixing periods.
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

def run(*args: str) -> None:
    print("$", " ".join(args))
    subprocess.run(list(args), cwd=ROOT, check=True)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-back", type=int, default=14)
    ap.add_argument("--retrain", action="store_true", help="réentraîner XGBoost et rechercher à nouveau les stratégies")
    ap.add_argument("--xgb-n-iter", type=int, default=30)
    ap.add_argument("--strategy-candidates", type=int, default=360)
    args = ap.parse_args()

    run(PYTHON, str(ROOT / "scripts" / "collect_bcc.py"), "--days-back", str(args.days_back))

    if args.retrain:
        xgb_dir = ROOT / "analysis" / "xgboost"
        strat_dir = ROOT / "analysis" / "strategy"
        raw = xgb_dir / "data" / "raw" / "cours-de-change-quotidien.csv"
        run(PYTHON, str(xgb_dir / "train_pipeline.py"), "--input", str(raw), "--n-iter", str(args.xgb_n_iter), "--quiet")
        run(PYTHON, str(strat_dir / "run_strategy.py"), "--input", str(strat_dir / "data" / "series_clean.csv"), "--candidate-limit", str(args.strategy_candidates))

    run(PYTHON, str(ROOT / "scripts" / "build_site_analysis.py"))
    # update_forecast produces the site's generic 20-step forecast and is cheap compared with re-training.
    run(PYTHON, str(ROOT / "scripts" / "update_forecast.py"), "--no-fetch", "--force-model")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
