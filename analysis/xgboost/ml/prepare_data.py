"""
Chargement + contrôles qualité de la série USD/CDF.

Principes :
  * AUCUNE valeur n'est inventée, interpolée ou modifiée.
  * Les observations manifestement erronées sont EXCLUES (jamais remplacées) et
    listées dans data/processed/excluded_observations.csv avec la raison.
  * Les valeurs extrêmes plausibles (vraie volatilité de marché) sont CONSERVÉES
    et seulement signalées.
  * Tout est consigné dans ml/reports/data_quality.json.

Le chargeur accepte un export BCC CSV (une ou plusieurs colonnes de devises,
BOM UTF-8, séparateur , ou ;) ou JSON, sans changer le reste du pipeline.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg

log = logging.getLogger(__name__)


class DataQualityError(RuntimeError):
    """Problème de données qu'on refuse de résoudre en « devinant »."""


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #
def _pick_column(columns: list[str], explicit: str | None, candidates: list[str], what: str) -> str:
    if explicit:
        if explicit not in columns:
            raise DataQualityError(f"Colonne {what} '{explicit}' introuvable. Colonnes: {columns[:30]}")
        return explicit
    for c in candidates:
        if c in columns:
            return c
    raise DataQualityError(
        f"Colonne {what} introuvable parmi {candidates}. Colonnes présentes: {columns[:30]}. "
        f"Utilisez --{'date' if what == 'date' else 'value'}-column."
    )


def _json_to_frame(payload) -> pd.DataFrame:
    """Accepte : [{date,value},...] | {"data":[...]} | {"2017-01-02": 1215.5, ...}."""
    if isinstance(payload, dict):
        for key in ("data", "observations", "series", "values", "rates", "items"):
            if key in payload and isinstance(payload[key], list):
                payload = payload[key]
                break
        else:
            if all(isinstance(v, (int, float, str)) for v in payload.values()):
                return pd.DataFrame({"date": list(payload.keys()), "value": list(payload.values())})
            raise DataQualityError(f"Structure JSON non reconnue. Clés: {list(payload)[:10]}")
    if not isinstance(payload, list):
        raise DataQualityError("Le JSON doit contenir une liste d'observations.")
    return pd.DataFrame(payload)


