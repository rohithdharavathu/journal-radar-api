"""Parse Scimago CSV → scripts/data/scimago_clean.json

Fixes over original:
- Multi-strategy quartile extraction (direct column → regex from categories)
- Strips (Q1)/(Q2)/... suffixes from subject_category names
- ISSN normalizer now handles X check digit
"""
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from utils.issn import parse_issn_pair

DATA_DIR = Path(__file__).parent / "data"
OUTPUT = DATA_DIR / "scimago_clean.json"


def _find_scimago_csv() -> Path:
    """Pick the most recent scimagojr_<year>.csv in data/."""
    candidates = sorted(DATA_DIR.glob("scimagojr_*.csv"), reverse=True)
    if not candidates:
        raise FileNotFoundError(
            "No scimagojr_*.csv found in scripts/data/.\n"
            "Run: python 00_download_sources.py"
        )
    chosen = candidates[0]
    print(f"  Using Scimago file: {chosen.name}")
    return chosen


INPUT = _find_scimago_csv()

DIRECT_QUARTILE_COLS = ['SJR Best Quartile', 'Quartile (best)', 'Best Quartile', 'Quartile']
CATEGORY_COLS = ['Categories', 'Subject Category', 'Subject Categories']


def extract_quartile(row, columns) -> str | None:
    # Strategy 1: direct column
    for col in DIRECT_QUARTILE_COLS:
        if col in columns:
            val = str(row.get(col, '')).strip()
            if val in ('Q1', 'Q2', 'Q3', 'Q4'):
                return val

    # Strategy 2: regex from categories string e.g. "Hematology (Q1); Oncology (Q2)"
    for col in CATEGORY_COLS:
        if col in columns:
            cats = str(row.get(col, '') or '')
            matches = re.findall(r'\(Q([1-4])\)', cats)
            if matches:
                return f"Q{min(int(m) for m in matches)}"  # best (lowest) quartile

    return None


def clean_category_name(raw: str) -> str | None:
    """'Hematology (Q1)' → 'Hematology'. Also strips trailing semicolons."""
    if not raw or str(raw).strip() in ('', 'nan'):
        return None
    first = str(raw).split(';')[0].strip()
    cleaned = re.sub(r'\s*\(Q[1-4]\)', '', first).strip()
    return cleaned or None


def first_area(raw) -> str | None:
    if not raw or str(raw).strip() in ('', 'nan'):
        return None
    parts = [x.strip() for x in str(raw).split(';')]
    return parts[0] if parts else None


def parse_float(raw) -> float | None:
    try:
        val = float(str(raw).replace(',', '.'))
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    except (ValueError, TypeError):
        return None


def parse_int(raw) -> int | None:
    try:
        return int(float(str(raw)))
    except (ValueError, TypeError):
        return None


def main():
    print(f"Reading {INPUT}...")
    df = pd.read_csv(INPUT, sep=';', encoding='utf-8', dtype=str)
    columns = set(df.columns)
    print(f"  Columns: {list(df.columns)}")
    print(f"  Total rows: {len(df)}")

    # Filter journals only
    if 'Type' in columns:
        df = df[df['Type'].str.strip().str.lower() == 'journal']
        print(f"  After filtering type=journal: {len(df)}")

    records = []
    for i, (_, row) in enumerate(df.iterrows()):
        if (i + 1) % 5000 == 0:
            print(f"  Processed {i + 1} rows...")

        issn_raw = str(row.get('Issn', '') or '')
        issn_print, issn_electronic = parse_issn_pair(issn_raw)

        # Find category column name
        cat_col = next((c for c in CATEGORY_COLS if c in columns), None)
        cat_raw = str(row.get(cat_col, '') or '') if cat_col else ''

        record = {
            'title': str(row.get('Title', '')).strip() or None,
            'issn_print': issn_print,
            'issn_electronic': issn_electronic,
            'sjr_score': parse_float(row.get('SJR', '')),
            'h_index': parse_int(row.get('H index', '')),
            'quartile': extract_quartile(row, columns),
            'subject_area': first_area(row.get('Areas', '')),
            'subject_category': clean_category_name(cat_raw),
            'publisher': str(row.get('Publisher', '')).strip() or None,
            'country': str(row.get('Country', '')).strip() or None,
        }

        if not record['title']:
            continue

        records.append(record)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    with_q = sum(1 for j in records if j['quartile'])
    pct = with_q / len(records) * 100 if records else 0
    print(f"\n✓ Total records: {len(records)}")
    print(f"✓ Quartile coverage: {with_q}/{len(records)} ({pct:.1f}%)")

    if pct < 80:
        print("\nWARNING: Quartile coverage below 80%.")
        print("Column names found:", [c for c in df.columns if 'quart' in c.lower() or 'categor' in c.lower()])
        print("Run inspect_csvs.py and check actual column names.")
    else:
        print("✓ Quartile coverage OK (>80%)")

    print(f"\nOutput → {OUTPUT}")


if __name__ == '__main__':
    main()
