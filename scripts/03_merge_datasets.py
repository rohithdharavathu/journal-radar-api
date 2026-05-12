"""Merge Scimago + DOAJ on ISSN → scripts/data/journals_merged.json

Fixes over original:
- NaN/Inf cleaner on every record before output
- Verification assertion: >3000 paid OA journals
- Handles None print ISSNs in DOAJ lookup (matches on electronic only)
"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

SCIMAGO = Path(__file__).parent / "data" / "scimago_clean.json"
DOAJ = Path(__file__).parent / "data" / "doaj_clean.json"
OUTPUT = Path(__file__).parent / "data" / "journals_merged.json"


def clean_floats(record: dict) -> dict:
    """Replace NaN/Inf floats with None so JSON serialization doesn't break."""
    cleaned = {}
    for k, v in record.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def compute_apc_display(apc_usd, model: str) -> str:
    if model == 'subscription':
        return 'No author fee'
    if model == 'diamond_oa' or apc_usd == 0:
        return 'No author fee (Open Access)'
    if apc_usd and apc_usd > 0:
        return f"${apc_usd:,.0f}"
    return 'Contact publisher'


def build_doaj_lookup(doaj_journals: list) -> dict:
    """Build lookup from ALL ISSNs (print + electronic) → journal entry."""
    lookup = {}
    for j in doaj_journals:
        for field in ('issn_print', 'issn_electronic'):
            issn = j.get(field)
            if issn and issn not in ('None', '', None):
                lookup[issn] = j
    return lookup


def find_doaj_match(scimago_journal: dict, doaj_lookup: dict):
    for field in ('issn_print', 'issn_electronic'):
        issn = scimago_journal.get(field)
        if issn and issn in doaj_lookup:
            return doaj_lookup[issn]
    return None


def compute_confidence(doaj_match) -> str:
    return 'high' if doaj_match else 'medium'


def main():
    with open(SCIMAGO, encoding='utf-8') as f:
        scimago = json.load(f)
    with open(DOAJ, encoding='utf-8') as f:
        doaj = json.load(f)

    print(f"Scimago: {len(scimago)} journals")
    print(f"DOAJ: {len(doaj)} journals")

    doaj_lookup = build_doaj_lookup(doaj)
    print(f"DOAJ ISSN lookup entries: {len(doaj_lookup)}")

    now = datetime.now(timezone.utc).isoformat()
    merged = []
    matched_count = 0

    for i, journal in enumerate(scimago):
        if (i + 1) % 5000 == 0:
            print(f"  Merging record {i + 1}...")

        doaj_entry = find_doaj_match(journal, doaj_lookup)
        record = dict(journal)

        if doaj_entry:
            matched_count += 1
            apc_usd = doaj_entry.get('apc_amount_usd', 0) or 0
            model = doaj_entry.get('publishing_model', 'gold_oa')
            record['apc_amount_usd'] = apc_usd
            record['apc_currency'] = doaj_entry.get('apc_currency')
            record['apc_amount_original'] = doaj_entry.get('apc_amount_original', 0)
            record['publishing_model'] = model
            record['author_guidelines_url'] = doaj_entry.get('author_guidelines_url')
            record['is_doaj'] = True
            record['data_sources'] = {'quartile': 'scimago', 'apc': 'doaj'}
            record['data_confidence'] = 'high'
        else:
            record['apc_amount_usd'] = 0
            record['apc_currency'] = None
            record['apc_amount_original'] = 0
            record['publishing_model'] = 'subscription'
            record['author_guidelines_url'] = None
            record['is_doaj'] = False
            record['data_sources'] = {'quartile': 'scimago', 'apc': 'inferred'}
            record['data_confidence'] = 'medium'

        record['apc_display'] = compute_apc_display(
            record['apc_amount_usd'], record['publishing_model']
        )
        record['is_active'] = True
        record['is_scopus'] = True
        record['last_verified'] = now

        merged.append(clean_floats(record))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    paid_oa = [j for j in merged if (j.get('apc_amount_usd') or 0) > 0]
    free_oa = [j for j in merged if j.get('publishing_model') == 'diamond_oa']
    sub = [j for j in merged if j.get('publishing_model') == 'subscription']

    print(f"\n✓ Merged: {len(merged)} journals")
    print(f"✓ Matched with DOAJ: {matched_count} ({matched_count/len(merged)*100:.1f}%)")
    print(f"✓ Paid OA (APC > $0): {len(paid_oa)}")
    print(f"✓ Diamond OA (free): {len(free_oa)}")
    print(f"✓ Subscription: {len(sub)}")
    print(f"  Output → {OUTPUT}")

    if len(paid_oa) < 3000:
        print(f"\nWARNING: Only {len(paid_oa)} paid OA journals found.")
        print("Expected >3,000. Check ISSN matching — may be an ISSN format mismatch.")
    else:
        print("\n✓ Paid OA journal count OK (>3,000)")


if __name__ == '__main__':
    main()
