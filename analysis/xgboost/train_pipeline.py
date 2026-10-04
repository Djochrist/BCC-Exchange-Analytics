#!/usr/bin/env python3
"""
Pipeline complet USD/CDF  ->  XGBoost direct (h=5, 10, 20)  ->  data/model.json

    python train_pipeline.py

Options utiles :
    --input export_bcc.csv     autre fichier (CSV/JSON) ; --date-column / --value-column si besoin
    --quick                    recherche d'hyperparamètres réduite (test rapide du code)
    --n-iter 50                nombre de candidats aléatoires par horizon
    --ablation                 compare aussi les variables « niveaux bruts » (sans écraser les sorties)
"""
from __future__ import annotations

import argparse
import json
import logging
import time

import pandas as pd

from ml import config as cfg
from ml import features as F
from ml.evaluate import (compact_metrics, evaluate_horizon, feature_importance_table, make_figures, write_reports)
from ml.predict import build_model_json
from ml.prepare_data import prepare
from ml.train_xgboost import save_models, test_start_row, train_all


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=None)
    ap.add_argument("--date-column", default=None)
    ap.add_argument("--value-column", default=None)
    ap.add_argument("--n-iter", type=int, default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    t_global = time.time()
    n_iter = 4 if a.quick else (a.n_iter or cfg.N_ITER_SEARCH)
    verbose = not a.quiet

    # 1-2) chargement + nettoyage ------------------------------------------------------------ #
    print("[1/8] Chargement et contrôle qualité")
    series, rep = prepare(a.input, a.date_column, a.value_column, save=True)
    print(f"      {rep['n_rows_input']} lignes lues -> {rep['n_rows_clean']} conservées, {rep['n_rows_excluded']} exclues "
          f"({rep['date_min']} → {rep['date_max']})")
    for f in rep["anomaly_detection"]["flagged"]:
        print(f"      exclue (excursion réversible) : {f['date']}  {f['value']}")
    print(f"      espacement : écarts de jours {rep['spacing']['gap_days_distribution']} | modifiées: 0 | interpolées: 0")

    # 3-4) variables + jeux h5/h10/h20 ------------------------------------------------------- #
    print("[2/8] Construction des variables (passé strict)")
    catalog = F.build_feature_catalog(series)
    t0_row = test_start_row(catalog, cfg.FEATURE_SET)
    t0_date = catalog["date"].iloc[t0_row]

    # 5-9) validation temporelle, recherche d'hyperparamètres, entraînement ------------------- #
    print(f"[3/8] Walk-forward + recherche d'hyperparamètres ({n_iter}+1 candidats par horizon)")
    results = train_all(catalog, cfg.FEATURE_SET, n_iter, verbose)

    print("[4/8] Évaluation vs baseline naïve (test final hors échantillon)")
    ev = {f"h{h}": evaluate_horizon(r) for h, r in results.items()}

    print("[5/8] Importance des variables (gain + permutation)")
    fi = feature_importance_table(results)

    print("[6/8] Sauvegarde modèles et rapports")
    save_models(results)
    write_reports(results, ev, fi, rep)
    meta = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "feature_set": cfg.FEATURE_SET,
        "feature_names": results[cfg.HORIZONS[0]]["feature_names"],
        "trained_through": rep["date_max"],
        "horizons": {f"h{h}": {"selected_model": ev[f"h{h}"]["selection"]["selected_model"],
                               "best_params": r["best_params"], "interval_method": cfg.INTERVAL_METHOD,
                               "calibration": ev[f"h{h}"]["intervals"]["calibration_deploy"]}
                     for h, r in results.items()},
    }
    cfg.MODEL_META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("[7/8] Graphiques")
    make_figures(results, ev, fi, series, [f["date"] for f in rep["anomaly_detection"]["flagged"]], t0_date)

    print("[8/8] Génération de data/model.json")
    metrics_payload = json.loads((cfg.REPORTS_DIR / "metrics.json").read_text(encoding="utf-8"))
    model_json = build_model_json(series, meta, metrics_payload, rep)
    cfg.MODEL_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg.MODEL_JSON_PATH.write_text(json.dumps(model_json, indent=2, ensure_ascii=False), encoding="utf-8")

    # ablation optionnelle --------------------------------------------------------------------- #
    if a.ablation:
        print(f"[+] Ablation : variables '{cfg.ABLATION_FEATURE_SET}' (n'écrase aucune sortie principale)")
        res2 = train_all(catalog, cfg.ABLATION_FEATURE_SET, n_iter, verbose)
        rows = []
        for h, r in res2.items():
            e = evaluate_horizon(r)
            rows.append({"horizon": h, "feature_set": cfg.ABLATION_FEATURE_SET, "score_relatif_walk_forward": e["walk_forward"]["score_relatif_mean"],
                         "score_relatif_holdout": e["holdout"]["score_relatif"], "mae_xgboost": e["holdout"]["models"]["xgboost"]["mae"],
                         "mae_naive": e["holdout"]["models"]["naive"]["mae"]})
            e0 = ev[f"h{h}"]
            rows.append({"horizon": h, "feature_set": cfg.FEATURE_SET, "score_relatif_walk_forward": e0["walk_forward"]["score_relatif_mean"],
                         "score_relatif_holdout": e0["holdout"]["score_relatif"], "mae_xgboost": e0["holdout"]["models"]["xgboost"]["mae"],
                         "mae_naive": e0["holdout"]["models"]["naive"]["mae"]})
        pd.DataFrame(rows).sort_values(["horizon", "feature_set"]).to_csv(cfg.REPORTS_DIR / "ablation_feature_sets.csv", index=False)

    # résumé terminal -------------------------------------------------------------------------- #
    line = "=" * 92
    print("\n" + line)
    print(f" RÉSUMÉ — {cfg.TARGET_NAME} | test final : {t0_date.date()} → {rep['date_max']} | variables: {cfg.FEATURE_SET}")
    print(line)
    print(f" {'h':>3} | {'MAE naïve':>10} | {'MAE XGB':>9} | {'score test':>10} | {'score WF':>8} | {'DM p(1 côté)':>12} | {'IC90% ratio':>15} | modèle")
    for h in cfg.HORIZONS:
        e = ev[f"h{h}"]; m = e["holdout"]["models"]
        ci = e["holdout"]["bootstrap_mae_ratio"]
        print(f" {h:>3} | {m['naive']['mae']:>10.3f} | {m['xgboost']['mae']:>9.3f} | {e['holdout']['score_relatif']:>10.3f} | "
              f"{e['walk_forward']['score_relatif_mean']:>8.3f} | {e['holdout']['diebold_mariano_mae']['p_value_xgb_better_one_sided']:>12.3f} | "
              f"[{ci['lower']:.2f};{ci['upper']:.2f}]".ljust(0) + f" | {e['selection']['selected_model']}")
    print("-" * 92)
    for h in cfg.HORIZONS:
        e = ev[f"h{h}"]
        print(f" h={h:<2}: {e['selection']['verdict']}")
    print("-" * 92)
    print(f" Dernière observation : {model_json['last_observation']['date']}  {model_json['last_observation']['value']}")
    for k, v in model_json["forecast"].items():
        cov = model_json["interval"]["empirical_coverage_on_holdout"][k]
        print(f"   {k:>3} ≈ {v['value']:>9.2f}  [{v['lower']:.2f} ; {v['upper']:.2f}]  ({v['model_used']}, couverture empirique test: {cov:.0%} pour {cfg.INTERVAL_LEVEL:.0%} nominal)")
    print(line)
    print(f" Modèles : {cfg.MODELS_DIR} | Rapports : {cfg.REPORTS_DIR} | Site : {cfg.MODEL_JSON_PATH}")
    print(f" Durée totale : {time.time() - t_global:.0f} s")


if __name__ == "__main__":
    main()
