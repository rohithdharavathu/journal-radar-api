"""Fetch Impact Factor (IF) from OpenAlex for journals that have an ISSN.

OpenAlex API: https://api.openalex.org/sources?filter=issn:{issn}
Response field: results[0].summary_stats.impact_factor (2yr IF)

Steps:
  1. Fetch up to 2000 journals where impact_factor IS NULL and has an ISSN, ordered by sjr_score DESC.
  2. For each journal, call OpenAlex and extract summary_stats.impact_factor.
  3. Accumulate updates; batch-write to Supabase every 100 journals.
  4. Rate limit: 5 req/s (sleep 0.2 s between calls).
  5. Print progress every 50 journals.
"""

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent.parent / 'api' / '.env')

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

OPENALEX_BASE = 'https://api.openalex.org/sources'
MAILTO = 'rohith.dharavathu.112@gmail.com'
BATCH_SIZE = 100
SLEEP_BETWEEN = 0.2  # 5 req/s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_impact_factor(issn: str) -> float | None:
    """Call OpenAlex and return the 2yr impact factor, or None."""
    params = {
        'filter': f'issn:{issn}',
        'select': 'id,summary_stats,cited_by_count',
        'mailto': MAILTO,
    }
    try:
        r = requests.get(OPENALEX_BASE, params=params, timeout=15)
        if r.status_code != 200:
            return None
        results = r.json().get('results', [])
        if not results:
            return None
        stats = results[0].get('summary_stats') or {}
        val = stats.get('impact_factor') or stats.get('2yr_mean_citedness')
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
        return None
    except requests.RequestException:
        return None
    except Exception:
        return None


def flush_updates(pending: list[dict]) -> int:
    """Write pending {id, impact_factor} records to Supabase one-by-one (no batch by value)."""
    written = 0
    for item in pending:
        try:
            supabase.table('journals').update(
                {'impact_factor': item['impact_factor']}
            ).eq('id', item['id']).execute()
            written += 1
        except Exception as e:
            print(f"  [warn] Failed to update journal {item['id']}: {e}")
    return written


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Fetching journals with NULL impact_factor and an ISSN...")
    result = (
        supabase.table('journals')
        .select('id, issn_print, issn_electronic')
        .is_('impact_factor', 'null')
        .or_('issn_print.neq.null,issn_electronic.neq.null')  # has at least one ISSN
        .order('sjr_score', desc=True)
        .limit(2000)
        .execute()
    )
    journals = result.data or []
    # Filter in Python as a safety net (some DBs may not filter JSONB nulls cleanly)
    journals = [
        j for j in journals
        if j.get('issn_print') or j.get('issn_electronic')
    ]
    print(f"  {len(journals)} journals to process.")

    pending: list[dict] = []
    total_written = 0
    found = 0

    for i, journal in enumerate(journals):
        jid = journal['id']
        issn = journal.get('issn_print') or journal.get('issn_electronic')

        if not issn:
            continue

        if_val = fetch_impact_factor(issn)
        time.sleep(SLEEP_BETWEEN)

        if if_val is not None:
            pending.append({'id': jid, 'impact_factor': if_val})
            found += 1

        # Flush every BATCH_SIZE
        if len(pending) >= BATCH_SIZE:
            total_written += flush_updates(pending)
            pending.clear()

        # Progress
        if (i + 1) % 50 == 0:
            print(
                f"  [{i + 1}/{len(journals)}] found so far: {found}, "
                f"written: {total_written}, pending: {len(pending)}"
            )

    # Final flush
    if pending:
        total_written += flush_updates(pending)
        pending.clear()

    print(
        f"\nDone. Processed {len(journals)} journals. "
        f"IFs found: {found}. Supabase rows updated: {total_written}."
    )


if __name__ == '__main__':
    main()
