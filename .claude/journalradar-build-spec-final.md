# JournalRadar — BUILD SPEC (Locked)

> Every decision is made. No ambiguity. Build from this document.

---

## IDENTITY

| Field | Value |
|-------|-------|
| Product name | JournalRadar |
| Tagline | "Every Scopus journal. One search." |
| Repo name | `journal-radar` (monorepo) |
| Repo visibility | Public |
| Domain | journalradar.com |
| License | Decide at v1 launch (unlicensed during test phase) |

---

## ARCHITECTURE

```
┌──────────────────────────────────────┐
│         FRONTEND (Next.js 14)        │
│   Vercel · App Router · Tailwind     │
│   shadcn/ui · Light mode default     │
│           + dark toggle              │
│                                      │
│   Pages:                             │
│   /            → Search + filters    │
│   /journal/[id] → Journal profile    │
│   /report      → Report experience   │
│   /about       → About + disclaimer  │
│   /login       → Google OAuth        │
└──────────────┬───────────────────────┘
               │ Supabase JS Client
               │ (direct DB queries via PostgREST)
               │ NO FastAPI on Day 1
┌──────────────┴───────────────────────┐
│         SUPABASE (Free Tier)         │
│   PostgreSQL · PostgREST · Auth      │
│                                      │
│   Tables: journals, quartile_history,│
│   acceptance_reports, feedback       │
│                                      │
│   Auth: Google Sign-In               │
│   RLS: Public read, auth'd write     │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│      DATA PIPELINE (Python scripts)  │
│   /scripts directory in monorepo     │
│   Run locally, seed Supabase         │
│   Scimago CSV + DOAJ CSV → merge     │
│   → insert into Supabase             │
└──────────────────────────────────────┘
```

**No FastAPI.** Next.js talks to Supabase directly via JS client. FastAPI comes later when AI matcher needs Python + embeddings.

---

## REPO STRUCTURE

```
journal-radar/
├── frontend/                    # Next.js 14 app
│   ├── app/
│   │   ├── layout.tsx          # Root layout, theme provider, nav
│   │   ├── page.tsx            # Home: search + filters + results
│   │   ├── journal/
│   │   │   └── [id]/
│   │   │       └── page.tsx    # Journal profile
│   │   ├── report/
│   │   │   └── page.tsx        # Report acceptance experience
│   │   ├── about/
│   │   │   └── page.tsx        # About + disclaimer
│   │   └── login/
│   │       └── page.tsx        # Google OAuth
│   ├── components/
│   │   ├── ui/                 # shadcn/ui components
│   │   ├── search-bar.tsx
│   │   ├── filter-sidebar.tsx
│   │   ├── journal-card.tsx
│   │   ├── journal-profile.tsx
│   │   ├── report-form.tsx
│   │   ├── feedback-button.tsx # "Report an issue" per card
│   │   ├── feedback-modal.tsx  # Exit feedback (testing phase)
│   │   ├── currency-toggle.tsx # USD ↔ INR
│   │   ├── theme-toggle.tsx    # Light ↔ Dark
│   │   └── last-updated.tsx    # Timestamp badge
│   ├── lib/
│   │   ├── supabase.ts         # Supabase client init
│   │   ├── queries.ts          # All DB query functions
│   │   ├── types.ts            # TypeScript interfaces
│   │   └── constants.ts        # Currency rates, filter options
│   ├── public/
│   ├── tailwind.config.ts
│   ├── next.config.js
│   └── package.json
│
├── scripts/                     # Python data pipeline
│   ├── 01_parse_scimago.py     # Parse Scimago CSV → clean JSON
│   ├── 02_parse_doaj.py        # Parse DOAJ CSV → clean JSON
│   ├── 03_merge_datasets.py    # Merge on ISSN → final JSON
│   ├── 04_seed_supabase.py     # Insert merged data into Supabase
│   ├── 05_enrich_openalex.py   # Evening: pull OpenAlex data
│   ├── utils/
│   │   ├── issn.py             # ISSN normalization
│   │   └── currency.py         # Currency conversion helpers
│   └── requirements.txt        # pandas, supabase-py, requests
│
├── supabase/
│   └── schema.sql              # Full database schema
│
├── .gitignore
└── README.md
```

