-- ============================================================
-- PHASE 3 MIGRATIONS — run in Supabase SQL editor
-- ============================================================

-- 1. UNIQUE constraints on ISSN so upsert-by-ISSN works safely
--    NULL ISSNs are excluded (journals with no print ISSN won't conflict)
CREATE UNIQUE INDEX IF NOT EXISTS journals_issn_print_unique
    ON journals (issn_print)
    WHERE issn_print IS NOT NULL AND issn_print <> '';

CREATE UNIQUE INDEX IF NOT EXISTS journals_issn_electronic_unique
    ON journals (issn_electronic)
    WHERE issn_electronic IS NOT NULL AND issn_electronic <> '';

-- 2. Index on issn_print for fast lookup during annual upsert
CREATE INDEX IF NOT EXISTS idx_journals_issn_print ON journals (issn_print);
CREATE INDEX IF NOT EXISTS idx_journals_issn_electronic ON journals (issn_electronic);
