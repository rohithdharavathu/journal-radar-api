"""Populate the aims_scope column by fetching journal homepages and extracting
the <meta name="description"> or <meta property="og:description"> tag.

Steps:
  1. Fetch up to 500 journals where aims_scope IS NULL AND homepage_url IS NOT NULL,
     ordered by sjr_score DESC.
  2. For each journal, GET the homepage with a 10-second timeout.
  3. Parse with BeautifulSoup; prefer <meta name="description">, fall back to og:description.
  4. If content length > 100 chars, store as aims_scope.
  5. Batch-update Supabase every 50 journals.
  6. Sleep 1 second between requests.
  7. Skip and log on any exception.
  8. Print progress every 25 journals.
"""

import os
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent.parent / 'api' / '.env')

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    'User-Agent': 'JournalRadar/1.0 (rohith.dharavathu.112@gmail.com)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}
TIMEOUT = 10
BATCH_SIZE = 50
SLEEP_BETWEEN = 1.0
MIN_DESC_LENGTH = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def scrape_description(url: str) -> str | None:
    """Fetch the page and extract a meta description. Returns None on failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')

        # Primary: <meta name="description">
        tag = soup.find('meta', attrs={'name': 'description'})
        if tag and tag.get('content'):
            content = tag['content'].strip()
            if len(content) >= MIN_DESC_LENGTH:
                return content

        # Fallback: <meta property="og:description">
        tag = soup.find('meta', attrs={'property': 'og:description'})
        if tag and tag.get('content'):
            content = tag['content'].strip()
            if len(content) >= MIN_DESC_LENGTH:
                return content

        return None
    except Exception as exc:
        raise exc  # let caller handle


def flush_updates(pending: list[dict]) -> int:
    """Write accumulated aims_scope updates to Supabase."""
    written = 0
    for item in pending:
        try:
            supabase.table('journals').update(
                {'aims_scope': item['aims_scope']}
            ).eq('id', item['id']).execute()
            written += 1
        except Exception as e:
            print(f"  [warn] Failed to update journal {item['id']}: {e}")
    return written


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Fetching journals with NULL aims_scope and a homepage URL...")
    result = (
        supabase.table('journals')
        .select('id, homepage_url, title')
        .is_('aims_scope', 'null')
        .not_.is_('homepage_url', 'null')
        .order('sjr_score', desc=True)
        .limit(500)
        .execute()
    )
    journals = result.data or []
    # Safety filter
    journals = [j for j in journals if j.get('homepage_url')]
    print(f"  {len(journals)} journals to process.")

    pending: list[dict] = []
    total_written = 0
    found = 0
    skipped = 0

    for i, journal in enumerate(journals):
        jid = journal['id']
        url = journal.get('homepage_url', '').strip()
        title = journal.get('title', f'id={jid}')

        if not url:
            continue

        try:
            description = scrape_description(url)
            if description:
                pending.append({'id': jid, 'aims_scope': description})
                found += 1
        except Exception as exc:
            skipped += 1
            print(f"  [skip] {title!r} ({url}): {exc}")

        time.sleep(SLEEP_BETWEEN)

        # Flush batch
        if len(pending) >= BATCH_SIZE:
            total_written += flush_updates(pending)
            pending.clear()

        # Progress
        if (i + 1) % 25 == 0:
            print(
                f"  [{i + 1}/{len(journals)}] found: {found}, "
                f"written: {total_written}, skipped: {skipped}, pending: {len(pending)}"
            )

    # Final flush
    if pending:
        total_written += flush_updates(pending)
        pending.clear()

    print(
        f"\nDone. Processed {len(journals)} journals. "
        f"Descriptions found: {found}. Skipped: {skipped}. "
        f"Supabase rows updated: {total_written}."
    )


if __name__ == '__main__':
    main()