---

## DATABASE SCHEMA (Supabase PostgreSQL)

```sql
-- ============================================================
-- JOURNALS (core table)
-- ============================================================
CREATE TABLE journals (
    id                  SERIAL PRIMARY KEY,
    title               TEXT NOT NULL,
    issn_print          VARCHAR(9),
    issn_electronic     VARCHAR(9),
    publisher           TEXT,
    country             VARCHAR(100),
    homepage_url        TEXT,

    -- Classification
    subject_area        TEXT,           -- "Computer Science", "Engineering", "Medicine"
    subject_category    TEXT,           -- "Artificial Intelligence", "Mechanical Eng"
    topics              JSONB,          -- OpenAlex enrichment (Phase 2)

    -- Rankings
    quartile            VARCHAR(2),     -- Q1, Q2, Q3, Q4
    sjr_score           DECIMAL(6,3),
    h_index             INTEGER,

    -- APC & Access
    apc_amount_usd      DECIMAL(10,2),  -- NULL = unknown, 0 = no author fee
    apc_currency        VARCHAR(3),     -- Original currency
    apc_amount_original DECIMAL(10,2),  -- Original amount
    publishing_model    VARCHAR(20),    -- 'subscription', 'diamond_oa', 'gold_oa', 'hybrid'
    author_guidelines_url TEXT,

    -- Display helpers
    apc_display         TEXT,           -- Pre-computed: "No author fee", "$2,160", etc.

    -- Status
    is_active           BOOLEAN DEFAULT true,
    is_scopus           BOOLEAN DEFAULT true,
    is_doaj             BOOLEAN DEFAULT false,

    -- Metrics
    works_count         INTEGER,
    works_recent_2yr    INTEGER,
    cite_score          DECIMAL(6,2),

    -- Crowdsourced (starts NULL)
    avg_acceptance_weeks    DECIMAL(4,1),
    acceptance_report_count INTEGER DEFAULT 0,
    plagiarism_limit        INTEGER,

    -- Data quality
    data_sources        JSONB,          -- {"quartile":"scimago","apc":"doaj"}
    data_confidence     VARCHAR(10) DEFAULT 'medium',
    last_verified       TIMESTAMP DEFAULT NOW(),

    -- Timestamps
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- Full-text search
ALTER TABLE journals ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(publisher, '') || ' ' ||
            coalesce(subject_area, '') || ' ' ||
            coalesce(subject_category, '')
        )
    ) STORED;

CREATE INDEX idx_journals_search ON journals USING GIN(search_vector);
CREATE INDEX idx_journals_quartile ON journals(quartile);
CREATE INDEX idx_journals_apc ON journals(apc_amount_usd);
CREATE INDEX idx_journals_subject_area ON journals(subject_area);
CREATE INDEX idx_journals_subject_cat ON journals(subject_category);
CREATE INDEX idx_journals_model ON journals(publishing_model);
CREATE INDEX idx_journals_active ON journals(is_active);
CREATE INDEX idx_journals_country ON journals(country);
CREATE INDEX idx_journals_sjr ON journals(sjr_score DESC);

-- ============================================================
-- QUARTILE HISTORY (trajectory tracking)
-- ============================================================
CREATE TABLE quartile_history (
    id          SERIAL PRIMARY KEY,
    journal_id  INTEGER REFERENCES journals(id) ON DELETE CASCADE,
    year        INTEGER NOT NULL,
    quartile    VARCHAR(2),
    sjr_score   DECIMAL(6,3),
    UNIQUE(journal_id, year)
);

CREATE INDEX idx_qh_journal ON quartile_history(journal_id);

-- ============================================================
-- ACCEPTANCE REPORTS (crowdsourced)
-- ============================================================
CREATE TABLE acceptance_reports (
    id                  SERIAL PRIMARY KEY,
    journal_id          INTEGER REFERENCES journals(id) ON DELETE CASCADE,
    user_id             UUID REFERENCES auth.users(id),
    submitted_date      DATE NOT NULL,
    decision_date       DATE NOT NULL,
    decision_type       VARCHAR(20) NOT NULL CHECK (decision_type IN ('accepted', 'rejected', 'major_revision', 'minor_revision')),
    weeks_to_decision   INTEGER GENERATED ALWAYS AS (
        EXTRACT(DAY FROM (decision_date - submitted_date)) / 7
    ) STORED,
    reporter_role       VARCHAR(30),    -- 'phd_student', 'postdoc', 'assistant_prof', 'associate_prof', 'professor', 'industry'
    reporter_country    VARCHAR(100),
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ar_journal ON acceptance_reports(journal_id);

-- ============================================================
-- FEEDBACK (per journal card + exit feedback)
-- ============================================================
CREATE TABLE feedback (
    id          SERIAL PRIMARY KEY,
    journal_id  INTEGER REFERENCES journals(id) ON DELETE CASCADE,  -- NULL for general feedback
    user_id     UUID REFERENCES auth.users(id),
    type        VARCHAR(20) NOT NULL,   -- 'data_issue', 'missing_info', 'general', 'exit_feedback'
    message     TEXT NOT NULL,
    metadata    JSONB,                  -- e.g., {"field": "apc", "expected": "$0", "found": "$2000"}
    resolved    BOOLEAN DEFAULT false,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- BOOKMARKS (for logged-in users)
-- ============================================================
CREATE TABLE bookmarks (
    id          SERIAL PRIMARY KEY,
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    journal_id  INTEGER REFERENCES journals(id) ON DELETE CASCADE,
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, journal_id)
);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

-- Journals: public read
ALTER TABLE journals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Journals are public" ON journals FOR SELECT USING (true);

-- Acceptance reports: public read, auth'd insert
ALTER TABLE acceptance_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Reports are public" ON acceptance_reports FOR SELECT USING (true);
CREATE POLICY "Auth users can report" ON acceptance_reports FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Feedback: auth'd insert, not publicly readable
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Auth users can submit feedback" ON feedback FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Bookmarks: private per user
ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own bookmarks" ON bookmarks FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users create own bookmarks" ON bookmarks FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users delete own bookmarks" ON bookmarks FOR DELETE USING (auth.uid() = user_id);
```

