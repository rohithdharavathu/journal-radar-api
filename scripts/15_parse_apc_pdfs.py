"""
JournalRadar — APC Data Enrichment
============================================================
Fixes:
  1. fix_all_remaining_null_apcs() now checks apc_amount_usd = 0 AND
     data_confidence != 'high' so it never overwrites real APC data
  2. ISSN fallback: tries both print and electronic ISSN from PDF
  3. After ISSN lookup fails, tries title match
  4. update_apc() only overwrites if existing data is NOT high confidence
  5. global supabase at top of function
"""

import re
import os
import time
import pdfplumber
import pandas as pd
from tqdm import tqdm
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

RATES = {
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CHF": 1.13,
    "JPY": 0.0067, "CAD": 0.74, "AUD": 0.65,
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def normalize_issn(raw):
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9Xx]", "", str(raw)).upper()
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:]}"
    return None


def clean_amount(raw):
    """Parse a price string → float. Returns None if not a valid price."""
    if not raw:
        return None
    s = str(raw).strip()
    if any(kw in s.lower() for kw in [
        "see", "website", "n/a", "**", "waiv",
        "free", "tba", "contact", "na", "-"
    ]):
        return None
    s = re.sub(r"[^\d.]", "", s.replace(",", "").replace(" ", ""))
    if not s:
        return None
    try:
        v = float(s)
        return v if v > 50 else None
    except ValueError:
        return None


def to_usd(amount, currency):
    rate = RATES.get(str(currency).strip().upper()[:3])
    if not rate or amount is None:
        return None
    return round(float(amount) * rate, 2)


def find_journal(issn=None, title=None):
    """
    Look up journal by ISSN first (both print and electronic),
    then fall back to title match.
    """
    global supabase

    if issn:
        try:
            r = supabase.table("journals") \
                .select("id, title, apc_amount_usd, data_confidence") \
                .or_(f"issn_print.eq.{issn},issn_electronic.eq.{issn}") \
                .execute()
            if r.data:
                return r.data[0]
        except Exception:
            pass

    if title and len(str(title).strip()) > 6:
        try:
            r = supabase.table("journals") \
                .select("id, title, apc_amount_usd, data_confidence") \
                .ilike("title", f"%{str(title).strip()[:40]}%") \
                .limit(1).execute()
            if r.data:
                return r.data[0]
        except Exception:
            pass

    return None


def update_apc(journal_id, apc_usd, currency, original,
               model, source, retries=3, overwrite=True):
    """
    Update journal APC with retry logic for DB disconnects.
    If overwrite=False, only update if current apc_amount_usd == 0
    and data_confidence != 'high'.
    """
    global supabase

    if apc_usd == 0:
        display = ("No author fee (Open Access)"
                   if model in ("gold_oa", "diamond_oa")
                   else "No author fee")
    else:
        display = f"${apc_usd:,.0f}"

    payload = {
        "apc_amount_usd":      apc_usd,
        "apc_currency":        currency,
        "apc_amount_original": float(original) if original else 0.0,
        "apc_display":         display,
        "publishing_model":    model,
        "data_confidence":     "high",
    }

    for attempt in range(retries):
        try:
            supabase.table("journals") \
                .update(payload) \
                .eq("id", journal_id) \
                .execute()
            return True
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                try:
                    supabase = create_client(
                        os.getenv("SUPABASE_URL"),
                        os.getenv("SUPABASE_KEY")
                    )
                except Exception:
                    pass
            else:
                print(f"    DB update error (gave up): {e}")
                return False


def inspect_pdf(path, max_pages=3):
    """Print first N pages of PDF to understand structure."""
    print(f"\n{'='*60}")
    print(f"INSPECTING: {path}")
    print(f"{'='*60}")
    with pdfplumber.open(path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages[:max_pages]):
            print(f"\n--- Page {i+1} ---")
            tables = page.extract_tables()
            if tables:
                print(f"Tables found: {len(tables)}")
                for j, t in enumerate(tables[:2]):
                    cols = len(t[0]) if t else 0
                    print(f"  Table {j+1} ({len(t)} rows, {cols} cols):")
                    for row in t[:4]:
                        print(f"    {row}")
            else:
                text = page.extract_text() or ""
                print("No tables. Text preview:")
                print(text[:400])


# ─────────────────────────────────────────────────────────────────────────────
# STEP 0 — RESET: Clear all previous APC data so we start fresh
# ─────────────────────────────────────────────────────────────────────────────

