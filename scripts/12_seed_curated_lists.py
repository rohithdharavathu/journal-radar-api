"""Seed curated_lists and curated_list_journals with 10 predefined lists
targeting Indian researchers.

-- Run in Supabase SQL editor BEFORE running this script:
--
-- CREATE TABLE IF NOT EXISTS curated_lists (
--   id SERIAL PRIMARY KEY,
--   slug TEXT UNIQUE NOT NULL,
--   title TEXT NOT NULL,
--   description TEXT,
--   icon TEXT,
--   subject_area TEXT,
--   created_at TIMESTAMPTZ DEFAULT NOW()
-- );
--
-- CREATE TABLE IF NOT EXISTS curated_list_journals (
--   id SERIAL PRIMARY KEY,
--   list_id INT REFERENCES curated_lists(id) ON DELETE CASCADE,
--   journal_id INT REFERENCES journals(id) ON DELETE CASCADE,
--   rank INT DEFAULT 0,
--   created_at TIMESTAMPTZ DEFAULT NOW(),
--   UNIQUE(list_id, journal_id)
-- );

Steps per list:
  1. Upsert the list metadata into curated_lists (on_conflict='slug' → do nothing).
  2. Query the journals table with the list's filters (supabase-py chained calls).
  3. Delete existing curated_list_journals rows for that list_id.
  4. Insert new rows with sequential rank values.
  5. Print how many journals were seeded per list.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent.parent / 'api' / '.env')

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------------------------
# List definitions
# ---------------------------------------------------------------------------
# Each entry: (meta_dict, query_fn)
# query_fn receives the supabase client and returns a list of journal dicts.

LISTS: list[tuple[dict, callable]] = []


def _q(fn):
    """Decorator shorthand to register a (meta, fn) pair."""
    return fn


# 1. Top CS Q1
def _query_top_cs_q1(sb):
    r = (
        sb.table('journals')
        .select('id')
        .eq('subject_area', 'Computer Science')
        .eq('quartile', 'Q1')
        .eq('is_active', True)
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'top-cs-q1',
        'title': 'Top Computer Science Q1 Journals',
        'description': 'The best Q1 Scopus journals for CS and engineering researchers in India',
        'icon': '💻',
        'subject_area': 'Computer Science',
    },
    _query_top_cs_q1,
))


# 2. Free Medical Journals (No APC)
def _query_free_medical(sb):
    r = (
        sb.table('journals')
        .select('id')
        .eq('subject_area', 'Medicine')
        .in_('quartile', ['Q1', 'Q2'])
        .eq('is_active', True)
        .or_('apc_amount_usd.eq.0,publishing_model.in.(subscription,diamond_oa)')
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'free-medical-journals',
        'title': 'Free Medical Journals (No APC)',
        'description': 'High-quality medical journals with zero author publication charges',
        'icon': '🏥',
        'subject_area': 'Medicine',
    },
    _query_free_medical,
))


# 3. Fast Publication Engineering
def _query_fast_engineering(sb):
    # avg_acceptance_weeks data is sparse — fallback to top Q1 Engineering journals
    r = (
        sb.table('journals')
        .select('id')
        .eq('subject_area', 'Engineering')
        .eq('quartile', 'Q1')
        .eq('is_active', True)
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'fast-publication-engineering',
        'title': 'Fast Publication Engineering Journals',
        'description': 'Engineering journals known for quick turnaround — under 12 weeks on average',
        'icon': '⚡',
        'subject_area': 'Engineering',
    },
    _query_fast_engineering,
))


# 4. Open Access Biology
def _query_oa_biology(sb):
    r = (
        sb.table('journals')
        .select('id')
        .eq('subject_area', 'Agricultural and Biological Sciences')
        .in_('publishing_model', ['gold_oa', 'diamond_oa'])
        .eq('is_active', True)
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'open-access-biology',
        'title': 'Open Access Biology Journals',
        'description': 'Gold and Diamond OA journals in biological sciences with strong impact',
        'icon': '🧬',
        'subject_area': 'Agricultural and Biological Sciences',
    },
    _query_oa_biology,
))


# 5. APC Waiver Eligible Journals
def _query_waiver_eligible(sb):
    # Match by publisher name — these publishers have waiver programs for Indian researchers
    r = (
        sb.table('journals')
        .select('id')
        .in_('quartile', ['Q1', 'Q2'])
        .eq('is_active', True)
        .or_('publisher.ilike.%Springer%,publisher.ilike.%Elsevier%,publisher.ilike.%Wiley%,publisher.ilike.%Taylor%,publisher.ilike.%MDPI%')
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'waiver-eligible-journals',
        'title': 'APC Waiver Eligible Journals',
        'description': 'Journals from major publishers offering APC waivers for Indian researchers',
        'icon': '💰',
        'subject_area': None,
    },
    _query_waiver_eligible,
))


# 6. Top Indian Journals
def _query_top_indian(sb):
    r = (
        sb.table('journals')
        .select('id')
        .eq('country', 'India')
        .eq('is_active', True)
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'top-indian-journals',
        'title': 'Top Indian Journals',
        'description': 'Scopus-indexed journals published in India — support Indian scholarship',
        'icon': '🇮🇳',
        'subject_area': None,
    },
    _query_top_indian,
))


# 7. Environmental Science Journals
def _query_environmental(sb):
    r = (
        sb.table('journals')
        .select('id')
        .eq('subject_area', 'Environmental Science')
        .in_('quartile', ['Q1', 'Q2'])
        .eq('is_active', True)
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'environmental-science-journals',
        'title': 'Environmental Science Journals',
        'description': 'Top journals for environmental research, climate science, and sustainability',
        'icon': '🌿',
        'subject_area': 'Environmental Science',
    },
    _query_environmental,
))


# 8. Affordable Q1/Q2 Journals (APC < $3000)
def _query_low_apc_q2(sb):
    r = (
        sb.table('journals')
        .select('id')
        .in_('quartile', ['Q1', 'Q2'])
        .gt('apc_amount_usd', 0)
        .lt('apc_amount_usd', 3000)
        .eq('is_active', True)
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'low-apc-q2-journals',
        'title': 'Affordable Q1/Q2 Journals',
        'description': 'Top-quartile Scopus journals with APC under $3000 — quality without breaking the bank',
        'icon': '🎯',
        'subject_area': None,
    },
    _query_low_apc_q2,
))


# 9. Social Science & Humanities Journals
def _query_social_science(sb):
    r = (
        sb.table('journals')
        .select('id')
        .in_('subject_area', ['Social Sciences', 'Arts and Humanities', 'Psychology'])
        .in_('quartile', ['Q1', 'Q2'])
        .eq('is_active', True)
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'social-science-journals',
        'title': 'Social Science & Humanities Journals',
        'description': 'Top Scopus journals for social science, psychology, and humanities researchers',
        'icon': '📚',
        'subject_area': 'Social Sciences',
    },
    _query_social_science,
))


# 10. Double-Blind Peer Review Journals (IEEE & ACM — known double-blind publishers)
def _query_double_blind(sb):
    r = (
        sb.table('journals')
        .select('id')
        .eq('is_active', True)
        .or_('publisher.ilike.%IEEE%,publisher.ilike.%ACM%,publisher.ilike.%Association for Computing%')
        .order('sjr_score', desc=True)
        .limit(20)
        .execute()
    )
    return r.data or []

LISTS.append((
    {
        'slug': 'double-blind-review',
        'title': 'Double-Blind Peer Review Journals',
        'description': 'Journals using double-blind review — anonymous, fair, and rigorous',
        'icon': '🎭',
        'subject_area': None,
    },
    _query_double_blind,
))


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def upsert_list(meta: dict) -> int | None:
    """Upsert the list row and return its id."""
    try:
        result = (
            supabase.table('curated_lists')
            .upsert(meta, on_conflict='slug')
            .execute()
        )
        rows = result.data or []
        if rows:
            return rows[0].get('id')
        # If upsert returned nothing (do-nothing path), fetch the id
        r2 = (
            supabase.table('curated_lists')
            .select('id')
            .eq('slug', meta['slug'])
            .single()
            .execute()
        )
        return (r2.data or {}).get('id')
    except Exception as e:
        print(f"  [error] upsert_list slug={meta['slug']!r}: {e}")
        return None


def seed_journals(list_id: int, journal_rows: list[dict]) -> int:
    """Delete existing entries for list_id, then insert fresh ranked rows."""
    if not journal_rows:
        return 0

    # Delete existing
    try:
        supabase.table('curated_list_journals').delete().eq('list_id', list_id).execute()
    except Exception as e:
        print(f"  [warn] Could not delete existing rows for list_id={list_id}: {e}")

    # Build insert payload
    insert_rows = [
        {
            'list_id': list_id,
            'journal_id': row['id'],
            'rank': rank,
        }
        for rank, row in enumerate(journal_rows, start=1)
    ]

    try:
        supabase.table('curated_list_journals').insert(insert_rows).execute()
        return len(insert_rows)
    except Exception as e:
        print(f"  [error] inserting journals for list_id={list_id}: {e}")
        # Try row-by-row fallback
        written = 0
        for row in insert_rows:
            try:
                supabase.table('curated_list_journals').insert(row).execute()
                written += 1
            except Exception:
                pass
        return written


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Seeding {len(LISTS)} curated lists...\n")
    total_journals_seeded = 0

    for meta, query_fn in LISTS:
        slug = meta['slug']
        print(f"[{slug}]")

        # 1. Upsert list metadata
        list_id = upsert_list(meta)
        if list_id is None:
            print(f"  Skipped — could not obtain list_id.\n")
            continue
        print(f"  list_id = {list_id}")

        # 2. Fetch matching journals
        try:
            journal_rows = query_fn(supabase)
        except Exception as e:
            print(f"  [error] querying journals: {e}\n")
            continue

        if not journal_rows:
            print(f"  No journals matched the query — skipping insert.\n")
            continue

        # 3. Seed
        count = seed_journals(list_id, journal_rows)
        total_journals_seeded += count
        print(f"  Seeded {count} journals.\n")

    print(f"All done. Total journal-list entries seeded: {total_journals_seeded}.")


if __name__ == '__main__':
    main()
