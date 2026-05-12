# JournalRadar — Phase 2 Lock + Feature Gap Analysis

---

## CURRENT STATE (End of Phase 1)

### What works
- 30,000 journals seeded in Supabase
- All pages load (/, /journal/[id], /report, /about, /login)
- Google OAuth configured
- Supabase RLS policies active
- Deployed on Vercel + Supabase
- Basic journal cards rendering
- Feedback modal per card (UI exists)
- Exit feedback form (UI exists)
- Currency toggle USD ↔ INR (UI exists)
- Theme toggle light ↔ dark (UI exists)

### What's broken
| Issue | Root Cause |
|-------|-----------|
| Quartile = None for all 30K journals | Parser not extracting from "Subject (Q1)" string in Scimago CSV |
| APC shows "No author fee" for almost all | Paid OA journals not matching DOAJ due to ISSN mismatch |
| Search = exact match only | Supabase textSearch using plain mode not websearch mode |
| Filters not working meaningfully | Downstream of broken quartile + APC data |
| Deep search missing (image forensics, deepfakes) | search_vector only indexes title/publisher/subject — no topic-level tags |

---

## PHASE 2 — LOCKED SCOPE

### P2.1 — Data Fixes (critical, do first)
- [ ] Fix quartile extraction in `01_parse_scimago.py` (regex from "Subject (Q1)" string)
- [ ] Fix ISSN matching in `03_merge_datasets.py` (handle None print ISSNs, match on electronic only)
- [ ] Fix search mode in `queries.ts` (plain → websearch)
- [ ] Reseed database after fixes (run 01 → 03 → 04)
- [ ] Verify: quartile distribution across Q1/Q2/Q3/Q4 looks real
- [ ] Verify: APC data shows paid journals correctly (IEEE Access $2,160 etc.)

### P2.2 — OpenAlex Enrichment
- [ ] Run `05_enrich_openalex.py` for all 30K journals
- [ ] Adds: homepage_url, works_count, works_recent_2yr, topic hierarchy
- [ ] Rebuild search_vector to include topics (SQL migration in Supabase)
- [ ] Test: "image forensics", "deepfake detection", "natural language processing" all return relevant results

### P2.3 — Search Enhancement
- [ ] Websearch mode fix (unblocks fuzzy + phrase search)
- [ ] Search now covers: title + publisher + subject_area + subject_category + topics
- [ ] Add search suggestions / autocomplete (top matching journal names as you type)

### P2.4 — AI Abstract Matcher (flagship feature)
- [ ] FastAPI service (Python) — comes back now that data is clean
- [ ] Endpoint: POST /match — accepts abstract text, returns top 10 journals
- [ ] Embedding model: text-embedding-3-small (OpenAI) or nomic-embed-text (free local)
- [ ] Journal embeddings: generate from scope description + subject tags + recent paper titles
- [ ] Store embeddings in pgvector column in Supabase
- [ ] Similarity search: cosine distance on abstract embedding vs journal embeddings
- [ ] Post-filter by user prefs: max APC, min quartile
- [ ] Frontend: "Match my abstract" button on homepage → paste modal → ranked results
- [ ] Each result shows: match score, why it matched, APC, quartile, acceptance time

### P2.5 — Acceptance Time Crowdsource Display
- [ ] Aggregate reports per journal (once faculty start submitting)
- [ ] Show on journal card: "~8 weeks (12 reports)"
- [ ] Show on profile: distribution bar (fast <8 / medium 8-16 / slow 16+)
- [ ] Trigger avg_acceptance_weeks update on new report insert (Supabase trigger or script)

### P2.6 — Missing Domains Fix
- [ ] Audit which subject areas are underrepresented
- [ ] Manually add high-priority journals missing from Scimago/DOAJ:
  - IEEE TIFS, Pattern Recognition, Expert Systems with Applications
  - Nature, Science, Lancet (top-tier across domains)
  - Key Indian journals (for faculty testers)
- [ ] Create `scripts/06_manual_additions.py` — curated list of ~200 critical journals with hand-verified data

---

## FULL FEATURE GAP: PRESENT → FINAL PRODUCT

### LAYER 1: DATA (foundation)

| Feature | Present | Phase 2 | Final Product |
|---------|---------|---------|---------------|
| Quartile (Q1-Q4) | ❌ All null | ✅ Fixed | ✅ + historical trajectory |
| APC cost | ⚠️ Partial (subscription only) | ✅ Fixed DOAJ merge | ✅ + monthly scrape updates |
| Search coverage | ⚠️ Exact match only | ✅ Websearch + topics | ✅ + semantic/embedding search |
| Topic tags | ❌ Missing | ✅ OpenAlex enrichment | ✅ + curated manual tags |
| Acceptance time | ❌ No data | ⚠️ Crowdsource starts | ✅ Rich distribution data |
| Plagiarism limits | ❌ Missing | ❌ Deferred | ✅ LLM-extracted from guidelines |
| Format templates | ❌ Missing | ❌ Deferred | ✅ LaTeX + Word template links |
| Waiver eligibility | ❌ Missing | ❌ Deferred | ✅ Per-publisher waiver rules |
| Predatory risk score | ❌ Missing | ❌ Deferred | ✅ Multi-signal scoring |
| APC history | ❌ Missing | ❌ Deferred | ✅ Price change tracking |
| Quartile trajectory | ❌ Missing | ⚠️ Schema ready | ✅ Multi-year chart |
| Manual curated journals | ❌ Missing | ✅ ~200 critical | ✅ 1000+ curated |
| Data freshness | ❌ Static | ❌ Still static | ✅ Monthly cron pipeline |

### LAYER 2: SEARCH & DISCOVERY

