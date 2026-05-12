"""Generate embeddings for all journals using OpenAI text-embedding-3-small.

Cost: ~$0.10 for 30K journals
Batch: 100 journals per API call
Checkpoint: every 500 records to data/embedding_progress.json
"""
import json
import math
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

root = Path(__file__).parent.parent
for _p in [root / 'frontend' / '.env.local', root / '.env.local', root / '.env']:
    if _p.exists():
        load_dotenv(_p, override=False)

CHECKPOINT_FILE = Path(__file__).parent / 'data' / 'embedding_progress.json'
BATCH_SIZE = 100
CHECKPOINT_EVERY = 500
EMBED_MODEL = 'text-embedding-3-small'


def save_checkpoint(processed_ids: set):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'processed_ids': list(processed_ids)}, f)


def load_checkpoint() -> set:
    try:
        with open(CHECKPOINT_FILE, encoding='utf-8') as f:
            return set(json.load(f).get('processed_ids', []))
    except Exception:
        return set()


def build_text(j: dict) -> str:
    topics = ' '.join(
        t['name'] for t in (j.get('topics') or [])[:10]
        if t.get('name')
    )
    parts = [
        j.get('title', ''),
        j.get('subject_area', ''),
        j.get('subject_category', ''),
        j.get('publisher', ''),
        topics,
    ]
    return ' '.join(p for p in parts if p).strip()


def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def main():
    url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or os.environ.get('SUPABASE_URL')
    key = (
        os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        or os.environ.get('SUPABASE_SERVICE_KEY')
        or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    )
    openai_key = os.environ.get('OPENAI_API_KEY')
    if not openai_key:
        raise ValueError("OPENAI_API_KEY not found in environment. Add to frontend/.env.local")

    client = create_client(url, key)
    openai_client = OpenAI(api_key=openai_key)

    # Load all journals
    print("Loading journals from Supabase...")
    all_journals = []
    page_size = 1000
    start = 0
    while True:
        result = client.table('journals')\
            .select('id, title, subject_area, subject_category, publisher, topics')\
            .range(start, start + page_size - 1)\
            .execute()
        batch = result.data or []
        all_journals.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    print(f"Total journals: {len(all_journals)}")

    processed_ids = load_checkpoint()
    print(f"Resuming: {len(processed_ids)} already embedded")

    to_process = [j for j in all_journals if j['id'] not in processed_ids]
    print(f"Remaining to embed: {len(to_process)}")

    total_embedded = 0
    since_checkpoint = 0

    for batch in chunk(to_process, BATCH_SIZE):
        texts = [build_text(j) for j in batch]
        # Skip empty texts
        valid = [(j, t) for j, t in zip(batch, texts) if t.strip()]

        if not valid:
            for j in batch:
                processed_ids.add(j['id'])
            continue

        valid_journals, valid_texts = zip(*valid)

        try:
            response = openai_client.embeddings.create(
                model=EMBED_MODEL,
                input=list(valid_texts),
            )
        except Exception as e:
            print(f"  OpenAI error: {e}. Skipping batch, will retry next run.")
            time.sleep(5)
            continue

        for j, emb_obj in zip(valid_journals, response.data):
            vector = emb_obj.embedding
            try:
                client.table('journals')\
                    .update({'embedding': vector})\
                    .eq('id', j['id'])\
                    .execute()
            except Exception as e:
                print(f"  DB error for journal {j['id']}: {e}")

            processed_ids.add(j['id'])
            total_embedded += 1
            since_checkpoint += 1

        if since_checkpoint >= CHECKPOINT_EVERY:
            save_checkpoint(processed_ids)
            since_checkpoint = 0
            print(f"  Checkpoint. Embedded so far: {total_embedded}")

        time.sleep(0.5)  # respect OpenAI rate limits

    save_checkpoint(processed_ids)
    print(f"\nDone. Total embedded: {total_embedded}")
    print("Verify: run in Supabase SQL editor:")
    print("  SELECT COUNT(*) FROM journals WHERE embedding IS NOT NULL;")


if __name__ == '__main__':
    main()
