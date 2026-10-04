#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
series = json.loads((ROOT/'data/usd-cdf.json').read_text(encoding='utf-8'))
assert series.get('source') == 'Banque Centrale du Congo'
rows = series.get('series', [])
assert rows and rows == sorted(rows, key=lambda x: x['date'])
assert all(float(r['value']) > 0 for r in rows)
model = json.loads((ROOT/'data/model.json').read_text(encoding='utf-8'))
assert model.get('last_date') == rows[-1]['date']
print(f"OK: {len(rows)} observations jusqu'au {rows[-1]['date']} | modèle jusqu'au {model['last_date']}")