| Feature | Present | Phase 2 | Final Product |
|---------|---------|---------|---------------|
| Keyword search | ⚠️ Exact only | ✅ Websearch mode | ✅ Semantic + keyword hybrid |
| Subject filter | ⚠️ Data broken | ✅ Fixed | ✅ + multi-select |
| Quartile filter | ⚠️ Data broken | ✅ Fixed | ✅ |
| APC filter | ⚠️ Data broken | ✅ Fixed | ✅ + INR slider |
| Publishing model filter | ⚠️ Data broken | ✅ Fixed | ✅ |
| Acceptance time filter | ❌ No data | ⚠️ Partial | ✅ |
| Country filter | ✅ Works | ✅ | ✅ |
| Publisher filter | ✅ Works | ✅ | ✅ |
| AI abstract matcher | ❌ Missing | ✅ Built | ✅ + improved reranking |
| Search autocomplete | ❌ Missing | ✅ Basic | ✅ Rich suggestions |
| Saved searches | ❌ Missing | ❌ Deferred | ✅ |
| Similar journals | ❌ Missing | ❌ Deferred | ✅ "Journals like this" |

### LAYER 3: JOURNAL PROFILE

| Feature | Present | Phase 2 | Final Product |
|---------|---------|---------|---------------|
| Basic metadata | ✅ | ✅ | ✅ |
| Quartile badge | ❌ Null data | ✅ Fixed | ✅ |
| APC display | ⚠️ Wrong | ✅ Fixed | ✅ |
| Quartile history | ⚠️ Schema ready, no data | ⚠️ Partial | ✅ Multi-year chart |
| Acceptance time distribution | ❌ No data | ⚠️ Starts filling | ✅ Rich histogram |
| Plagiarism limit | ❌ Missing | ❌ Deferred | ✅ |
| Format template links | ❌ Missing | ❌ Deferred | ✅ LaTeX + Word |
| Recent papers | ❌ Missing | ✅ OpenAlex | ✅ Last 5 papers with DOI |
| Rejection rate | ❌ Missing | ❌ Deferred | ✅ Crowdsourced |
| Editorial board | ❌ Missing | ❌ Deferred | ✅ |
| Scimago link | ✅ | ✅ | ✅ |
| Author guidelines link | ⚠️ Partial | ✅ DOAJ enriched | ✅ |
| Submit paper link | ✅ (homepage) | ✅ | ✅ |

### LAYER 4: USER FEATURES

| Feature | Present | Phase 2 | Final Product |
|---------|---------|---------|---------------|
| Google Sign-In | ✅ | ✅ | ✅ |
| Bookmarks | ✅ Schema + UI | ✅ | ✅ |
| Report acceptance time | ✅ UI exists | ✅ | ✅ |
| Report data issue | ✅ UI exists | ✅ | ✅ |
| Exit feedback | ✅ UI exists | ✅ | ✅ |
| Submission tracker | ❌ Missing | ❌ Deferred | ✅ Track submit → decision |
| Email alerts (APC change) | ❌ Missing | ❌ Deferred | ✅ |
| Delisting alerts | ❌ Missing | ❌ Deferred | ✅ |
| Export (CSV/BibTeX) | ❌ Missing | ❌ Deferred | ✅ |
| Comparison table | ❌ Missing | ❌ Deferred | ✅ Compare 3 journals side-by-side |
| Profile page | ❌ Missing | ❌ Deferred | ✅ Submission history, bookmarks |

### LAYER 5: PLATFORM

| Feature | Present | Phase 2 | Final Product |
|---------|---------|---------|---------------|
| SEO meta tags | ⚠️ Basic | ✅ Per journal page | ✅ Full OG + schema.org |
| Static journal pages (SSG) | ❌ Dynamic only | ✅ | ✅ 30K static pages |
| Mobile responsive | ⚠️ Basic | ✅ Polish pass | ✅ |
| Performance (pagination) | ✅ | ✅ | ✅ + infinite scroll option |
| Pro tier (Stripe) | ❌ | ❌ Deferred | ✅ $5/mo |
| Institutional dashboard | ❌ | ❌ Deferred | ✅ |
| API access (Pro) | ❌ | ❌ Deferred | ✅ |
| Admin panel | ❌ | ❌ Deferred | ✅ Manage feedback, data |
| Data freshness cron | ❌ Static | ❌ Deferred | ✅ Monthly auto-update |
| Multi-language | ❌ | ❌ Deferred | ✅ v3 |

---

## PHASE SUMMARY

| Phase | Status | Focus |
|-------|--------|-------|
| Phase 1 | ✅ Done | Scaffold + seed + deploy |
| Phase 2 | 🔒 Locked | Data fixes + OpenAlex + AI matcher + search |
| Phase 3 | Planned | UI polish + plagiarism + format templates + submission tracker |
| Phase 4 | Planned | Pro tier + Stripe + institutional + cron pipeline |
| Phase 5 | Planned | Mobile app + multi-language + API |

---

## PHASE 2 BUILD ORDER

```
Week 1 — Data
  Day 1: Fix quartile parser + ISSN merge + reseed
  Day 2: Run OpenAlex enrichment + rebuild search_vector
  Day 3: Manual additions (200 critical journals)
  Day 4: Verify all filters work correctly

Week 2 — AI Matcher
  Day 1: FastAPI setup + embedding generation for all journals
  Day 2: /match endpoint + pgvector similarity search
  Day 3: Frontend integration (paste abstract modal + results)
  Day 4: Testing + tuning

Week 3 — Polish + Launch push
  Day 1: Search autocomplete
  Day 2: Acceptance time display + crowdsource aggregation
  Day 3: SEO meta tags + static generation
  Day 4: Share widely — LinkedIn, Reddit, ResearchGate
```
