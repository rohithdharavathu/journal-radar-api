"""Annual data refresh for JournalRadar.

Run this once per year when Scimago publishes new rankings (usually Jan–Feb).

WHAT TO DO EACH YEAR:
1. Download new Scimago CSV from:
       https://www.scimagojr.com/journalrank.php  (Export → CSV)
   Save as: scripts/data/scimagojr_<YEAR>.csv
   Update SCIMAGO_FILE below to match the new filename.

2. Download new DOAJ CSV from:
       https://doaj.org/csv
   Save as: scripts/data/doaj.csv  (overwrite the old one)

3. Run this script:
       cd scripts
       python 18_annual_update.py

WHAT THIS SCRIPT DOES:
- Parses new Scimago + DOAJ data
- Merges on ISSN
- Snapshots current quartiles → quartile_history (preserves trend data)
- Upserts journals by ISSN — updates quartile, APC, SJR in place
- Journal IDs never change → all bookmarks, submissions, reports stay intact
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# ── CONFIG: update this each year ──────────────────────────────────────────
SCIMAGO_FILE = "scimagojr_2025.csv"   # ← change to new year's file
# ───────────────────────────────────────────────────────────────────────────

SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR / "data"


def run(script: str, label: str):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script)],
        check=False
    )
    if result.returncode != 0:
        print(f"\nERROR: {script} failed (exit {result.returncode}). Aborting.")
        sys.exit(1)
    print(f"  ✓ {label} complete")


def preflight():
    scimago_path = DATA_DIR / SCIMAGO_FILE
    doaj_path = DATA_DIR / "doaj.csv"
    missing = []
    if not scimago_path.exists():
        missing.append(str(scimago_path))
    if not doaj_path.exists():
        missing.append(str(doaj_path))
    if missing:
        print("ERROR: Missing required data files:")
        for f in missing:
            print(f"  {f}")
        print("\nSee instructions at the top of this script.")
        sys.exit(1)
    print(f"Preflight OK — {SCIMAGO_FILE} + doaj.csv found.")


def main():
    print(f"\nJournalRadar Annual Update — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Scimago file: {SCIMAGO_FILE}")

    preflight()

    # Step 1: Parse sources
    run("01_parse_scimago.py", "Parse Scimago CSV")
    run("02_parse_doaj.py",    "Parse DOAJ CSV")

    # Step 2: Merge
    run("03_merge_datasets.py", "Merge Scimago + DOAJ on ISSN")

    # Step 3: Upsert (snapshots quartile history internally)
    run("04_seed_supabase.py",  "Upsert journals into Supabase (safe — IDs preserved)")

    # Step 4: Recompute quartile trends from updated history
    run("08_compute_trends.py", "Recompute quartile trends (rising/falling/stable)")

    print(f"\n{'='*60}")
    print("  Annual update complete.")
    print("  Next: optionally run 17_openalex_enrichment.py to refresh")
    print("  topics/works_count for new/changed journals (~90 min).")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
