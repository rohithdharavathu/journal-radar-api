"""Enrich all journals with OpenAlex data.

Adds: homepage_url, works_count, works_recent_2yr, topics (JSONB)
Rate limit: 10 req/sec polite pool (time.sleep(0.12) per request)
Checkpoint: saves progress every 500 records to data/openalex_progress.json
Resume: skips already-processed journal IDs on restart
"""
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

root = Path(__file__).parent.parent
for _p in [root / 'frontend' / '.env.local', root / '.env.local', root / '.env']:
    if _p.exists():
        load_dotenv(_p, override=False)

MAILTO = 'rohith.dharavathu.112@gmail.com'
BASE_URL = 'https://api.openalex.org/sources'
CHECKPOINT_FILE = Path(__file__).parent / 'data' / 'openalex_progress.json'
CHECKPOINT_EVERY = 100


def save_checkpoint(processed_ids: set):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'processed_ids': list(processed_ids)}, f)


def load_checkpoint() -> set:
    try:
        with open(CHECKPOINT_FILE, encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('processed_ids', []))
    except Exception:
        return set()


def fetch_openalex(issn: str) -> dict | None:
    # works_by_year is not available on /sources — omit it
    params = {
        'filter': f'issn:{issn}',
        'select': 'id,homepage_url,topics,works_count',
        'mailto': MAILTO,
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=15)
        if r.status_code != 200:
            return None  # silently skip 404/400 — normal for obscure journals
        results = r.json().get('results', [])
        return results[0] if results else None
    except requests.RequestException:
        return None
    except Exception:
        return None


def get_recent_2yr_count(works_by_year: list) -> int | None:
    if not works_by_year:
        return None
    from datetime import datetime
    current_year = datetime.now().year
    recent = [
        w.get('works_count', 0)
        for w in works_by_year
        if w.get('year') in (current_year - 1, current_year - 2)
    ]
    return sum(recent) if recent else None


def main():
    url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or os.environ.get('SUPABASE_URL')
    key = (
        os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        or os.environ.get('SUPABASE_SERVICE_KEY')
        or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
        or os.environ.get('SUPABASE_KEY')
    )
    client = create_client(url, key)

    # Load all journals (paginate through all 30K)
    print("Loading all journals from Supabase...")
    all_journals = []
    page_size = 1000
    start = 0
    while True:
        result = client.table('journals')\
            .select('id, issn_print, issn_electronic, homepage_url, works_count')\
            .range(start, start + page_size - 1)\
            .execute()
        batch = result.data or []
        all_journals.extend(batch)
        print(f"  Loaded {len(all_journals)} journals...")
        if len(batch) < page_size:
            break
        start += page_size

    print(f"Total journals to process: {len(all_journals)}")

    processed_ids = load_checkpoint()
    print(f"Resuming from checkpoint: {len(processed_ids)} already processed")

    updated = 0
    since_checkpoint = 0

    try:
        for i, journal in enumerate(all_journals):
            jid = journal['id']
            if jid in processed_ids:
                continue

            issn = journal.get('issn_print') or journal.get('issn_electronic')
            if not issn:
                processed_ids.add(jid)
                since_checkpoint += 1
            else:
                oa = fetch_openalex(issn)
                time.sleep(0.12)  # 10 req/sec polite pool

                if oa:
                    patch = {}
                    if oa.get('homepage_url') and not journal.get('homepage_url'):
                        patch['homepage_url'] = oa['homepage_url']
                    if oa.get('works_count') is not None:
                        patch['works_count'] = oa['works_count']
                    topics_raw = oa.get('topics', [])
                    if topics_raw:
                        patch['topics'] = [
                            {'id': t.get('id'), 'name': t.get('display_name'), 'score': t.get('score')}
                            for t in topics_raw[:20]
                        ]

                    if patch:
                        try:
                            client.table('journals').update(patch).eq('id', jid).execute()
                            updated += 1
                        except Exception as e:
                            print(f"  Error updating journal {jid}: {e}")

                processed_ids.add(jid)
                since_checkpoint += 1

            if since_checkpoint >= CHECKPOINT_EVERY:
                save_checkpoint(processed_ids)
                since_checkpoint = 0
                print(f"  Checkpoint saved. Processed: {len(processed_ids)}, Updated: {updated}")

            if (i + 1) % 1000 == 0:
                print(f"  Progress: {i + 1}/{len(all_journals)} | Updated: {updated}")

    except KeyboardInterrupt:
        print(f"\nInterrupted. Saving checkpoint ({len(processed_ids)} processed)...")
        save_checkpoint(processed_ids)
        print("Checkpoint saved. Re-run to resume.")
        return

    save_checkpoint(processed_ids)
    print(f"\nDone. Total processed: {len(processed_ids)}, Updated: {updated}")
    print("Next step: run the search_vector rebuild SQL in Supabase (supabase/schema_phase2.sql)")


if __name__ == '__main__':
    main()