---

## QUERY PATTERNS (Supabase JS Client)

```typescript
// lib/queries.ts

import { createClient } from '@supabase/supabase-js'
import type { Journal, FilterParams } from './types'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

// Main search + filter query
export async function searchJournals(params: FilterParams) {
  let query = supabase
    .from('journals')
    .select('*', { count: 'exact' })
    .eq('is_active', true)

  // Full-text search
  if (params.q) {
    query = query.textSearch('search_vector', params.q, {
      type: 'websearch',
      config: 'english'
    })
  }

  // Filters
  if (params.subject_area) {
    query = query.eq('subject_area', params.subject_area)
  }
  if (params.subject_category) {
    query = query.eq('subject_category', params.subject_category)
  }
  if (params.quartiles?.length) {
    query = query.in('quartile', params.quartiles)
  }
  if (params.apc_max !== undefined) {
    query = query.lte('apc_amount_usd', params.apc_max)
  }
  if (params.apc_min !== undefined) {
    query = query.gte('apc_amount_usd', params.apc_min)
  }
  if (params.models?.length) {
    query = query.in('publishing_model', params.models)
  }
  if (params.acceptance_max) {
    query = query.lte('avg_acceptance_weeks', params.acceptance_max)
  }

  // Sort
  const sortField = params.sort || 'sjr_score'
  const sortOrder = params.order === 'asc' ? true : false
  query = query.order(sortField, { ascending: sortOrder, nullsFirst: false })

  // Pagination
  const page = params.page || 1
  const limit = params.limit || 20
  const from = (page - 1) * limit
  query = query.range(from, from + limit - 1)

  return query
}

// Get single journal with history
export async function getJournal(id: number) {
  const [journal, history, reports] = await Promise.all([
    supabase.from('journals').select('*').eq('id', id).single(),
    supabase.from('quartile_history').select('*').eq('journal_id', id).order('year', { ascending: false }),
    supabase.from('acceptance_reports').select('*').eq('journal_id', id).order('created_at', { ascending: false }).limit(50),
  ])
  return { journal: journal.data, history: history.data, reports: reports.data }
}

// Get distinct subject areas for filter dropdown
export async function getSubjectAreas() {
  const { data } = await supabase
    .from('journals')
    .select('subject_area, subject_category')
    .eq('is_active', true)
  // Deduplicate and build hierarchy client-side
  return data
}

// Submit acceptance report
export async function submitReport(report: AcceptanceReport) {
  return supabase.from('acceptance_reports').insert(report)
}

// Submit feedback
export async function submitFeedback(feedback: Feedback) {
  return supabase.from('feedback').insert(feedback)
}

// Toggle bookmark
export async function toggleBookmark(userId: string, journalId: number) {
  const existing = await supabase
    .from('bookmarks')
    .select('id')
    .eq('user_id', userId)
    .eq('journal_id', journalId)
    .single()

  if (existing.data) {
    return supabase.from('bookmarks').delete().eq('id', existing.data.id)
  }
  return supabase.from('bookmarks').insert({ user_id: userId, journal_id: journalId })
}
```

