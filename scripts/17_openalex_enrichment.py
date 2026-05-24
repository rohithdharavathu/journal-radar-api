"""
JournalRadar — OpenAlex Data Enrichment
========================================
Script: 17_openalex_enrichment.py

Fetches from OpenAlex for ALL journals:
  - apc_usd / apc_prices       → real APC data
  - summary_stats              → h_index, 2yr_mean_citedness
  - works_count                → total publications
  - counts_by_year             → recent activity (last 2 years)
  - is_oa / is_in_doaj         → OA status
  - homepage_url               → journal website
  - topics                     → subject areas

Run: python 17_openalex_enrichment.py
"""

import os
import time
import requests
from tqdm import tqdm
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# DB CLIENT
# ─────────────────────────────────────────────────────────────────────────────

class DB:
    def __init__(self):
        self._url    = os.getenv("SUPABASE_URL")
        self._key    = os.getenv("SUPABASE_KEY")
        self._client = create_client(self._url, self._key)

    def reconnect(self):
        try:
            self._client = create_client(self._url, self._key)
        except Exception as e:
            print(f"  Reconnect failed: {e}")

    def table(self, name):
        return self._client.table(name)


db = DB()

# ─────────────────────────────────────────────────────────────────────────────
# OPENALEX FETCHER
# ─────────────────────────────────────────────────────────────────────────────

OPENALEX_HEADERS = {
    "User-Agent": "JournalRadar/1.0 (mailto:admin@journalradar.com)"
}

def fetch_openalex(issn):
    """
    Fetch full journal data from OpenAlex by ISSN.
    Returns the source dict or None.
    """
    if not issn:
        return None

    try:
        r = requests.get(
            "https://api.openalex.org/sources",
            params={
                "filter": f"issn:{issn}",
                "select": ",".join([
                    "id",
                    "issn",
                    "issn_l",
                    "display_name",
                    "homepage_url",
                    "apc_prices",
                    "apc_usd",
                    "is_oa",
                    "is_in_doaj",
                    "works_count",
                    "oa_works_count",
                    "cited_by_count",
                    "summary_stats",
                    "counts_by_year",
                    "topics",
                    "country_code",
                    "type",
                ]),
            },
            headers=OPENALEX_HEADERS,
            timeout=15
        )

        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return results[0]

        if r.status_code == 429:
            time.sleep(5)

    except Exception:
        pass

    return None


def extract_fields(source):
    """
    Extract useful fields from OpenAlex source response.
    Returns a dict of fields to update in our DB.
    """
    if not source:
        return {}

    updates = {}

    # ── APC data ─────────────────────────────────────────────────────────────
    apc_usd = source.get("apc_usd")
    if apc_usd and float(apc_usd) > 0:
        updates["oa_apc_usd"]   = float(apc_usd)
        updates["apc_usd_openalex"] = float(apc_usd)

    apc_prices = source.get("apc_prices", [])
    if apc_prices:
        # Find USD price
        for p in apc_prices:
            if p.get("currency") == "USD" and p.get("price", 0) > 0:
                updates["oa_apc_usd"] = float(p["price"])
                break

    # ── Summary stats ─────────────────────────────────────────────────────────
    stats = source.get("summary_stats", {})
    if isinstance(stats, dict):
        # 2yr mean citedness ≈ impact factor equivalent
        citedness = stats.get("2yr_mean_citedness")
        if citedness is not None:
            updates["cite_score"] = round(float(citedness), 3)

        h_index = stats.get("h_index")
        if h_index is not None:
            updates["h_index"] = int(h_index)

        i10 = stats.get("i10_index")
        if i10 is not None:
            updates["i10_index"] = int(i10)

    # ── Works count ───────────────────────────────────────────────────────────
    works = source.get("works_count")
    if works is not None:
        updates["works_count"] = int(works)

    # ── Recent publications (last 2 years) ────────────────────────────────────
    counts_by_year = source.get("counts_by_year", [])
    if counts_by_year:
        # Get most recent 2 years
        recent = sorted(counts_by_year, key=lambda x: x.get("year", 0), reverse=True)
        recent_2yr = sum(
            y.get("works_count", 0)
            for y in recent[:2]
        )
        if recent_2yr > 0:
            updates["works_recent_2yr"] = recent_2yr

    # ── OA status ─────────────────────────────────────────────────────────────
    is_oa = source.get("is_oa")
    if is_oa is not None:
        updates["is_oa_openalex"] = bool(is_oa)

    is_doaj = source.get("is_in_doaj")
    if is_doaj is not None:
        updates["is_doaj_openalex"] = bool(is_doaj)

    # ── Homepage URL ──────────────────────────────────────────────────────────
    homepage = source.get("homepage_url")
    if homepage:
        updates["homepage_url"] = str(homepage)

    # ── Country ───────────────────────────────────────────────────────────────
    country = source.get("country_code")
    if country:
        updates["country_code"] = str(country)

    # ── Cited by count ────────────────────────────────────────────────────────
    cited = source.get("cited_by_count")
    if cited is not None:
        updates["cited_by_count"] = int(cited)

    return updates


