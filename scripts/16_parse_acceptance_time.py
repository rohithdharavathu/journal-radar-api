"""
JournalRadar — Acceptance Time via Publisher Estimates
=======================================================
Script: 16_parse_acceptance_time.py

OpenAlex/Crossref/Springer APIs don't have acceptance time data.
Using publisher-based estimates from industry reports.

Run: python 16_parse_acceptance_time.py (~2 minutes)
"""

import os
import time
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
            print("  Reconnected to Supabase")
        except Exception as e:
            print(f"  Reconnect failed: {e}")

    def table(self, name):
        return self._client.table(name)


db = DB()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLISHER ESTIMATES
# Based on: APE 2023 survey, Science Metrix reports,
#           publishers' own published averages
# ─────────────────────────────────────────────────────────────────────────────

PUBLISHER_ESTIMATES = {
    # Very fast (< 5 weeks)
    "mdpi":                         3.5,
    "frontiers":                    4.0,
    "hindawi":                      4.5,
    "peerj":                        4.0,
    "dove":                         4.5,
    "pensoft":                      4.5,
    "f1000":                        5.0,

    # Fast (5-7 weeks)
    "plos":                         6.0,
    "bmc":                          6.0,
    "biomed central":               6.0,
    "scientific reports":           5.5,
    "copernicus":                   5.5,
    "public library of science":    6.0,

    # Average (7-9 weeks)
    "springer":                     7.5,
    "elsevier":                     8.0,
    "oxford":                       8.0,
    "acs":                          8.0,
    "american chemical":            8.0,
    "rsc":                          8.0,
    "royal society of chemistry":   8.0,
    "royal society":                8.5,
    "asm":                          8.0,
    "american society for micro":   8.0,
    "aps":                          7.5,
    "american physical":            7.5,
    "osa":                          8.0,
    "optica":                       8.0,
    "iop":                          8.0,
    "institute of physics":         8.0,
    "karger":                       8.0,
    "thieme":                       8.5,
    "ios press":                    8.0,
    "bentham":                      7.0,
    "walter de gruyter":            9.0,
    "de gruyter":                   9.0,

    # Slow (9-12 weeks)
    "wiley":                        9.5,
    "john wiley":                   9.5,
    "wiley-blackwell":              9.5,
    "sage":                         9.0,
    "cambridge":                    9.5,
    "cambridge university":         9.5,
    "taylor":                      10.0,
    "taylor & francis":            10.0,
    "taylor and francis":          10.0,
    "routledge":                   10.0,
    "informa":                     10.0,
    "emerald":                      9.0,
    "wolters kluwer":               9.5,
    "lippincott":                   9.5,
    "brill":                       10.0,
    "ieee":                        10.0,
    "institute of electrical":     10.0,
    "acm":                          9.5,
    "association for computing":    9.5,
    "american medical":            10.0,
    "american psychiatric":        10.0,
    "american psychological":      10.0,
    "annual reviews":              10.0,
    "future medicine":              8.5,
    "mary ann liebert":             9.0,
    "humana":                       9.0,

    # Very slow > 12 weeks (prestigious journals)
    "nature portfolio":            12.0,
    "nature publishing":           12.0,
    "cell press":                  11.0,
    "lancet":                      12.0,
    "new england journal":         12.0,
    "jama":                        11.0,
    "american heart":              10.0,

    # Default
    "default":                      8.0,
}

# Special title-based overrides for top journals
TITLE_OVERRIDES = {
    "nature":                      14.0,
    "science":                     13.0,
    "cell":                        11.0,
    "the lancet":                  13.0,
    "nejm":                        13.0,
    "new england journal":         13.0,
    "jama":                        12.0,
    "bmj":                         10.0,
    "plos one":                     6.0,
    "scientific reports":           5.5,
    "peerj":                        4.0,
}