---

## TYPE DEFINITIONS

```typescript
// lib/types.ts

export interface Journal {
  id: number
  title: string
  issn_print: string | null
  issn_electronic: string | null
  publisher: string | null
  country: string | null
  homepage_url: string | null
  subject_area: string | null
  subject_category: string | null
  quartile: 'Q1' | 'Q2' | 'Q3' | 'Q4' | null
  sjr_score: number | null
  h_index: number | null
  apc_amount_usd: number | null
  apc_currency: string | null
  apc_amount_original: number | null
  publishing_model: 'subscription' | 'diamond_oa' | 'gold_oa' | 'hybrid' | null
  apc_display: string | null
  author_guidelines_url: string | null
  is_active: boolean
  is_scopus: boolean
  is_doaj: boolean
  works_count: number | null
  works_recent_2yr: number | null
  avg_acceptance_weeks: number | null
  acceptance_report_count: number
  data_confidence: 'high' | 'medium' | 'low'
  last_verified: string
  updated_at: string
}

export interface FilterParams {
  q?: string
  subject_area?: string
  subject_category?: string
  quartiles?: string[]
  apc_min?: number
  apc_max?: number
  models?: string[]
  acceptance_max?: number
  country?: string
  sort?: string
  order?: 'asc' | 'desc'
  page?: number
  limit?: number
}

export interface QuartileHistory {
  year: number
  quartile: string
  sjr_score: number | null
}

export interface AcceptanceReport {
  journal_id: number
  user_id: string
  submitted_date: string
  decision_date: string
  decision_type: 'accepted' | 'rejected' | 'major_revision' | 'minor_revision'
  reporter_role: string
  reporter_country: string
}

export interface Feedback {
  journal_id: number | null
  user_id: string
  type: 'data_issue' | 'missing_info' | 'general' | 'exit_feedback'
  message: string
  metadata?: Record<string, unknown>
}
```

---

## DATA PIPELINE LOGIC

### Script 1: Parse Scimago (01_parse_scimago.py)

