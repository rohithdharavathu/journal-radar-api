-- ============================================================
-- PHASE 2 MIGRATIONS — run in Supabase SQL editor
-- ============================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add embedding column (1536 dims = text-embedding-3-small)
ALTER TABLE journals ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- 3. HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_journals_embedding
    ON journals USING hnsw (embedding vector_cosine_ops);

-- 4. match_journals RPC — called by FastAPI /match endpoint
DROP FUNCTION IF EXISTS match_journals(vector, integer);

CREATE OR REPLACE FUNCTION match_journals(
    query_embedding vector(1536),
    match_count int DEFAULT 40
)
RETURNS TABLE (
    id int,
    title text,
    publisher text,
    country text,
    quartile varchar,
    sjr_score decimal,
    h_index int,
    apc_amount_usd decimal,
    apc_display text,
    publishing_model varchar,
    subject_area text,
    subject_category text,
    homepage_url text,
    author_guidelines_url text,
    avg_acceptance_weeks decimal,
    acceptance_report_count int,
    is_doaj boolean,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        j.id, j.title, j.publisher, j.country,
        j.quartile, j.sjr_score, j.h_index,
        j.apc_amount_usd, j.apc_display, j.publishing_model,
        j.subject_area, j.subject_category,
        j.homepage_url, j.author_guidelines_url,
        j.avg_acceptance_weeks, j.acceptance_report_count,
        j.is_doaj,
        1 - (j.embedding <=> query_embedding) AS similarity
    FROM journals j
    WHERE j.embedding IS NOT NULL
      AND j.is_active = true
    ORDER BY j.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- 5. Rebuild search_vector to include topic names from OpenAlex
--    Run this AFTER 05_enrich_openalex.py completes

-- Helper: extract topic names from JSONB — must be IMMUTABLE to use in generated column
CREATE OR REPLACE FUNCTION extract_topic_names(topics jsonb)
RETURNS text
LANGUAGE sql IMMUTABLE
AS $$
    SELECT coalesce(string_agg(t->>'name', ' '), '')
    FROM jsonb_array_elements(coalesce(topics, '[]'::jsonb)) t;
$$;

ALTER TABLE journals DROP COLUMN IF EXISTS search_vector;

ALTER TABLE journals ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(publisher, '') || ' ' ||
            coalesce(subject_area, '') || ' ' ||
            coalesce(subject_category, '') || ' ' ||
            extract_topic_names(topics)
        )
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_journals_search ON journals USING GIN(search_vector);

-- 6. Submissions table (for Phase 3 tracker)
CREATE TABLE IF NOT EXISTS submissions (
    id              SERIAL PRIMARY KEY,
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    journal_id      INTEGER REFERENCES journals(id) ON DELETE SET NULL,
    paper_title     TEXT NOT NULL,
    submitted_date  DATE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'submitted'
                    CHECK (status IN (
                        'submitted', 'under_review', 'revision',
                        'accepted', 'rejected', 'withdrawn'
                    )),
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own submissions" ON submissions;
DROP POLICY IF EXISTS "Users create own submissions" ON submissions;
DROP POLICY IF EXISTS "Users update own submissions" ON submissions;
DROP POLICY IF EXISTS "Users delete own submissions" ON submissions;

CREATE POLICY "Users see own submissions" ON submissions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users create own submissions" ON submissions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own submissions" ON submissions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users delete own submissions" ON submissions
    FOR DELETE USING (auth.uid() = user_id);

-- Trigger to keep avg_acceptance_weeks up-to-date on new reports
CREATE OR REPLACE FUNCTION update_journal_acceptance_avg()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE journals
    SET
        avg_acceptance_weeks = (
            SELECT AVG(weeks_to_decision)
            FROM acceptance_reports
            WHERE journal_id = NEW.journal_id
        ),
        acceptance_report_count = (
            SELECT COUNT(*)
            FROM acceptance_reports
            WHERE journal_id = NEW.journal_id
        )
    WHERE id = NEW.journal_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_acceptance_avg
    AFTER INSERT ON acceptance_reports
    FOR EACH ROW EXECUTE FUNCTION update_journal_acceptance_avg();