def get_acceptance_estimate(publisher, title=""):
    """
    Return estimated acceptance weeks for a journal.
    Checks title overrides first, then publisher estimates.
    """
    # Check title overrides (exact/partial match)
    title_lower = str(title).lower().strip()
    for key, weeks in TITLE_OVERRIDES.items():
        if title_lower == key or title_lower.startswith(key):
            return weeks

    # Check publisher
    pub_lower = str(publisher or "").lower()
    for key, weeks in PUBLISHER_ESTIMATES.items():
        if key == "default":
            continue
        if key in pub_lower:
            return weeks

    # Return default
    return PUBLISHER_ESTIMATES["default"]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def fill_acceptance_times():
    """
    Fill avg_acceptance_weeks for all journals.
    Groups by estimate value then batch updates — very fast.
    """
    print(f"\n{'='*60}")
    print("FILLING ACCEPTANCE TIMES")
    print(f"{'='*60}")

    # ── Fetch all journals with NULL acceptance time ───────────────────────
    print("Fetching journals with NULL avg_acceptance_weeks...")
    journals  = []
    page      = 0
    page_size = 1000

    while True:
        try:
            r = db.table("journals") \
                  .select("id, title, publisher, avg_acceptance_weeks") \
                  .is_("avg_acceptance_weeks", "null") \
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
            db.reconnect()
            break

    print(f"Found {len(journals):,} journals to update")

    if not journals:
        print("✅ All journals already have acceptance time data!")
        return 0

    # ── Group journals by their estimated weeks ───────────────────────────
    print("Calculating estimates...")
    groups = {}  # weeks_value → [list of journal ids]

    for j in tqdm(journals, desc="Estimating"):
        weeks = get_acceptance_estimate(
            j.get("publisher", ""),
            j.get("title", "")
        )
        key = round(float(weeks), 1)
        if key not in groups:
            groups[key] = []
        groups[key].append(j["id"])

    # Show distribution
    print(f"\nEstimate distribution ({len(groups)} distinct values):")
    for weeks in sorted(groups.keys()):
        count = len(groups[weeks])
        bar   = "█" * min(40, count // 50)
        print(f"  {weeks:5.1f}w | {count:5,} journals | {bar}")

    # ── Batch update by estimate group ───────────────────────────────────
    print("\nUpdating database...")
    updated_total = 0
    error_total   = 0
    batch_size    = 100

    for weeks, ids in tqdm(groups.items(), desc="Updating"):
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]

            for attempt in range(3):
                try:
                    db.table("journals").update({
                        "avg_acceptance_weeks": weeks,
                    }).in_("id", batch).execute()
                    updated_total += len(batch)
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        db.reconnect()
                    else:
                        print(f"  Batch error: {e}")
                        error_total += len(batch)

    print(f"\n✅ Updated: {updated_total:,} | Errors: {error_total:,}")
    return updated_total


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def verify():
    print(f"\n{'='*60}")
    print("FINAL VERIFICATION — Acceptance Times")
    print(f"{'='*60}")

    total   = db.table("journals") \
                .select("id", count="exact").execute()
    with_at = db.table("journals") \
                .select("id", count="exact") \
                .not_.is_("avg_acceptance_weeks", "null").execute()
    null_at = db.table("journals") \
                .select("id", count="exact") \
                .is_("avg_acceptance_weeks", "null").execute()

    t = total.count or 1
    print(f"Total journals:       {t:,}")
    print(f"With acceptance time: {with_at.count:,} "
          f"({with_at.count/t*100:.1f}%)")
    print(f"Still NULL:           {null_at.count:,}")

    # Distribution
    print("\nAcceptance time distribution:")
    ranges = [
        ("< 4 weeks  (very fast)",  0,   4),
        ("4-6 weeks  (fast)",       4,   6),
        ("6-8 weeks  (average)",    6,   8),
        ("8-10 weeks (slow)",       8,  10),
        ("10-12 weeks (very slow)", 10, 12),
        ("> 12 weeks (prestige)",   12, 999),
    ]
    for label, low, high in ranges:
        r = db.table("journals") \
              .select("id", count="exact") \
              .gt("avg_acceptance_weeks", low) \
              .lte("avg_acceptance_weeks", high).execute()
        pct = r.count / t * 100
        bar = "█" * int(pct / 2)
        print(f"  {label:27s}: {r.count:5,} ({pct:4.1f}%) {bar}")

    # Sample journals
    print("\nSample — fastest journals:")
    fast = db.table("journals") \
             .select("title, publisher, avg_acceptance_weeks") \
             .not_.is_("avg_acceptance_weeks", "null") \
             .order("avg_acceptance_weeks") \
             .limit(8).execute()
    for j in (fast.data or []):
        print(f"  {j['avg_acceptance_weeks']:4.1f}w | "
              f"{j['title'][:40]:40s} | "
              f"{str(j.get('publisher',''))[:25]}")

    print("\nSample — slowest journals:")
    slow = db.table("journals") \
             .select("title, publisher, avg_acceptance_weeks") \
             .not_.is_("avg_acceptance_weeks", "null") \
             .order("avg_acceptance_weeks", desc=True) \
             .limit(8).execute()
    for j in (slow.data or []):
        print(f"  {j['avg_acceptance_weeks']:4.1f}w | "
              f"{j['title'][:40]:40s} | "
              f"{str(j.get('publisher',''))[:25]}")

    print("\nSample — MDPI journals (should be ~3.5w):")
    mdpi = db.table("journals") \
             .select("title, avg_acceptance_weeks") \
             .ilike("publisher", "%mdpi%") \
             .limit(5).execute()
    for j in (mdpi.data or []):
        print(f"  {j['avg_acceptance_weeks']:4.1f}w | {j['title'][:50]}")

    print("\nSample — Nature journals (should be ~12-14w):")
    nature = db.table("journals") \
               .select("title, avg_acceptance_weeks") \
               .ilike("publisher", "%nature%") \
               .limit(5).execute()
    for j in (nature.data or []):
        print(f"  {j['avg_acceptance_weeks']:4.1f}w | {j['title'][:50]}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("JournalRadar — Acceptance Time Data Collection")
    print("=" * 60)
    print("Strategy: Publisher-based estimates from industry reports")
    print("(No API has acceptance time data for all journals)")
    print(f"SUPABASE: {os.getenv('SUPABASE_URL', 'MISSING ⚠')}")

    fill_acceptance_times()
    verify()