```
Input: scimagojr_2024.csv (semicolon-delimited)
Columns used: Title; Issn; SJR; H index; Quartile (best); Areas; Categories; Publisher; Country; Type
Processing:
  - Filter Type = "journal" (exclude book series, conferences)
  - Normalize ISSN: split on ", " → extract print + electronic
  - Take "Quartile (best)" → single best quartile value
  - Map "Areas" → subject_area (first area)
  - Map "Categories" → subject_category (first category)
  - Handle missing values
Output: scimago_clean.json
Fields: title, issn_print, issn_electronic, sjr_score, h_index, quartile, subject_area, subject_category, publisher, country
Count: ~28,000 records
```

### Script 2: Parse DOAJ (02_parse_doaj.py)

```
Input: DOAJ CSV dump (journalcsv__doaj.csv)
Columns used: Journal title; ISSN; EISSN; APC amount; APC currency; Publisher; Country; Author guidelines URL
Processing:
  - Normalize ISSN
  - Convert APC to USD (hardcoded rates: EUR=1.08, GBP=1.27, CHF=1.13, etc.)
  - If APC = 0 or empty → "diamond_oa"
  - If APC > 0 → "gold_oa"
  - Extract author_guidelines_url
Output: doaj_clean.json
Fields: issn_print, issn_electronic, apc_amount_original, apc_currency, apc_amount_usd, publishing_model, author_guidelines_url
Count: ~20,000 records
```

### Script 3: Merge (03_merge_datasets.py)

```
Logic:
  1. Load scimago_clean.json as base (has quartile — most important)
  2. Create ISSN lookup from DOAJ
  3. For each Scimago journal:
     a. Try match on issn_print, then issn_electronic
     b. If DOAJ match found:
        - Add APC data, model, guidelines URL
        - data_sources.apc = "doaj"
        - is_doaj = true
     c. If no DOAJ match:
        - apc_amount_usd = 0
        - publishing_model = "subscription"
        - apc_display = "No author fee"
        - data_sources.apc = "inferred"
  4. Generate apc_display:
     - 0 + subscription → "No author fee"
     - 0 + diamond_oa → "No author fee (Open Access)"
     - >0 → "$X,XXX" formatted
  5. Set data_confidence:
     - "high" if both Scimago + DOAJ matched
     - "medium" if Scimago only
  6. Set last_verified = current timestamp

Output: journals_merged.json (~28,000 records)
```

### Script 4: Seed Supabase (04_seed_supabase.py)

```
Logic:
  1. Load journals_merged.json
  2. Connect to Supabase via supabase-py
  3. Batch insert into journals table (chunks of 500)
  4. Log: total inserted, duplicates skipped, errors
  5. Verify: SELECT count(*) FROM journals
```

### Script 5: OpenAlex Enrichment (05_enrich_openalex.py — Evening)

```
Logic:
  1. Query OpenAlex: /sources?filter=type:journal,issn:{issn}&select=id,homepage_url,topics,works_count
  2. For each journal missing homepage_url or works_count:
     - Update with OpenAlex data
  3. Rate limit: use ?mailto=rohith@email.com for polite pool
  4. Batch: process 200/minute
```

---

## UI SPECIFICATIONS

### Color System (Light Mode Default)

```css
/* Light mode */
--bg: #ffffff;
--surface: #f8fafc;
--border: #e2e8f0;
--text: #0f172a;
--text-muted: #64748b;
--accent: #2563eb;       /* Blue — primary actions */
--accent-hover: #1d4ed8;
--success: #16a34a;      /* Green — "No author fee", Q1 */
--warning: #d97706;      /* Amber — Q3, medium confidence */
--q1: #2563eb;           /* Blue */
--q2: #16a34a;           /* Green */
--q3: #d97706;           /* Amber */
--q4: #6b7280;           /* Gray */

/* Dark mode (toggle) */
--bg: #0a0a0b;
--surface: #111114;
--border: #1e1e24;
--text: #e8e8f0;
--text-muted: #6b6b80;
--accent: #60a5fa;
```

### Component Specifications

