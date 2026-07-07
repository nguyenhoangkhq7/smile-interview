-- ============================================================
-- V3: Refactor resume_assessments Table
-- Removes the old LLM-computed scoring schema and replaces it
-- with the new architecture-compliant schema where:
--   - overall_match_score is computed by Java (ScoringService)
--   - role_type_detected (free-string) → job_category (ENUM-mapped VARCHAR)
--   - candidate_level (free-string)   → seniority_level (ENUM-mapped VARCHAR)
--   - section_wise_feedback (nested JSONB object) → evidence_items (flat JSONB array)
--   - Obsolete columns dropped
-- ============================================================

-- Step 1: Clear all old incompatible data (early dev/staging — no data retention needed)
TRUNCATE TABLE resume_assessments CASCADE;



-- Step 2: Drop obsolete columns that no longer exist in the new schema
ALTER TABLE resume_assessments
    DROP COLUMN IF EXISTS technical_depth_score,
    DROP COLUMN IF EXISTS match_level,
    DROP COLUMN IF EXISTS years_of_experience_estimate,
    DROP COLUMN IF EXISTS strong_areas,
    DROP COLUMN IF EXISTS gap_areas,
    DROP COLUMN IF EXISTS critical_missing_skills,
    DROP COLUMN IF EXISTS section_wise_feedback,
    DROP COLUMN IF EXISTS role_type_detected,
    DROP COLUMN IF EXISTS candidate_level;

-- Step 3: Add new columns aligned with the refactored architecture
ALTER TABLE resume_assessments
    -- Java-computed overall score (0-100); no longer provided by LLM
    ADD COLUMN IF NOT EXISTS overall_match_score INTEGER
        CHECK (overall_match_score >= 0 AND overall_match_score <= 100),

    -- JobCategory ENUM stored as string (e.g., 'BACKEND', 'FRONTEND')
    ADD COLUMN IF NOT EXISTS job_category VARCHAR(50)
        CHECK (job_category IN (
            'BACKEND','FRONTEND','FULLSTACK','DEVOPS',
            'DATA_ENGINEERING','ML_ENGINEERING','MOBILE','SECURITY','QA','OTHER'
        )),

    -- SeniorityLevel ENUM stored as string (e.g., 'FRESHER', 'MID')
    ADD COLUMN IF NOT EXISTS seniority_level VARCHAR(20)
        CHECK (seniority_level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD')),

    -- Flat JSONB array of EvidenceItem objects from the LLM evidence-matching engine
    -- Schema: [{ "criteria_id": long, "criteria_name": str, "jd_requirement": str,
    --            "cv_evidence": str|null, "status": "matched|weak|missing" }]
    ADD COLUMN IF NOT EXISTS evidence_items JSONB,

    -- Ordered list of actionable improvement suggestions (unchanged from old schema)
    ADD COLUMN IF NOT EXISTS top_priority_improvements JSONB;

-- Keep actionable_suggestions column renamed to top_priority_improvements
-- (column already dropped above if it existed under old name; new column added above)

-- Step 4: Add index on the new ENUM columns for analytics queries
CREATE INDEX IF NOT EXISTS idx_ra_job_category
    ON resume_assessments(job_category);

CREATE INDEX IF NOT EXISTS idx_ra_seniority_level
    ON resume_assessments(seniority_level);

CREATE INDEX IF NOT EXISTS idx_ra_overall_score
    ON resume_assessments(overall_match_score DESC);

-- Verify the final schema is as expected
COMMENT ON COLUMN resume_assessments.overall_match_score      IS 'Computed by Java ScoringService from weighted evidence items — never set by LLM';
COMMENT ON COLUMN resume_assessments.job_category             IS 'Maps to JobCategory enum; extracted by MetadataExtractionService from JD Markdown';
COMMENT ON COLUMN resume_assessments.seniority_level          IS 'Maps to SeniorityLevel enum; extracted by MetadataExtractionService from JD Markdown';
COMMENT ON COLUMN resume_assessments.evidence_items           IS 'Flat JSONB array of evidence matches per evaluation criterion; populated by LLM assessment call';
COMMENT ON COLUMN resume_assessments.top_priority_improvements IS 'Ordered list of actionable improvement suggestions returned by the LLM';
