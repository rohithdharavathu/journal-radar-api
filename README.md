# JournalRadar

> Every Scopus journal. One search.

A free, filterable search engine for 30,000+ Scopus-indexed academic journals. Find the right journal to publish in by filtering on APC cost, quartile ranking, subject area, publishing model, and acceptance time.

## Features

- **Search** — Full-text search (websearch mode) across title, publisher, subject area, ISSN, and OpenAlex topics
- **Filters** — Q1–Q4 quartiles, APC range (USD/INR), publishing model, subject area, acceptance time, country
- **AI Abstract Matcher** — Paste your abstract → ranked top-10 journals by semantic similarity (pgvector + OpenAI embeddings)
- **Scope Fit Analysis** — Claude evaluates how well your abstract fits a specific journal
- **Currency toggle** — USD / INR (₹83.5 fixed rate)
- **Journal profiles** — APC, SJR score, H-index, quartile history, acceptance data, recent papers, indexing badges
- **Community reports** — Crowdsourced acceptance timelines from researchers
- **Curated lists** — 10 expert-curated collections (CS Q1, free OA, fast acceptance, Indian researchers, etc.)
- **Compare journals** — Side-by-side comparison of up to 3 journals
- **Similar journals** — "Journals like this" powered by vector embeddings
- **Waiver info** — APC waiver eligibility per publisher
- **Export** — Download filtered results as CSV
- **Bookmarks** — Save journals (requires sign-in)
- **Submission tracker** — Track your paper's journey from submit → decision
- **Dark mode** — Toggle via header button

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16 (App Router) + React 19 + TypeScript |
| UI | Tailwind CSS 4 + shadcn/ui (base-ui variant) |
| Database | Supabase (PostgreSQL 15 + PostgREST + pgvector + Auth) |
| Backend API | FastAPI (Python, Railway hosted) |
| AI | OpenAI (text-embedding-3-small, gpt-4o-mini) + Anthropic Claude (scope-fit) |
| Data pipeline | Python 3.11 (pandas, requests, supabase-py) |
| Hosting | Vercel (frontend) + Railway (API) + Supabase (database) |
| Auth | Google Sign-In via Supabase Auth |

## Repo Structure

```
journal-radar/
├── frontend/          # Next.js 16 app (Vercel)
│   ├── app/           # App Router pages
│   ├── components/    # 40+ React components
│   └── lib/           # Supabase client, queries, types, API client
├── api/               # FastAPI service (Railway)
│   └── main.py        # /match, /scope-fit, /similar, /autocomplete endpoints
├── scripts/           # Python data pipeline (17 scripts)
│   └── data/          # Source CSVs + intermediate JSON files
├── supabase/          # Database schema SQL files
│   ├── schema.sql          # Phase 1: core tables, RLS, full-text search
│   └── schema_phase2.sql   # Phase 2: pgvector, embeddings, submissions, RPC
└── README.md
```

## Running Locally

### Frontend

```bash
cd frontend
cp ../.env.example .env.local
# Fill in NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_FASTAPI_URL
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Backend API (FastAPI)

```bash
cd api
pip install -r requirements.txt
cp ../.env.example .env
# Fill in SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
uvicorn main:app --reload
```

API runs at [http://localhost:8000](http://localhost:8000).

### Data Pipeline

```bash
cd scripts
pip install -r requirements.txt

# Place source files in scripts/data/
# - scimagojr_2025.csv  (from https://www.scimagojr.com/journalrank.php)
# - doaj.csv            (from https://doaj.org/csv)

# Core pipeline (in order)
python 01_parse_scimago.py       # Scimago CSV → clean JSON
python 02_parse_doaj.py          # DOAJ CSV → clean JSON
python 03_merge_datasets.py      # Merge on ISSN → journals_merged.json
python 04_seed_supabase.py       # Seed Supabase (truncates first)

# Enrichment (run after seeding)
python 05_enrich_openalex.py     # OpenAlex: topics, works_count, homepage_url
python 06_manual_additions.py    # 13 priority CS journals
python 07_generate_embeddings.py # OpenAI text-embedding-3-small (1536-dim vectors)
python 08_compute_trends.py      # Quartile trajectory analysis
python 09_populate_waivers.py    # APC waiver eligibility per publisher
python 10_fetch_impact_factors.py
python 11_scrape_aims_scope.py   # Journal scope/aims from publisher sites
python 12_seed_curated_lists.py  # 10 curated expert collections
python 15_parse_apc_pdfs.py      # Elsevier/Springer APC PDFs
python 16_parse_acceptance_time.py
python 17_openalex_enrichment.py # Comprehensive OpenAlex sync
```

### Database Schema

Run `supabase/schema.sql` then `supabase/schema_phase2.sql` in your Supabase SQL editor.

Required extensions: `pgvector`, `pg_trgm`

## Environment Variables

### Frontend (`.env.local`)

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_FASTAPI_URL=https://journal-radar-api-production.up.railway.app
NEXT_PUBLIC_API_SECRET_KEY=
NEXT_PUBLIC_TESTING_PHASE=true
```

### Backend API & Scripts (`.env`)

```
SUPABASE_URL=
SUPABASE_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
API_SECRET_KEY=
SPRINGER_API_KEY=
ELSEVIER_API_KEY=
```

## Deploying

### Frontend → Vercel

1. Push repo to GitHub
2. Import `frontend/` in Vercel (set root directory to `frontend`)
3. Add the frontend environment variables above

### API → Railway

```bash
cd api
railway login
railway up
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `journals` | 30K+ journals (core data, embeddings) |
| `quartile_history` | Year-by-year Q1–Q4 trajectory |
| `acceptance_reports` | Crowdsourced submission timelines |
| `feedback` | Per-journal data issue reports |
| `bookmarks` | User saved journals |
| `submissions` | User submission tracker |
| `curated_lists` | 10 expert-curated collections |
| `curated_list_journals` | Journal ↔ list mapping (ranked) |
| `scope_fit_cache` | Cached Claude scope-fit results |

## Contributing

- **Report data issues**: Use the "Report Issue" button on any journal card
- **Share acceptance experience**: Visit `/report` after signing in
- **Code contributions**: Open a GitHub issue or PR

## Data Sources

- [Scimago Journal Rankings](https://www.scimagojr.com) — Quartile, SJR, H-index (2025 data)
- [DOAJ](https://doaj.org) — APC costs, open access status
- [OpenAlex](https://openalex.org) — Topics, works count, recent papers
- Elsevier & Springer pricing PDFs — APC prices
- Community crowdsourced — Acceptance timelines

## Disclaimer

Always verify on the official journal website before submitting your paper. JournalRadar provides aggregated data for discovery purposes. We do not guarantee accuracy of APC costs, quartile rankings, or acceptance timelines.