def update_journal(journal_id, updates, retries=3):
    """Update journal with OpenAlex data."""
    if not updates:
        return False

    for attempt in range(retries):
        try:
            db.table("journals") \
              .update(updates) \
              .eq("id", journal_id) \
              .execute()
            return True
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                db.reconnect()
            else:
                print(f"    DB error: {e}")
                return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────

def enrich_from_openalex():
    """
    Fetch all journals and enrich with OpenAlex data.
    """
    print(f"\n{'='*60}")
    print("OpenAlex Enrichment — All Fields")
    print(f"{'='*60}")

    # Fetch all journals
    print("Fetching journals from DB...")
    journals  = []
    page      = 0
    page_size = 1000

    while True:
        try:
            r = db.table("journals") \
                  .select("id, title, issn_print, issn_electronic") \
                  .range(page * page_size, (page + 1) * page_size - 1) \
                  .execute()
            if not r.data:
                break
            journals.extend(r.data)
            page += 1
            if len(r.data) < page_size:
                break
        except Exception as e:
            print(f"  Fetch error: {e}")
            break

    print(f"Total journals: {len(journals):,}")

    # Stats
    updated   = 0
    not_found = 0
    apc_found = 0
    stats_found = 0

    # Progress tracking
    save_interval = 500

    for i, j in enumerate(tqdm(journals, desc="OpenAlex")):
        # Try electronic ISSN first, then print
        issns = []
        if j.get("issn_electronic"):
            issns.append(j["issn_electronic"])
        if j.get("issn_print"):
            issns.append(j["issn_print"])

        source = None
        for issn in issns:
            source = fetch_openalex(issn)
            if source:
                break

        if not source:
            not_found += 1
            time.sleep(0.1)
            continue

        # Extract fields
        updates = extract_fields(source)

        if not updates:
            not_found += 1
            time.sleep(0.1)
            continue

        # Track what we found
        if "oa_apc_usd" in updates:
            apc_found += 1
        if "cite_score" in updates:
            stats_found += 1

        # Update DB
        ok = update_journal(j["id"], updates)
        if ok:
            updated += 1
        
        time.sleep(0.1)   # polite crawling

        # Progress update
        if (i + 1) % save_interval == 0:
            print(f"\n  [{i+1}/{len(journals)}] "
                  f"Updated: {updated} | "
                  f"Not found: {not_found} | "
                  f"APC found: {apc_found} | "
                  f"Stats found: {stats_found}")

    print(f"\n{'='*60}")
    print(f"OpenAlex enrichment complete!")
    print(f"  Updated:     {updated:,}")
    print(f"  Not found:   {not_found:,}")
    print(f"  APC found:   {apc_found:,}")
    print(f"  Stats found: {stats_found:,}")

    return updated


# ─────────────────────────────────────────────────────────────────────────────
# APC SYNC — use OpenAlex APC to fill missing APC data
# ─────────────────────────────────────────────────────────────────────────────

