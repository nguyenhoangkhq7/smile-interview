-- ============================================================
-- V1: Initial Database Schema (Squashed)
-- Creates all tables for the matching service:
--   1. session_documents (raw and standardized documents)
--   2. question_banks (generated interview question banks)
--   3. resume_assessments (LLM/Java computed resume scoring and feedback)
--   4. job_categories (hierarchical job category tree)
--   5. evaluation_criteria (evidence-matching criteria definitions)
--   6. category_criteria_mapping (criteria mapped to categories with weights)
--   7. suggested_criteria (dynamically extracted ad-hoc criteria)
--   8. users (user profiles for authentication)
-- ============================================================

-- Table 1: session_documents
CREATE TABLE IF NOT EXISTS session_documents (
    id               UUID PRIMARY KEY,
    session_id       VARCHAR(128) NOT NULL,
    document_type    VARCHAR(10) NOT NULL,
    markdown_content TEXT NOT NULL,
    created_at       TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_session_docs_session_id ON session_documents(session_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_docs_session_type_unique ON session_documents(session_id, document_type);

-- Table 2: question_banks
CREATE TABLE IF NOT EXISTS question_banks (
    id                 UUID PRIMARY KEY,
    session_id         VARCHAR(128) NOT NULL,
    metadata           JSONB,
    question_bank_json JSONB NOT NULL,
    question_config    JSONB,
    candidate_context  JSONB,
    total_questions    INTEGER,
    created_at         TIMESTAMP NOT NULL,
    updated_at         TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qb_session_id ON question_banks(session_id);

-- Table 3: resume_assessments
CREATE TABLE IF NOT EXISTS resume_assessments (
    id                        UUID PRIMARY KEY,
    session_id                VARCHAR(128) NOT NULL UNIQUE,
    created_at                TIMESTAMP NOT NULL,
    overall_match_score       INTEGER CHECK (overall_match_score >= 0 AND overall_match_score <= 100),
    job_category              VARCHAR(50) CHECK (job_category IN (
                                  'BACKEND','FRONTEND','FULLSTACK','DEVOPS',
                                  'DATA_ENGINEERING','ML_ENGINEERING','MOBILE','SECURITY','QA','OTHER'
                              )),
    seniority_level           VARCHAR(20) CHECK (seniority_level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD')),
    evidence_items            JSONB,
    additional_evidence_items JSONB,
    top_priority_improvements JSONB
);

CREATE INDEX IF NOT EXISTS idx_resume_assessment_session_id ON resume_assessments(session_id);
CREATE INDEX IF NOT EXISTS idx_ra_job_category ON resume_assessments(job_category);
CREATE INDEX IF NOT EXISTS idx_ra_seniority_level ON resume_assessments(seniority_level);
CREATE INDEX IF NOT EXISTS idx_ra_overall_score ON resume_assessments(overall_match_score DESC);

COMMENT ON COLUMN resume_assessments.overall_match_score       IS 'Computed by Java ScoringService from weighted evidence items';
COMMENT ON COLUMN resume_assessments.job_category              IS 'Maps to JobCategory enum; extracted by MetadataExtractionService';
COMMENT ON COLUMN resume_assessments.seniority_level           IS 'Maps to SeniorityLevel enum; extracted by MetadataExtractionService';
COMMENT ON COLUMN resume_assessments.evidence_items            IS 'Flat JSONB array of evidence matches per evaluation criterion';
COMMENT ON COLUMN resume_assessments.additional_evidence_items IS 'Flat JSONB array of evidence matches for JD-specific ad-hoc criteria';
COMMENT ON COLUMN resume_assessments.top_priority_improvements  IS 'Ordered list of actionable improvement suggestions';

-- Table 4: job_categories
CREATE TABLE IF NOT EXISTS job_categories (
    id        BIGSERIAL PRIMARY KEY,
    name      VARCHAR(100) NOT NULL UNIQUE,
    parent_id BIGINT       REFERENCES job_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_job_categories_parent_id ON job_categories(parent_id);

COMMENT ON TABLE  job_categories            IS 'Hierarchical tree of job categories for rule engine traversal';
COMMENT ON COLUMN job_categories.name       IS 'Category name — maps to JobCategory enum';
COMMENT ON COLUMN job_categories.parent_id  IS 'Parent node in the adjacency-list tree; NULL = root node';

-- Table 5: evaluation_criteria
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    id                  BIGSERIAL PRIMARY KEY,
    criteria_name       VARCHAR(200) NOT NULL UNIQUE,
    prompt_instruction  TEXT         NOT NULL
);

COMMENT ON TABLE  evaluation_criteria                   IS 'Assessment dimensions injected as evidence-matching instructions into the LLM prompt';
COMMENT ON COLUMN evaluation_criteria.criteria_name     IS 'Human-readable name shown in the UI';
COMMENT ON COLUMN evaluation_criteria.prompt_instruction IS 'Zero-shot instruction injected into the assessment LLM prompt';

-- Table 6: category_criteria_mapping
CREATE TABLE IF NOT EXISTS category_criteria_mapping (
    job_category_id  BIGINT           NOT NULL REFERENCES job_categories(id) ON DELETE CASCADE,
    criteria_id      BIGINT           NOT NULL REFERENCES evaluation_criteria(id) ON DELETE CASCADE,
    weight_percentage DOUBLE PRECISION NOT NULL CHECK (weight_percentage > 0 AND weight_percentage <= 100),
    seniority_level  VARCHAR(20)      NOT NULL CHECK (seniority_level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD','ALL')),

    PRIMARY KEY (job_category_id, criteria_id, seniority_level)
);

CREATE INDEX IF NOT EXISTS idx_ccm_category_seniority ON category_criteria_mapping(job_category_id, seniority_level);

COMMENT ON TABLE  category_criteria_mapping                  IS 'Maps criteria to categories with per-seniority weight percentages';
COMMENT ON COLUMN category_criteria_mapping.weight_percentage IS 'Relative weight of this criterion for scoring';
COMMENT ON COLUMN category_criteria_mapping.seniority_level   IS 'ALL = applies to every level; specific value overrides ALL for that level';

-- Table 7: suggested_criteria
CREATE TABLE IF NOT EXISTS suggested_criteria (
    id               BIGSERIAL PRIMARY KEY,
    job_category     VARCHAR(50)  NOT NULL,
    criteria_name    VARCHAR(200) NOT NULL,
    occurrence_count INT          NOT NULL DEFAULT 1,
    last_seen_at     TIMESTAMP    NOT NULL,
    sample_jd_text   TEXT,
    promoted         BOOLEAN      NOT NULL DEFAULT FALSE
);

-- Table 8: users
CREATE TABLE IF NOT EXISTS users (
    id                UUID PRIMARY KEY,
    username          VARCHAR(255) NOT NULL,
    email             VARCHAR(255) NOT NULL UNIQUE,
    password_hash     VARCHAR(255) NOT NULL,
    role              VARCHAR(50) NOT NULL,
    phone_number      VARCHAR(50),
    avatar_url        VARCHAR(255),
    default_resume_id UUID,
    created_at        TIMESTAMP NOT NULL
);
