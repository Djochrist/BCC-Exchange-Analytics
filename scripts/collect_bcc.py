#!/usr/bin/env python3
"""Collect USD/CDF observations from the official BCC daily pages.

The collector re-checks the most recent calendar days so late publications or
corrections can be picked up. It never invents, interpolates or silently
replaces an observation.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "usd-cdf.json"
RAW_PATH = ROOT / "analysis" / "xgboost" / "data" / "raw" / "cours-de-change-quotidien.csv"
STRATEGY_PATH = ROOT / "analysis" / "strategy" / "data" / "series_clean.csv"
STATUS_PATH = ROOT / "data" / "automation.json"
BCC_BASE = "https://www.bcc.cd/marche-des-changes/cours-de-change"
USER_AGENT = "USD-CDF-BCC/2.0 (+https://www.bcc.cd/)"


def load_series() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def save_series(payload: dict) -> None:
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_rate(html: str) -> float | None:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"USD\s*\(cours\s+moyen\)\s*([^0-9]{0,80})([0-9][0-9\s.,]*)", text, re.I)
    if not m:
        m = re.search(r"\bUSD\b\s*[^0-9]{0,120}([0-9][0-9\s.,]*)", text, re.I)
    if not m:
        return None
    raw = m.group(2 if len(m.groups()) > 1 else 1).strip().replace("\u202f", "").replace(" ", "")
    # Prefer comma as decimal separator when it is the last separator.
    if "," in raw and "." in raw:
        raw = raw.replace(".", "") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
        if "," in raw:
            raw = raw.replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if 500 <= value <= 10000 else None


def fetch_day(day: date, timeout: int = 25, retries: int = 2) -> float | None:
    url = f"{BCC_BASE}/{day.isoformat()}"
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
            with urlopen(req, timeout=timeout) as response:
                html = response.read().decode("utf-8", errors="ignore")
            return parse_rate(html)
        except (HTTPError, URLError, TimeoutError) as exc:
            if attempt < retries:
                time.sleep(1.25 * (attempt + 1))
            else:
                print(f"[BCC] {day}: échec ({exc})", file=sys.stderr)
    return None


def write_raw_csv(series: list[dict]) -> None:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAW_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "USD/CDF"])
        for row in series:
            w.writerow([row["date"], row["value"]])


def sync_strategy_csv(series: list[dict]) -> None:
    STRATEGY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STRATEGY_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "value"])
        for row in series:
            w.writerow([row["date"], row["value"]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-back", type=int, default=14)
    ap.add_argument("--today", default=None, help="date ISO utile pour les tests, sinon date UTC")
    args = ap.parse_args()

    payload = load_series()
    known = {x["date"]: float(x["value"]) for x in payload.get("series", [])}
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    start = max(date(2017, 1, 1), today - timedelta(days=max(1, args.days_back)))
    attempted = 0
    added = 0
    changed = 0

    cursor = start
    while cursor <= today:
        attempted += 1
        value = fetch_day(cursor)
        if value is not None:
            key = cursor.isoformat()
            old = known.get(key)
            known[key] = round(value, 6)
            if old is None:
                added += 1
            elif not math.isclose(old, value, rel_tol=0, abs_tol=1e-9):
                changed += 1
        cursor += timedelta(days=1)

    merged = [{"date": d, "value": known[d]} for d in sorted(known)]
    payload["series"] = merged
    payload["observations"] = len(merged)
    if merged:
        payload["period"] = {"start": merged[0]["date"], "end": merged[-1]["date"]}
    payload["source"] = "Banque Centrale du Congo"
    payload["sourceUrl"] = "https://www.bcc.cd/statistiques/secteur-exterieur/cours-de-change"
    payload["collection"] = {
        "method": "pages quotidiennes officielles BCC",
        "endpoint_pattern": BCC_BASE + "/{YYYY-MM-DD}",
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "window_start": start.isoformat(),
        "window_end": today.isoformat(),
        "calendar_days_attempted": attempted,
        "observations_added": added,
        "observations_corrected": changed,
    }
    payload["snapshotNote"] = (
        "Les observations sont collectées automatiquement depuis les pages quotidiennes officielles "
        "de la Banque Centrale du Congo. Les jours sans cotation sont ignorés et aucune valeur n'est interpolée."
    )
    save_series(payload)
    write_raw_csv(merged)
    sync_strategy_csv(merged)
    STATUS_PATH.write_text(json.dumps(payload["collection"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[DONE] BCC: {len(merged)} observations | nouvelles={added} | corrections={changed} | fenêtre={start}→{today}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