**Journal Card (search results)**
```
┌─────────────────────────────────────────────────────┐
│ [Q1]  Expert Systems with Applications              │
│       Elsevier · Netherlands                        │
│                                                     │
│  Subject: Computer Science → Artificial Intelligence│
│  APC: No author fee · Model: Subscription           │
│  SJR: 2.480 · H-index: 242                         │
│  Papers/year: 3,400 · Updated: May 2026            │
│                                                     │
│  [View Profile]  [🔖 Bookmark]  [⚠ Report Issue]   │
└─────────────────────────────────────────────────────┘

- Quartile badge: colored pill (top-left)
- "Report Issue" button: opens feedback modal per journal
- "Last updated" timestamp visible on every card
- APC shown as: "No author fee" OR "$2,160" OR "No author fee (Open Access)"
```

**Filter Sidebar**
```
SUBJECT AREA          [dropdown — dynamic from DB]
SUB-CATEGORY          [dropdown — depends on area selection]
QUARTILE              [checkbox group: □Q1 □Q2 □Q3 □Q4]
APC RANGE (USD)       [range slider: $0 ─────── $5,000+]
APC RANGE (INR)       [toggle shows INR values]
PUBLISHING MODEL      [checkbox: □Subscription □Diamond OA □Gold OA □Hybrid]
ACCEPTANCE TIME       [radio: <8wks <12wks <20wks Any]
PUBLISHER COUNTRY     [dropdown]

[Reset Filters]
```

**Currency Toggle (header)**
```
[USD ▼]  ← dropdown: USD | INR
When INR selected:
  - All APC values converted at fixed rate (1 USD = ₹83.5)
  - Show: "₹1,80,360" instead of "$2,160"
  - "No author fee" stays unchanged
```

**Feedback Modal (per journal card)**
```
┌──────────────────────────────────────┐
│ Report an issue                      │
│                                      │
│ Journal: Expert Systems with Apps    │
│                                      │
│ Issue type:                          │
│ ○ APC is incorrect                   │
│ ○ Quartile is wrong                  │
│ ○ Journal is discontinued            │
│ ○ Link is broken                     │
│ ○ Other                              │
│                                      │
│ Details: [textarea]                  │
│                                      │
│ [Submit]  [Cancel]                   │
└──────────────────────────────────────┘
Requires Google sign-in.
```

**Exit Feedback (testing phase only)**
```
Trigger: When user has been on site >2 minutes and moves to close/navigate away
OR: Floating "Give Feedback" button in bottom-right

┌──────────────────────────────────────┐
│ Help us improve JournalRadar         │
│                                      │
│ How useful was this tool? [1-5 stars]│
│                                      │
│ What's missing? [textarea]           │
│                                      │
│ Would you use this regularly?        │
│ ○ Yes  ○ Maybe  ○ No                │
│                                      │
│ [Submit Feedback]  [Skip]            │
└──────────────────────────────────────┘
```

---

## PAGES BREAKDOWN

### / (Home — Search Page)
- Header: Logo + tagline + currency toggle + theme toggle + [Sign In]
- Search bar (prominent, centered)
- Filter sidebar (left, collapsible on mobile)
- Results grid (right, journal cards)
- Pagination (bottom)
- Stats bar: "Showing X of Y journals"
- Sort dropdown: SJR score | H-index | APC (low→high) | APC (high→low) | Name A-Z

### /journal/[id] (Profile Page)
- Back button
- Journal title + publisher + country
- 4 stat cards: Quartile | APC | Acceptance time | SJR
- Details section: subject, model, H-index, ISSN, papers/year, indexing status
- Quartile history: table or small line chart (2020-2024)
- Acceptance time distribution (if reports exist): histogram or range bar
- Useful links: Author guidelines | Homepage | Scimago page | Submit paper
- "Report your experience" CTA → links to /report?journal_id=X
- "Report an issue" button → feedback modal
- "Last verified" timestamp

