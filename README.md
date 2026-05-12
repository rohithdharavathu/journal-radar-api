# JournalRadar

> Every Scopus journal. One search.

A free, filterable search engine for 28,000+ Scopus-indexed academic journals. Find the right journal to publish in by filtering on APC cost, quartile ranking, subject area, publishing model, and acceptance time.

## Features

- **Search** — Full-text search across title, publisher, subject area, and ISSN
- **Filter** — Q1–Q4 quartiles, APC range, publishing model, subject area, acceptance time
- **Currency toggle** — USD / INR (₹83.5 conversion rate)
- **Journal profiles** — APC, SJR score, H-index, quartile history, acceptance data
- **Community reports** — Crowdsourced acceptance timelines from researchers
- **Bookmarks** — Save journals (requires sign-in)
- **Dark mode** — Toggle via header button

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16 (App Router) + Tailwind CSS + shadcn/ui |
| Database | Supabase (PostgreSQL + PostgREST + Auth) |
| Data pipeline | Python (pandas, requests, supabase-py) |
| Hosting | Vercel (frontend) + Supabase (backend) |
| Auth | Google Sign-In via Supabase Auth |

## Repo Structure

```
journal-radar/
├── frontend/          # Next.js app
├── scripts/           # Python data pipeline
├── supabase/          # Database schema SQL
└── README.md
```

## Running Locally

### Frontend

```bash
cd frontend
cp ../.env.example .env.local
# Fill in your Supabase URL and anon key
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Data Pipeline

```bash
cd scripts
pip install -r requirements.txt

# Place downloaded CSVs in scripts/data/
# - scimagojr_2024.csv  (from https://www.scimagojr.com/journalrank.php)
# - journalcsv__doaj.csv  (from https://doaj.org/csv)

python 01_parse_scimago.py
python 02_parse_doaj.py
python 03_merge_datasets.py
python 04_seed_supabase.py   # needs .env.local with Supabase creds
```

### Database Schema

Run `supabase/schema.sql` in your Supabase SQL editor to create all tables, indexes, and RLS policies.

## Deploying to Vercel

1. Push this repo to GitHub
2. Import `frontend/` into Vercel (set root directory to `frontend`)
3. Add environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_TESTING_PHASE=true`

## Contributing

- **Report data issues**: Use the "Report Issue" button on any journal card
- **Share acceptance experience**: Visit `/report` after signing in
- **Code contributions**: Open a GitHub issue or PR

## Data Sources

- [Scimago Journal Rankings](https://www.scimagojr.com) — Quartile, SJR, H-index
- [DOAJ](https://doaj.org) — APC costs, open access status
- [OpenAlex](https://openalex.org) — Supplemental enrichment
- Community crowdsourced acceptance timelines

## Disclaimer

Always verify on the official journal website before submitting your paper. JournalRadar provides aggregated data for discovery purposes. We do not guarantee accuracy of APC costs, quartile rankings, or acceptance timelines.
