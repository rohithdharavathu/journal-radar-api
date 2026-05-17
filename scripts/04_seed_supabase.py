"""Seed merged journals JSON into Supabase journals table.

SAFE for annual re-runs:
- First run (empty DB): inserts all 30K journals, assigns stable IDs
- Subsequent runs (annual update): UPSERTS by issn_print — updates quartile,
  APC, SJR in place WITHOUT changing journal IDs. All user data
  (bookmarks, submissions, acceptance_reports) remains intact.
- Before upserting, snapshots current quartile into quartile_history so
  year-over-year trend data accumulates automatically.

Requires schema_phase3.sql to be run first (UNIQUE index on issn_print).
"""
import json
import math
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

root = Path(__file__).parent.parent
for dotenv_path in [
    root / 'frontend' / '.env.local',
    root / '.env.local',
    root / '.env',
    root / '.env.example',
]:
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=False)

INPUT = Path(__file__).parent / "data" / "journals_merged.json"
CHUNK_SIZE = 500

# Fields written on first insert
INSERT_FIELDS = [
    'title', 'issn_print', 'issn_electronic', 'publisher', 'country',
    'subject_area', 'subject_category', 'quartile', 'sjr_score', 'h_index',
    'apc_amount_usd', 'apc_currency', 'apc_amount_original', 'publishing_model',
    'author_guidelines_url', 'apc_display', 'is_active', 'is_scopus', 'is_doaj',
    'data_sources', 'data_confidence', 'last_verified',
]

# Fields updated on conflict (annual refresh — values that change year to year)
UPDATE_FIELDS = [
    'quartile', 'sjr_score', 'h_index',
    'apc_amount_usd', 'apc_currency', 'apc_amount_original', 'apc_display',
    'publisher', 'country', 'subject_area', 'subject_category',
    'is_active', 'is_scopus', 'is_doaj',
    'data_sources', 'data_confidence', 'last_verified',
]


def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def clean_floats(record: dict) -> dict:
    return {
        k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
        for k, v in record.items()
    }


def snapshot_quartile_history(client, current_year: int):
    """Copy current quartile from journals → quartile_history before overwriting."""
    print(f"Snapshotting current quartiles into quartile_history (year={current_year})...")
    try:
        existing = client.table('journals').select('id, quartile').execute()
        rows = existing.data or []
        history_rows = [
            {'journal_id': r['id'], 'year': current_year, 'quartile': r['quartile']}
            for r in rows
            if r.get('quartile') and r.get('id')
        ]
        if not history_rows:
            print("  No existing journals to snapshot.")
            return
        for batch in chunk(history_rows, CHUNK_SIZE):
            client.table('quartile_history').upsert(
                batch, on_conflict='journal_id,year'
            ).execute()
        print(f"  Snapshotted {len(history_rows)} quartile records.")
    except Exception as e:
        print(f"  WARNING: Quartile snapshot failed — {e}")


def main():
    url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or os.environ.get('SUPABASE_URL')
    key = (
        os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        or os.environ.get('SUPABASE_SERVICE_KEY')
        or os.environ.get('SUPABASE_KEY')
    )
    if not url or not key:
        raise ValueError(
            "Supabase credentials not found.\n"
            "Set SUPABASE_SERVICE_ROLE_KEY in frontend/.env.local"
        )
    if 'anon' in key:
        raise ValueError("anon key won't bypass RLS. Use service_role key.")

    client = create_client(url, key)

    with open(INPUT, encoding='utf-8') as f:
        journals = json.load(f)
    print(f"Loaded {len(journals)} journals from {INPUT.name}.")

    # Check if DB is empty (first run) or has data (annual update)
    count_result = client.table('journals').select('id', count='exact').execute()
    existing_count = count_result.count or 0
    is_first_run = existing_count == 0

    if is_first_run:
        print("First run detected — inserting all journals.")
    else:
        print(f"Annual update detected — {existing_count} journals in DB.")
        current_year = datetime.now().year
        # Snapshot BEFORE we overwrite quartile data
        snapshot_quartile_history(client, current_year)

    total_upserted = 0
    errors = 0

    for i, batch in enumerate(chunk(journals, CHUNK_SIZE)):
        rows = [clean_floats({k: j.get(k) for k in INSERT_FIELDS}) for j in batch]
        # Skip rows with no ISSN — can't upsert without a unique key
        rows = [r for r in rows if r.get('issn_print') or r.get('issn_electronic')]
        try:
            client.table('journals').upsert(
                rows,
                on_conflict='issn_print',
            ).execute()
            total_upserted += len(rows)
            if (i + 1) % 10 == 0 or total_upserted >= len(journals) - CHUNK_SIZE:
                print(f"  Chunk {i + 1}: upserted {len(rows)} (total: {total_upserted})")
        except Exception as e:
            errors += 1
            print(f"  Chunk {i + 1}: ERROR — {e}")

    final_count = client.table('journals').select('id', count='exact').execute().count
    print(f"\nDone. Upserted: {total_upserted}, Errors: {errors}, Total in DB: {final_count}")


if __name__ == '__main__':
    main()