def sync_openalex_apc():
    """
    After enrichment, sync OpenAlex APC data into main apc_amount_usd
    for journals where we don't have better data.
    """
    print(f"\n{'='*60}")
    print("Syncing OpenAlex APC → apc_amount_usd")
    print(f"{'='*60}")

    # Run SQL to sync
    try:
        result = db.table("journals") \
                   .select("id, apc_amount_usd, oa_apc_usd, publishing_model") \
                   .not_.is_("oa_apc_usd", "null") \
                   .gt("oa_apc_usd", 0) \
                   .execute()

        journals = result.data or []
        print(f"Journals with OpenAlex APC: {len(journals):,}")

        updated = 0
        for j in tqdm(journals, desc="Syncing APC"):
            oa_apc = j.get("oa_apc_usd", 0)
            current_apc = j.get("apc_amount_usd", 0)

            # Only update if current APC is 0 or missing
            # Don't overwrite high-confidence PDF data
            if current_apc and current_apc > 0:
                continue

            if oa_apc and oa_apc > 0:
                try:
                    db.table("journals").update({
                        "apc_amount_usd":      round(float(oa_apc), 2),
                        "apc_display":         f"${round(float(oa_apc)):,}",
                        "apc_currency":        "USD",
                        "apc_amount_original": round(float(oa_apc), 2),
                        "publishing_model":    "gold_oa",
                        "data_confidence":     "high",
                        "data_sources":        {"apc": "openalex"},
                    }).eq("id", j["id"]).execute()
                    updated += 1
                except Exception as e:
                    print(f"  Sync error: {e}")

        print(f"APC sync → Updated: {updated:,}")
        return updated

    except Exception as e:
        print(f"Sync error: {e}")
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def verify():
    print(f"\n{'='*60}")
    print("FINAL VERIFICATION")
    print(f"{'='*60}")

    total = db.table("journals").select("id", count="exact").execute()
    t = total.count or 1

    # APC coverage
    paid = db.table("journals").select("id", count="exact") \
             .gt("apc_amount_usd", 0).execute()
    print(f"Total journals:      {t:,}")
    print(f"With paid APC:       {paid.count:,} ({paid.count/t*100:.1f}%)")

    # cite_score coverage
    try:
        with_cs = db.table("journals").select("id", count="exact") \
                    .not_.is_("cite_score", "null").execute()
        print(f"With cite_score:     {with_cs.count:,} ({with_cs.count/t*100:.1f}%)")
    except Exception:
        pass

    # h_index coverage
    try:
        with_hi = db.table("journals").select("id", count="exact") \
                    .not_.is_("h_index", "null").execute()
        print(f"With h_index:        {with_hi.count:,} ({with_hi.count/t*100:.1f}%)")
    except Exception:
        pass

    # works_count coverage
    try:
        with_wc = db.table("journals").select("id", count="exact") \
                    .not_.is_("works_count", "null").execute()
        print(f"With works_count:    {with_wc.count:,} ({with_wc.count/t*100:.1f}%)")
    except Exception:
        pass

    # Top journals by citedness
    print("\nTop journals by 2yr citedness (impact factor):")
    try:
        top = db.table("journals") \
               .select("title, cite_score, h_index, apc_amount_usd") \
               .not_.is_("cite_score", "null") \
               .order("cite_score", desc=True) \
               .limit(10).execute()
        for j in (top.data or []):
            print(f"  {j['title'][:45]:45s} | "
                  f"IF={j.get('cite_score', 0):6.2f} | "
                  f"h={j.get('h_index', 0):4} | "
                  f"APC=${j.get('apc_amount_usd', 0):,.0f}")
    except Exception as e:
        print(f"  Error: {e}")

    # Sample with APC from OpenAlex
    print("\nSample journals with OpenAlex APC:")
    try:
        sample = db.table("journals") \
                   .select("title, apc_amount_usd, cite_score, "
                           "works_count, homepage_url") \
                   .gt("apc_amount_usd", 0) \
                   .not_.is_("cite_score", "null") \
                   .order("cite_score", desc=True) \
                   .limit(8).execute()
        for j in (sample.data or []):
            print(f"  {j['title'][:40]:40s} | "
                  f"APC=${j.get('apc_amount_usd',0):6,.0f} | "
                  f"IF={j.get('cite_score',0):5.2f} | "
                  f"works={j.get('works_count',0):,}")
    except Exception as e:
        print(f"  Error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("JournalRadar — OpenAlex Data Enrichment")
    print("=" * 60)
    print(f"SUPABASE: {os.getenv('SUPABASE_URL', 'MISSING ⚠')}")
    print("\nData fields to collect:")
    print("  ✓ apc_usd / apc_prices   (real APC amounts)")
    print("  ✓ 2yr_mean_citedness      (impact factor equivalent)")
    print("  ✓ h_index                 (journal prestige)")
    print("  ✓ works_count             (total publications)")
    print("  ✓ works_recent_2yr        (recent activity)")
    print("  ✓ homepage_url            (journal website)")
    print("  ✓ is_oa / is_in_doaj      (OA status)")
    print("  ✓ cited_by_count          (total citations)")

    # Step 1: Enrich from OpenAlex
    enrich_from_openalex()

    # Step 2: Sync APC data
    sync_openalex_apc()

    # Step 3: Verify
    verify()