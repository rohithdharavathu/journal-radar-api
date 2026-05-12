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
    subject_area        TEXT,
    subject_category    TEXT,
    topics              JSONB,

    -- Rankings
    quartile            VARCHAR(2),
    sjr_score           DECIMAL(6,3),
    h_index             INTEGER,

    -- APC & Access
    apc_amount_usd      DECIMAL(10,2),
    apc_currency        VARCHAR(3),
    apc_amount_original DECIMAL(10,2),
    publishing_model    VARCHAR(20),
    author_guidelines_url TEXT,

    -- Display helpers
    apc_display         TEXT,

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
    data_sources        JSONB,
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
-- QUARTILE HISTORY
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
    reporter_role       VARCHAR(30),
    reporter_country    VARCHAR(100),
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ar_journal ON acceptance_reports(journal_id);

-- ============================================================
-- FEEDBACK
-- ============================================================
CREATE TABLE feedback (
    id          SERIAL PRIMARY KEY,
    journal_id  INTEGER REFERENCES journals(id) ON DELETE CASCADE,
    user_id     UUID REFERENCES auth.users(id),
    type        VARCHAR(20) NOT NULL,
    message     TEXT NOT NULL,
    metadata    JSONB,
    resolved    BOOLEAN DEFAULT false,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- BOOKMARKS
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

ALTER TABLE journals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Journals are public" ON journals FOR SELECT USING (true);

ALTER TABLE acceptance_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Reports are public" ON acceptance_reports FOR SELECT USING (true);
CREATE POLICY "Auth users can report" ON acceptance_reports FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Auth users can submit feedback" ON feedback FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own bookmarks" ON bookmarks FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users create own bookmarks" ON bookmarks FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users delete own bookmarks" ON bookmarks FOR DELETE USING (auth.uid() = user_id);
