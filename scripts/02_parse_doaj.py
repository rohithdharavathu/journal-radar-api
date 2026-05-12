"""Parse DOAJ CSV → scripts/data/doaj_clean.json"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from utils.issn import normalize_issn
from utils.currency import to_usd

INPUT = Path(__file__).parent / "data" / "doaj.csv"
OUTPUT = Path(__file__).parent / "data" / "doaj_clean.json"


def parse_float(raw) -> float | None:
    try:
        val = float(str(raw).replace(',', '.').strip())
        return val if val >= 0 else None
    except (ValueError, TypeError):
        return None


def main():
    print(f"Reading {INPUT}...")
    df = pd.read_csv(INPUT, encoding='utf-8', dtype=str)
    print(f"  Total rows: {len(df)}")

    # Normalize column names (DOAJ headers vary)
    df.columns = [c.strip() for c in df.columns]

    # Map flexible column names
    col_map = {}
    for col in df.columns:
        c = col.lower()
        if 'journal title' in c:
            col_map['title'] = col
        elif c in ('issn', 'print issn', 'journal issn (print version)'):
            col_map['issn'] = col
        elif c in ('eissn', 'online issn', 'journal eissn (online version)'):
            col_map['eissn'] = col
        elif 'apc amount' in c or ('apc' in c and 'amount' in c):
            col_map['apc_amount'] = col
        elif 'apc currency' in c or ('apc' in c and 'currency' in c):
            col_map['apc_currency'] = col
        elif 'author guidelines' in c or 'guidelines url' in c:
            col_map['guidelines'] = col

    records = []
    for _, row in df.iterrows():
        issn_print = normalize_issn(str(row.get(col_map.get('issn', ''), '') or ''))
        issn_electronic = normalize_issn(str(row.get(col_map.get('eissn', ''), '') or ''))

        if not issn_print and not issn_electronic:
            continue

        apc_raw = parse_float(row.get(col_map.get('apc_amount', ''), ''))
        apc_currency = str(row.get(col_map.get('apc_currency', ''), '') or '').strip().upper() or None

        apc_usd = None
        if apc_raw and apc_currency:
            apc_usd = to_usd(apc_raw, apc_currency)

        if apc_usd and apc_usd > 0:
            publishing_model = 'gold_oa'
        else:
            publishing_model = 'diamond_oa'
            apc_raw = 0
            apc_usd = 0

        guidelines = str(row.get(col_map.get('guidelines', ''), '') or '').strip() or None

        records.append({
            'issn_print': issn_print,
            'issn_electronic': issn_electronic,
            'apc_amount_original': apc_raw,
            'apc_currency': apc_currency,
            'apc_amount_usd': apc_usd,
            'publishing_model': publishing_model,
            'author_guidelines_url': guidelines,
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"  Output: {len(records)} journals → {OUTPUT}")


if __name__ == '__main__':
    main()