def load_raw(path: str | Path, date_column: str | None = None, value_column: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Retourne (DataFrame['date_raw','value_raw'] dans l'ORDRE DU FICHIER, infos de lecture)."""
    path = Path(path)
    if not path.exists():
        raise DataQualityError(f"Fichier introuvable : {path}")

    if path.suffix.lower() == ".json":
        df = _json_to_frame(json.loads(path.read_text(encoding="utf-8-sig")))
    else:
        # sep=None => détection automatique (, ; tab) ; utf-8-sig supprime le BOM.
        df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig", dtype=str)

    df.columns = [str(c).strip().strip("\ufeff") for c in df.columns]
    cols = list(df.columns)
    dcol = _pick_column(cols, date_column, cfg.DATE_COLUMN_CANDIDATES, "date")
    vcol = _pick_column(cols, value_column, cfg.VALUE_COLUMN_CANDIDATES, "valeur")

    other = [c for c in cfg.VALUE_COLUMN_CANDIDATES if c in cols and c != vcol]
    if other:
        log.warning("Plusieurs colonnes candidates (%s) ; utilisée: '%s'.", other, vcol)

    out = df[[dcol, vcol]].rename(columns={dcol: "date_raw", vcol: "value_raw"})
    info = {"path": str(path), "format": path.suffix.lower().lstrip("."), "date_column": dcol,
            "value_column": vcol, "n_columns_in_file": len(cols), "n_rows_in_file": int(len(df))}
    return out, info


# --------------------------------------------------------------------------- #
# Détection d'excursions réversibles (erreurs de données)
# --------------------------------------------------------------------------- #
def detect_reverting_excursions(values: np.ndarray, max_block: int, excursion: float, revert_tol: float) -> np.ndarray:
    """
    Masque booléen des observations appartenant à un bloc (1..max_block) qui :
      - s'écarte d'au moins `excursion` (relatif) de la valeur AVANT le bloc, sur chaque point ;
      - et dont la valeur APRÈS le bloc est revenue à `revert_tol` près de la valeur AVANT.
    Les premières et dernières observations ne peuvent pas être testées (pas de
    référence d'un côté) : c'est signalé dans le rapport.
    """
    n = len(values)
    flag = np.zeros(n, dtype=bool)
    for L in range(1, max_block + 1):
        for i in range(1, n - L):
            before, after = values[i - 1], values[i + L]
            if abs(after / before - 1.0) <= revert_tol and np.all(np.abs(values[i:i + L] / before - 1.0) >= excursion):
                flag[i:i + L] = True
    return flag


# --------------------------------------------------------------------------- #
# Audit + nettoyage
# --------------------------------------------------------------------------- #
def audit_and_clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Retourne (série propre [date, value], observations exclues, rapport).
    Lève DataQualityError pour les cas qu'on ne doit pas « deviner ».
    """
    rep: dict = {"n_rows_input": int(len(raw))}
    df = raw.copy()
    df["row_in_file"] = np.arange(len(df))

    # 1) dates invalides ---------------------------------------------------- #
    df["date"] = pd.to_datetime(df["date_raw"], errors="coerce", dayfirst=cfg.DATE_DAYFIRST)
    bad_date = df["date"].isna()
    rep["invalid_dates"] = int(bad_date.sum())

    # 2) valeurs manquantes / non numériques / non positives ---------------- #
    s = df["value_raw"].astype(str).str.strip().str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
    # virgule décimale uniquement si pas de point (évite de casser "1,234.5")
    s = s.where(~(s.str.contains(",") & ~s.str.contains(r"\.")), s.str.replace(",", ".", regex=False))
    df["value"] = pd.to_numeric(s.replace({"": np.nan, "nan": np.nan, "None": np.nan, "null": np.nan}), errors="coerce")
    missing_raw = df["value_raw"].isna() | s.isin(["", "nan", "None", "null"])
    non_numeric = df["value"].isna() & ~missing_raw
    non_positive = df["value"].notna() & (df["value"] <= 0)
    non_finite = df["value"].notna() & ~np.isfinite(df["value"])
    rep["missing_values"] = int(missing_raw.sum())
    rep["non_numeric_values"] = int(non_numeric.sum())
    rep["non_positive_values"] = int(non_positive.sum())
    rep["non_finite_values"] = int(non_finite.sum())

    invalid_rows = bad_date | df["value"].isna() | non_positive | non_finite
    excluded_invalid = df[invalid_rows].assign(reason=lambda x: np.select(
        [x["date"].isna(), x["value"].isna(), x["value"] <= 0], ["date_invalide", "valeur_manquante_ou_non_numerique", "valeur_non_positive"], "valeur_non_finie"))
    df = df[~invalid_rows].copy()

    # 3) doublons ----------------------------------------------------------- #
    dup_mask = df.duplicated(subset=["date"], keep=False)
    if dup_mask.any():
        grp = df[dup_mask].groupby("date")["value"].nunique()
        conflicting = grp[grp > 1]
        rep["duplicate_dates"] = int(df["date"].duplicated().sum())
        rep["conflicting_duplicate_dates"] = [d.strftime("%Y-%m-%d") for d in conflicting.index]
        if len(conflicting):
            raise DataQualityError(
                f"{len(conflicting)} date(s) en double avec des valeurs DIFFÉRENTES (ex: "
                f"{rep['conflicting_duplicate_dates'][:5]}). Je ne choisis pas à votre place : corrigez l'export BCC."
            )
        df = df.drop_duplicates(subset=["date"], keep="first")  # doublons strictement identiques
    else:
        rep["duplicate_dates"] = 0
        rep["conflicting_duplicate_dates"] = []

    # 4) ordre chronologique ------------------------------------------------ #
    rep["was_chronological_in_file"] = bool(df["date"].is_monotonic_increasing)
    if not rep["was_chronological_in_file"]:
        log.warning("Fichier non chronologique : tri par date (aucune valeur modifiée).")
    df = df.sort_values("date", kind="mergesort").reset_index(drop=True)

    # 5) espacement --------------------------------------------------------- #
    gaps = df["date"].diff().dt.days.dropna()
    rep["spacing"] = {
        "gap_days_distribution": {str(int(k)): int(v) for k, v in gaps.value_counts().sort_index().items()},
        "median_gap_days": float(gaps.median()),
        "max_gap_days": int(gaps.max()),
        "weekday_distribution": {str(int(k)): int(v) for k, v in df["date"].dt.dayofweek.value_counts().sort_index().items()},
        "has_weekend_observations": bool((df["date"].dt.dayofweek >= 5).any()),
        "gaps_over_threshold": [
            {"from": df["date"].iloc[i - 1].strftime("%Y-%m-%d"), "to": df["date"].iloc[i].strftime("%Y-%m-%d"), "days": int(g)}
            for i, g in gaps.items() if g > cfg.GAP_WARNING_DAYS
        ],
        "note": "Les horizons h sont comptés en OBSERVATIONS, pas en jours calendaires.",
    }

    # 6) excursions réversibles (erreurs de données) ------------------------ #
    vals = df["value"].to_numpy(float)
    flag = detect_reverting_excursions(vals, cfg.ANOMALY_MAX_BLOCK, cfg.ANOMALY_EXCURSION, cfg.ANOMALY_REVERT_TOL)
    anomalies = df[flag].copy()
    anomalies["reason"] = "excursion_reversible"
    rep["anomaly_detection"] = {
        "rule": (f"bloc de 1 à {cfg.ANOMALY_MAX_BLOCK} obs. écartées de ≥{cfg.ANOMALY_EXCURSION:.0%} de la valeur avant le bloc, "
                 f"avec retour à ±{cfg.ANOMALY_REVERT_TOL:.0%} de cette valeur juste après"),
        "policy": cfg.ANOMALY_POLICY,
        "n_flagged": int(flag.sum()),
        "flagged": [{"date": r.date.strftime("%Y-%m-%d"), "value": float(r.value)} for r in anomalies.itertuples()],
        "limits": "Les 1res/dernières observations ne peuvent pas être validées par ce test (pas de valeur avant/après).",
    }

    # 7) rendements extrêmes (info seulement, jamais supprimés) ------------- #
    kept_for_ret = df.loc[~flag if cfg.ANOMALY_POLICY == "exclude" else slice(None)]
    ret = kept_for_ret["value"].pct_change().dropna()
    med = ret.median()
    mad = float((ret - med).abs().median() * 1.4826)
    z = (ret - med).abs() / mad if mad > 0 else ret * 0
    extreme = kept_for_ret.loc[z[z > cfg.EXTREME_RETURN_Z].index]
    rep["extreme_returns_kept"] = {
        "threshold_robust_z": cfg.EXTREME_RETURN_Z,
        "n": int(len(extreme)),
        "by_year": {str(k): int(v) for k, v in extreme["date"].dt.year.value_counts().sort_index().items()},
        "note": "CONSERVÉS : correspondent à de vraies phases de volatilité (ex. 2023). Aucune suppression arbitraire.",
    }
    rep["repeated_consecutive_values"] = int((df["value"].diff() == 0).sum())

    # 8) application de la politique ---------------------------------------- #
    if cfg.ANOMALY_POLICY == "exclude" and flag.any():
        excluded_anom = anomalies
        clean = df[~flag].reset_index(drop=True)
    else:
        excluded_anom = anomalies.iloc[0:0]
        clean = df.reset_index(drop=True)

    excluded = pd.concat([
        excluded_invalid[["row_in_file", "date_raw", "value_raw", "reason"]],
        excluded_anom.assign(date_raw=excluded_anom["date"].dt.strftime("%Y-%m-%d"), value_raw=excluded_anom["value"].astype(str))[
            ["row_in_file", "date_raw", "value_raw", "reason"]],
    ], ignore_index=True) if (len(excluded_invalid) or len(excluded_anom)) else pd.DataFrame(
        columns=["row_in_file", "date_raw", "value_raw", "reason"])

    # 9) sanité de la dernière observation (non vérifiable par réversion) --- #
    last, prev = clean["value"].iloc[-1], clean["value"].iloc[-2]
    rep["last_observation"] = {
        "date": clean["date"].iloc[-1].strftime("%Y-%m-%d"), "value": float(last),
        "change_vs_previous": float(last / prev - 1),
        "alert": bool(abs(last / prev - 1) > cfg.LAST_OBS_ALERT),
    }
    if rep["last_observation"]["alert"]:
        log.warning("La dernière observation varie de %.1f%% : à vérifier manuellement.", 100 * (last / prev - 1))

    rep.update({
        "n_rows_clean": int(len(clean)),
        "n_rows_excluded": int(len(excluded)),
        "date_min": clean["date"].iloc[0].strftime("%Y-%m-%d"),
        "date_max": clean["date"].iloc[-1].strftime("%Y-%m-%d"),
        "value_min": float(clean["value"].min()),
        "value_max": float(clean["value"].max()),
        "modified_values": 0,
        "interpolated_values": 0,
    })
    return clean[["date", "value"]], excluded, rep


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #
def prepare(path: str | Path | None = None, date_column: str | None = None, value_column: str | None = None,
            save: bool = True) -> tuple[pd.DataFrame, dict]:
    raw, info = load_raw(path or cfg.DEFAULT_INPUT, date_column, value_column)
    clean, excluded, rep = audit_and_clean(raw)
    rep["source"] = info
    if save:
        cfg.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        cfg.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        clean.assign(date=clean["date"].dt.strftime("%Y-%m-%d")).to_csv(cfg.CLEAN_SERIES_PATH, index=False)
        excluded.to_csv(cfg.EXCLUDED_PATH, index=False)
        cfg.DATA_QUALITY_REPORT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    return clean, rep


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Contrôle qualité de la série USD/CDF")
    ap.add_argument("--input", default=None)
    ap.add_argument("--date-column", default=None)
    ap.add_argument("--value-column", default=None)
    a = ap.parse_args()
    series, report = prepare(a.input, a.date_column, a.value_column)
    print(json.dumps({k: report[k] for k in ("n_rows_input", "n_rows_clean", "n_rows_excluded", "date_min", "date_max")}, indent=2))
    print("Rapport complet :", cfg.DATA_QUALITY_REPORT)
