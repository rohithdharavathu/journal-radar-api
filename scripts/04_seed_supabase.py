"""Seed merged journals JSON into Supabase journals table.

Changes over original:
- Truncates existing rows before reseeding (avoids duplicates)
- NaN cleaner on every batch before insert
"""
import json
import math
import os
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

FIELDS = [
    'title', 'issn_print', 'issn_electronic', 'publisher', 'country',
    'subject_area', 'subject_category', 'quartile', 'sjr_score', 'h_index',
    'apc_amount_usd', 'apc_currency', 'apc_amount_original', 'publishing_model',
    'author_guidelines_url', 'apc_display', 'is_active', 'is_scopus', 'is_doaj',
    'data_sources', 'data_confidence', 'last_verified',
]


def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def clean_floats(record: dict) -> dict:
    cleaned = {}
    for k, v in record.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def main():
    url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or os.environ.get('SUPABASE_URL')
    key = (
        os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        or os.environ.get('SUPABASE_SERVICE_KEY')
        or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
        or os.environ.get('SUPABASE_KEY')
    )
    if not url or not key:
        raise ValueError(
            "Supabase credentials not found.\n"
            "Add SUPABASE_SERVICE_ROLE_KEY to frontend/.env.local\n"
            "(Supabase Dashboard → Settings → API → service_role secret)"
        )
    if 'anon' in key:
        print("WARNING: Using anon key — this will fail due to RLS. Use service_role key instead.")

    client = create_client(url, key)

    with open(INPUT, encoding='utf-8') as f:
        journals = json.load(f)

    print(f"Loaded {len(journals)} journals.")

    # Truncate before reseeding to avoid duplicates
    print("Clearing existing data...")
    try:
        client.table('journals').delete().neq('id', 0).execute()
        print("Table cleared.")
    except Exception as e:
        print(f"WARNING: Could not clear table: {e}")
        print("Proceeding with insert (may create duplicates).")

    print(f"Seeding in chunks of {CHUNK_SIZE}...")
    total_inserted = 0
    errors = 0

    for i, batch in enumerate(chunk(journals, CHUNK_SIZE)):
        rows = [clean_floats({k: j.get(k) for k in FIELDS}) for j in batch]
        try:
            client.table('journals').insert(rows).execute()
            total_inserted += len(batch)
            if (i + 1) % 10 == 0 or total_inserted == len(journals):
                print(f"  Chunk {i + 1}: inserted {len(batch)} (total: {total_inserted})")
        except Exception as e:
            errors += 1
            print(f"  Chunk {i + 1}: ERROR — {e}")

    print(f"\nDone. Inserted: {total_inserted}, Errors: {errors}")

    try:
        count_result = client.table('journals').select('id', count='exact').execute()
        print(f"Total in DB: {count_result.count}")
    except Exception as e:
        print(f"Could not verify count: {e}")


if __name__ == '__main__':
    main()
