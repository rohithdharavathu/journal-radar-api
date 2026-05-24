# JournalRadar — Phase Tracker & Feature Status

> Last updated: 2026-05-15

---

## BUILD PHASES

| Phase | Status | Focus |
|-------|--------|-------|
| Phase 1 | ✅ Done | Scaffold + seed + deploy (Day 1) |
| Phase 2 | ✅ Done | Data fixes + OpenAlex + AI matcher + vector search |
| Phase 3 | ✅ Done | UI polish — tooltips, badges, compare, similar journals, waiver info, export |
| Phase 4 | ✅ Done | Scope fit API (Claude), APC PDF parsing, acceptance time enrichment, curated lists |
| Phase 5 | Planned | Pro tier (Stripe), email alerts, institutional pilot, mobile app |

---

## CURRENT STATE (End of Phase 4)

### What's live and working
- 30,000+ journals seeded in Supabase with quartile data, APC costs, topics
- Full-text websearch (title + publisher + subject + topics)
- AI abstract matcher (pgvector cosine similarity, FastAPI /match endpoint)
- Scope fit analysis via Claude (single + batch, cached)
- Similar journals by vector embedding
- Journal autocomplete suggestions
- All filters functional: quartile, APC, publishing model, acceptance time, country
- Currency toggle USD ↔ INR (₹83.5)
- Light/dark theme
- Google OAuth + bookmarks + feedback + report acceptance
- Submission tracker (/tracker)
- 10 curated expert lists (/lists, /lists/[slug])
- Journal comparison drawer (up to 3 journals)
- APC waiver info per publisher
- Export filtered results as CSV
- SEO meta tags + OG per journal page
- FastAPI live on Railway
- Frontend live on Vercel

### Known remaining gaps
| Issue | Status |
|-------|--------|
| Quartile history multi-year chart (visual) | Schema ready, partial data |
| Acceptance time histogram (rich) | Crowdsource filling in |
| Plagiarism limits | Deferred to Phase 5 |
| LaTeX/Word format template links | Deferred to Phase 5 |
| Monthly cron pipeline (auto data refresh) | Deferred to Phase 5 |
| Pro tier / Stripe | Deferred to Phase 5 |
| Admin panel | Deferred to Phase 5 |

---

## FEATURE GAP MATRIX: PRESENT → FINAL PRODUCT

### LAYER 1: DATA

| Feature | Phase 1 | Phase 2 | Phase 3-4 | Final |
|---------|---------|---------|-----------|-------|
| Quartile (Q1-Q4) | ❌ All null | ✅ Fixed | ✅ | ✅ + historical trajectory |
| APC cost | ⚠️ Partial | ✅ Fixed DOAJ merge | ✅ + Elsevier/Springer PDFs | ✅ + monthly scrape |
| Search coverage | ⚠️ Exact only | ✅ Websearch + topics | ✅ | ✅ |
| Topic tags | ❌ | ✅ OpenAlex | ✅ | ✅ + curated manual |
| Acceptance time | ❌ | ⚠️ Crowdsource starts | ✅ enriched | ✅ rich distribution |
| Waiver eligibility | ❌ | ❌ | ✅ Done | ✅ |
| APC from PDFs | ❌ | ❌ | ✅ Done | ✅ + monthly |
| Aims & scope text | ❌ | ❌ | ✅ Scraped | ✅ |
| Quartile trajectory | ❌ | ⚠️ Schema ready | ⚠️ Data partial | ✅ |
| Curated lists | ❌ | ❌ | ✅ 10 lists | ✅ 100+ lists |
| Manual critical journals | ❌ | ✅ 13 priority CS | ✅ | ✅ 1000+ |
| Data freshness | ❌ Static | ❌ Static | ❌ Static | ✅ Monthly cron |

### LAYER 2: SEARCH & DISCOVERY

| Feature | Phase 1 | Phase 2 | Phase 3-4 | Final |
|---------|---------|---------|-----------|-------|
| Keyword search | ⚠️ Exact | ✅ Websearch | ✅ | ✅ |
| AI abstract matcher | ❌ | ✅ Built | ✅ | ✅ + improved reranking |
| Scope fit (Claude) | ❌ | ❌ | ✅ Done | ✅ |
| Similar journals | ❌ | ❌ | ✅ Done | ✅ |
| Search autocomplete | ❌ | ✅ Basic | ✅ | ✅ |
| Curated list pages | ❌ | ❌ | ✅ Done | ✅ |
| Saved searches | ❌ | ❌ | ❌ | ✅ |

### LAYER 3: JOURNAL PROFILE