### /report (Report Experience — requires auth)
- Journal selector (searchable dropdown, pre-filled if journal_id in URL)
- Date submitted (date picker)
- Date of decision (date picker)
- Decision type: Accepted | Rejected | Major revision | Minor revision
- Your role: PhD student | Postdoc | Asst. Prof | Assoc. Prof | Professor | Industry
- Your country (dropdown)
- Submit button
- Thank you message + "Your report helps thousands of researchers"

### /about
- What is JournalRadar
- How data is collected (transparency)
- Data sources: Scimago, DOAJ, OpenAlex, Scopus, Crowdsourced
- Disclaimer: "Always verify on the official journal website before submitting your paper. JournalRadar provides aggregated data for discovery purposes. We do not guarantee accuracy of APC costs, quartile rankings, or acceptance timelines."
- Contact / feedback
- Privacy: "We use Google Sign-In for authentication. We do not sell your data."

### /login
- Google Sign-In button via Supabase Auth
- "Sign in to bookmark journals, report experiences, and submit feedback"
- Redirect back to previous page after auth

---

## DAY 1 BUILD TIMELINE (10 hours)

### Block 1: Data Pipeline (2.5 hours)
```
00:00 - 00:30  Download Scimago CSV + DOAJ CSV
00:30 - 01:00  Write + run 01_parse_scimago.py
01:00 - 01:30  Write + run 02_parse_doaj.py
01:30 - 02:00  Write + run 03_merge_datasets.py
02:00 - 02:30  Create Supabase project + run schema.sql + run 04_seed_supabase.py
```

### Block 2: Frontend Core (4 hours)
```
02:30 - 03:00  Init Next.js + Tailwind + shadcn/ui + Supabase client
03:00 - 04:00  Home page: search bar + filter sidebar + results grid
04:00 - 05:00  Journal cards + pagination + sort
05:00 - 06:00  Journal profile page (/journal/[id])
06:00 - 06:30  Currency toggle + theme toggle
```

### Block 3: Auth + Feedback (2 hours)
```
06:30 - 07:00  Google OAuth via Supabase Auth
07:00 - 07:30  Feedback modal (per-card "Report Issue")
07:30 - 08:00  Exit feedback form (floating button)
08:00 - 08:30  Report experience page (/report)
```

### Block 4: Polish + Deploy (1.5 hours)
```
08:30 - 09:00  About page with disclaimer
09:00 - 09:30  Mobile responsiveness pass
09:30 - 10:00  Deploy: Vercel (frontend) + verify Supabase
               Share link in WhatsApp group
```

### Evening (bonus — not required for Day 1)
```
Run 05_enrich_openalex.py for homepage URLs + topics
Fix any bugs from initial faculty feedback
```

---

## POST-DAY 1 ROADMAP

| Phase | Timeline | Features |
|-------|----------|----------|
| v1.0 (Day 1) | Today | Search + filter + profiles + feedback + auth |
| v1.1 (Week 2) | +7 days | Acceptance time aggregation display, SEO meta tags, bug fixes from faculty feedback |
| v1.2 (Week 3) | +14 days | AI abstract matcher (paste abstract → get journals), OpenAlex full enrichment |
| v1.3 (Week 4) | +21 days | Plagiarism limits (LLM extraction from author guidelines), format template links |
| v2.0 (Month 2) | +30 days | Pro tier (Stripe), submission tracker, institutional pilot |

---

## READY TO BUILD

Every decision is made:
- Architecture: Next.js → Supabase (no FastAPI Day 1)
- Data: Scimago + DOAJ merged by ISSN (~28K journals)
- Schema: journals + quartile_history + acceptance_reports + feedback + bookmarks
- UI: Light mode, 4 pages, filter sidebar, journal cards, currency toggle
- Auth: Google Sign-In via Supabase
- Feedback: Per-card "Report Issue" + exit feedback form
- APC display: "No author fee" for subscription/diamond, "$X,XXX" for paid
- Disclaimer: About page only
- Deploy: Vercel + Supabase
- Test: WhatsApp group with college faculty

**Next step: Open terminal → `mkdir journal-radar && cd journal-radar`**
