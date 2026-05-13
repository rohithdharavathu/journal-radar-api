"""
Compute quartile_trend for all journals based on quartile_history.

Rising:  quartile number decreased (Q2→Q1) comparing most recent vs 2 years prior
Falling: quartile number increased (Q1→Q2)
Stable:  no change or insufficient history (only 1 year of data)

Q1=1, Q2=2, Q3=3, Q4=4 numerically (lower is better).
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

Q_RANK = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}


def compute_trend(rows: list[dict]) -> str:
    if len(rows) < 2:
        return "stable"
    by_year = sorted(rows, key=lambda r: r["year"], reverse=True)
    newest = by_year[0]["quartile"]
    # Find a row at least 2 years older
    older = next((r for r in by_year[1:] if by_year[0]["year"] - r["year"] >= 2), None)
    if not older:
        older = by_year[-1]  # fall back to oldest available
    newest_rank = Q_RANK.get(newest)
    older_rank = Q_RANK.get(older["quartile"])
    if newest_rank is None or older_rank is None:
        return "stable"
    if newest_rank < older_rank:
        return "rising"
    if newest_rank > older_rank:
        return "falling"
    return "stable"


def main():
    print("Fetching quartile history...")
    all_history = supabase.from_("quartile_history").select("journal_id, year, quartile").execute()
    rows = all_history.data or []
    print(f"  {len(rows)} history rows loaded")

    # Group by journal_id
    from collections import defaultdict
    by_journal: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_journal[row["journal_id"]].append(row)

    # Compute trend per journal
    trend_map: dict[int, str] = {}
    for jid, jrows in by_journal.items():
        trend_map[jid] = compute_trend(jrows)

    counts = {"rising": 0, "falling": 0, "stable": 0}
    for t in trend_map.values():
        counts[t] = counts.get(t, 0) + 1
    print(f"  Trends computed: {counts}")

    # Batch update 500 at a time
    BATCH = 500
    journal_ids = list(trend_map.keys())
    total = len(journal_ids)
    updated = 0

    for i in range(0, total, BATCH):
        batch_ids = journal_ids[i : i + BATCH]
        # Group by trend value to minimize API calls
        by_trend: dict[str, list[int]] = defaultdict(list)
        for jid in batch_ids:
            by_trend[trend_map[jid]].append(jid)

        for trend_val, ids in by_trend.items():
            supabase.from_("journals").update({"quartile_trend": trend_val}).in_("id", ids).execute()

        updated += len(batch_ids)
        print(f"  Updated {updated}/{total}...")

    print(f"Done. {total} journals updated.")


if __name__ == "__main__":
    main()