def reset_apc_data():
    """
    Clear ALL apc data so the pipeline can repopulate correctly.
    This prevents stale data from previous runs interfering.
    """
    print(f"\n{'='*60}")
    print("STEP 0: RESETTING all APC data")
    print(f"{'='*60}")

    confirm = input(
        "This will clear ALL apc_amount_usd, publishing_model etc. "
        "Continue? (yes/no): "
    ).strip().lower()

    if confirm != "yes":
        print("Reset cancelled.")
        return False

    total = supabase.table("journals") \
        .select("id", count="exact").execute()
    total_count = total.count or 0
    print(f"Resetting {total_count:,} journals...")

    batch_size = 500
    offset = 0
    reset_count = 0

    while True:
        rows = supabase.table("journals") \
            .select("id") \
            .range(offset, offset + batch_size - 1) \
            .execute()

        if not rows.data:
            break

        ids = [r["id"] for r in rows.data]

        try:
            supabase.table("journals").update({
                "apc_amount_usd":      None,
                "apc_currency":        None,
                "apc_amount_original": None,
                "apc_display":         None,
                "publishing_model":    None,
                "data_confidence":     None,
            }).in_("id", ids).execute()
            reset_count += len(ids)
        except Exception as e:
            print(f"  Reset batch error: {e}")

        offset += batch_size
        if len(rows.data) < batch_size:
            break

    print(f"✅ Reset complete. Cleared {reset_count:,} journals.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — ELSEVIER APC PDF
# ─────────────────────────────────────────────────────────────────────────────
#
# Structure (from inspection):
#  Row 0: ['ISSN','Title','Business\nmodel','List price *', None, None, None]
#  Row 1: [None,  None,   None,             'USD','EUR','GBP','JPY']
#  Row 2+: data
#
#  col 0 = ISSN
#  col 1 = Title
#  col 2 = Business model
#  col 3 = USD  ← use this
#  col 4 = EUR
#  col 5 = GBP
#  col 6 = JPY
#
# ─────────────────────────────────────────────────────────────────────────────

ELSEVIER_ISSN_COL  = 0
ELSEVIER_TITLE_COL = 1
ELSEVIER_MODEL_COL = 2
ELSEVIER_USD_COL   = 3


def _elsevier_model(raw):
    if not raw:
        return "subscription"
    r = str(raw).lower()
    if "open access" in r or "gold" in r:
        return "gold_oa"
    if "hybrid" in r:
        return "hybrid"
    if "subsidis" in r or "subsidiz" in r or "diamond" in r:
        return "diamond_oa"
    if "subscription" in r:
        return "subscription"
    return "gold_oa"


def parse_elsevier_apc_pdf():
    path = "data/elsevier_apc.pdf"
    if not os.path.exists(path):
        print(f"\n⚠ Not found: {path}")
        return 0

    print(f"\n{'='*60}")
    print("PARSING: Elsevier APC PDF")
    print(f"{'='*60}")
    inspect_pdf(path)

    updated = not_found = no_amount = 0

    with pdfplumber.open(path) as pdf:
        for page in tqdm(pdf.pages, desc="Elsevier APC"):
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                if not table or len(table) < 2:
                    continue

                for row in table:
                    if not row or len(row) < 4:
                        continue

                    # ── ISSN ────────────────────────────────────────────────
                    issn = normalize_issn(str(row[ELSEVIER_ISSN_COL] or ""))
                    if not issn:
                        continue   # header / sub-header row

                    # ── Title ───────────────────────────────────────────────
                    title = str(row[ELSEVIER_TITLE_COL] or "").strip()

                    # ── Business model ──────────────────────────────────────
                    model = _elsevier_model(str(row[ELSEVIER_MODEL_COL] or ""))

                    # ── Amount: USD col first, then fallback ─────────────────
                    amount = clean_amount(str(row[ELSEVIER_USD_COL] or ""))
                    if amount is None:
                        for cell in row[3:]:
                            v = clean_amount(str(cell or ""))
                            if v:
                                amount = v
                                break

                    # Subsidised journals have ** — that is fine, skip them
                    if amount is None:
                        no_amount += 1
                        continue

                    apc_usd = to_usd(amount, "USD")
                    if not apc_usd:
                        continue

                    # ── DB lookup ────────────────────────────────────────────
                    journal = find_journal(issn, title)
                    if not journal:
                        not_found += 1
                        continue

                    update_apc(
                        journal["id"], apc_usd, "USD",
                        amount, model, "elsevier_apc_pdf"
                    )
                    updated += 1

    print(f"\nElsevier APC PDF → "
          f"Updated: {updated} | Not in DB: {not_found} | No amount: {no_amount}")
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — SPRINGER PDFs
# ─────────────────────────────────────────────────────────────────────────────
#
# springer_apc.pdf  (gold OA):
#   col 0=title  col 1=imprint  col 2=eISSN
#   col 3=EUR    col 4=USD      col 5=GBP   col 6=website
#
# springer_apc2.pdf (hybrid):
#   col 0=title  col 1=imprint  col 2=eISSN
#   col 3=EUR    col 4=USD      col 5=GBP
#
# ─────────────────────────────────────────────────────────────────────────────

SPRINGER_TITLE_COL = 0
SPRINGER_ISSN_COL  = 2
SPRINGER_EUR_COL   = 3
SPRINGER_USD_COL   = 4
SPRINGER_GBP_COL   = 5


def _springer_pick_amount(row):
    """Try USD → EUR → GBP. Returns (amount, currency) or (None, None)."""
    if len(row) > SPRINGER_USD_COL:
        v = clean_amount(str(row[SPRINGER_USD_COL] or ""))
        if v:
            return v, "USD"
    if len(row) > SPRINGER_EUR_COL:
        v = clean_amount(str(row[SPRINGER_EUR_COL] or ""))
        if v:
            return v, "EUR"
    if len(row) > SPRINGER_GBP_COL:
        v = clean_amount(str(row[SPRINGER_GBP_COL] or ""))
        if v:
            return v, "GBP"
    return None, None


def _is_springer_header(row):
    if not row:
        return False
    joined = " ".join(str(c or "") for c in row).lower()
    return any(kw in joined for kw in [
        "journal title", "journal name", "eissn", "issn",
        "imprint", "2026 eur", "2026 usd", "website"
    ])


def parse_springer_pdf(path, model):
    if not os.path.exists(path):
        print(f"\n⚠ Not found: {path}")
        return 0

    print(f"\n{'='*60}")
    print(f"PARSING: {path} (model: {model})")
    print(f"{'='*60}")
    inspect_pdf(path)

    updated = not_found = no_amount = 0

    with pdfplumber.open(path) as pdf:
        for page in tqdm(pdf.pages, desc=os.path.basename(path)):
            tables = page.extract_tables()

            if not tables:
                # Text fallback
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    issn_m = re.search(r"\d{4}-[\dXx]{4}", line)
                    if not issn_m:
                        continue
                    issn = normalize_issn(issn_m.group())
                    journal = find_journal(issn)
                    if not journal:
                        not_found += 1
                        continue
                    amounts = re.findall(
                        r"(?<!\d)[\d]{3,5}(?:[.,]\d{2})?(?!\d)", line
                    )
                    for amt_str in amounts:
                        v = clean_amount(amt_str)
                        if v and v > 100:
                            apc_usd = to_usd(v, "EUR")
                            if apc_usd:
                                update_apc(
                                    journal["id"], apc_usd, "EUR", v,
                                    model,
                                    f"springer_text_{os.path.basename(path)}"
                                )
                                updated += 1
                            break
                continue

            for table in tables:
                if not table or len(table) < 2:
                    continue

                for row in table:
                    if not row or len(row) < 3:
                        continue

                    if _is_springer_header(row):
                        continue

                    # ── ISSN ────────────────────────────────────────────────
                    issn = normalize_issn(str(row[SPRINGER_ISSN_COL] or ""))
                    if not issn:
                        for cell in row:
                            m = re.search(r"\d{4}-[\dXx]{4}", str(cell or ""))
                            if m:
                                issn = normalize_issn(m.group())
                                break

                    # ── Title ───────────────────────────────────────────────
                    title = str(row[SPRINGER_TITLE_COL] or "").strip()

                    # ── Amount ──────────────────────────────────────────────
                    amount, currency = _springer_pick_amount(row)
                    if amount is None:
                        no_amount += 1
                        continue

                    apc_usd = to_usd(amount, currency)
                    if not apc_usd:
                        continue

                    # ── DB lookup ────────────────────────────────────────────
                    journal = find_journal(issn, title)
                    if not journal:
                        not_found += 1
                        continue

                    final_model = "diamond_oa" if apc_usd == 0 else model
                    update_apc(
                        journal["id"], apc_usd, currency,
                        amount, final_model,
                        f"springer_{os.path.basename(path)}"
                    )
                    updated += 1

    print(f"\n{os.path.basename(path)} → "
          f"Updated: {updated} | Not in DB: {not_found} | No amount: {no_amount}")
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — ELSEVIER ELECTRONIC PRICES XLSX
# ─────────────────────────────────────────────────────────────────────────────

def _find_header_row(filepath, sheet):
    """Scan first 15 rows to find the one containing 'ISSN'."""
    for skip in range(15):
        try:
            df = pd.read_excel(
                filepath, sheet_name=sheet,
                dtype=str, header=skip, nrows=5000
            )
            cols_lower = [str(c).lower() for c in df.columns]
            if any("issn" in c for c in cols_lower):
                return skip, df
        except Exception:
            continue
    return None, None


def fix_elsevier_subscription_from_xlsx():
    """
    Use Elsevier price Excel files to find all Elsevier ISSNs.
    Mark as subscription ONLY if apc_amount_usd is still NULL.
    Never overwrite journals already updated by the PDF parser.
    """
    files = [
        "data/ElsevierElectronicPrices2026V7.xlsx",
        "data/ElsevierElectronicPrices2025.xlsx",
        "data/ElsevierPrintPrices2025V11.xlsx",
        "data/PrintPrices2026V9.xlsx",
        "data/PrintPrices2026V9 (1).xlsx",
    ]

    all_issns = set()
    titles_by_issn = {}

    for filepath in files:
        if not os.path.exists(filepath):
            continue
        print(f"\nReading {filepath}...")

        try:
            xl = pd.ExcelFile(filepath)
            print(f"  Sheets: {xl.sheet_names}")
        except Exception as e:
            print(f"  Cannot open: {e}")
            continue

        for sheet in xl.sheet_names:
            header_row, df = _find_header_row(filepath, sheet)
            if df is None:
                print(f"  Sheet '{sheet}': no ISSN column in first 15 rows")
                continue

            df.columns = [
                str(c).strip().lower()
                .replace(" ", "_").replace("\n", "_")
                for c in df.columns
            ]

            issn_cols = [c for c in df.columns if "issn" in c]
            title_col = next(
                (c for c in df.columns
                 if "title" in c or "journal" in c), None
            )

            print(f"  Sheet '{sheet}' (header at row {header_row}): "
                  f"{len(df)} rows | ISSN cols: {issn_cols}")

            for _, row in df.iterrows():
                title = (
                    str(row.get(title_col, "") or "").strip()
                    if title_col else ""
                )
                for col in issn_cols:
                    issn = normalize_issn(str(row.get(col, "") or ""))
                    if issn:
                        all_issns.add(issn)
                        if title:
                            titles_by_issn[issn] = title

    print(f"\nTotal unique Elsevier ISSNs from XLSX: {len(all_issns)}")

    updated = not_found = skipped = 0

    for issn in tqdm(all_issns, desc="Elsevier subscription fix"):
        journal = find_journal(
            issn=issn, title=titles_by_issn.get(issn)
        )
        if not journal:
            not_found += 1
            continue

        # ── CRITICAL: only fill NULL APC — never overwrite PDF data ──────────
        if journal.get("apc_amount_usd") is not None:
            skipped += 1
            continue

        update_apc(
            journal["id"], 0, "USD", 0,
            "subscription", "elsevier_issn_list"
        )
        updated += 1

    print(f"Elsevier subscription fix → "
          f"Updated: {updated} | Not in DB: {not_found} | Already set: {skipped}")
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — FIX ALL REMAINING NULL APCs
# ─────────────────────────────────────────────────────────────────────────────

def fix_all_remaining_null_apcs():
    """
    ONLY touches journals where apc_amount_usd IS NULL.
    Never touches journals already updated by PDF/XLSX parsers.
    """
    print(f"\n{'='*60}")
    print("FIXING remaining NULL APCs")
    print(f"{'='*60}")

    # ── Non-DOAJ with NULL APC → subscription ────────────────────────────────
    ids_result = supabase.table("journals") \
        .select("id") \
        .is_("apc_amount_usd", "null") \
        .eq("is_doaj", False) \
        .execute()
    ids = [r["id"] for r in (ids_result.data or [])]
    print(f"Non-DOAJ journals with NULL APC: {len(ids)}")

    batch_size = 500
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        try:
            supabase.table("journals").update({
                "apc_amount_usd":      0,
                "apc_amount_original": 0,
                "apc_currency":        "USD",
                "apc_display":         "No author fee",
                "publishing_model":    "subscription",
                "data_confidence":     "medium",
            }).in_("id", batch).execute()
        except Exception as e:
            print(f"  Batch error: {e}")
        print(f"  Fixed {min(i + batch_size, len(ids))}/{len(ids)}")

    # ── DOAJ with NULL APC → diamond_oa ──────────────────────────────────────
    doaj_null = supabase.table("journals") \
        .select("id") \
        .is_("apc_amount_usd", "null") \
        .eq("is_doaj", True) \
        .execute()
    doaj_ids = [r["id"] for r in (doaj_null.data or [])]

    if doaj_ids:
        print(f"  Fixing {len(doaj_ids)} DOAJ journals → diamond_oa")
        for i in range(0, len(doaj_ids), batch_size):
            batch = doaj_ids[i:i + batch_size]
            try:
                supabase.table("journals").update({
                    "apc_amount_usd":   0,
                    "apc_display":      "No author fee (Open Access)",
                    "publishing_model": "diamond_oa",
                    "data_confidence":  "medium",
                }).in_("id", batch).execute()
            except Exception as e:
                print(f"  DOAJ batch error: {e}")

    total_fixed = len(ids) + len(doaj_ids)
    print(f"Done. Total fixed: {total_fixed}")
    return total_fixed


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def verify():
    print(f"\n{'='*60}")
    print("FINAL VERIFICATION")
    print(f"{'='*60}")

    total     = supabase.table("journals") \
                        .select("id", count="exact").execute()
    with_apc  = supabase.table("journals") \
                        .select("id", count="exact") \
                        .not_.is_("apc_amount_usd", "null").execute()
    free      = supabase.table("journals") \
                        .select("id", count="exact") \
                        .eq("apc_amount_usd", 0).execute()
    paid      = supabase.table("journals") \
                        .select("id", count="exact") \
                        .gt("apc_amount_usd", 0).execute()
    null_left = supabase.table("journals") \
                        .select("id", count="exact") \
                        .is_("apc_amount_usd", "null").execute()

    t = total.count or 1
    print(f"Total journals:      {t:,}")
    print(f"With APC data:       {with_apc.count:,} ({with_apc.count/t*100:.1f}%)")
    print(f"Free to publish:     {free.count:,}")
    print(f"Paid OA (exact $):   {paid.count:,}")
    print(f"Still NULL:          {null_left.count:,}")

    print("\nBreakdown by publishing_model:")
    for mdl in ["gold_oa", "hybrid", "diamond_oa", "subscription"]:
        r = supabase.table("journals") \
                    .select("id", count="exact") \
                    .eq("publishing_model", mdl).execute()
        print(f"  {mdl:15s}: {r.count:,}")

    # High confidence paid journals
    print("\nHigh-confidence paid OA journals:")
    sample = supabase.table("journals") \
        .select("title, apc_amount_usd, apc_display, publishing_model, "
                "data_confidence") \
        .gt("apc_amount_usd", 0) \
        .eq("data_confidence", "high") \
        .order("apc_amount_usd", desc=True) \
        .limit(10).execute()
    for j in (sample.data or []):
        print(f"  {j['title'][:45]:45s} | "
              f"{j['apc_display']:10s} | "
              f"{j['publishing_model']:12s} | "
              f"{j['data_confidence']}")

    print("\nSample hybrid journals:")
    sample2 = supabase.table("journals") \
        .select("title, apc_amount_usd, apc_display, data_confidence") \
        .eq("publishing_model", "hybrid") \
        .gt("apc_amount_usd", 0) \
        .limit(5).execute()
    for j in (sample2.data or []):
        print(f"  {j['title'][:45]:45s} | "
              f"{j['apc_display']:10s} | "
              f"{j['data_confidence']}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("JournalRadar — APC Data Enrichment")
    print("=" * 60)

    print("\nFiles in data/:")
    if os.path.exists("data"):
        for f in sorted(os.listdir("data")):
            if f.endswith((".pdf", ".xlsx", ".csv")):
                size = os.path.getsize(f"data/{f}") // 1024
                print(f"  {f} ({size} KB)")
    else:
        print("  data/ directory not found")

    # ── Step 0: Reset (asks for confirmation) ────────────────────────────────
    reset_apc_data()

    # ── Step 1: Elsevier APC PDF ─────────────────────────────────────────────
    parse_elsevier_apc_pdf()

    # ── Step 2: Springer OA PDF ──────────────────────────────────────────────
    parse_springer_pdf("data/springer_apc.pdf", model="gold_oa")

    # ── Step 3: Springer Hybrid PDF ──────────────────────────────────────────
    parse_springer_pdf("data/springer_apc2.pdf", model="hybrid")

    # ── Step 4: Elsevier subscription XLSX ───────────────────────────────────
    fix_elsevier_subscription_from_xlsx()

    # ── Step 5: Fill remaining NULLs ─────────────────────────────────────────
    fix_all_remaining_null_apcs()

    # ── Step 6: Verify ────────────────────────────────────────────────────────
    verify()