"""Download Scimago and DOAJ source CSVs automatically.

DOAJ: direct public CSV export — always works.
Scimago: uses requests with browser headers. If blocked, falls back to
         instructions for manual download (Scimago sometimes rate-limits bots).

Run standalone:
    python 00_download_sources.py

Or called from 18_annual_update.py as step 0.
"""
import os
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CURRENT_YEAR = datetime.now().year

# DOAJ — public direct export, no auth needed
DOAJ_URL = "https://doaj.org/csv"
DOAJ_OUT = DATA_DIR / "doaj.csv"

# Scimago — try multiple URL patterns they've used over the years
SCIMAGO_URLS = [
    f"https://www.scimagojr.com/journalrank.php?out=xls&year={CURRENT_YEAR}",
    f"https://www.scimagojr.com/journalrank.php?out=xls&year={CURRENT_YEAR - 1}",
]
SCIMAGO_OUT = DATA_DIR / f"scimagojr_{CURRENT_YEAR}.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.scimagojr.com/journalrank.php",
}


def download(url: str, dest: Path, label: str, timeout: int = 120) -> bool:
    print(f"  Downloading {label}...")
    print(f"  URL: {url}")
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=timeout) as r:
            if r.status_code == 200:
                content_type = r.headers.get("Content-Type", "")
                # Scimago returns XLS or CSV depending on version
                if "html" in content_type and label == "Scimago":
                    print(f"  Got HTML instead of CSV — likely blocked by anti-bot.")
                    return False
                with open(dest, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
                size_kb = dest.stat().st_size // 1024
                print(f"  ✓ Saved to {dest} ({size_kb} KB)")
                return True
            else:
                print(f"  HTTP {r.status_code} — download failed.")
                return False
    except requests.RequestException as e:
        print(f"  Request error: {e}")
        return False


def download_doaj() -> bool:
    print("\n[1/2] DOAJ")
    ok = download(DOAJ_URL, DOAJ_OUT, "DOAJ")
    if not ok:
        print("\n  DOAJ download failed. Manual fallback:")
        print("  1. Go to https://doaj.org/csv")
        print(f"  2. Save as: {DOAJ_OUT}")
    return ok


def download_scimago() -> bool:
    print("\n[2/2] Scimago")

    # Check if we already have this year's file
    if SCIMAGO_OUT.exists() and SCIMAGO_OUT.stat().st_size > 100_000:
        print(f"  Already have {SCIMAGO_OUT.name} ({SCIMAGO_OUT.stat().st_size // 1024} KB) — skipping.")
        return True

    # Also check for previous year's file as fallback
    prev_year_file = DATA_DIR / f"scimagojr_{CURRENT_YEAR - 1}.csv"

    for url in SCIMAGO_URLS:
        ok = download(url, SCIMAGO_OUT, "Scimago", timeout=180)
        if ok and SCIMAGO_OUT.stat().st_size > 100_000:
            return True
        time.sleep(3)

    # Scimago blocked — check if previous year file exists as a usable fallback
    if prev_year_file.exists():
        print(f"\n  Using previous year file as fallback: {prev_year_file.name}")
        shutil.copy(prev_year_file, SCIMAGO_OUT)
        print(f"  Copied to {SCIMAGO_OUT}")
        print("  NOTE: This is last year's Scimago data. Quartile trends may be one year behind.")
        return True

    print("\n  Scimago automated download failed. Manual steps:")
    print("  1. Go to https://www.scimagojr.com/journalrank.php")
    print("  2. Click 'Export to CSV' (bottom of page)")
    print(f"  3. Save as: {SCIMAGO_OUT}")
    print("  4. Re-run this script or 18_annual_update.py")
    return False


def main() -> bool:
    print(f"JournalRadar — Source Download ({CURRENT_YEAR})")
    doaj_ok = download_doaj()
    scimago_ok = download_scimago()

    print("\n" + "=" * 50)
    print(f"  DOAJ:    {'✓ OK' if doaj_ok else '✗ FAILED — manual download needed'}")
    print(f"  Scimago: {'✓ OK' if scimago_ok else '✗ FAILED — manual download needed'}")
    print("=" * 50)

    return doaj_ok and scimago_ok


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
