"""Annual data refresh for JournalRadar — fully automated.

WHAT TO DO EACH YEAR (single command):
    cd scripts
    python 18_annual_update.py

That's it. No manual file downloads needed.

WHAT THIS SCRIPT DOES:
  Step 0: Download latest DOAJ + Scimago CSVs automatically
  Step 1: Parse Scimago CSV (auto-detects most recent year file)
  Step 2: Parse DOAJ CSV
  Step 3: Merge on ISSN
  Step 4: Upsert journals into Supabase — IDs never change, user data safe
          (also snapshots current quartiles → quartile_history before update)
  Step 5: Recompute quartile trends (rising/falling/stable)

IF Scimago blocks automated download:
  1. Go to https://www.scimagojr.com/journalrank.php
  2. Click 'Export to CSV'
  3. Save as scripts/data/scimagojr_<YEAR>.csv
  4. Re-run this script — it will skip the download and use your file.

SCHEDULE: Run once a year, around February (when Scimago releases new data).
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime

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
    print(f"  ✓ {label} done")


def main():
    print(f"\nJournalRadar Annual Update — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Step 0: Download sources (graceful — continues if Scimago is blocked
    #         and a local file already exists)
    print(f"\n{'='*60}")
    print("  Step 0: Download source data")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "00_download_sources.py")],
        check=False
    )
    if result.returncode != 0:
        # Scimago might be blocked but we may still have a local file — check
        scimago_files = sorted(DATA_DIR.glob("scimagojr_*.csv"), reverse=True)
        doaj_file = DATA_DIR / "doaj.csv"
        if not scimago_files or not doaj_file.exists():
            print("\nDownload failed and no local files found.")
            print("See manual instructions above.")
            sys.exit(1)
        print(f"\nDownload partially failed but local files found — continuing.")
        print(f"  Scimago: {scimago_files[0].name}")
        print(f"  DOAJ:    {doaj_file.name}")

    # Steps 1–5: Full pipeline
    run("01_parse_scimago.py",  "Step 1: Parse Scimago CSV")
    run("02_parse_doaj.py",     "Step 2: Parse DOAJ CSV")
    run("03_merge_datasets.py", "Step 3: Merge on ISSN")
    run("04_seed_supabase.py",  "Step 4: Upsert to Supabase (IDs preserved)")
    run("08_compute_trends.py", "Step 5: Recompute quartile trends")

    print(f"\n{'='*60}")
    print("  Annual update complete.")
    print()
    print("  Optional follow-up (run separately, takes ~90 min):")
    print("    python 17_openalex_enrichment.py")
    print("  This refreshes topics/works_count for new/changed journals.")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