| Feature | Phase 1 | Phase 2 | Phase 3-4 | Final |
|---------|---------|---------|-----------|-------|
| Basic metadata | ✅ | ✅ | ✅ | ✅ |
| Quartile badge + history | ❌ Null | ✅ Fixed | ✅ | ✅ |
| APC display | ⚠️ Wrong | ✅ Fixed | ✅ | ✅ |
| Acceptance time display | ❌ | ⚠️ Partial | ✅ | ✅ |
| Waiver info | ❌ | ❌ | ✅ Done | ✅ |
| Similar journals panel | ❌ | ❌ | ✅ Done | ✅ |
| Indexing badges | ❌ | ❌ | ✅ Done | ✅ |
| SEO meta / OG tags | ⚠️ Basic | ✅ | ✅ | ✅ |
| Plagiarism limit | ❌ | ❌ | ❌ | ✅ |
| Format templates | ❌ | ❌ | ❌ | ✅ |

### LAYER 4: USER FEATURES

| Feature | Phase 1 | Phase 2 | Phase 3-4 | Final |
|---------|---------|---------|-----------|-------|
| Google Sign-In | ✅ | ✅ | ✅ | ✅ |
| Bookmarks | ✅ | ✅ | ✅ | ✅ |
| Report acceptance time | ✅ | ✅ | ✅ | ✅ |
| Report data issue | ✅ | ✅ | ✅ | ✅ |
| Export CSV | ❌ | ❌ | ✅ Done | ✅ |
| Compare journals | ❌ | ❌ | ✅ Done | ✅ |
| Submission tracker | ❌ | ❌ | ✅ Done | ✅ |
| Email alerts | ❌ | ❌ | ❌ | ✅ |
| Profile page | ❌ | ❌ | ❌ | ✅ |

### LAYER 5: PLATFORM

| Feature | Phase 1 | Phase 2 | Phase 3-4 | Final |
|---------|---------|---------|-----------|-------|
| Mobile responsive | ⚠️ Basic | ✅ | ✅ | ✅ |
| Performance / pagination | ✅ | ✅ | ✅ | ✅ |
| Pro tier (Stripe) | ❌ | ❌ | ❌ | ✅ |
| Admin panel | ❌ | ❌ | ❌ | ✅ |
| Data freshness cron | ❌ | ❌ | ❌ | ✅ |
| Institutional dashboard | ❌ | ❌ | ❌ | ✅ |

---

## PHASE 5 NEXT STEPS (Planned)

```
Week 1 — Data Freshness
  - Monthly cron pipeline (Scimago + DOAJ + OpenAlex sync)
  - Quartile history multi-year chart (frontend visual)
  - Rich acceptance time histogram (once enough crowdsource data)

Week 2 — Monetization
  - Stripe Pro tier ($5/mo)
  - Pro features: bulk export, API access, saved searches, email alerts

Week 3 — Platform
  - Admin panel (manage feedback, fix data issues)
  - User profile page (submission history, bookmarks)
  - APC change alerts

Week 4 — Growth
  - Plagiarism limits (LLM extract from author guidelines)
  - Format template links (LaTeX + Word)
  - Institutional pilot
```

---

## CRITICAL TECHNICAL RULES

- **shadcn/ui uses `@base-ui/react` NOT Radix UI** → no `asChild`; use `render={<Component/>}` pattern
- **NO FastAPI for search/filter** — Supabase JS client directly via PostgREST
- **APC for subscription** = "No author fee" never "$0"
- **All filters URL-param driven** (shareable URLs)
- **Light mode default**, dark mode opt-in
- **Next.js 16 breaking changes**: verify against node_modules docs before assuming API behavior
- **Slider `onValueChange`**: `(value: number | readonly number[], ...) => void`

---

## DATA PIPELINE RUN ORDER

```bash
# Core (must run in order)
python 01_parse_scimago.py
python 02_parse_doaj.py
python 03_merge_datasets.py
python 04_seed_supabase.py       # truncates first!

# Enrichment (can run independently after seeding)
python 05_enrich_openalex.py     # ~90 min for 30K
python 06_manual_additions.py
python 07_generate_embeddings.py # ~90 min, ~$0.10 cost
python 08_compute_trends.py
python 09_populate_waivers.py
python 10_fetch_impact_factors.py
python 11_scrape_aims_scope.py
python 12_seed_curated_lists.py
python 15_parse_apc_pdfs.py      # needs scripts/data/elsevier_apc.pdf, springer_apc.pdf
python 16_parse_acceptance_time.py
python 17_openalex_enrichment.py # comprehensive OpenAlex sync
```
