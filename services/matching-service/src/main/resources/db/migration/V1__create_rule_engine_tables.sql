-- ============================================================
-- V1: Rule Engine Tables
-- Creates the 3-table hierarchical rule engine required by Step 3
-- of the SimInterview multi-stage analysis pipeline.
-- ============================================================

-- Enable pgvector extension (required for document_chunks.embedding)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- BASELINE SCHEMAS (Previously created by Hibernate ddl-auto: update)
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

-- Table 2: document_chunks
CREATE TABLE IF NOT EXISTS document_chunks (
    id            UUID PRIMARY KEY,
    session_id    VARCHAR(128) NOT NULL,
    document_type VARCHAR(10) NOT NULL,
    chunk_text    TEXT NOT NULL,
    embedding     vector(2560)
);

CREATE INDEX IF NOT EXISTS idx_doc_chunks_session_id ON document_chunks(session_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_doc_type ON document_chunks(document_type);

-- Table 3: question_banks
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

-- Table 4: resume_assessments (original baseline columns; migrated in V3)
CREATE TABLE IF NOT EXISTS resume_assessments (
    id                           UUID PRIMARY KEY,
    session_id                   VARCHAR(128) NOT NULL UNIQUE,
    created_at                   TIMESTAMP NOT NULL,
    competency_fit_score         INTEGER,
    technical_depth_score        INTEGER,
    match_level                  VARCHAR(50),
    candidate_level              VARCHAR(50),
    role_type_detected           VARCHAR(100),
    years_of_experience_estimate VARCHAR(100),
    strong_areas                 JSONB,
    gap_areas                    JSONB,
    critical_missing_skills      JSONB,
    section_wise_feedback        JSONB,
    actionable_suggestions       JSONB
);

CREATE INDEX IF NOT EXISTS idx_resume_assessment_session_id ON resume_assessments(session_id);

-- ============================================================
-- RULE ENGINE SCHEMAS
-- ============================================================


-- ============================================================
-- Table 1: job_categories
-- Self-referencing tree structure (Adjacency List model).
-- Traversed bottom-up by the WITH RECURSIVE CTE in
-- JobCriteriaRepository to aggregate all applicable criteria
-- from leaf → root (e.g., Java Backend → Backend → Software Engineering).
-- ============================================================
CREATE TABLE IF NOT EXISTS job_categories (
    id        BIGSERIAL PRIMARY KEY,
    name      VARCHAR(100) NOT NULL UNIQUE,
    parent_id BIGINT       REFERENCES job_categories(id) ON DELETE SET NULL
);

COMMENT ON TABLE  job_categories            IS 'Hierarchical tree of job categories for rule engine traversal';
COMMENT ON COLUMN job_categories.name       IS 'Category name — maps to JobCategory enum (e.g., BACKEND, FRONTEND)';
COMMENT ON COLUMN job_categories.parent_id  IS 'Parent node in the adjacency-list tree; NULL = root node';

-- ============================================================
-- Table 2: evaluation_criteria
-- Each row represents one assessment dimension.
-- prompt_instruction is injected verbatim into the LLM assessment
-- prompt as the evidence-matching instruction for that criterion.
-- ============================================================
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    id                  BIGSERIAL PRIMARY KEY,
    criteria_name       VARCHAR(200) NOT NULL UNIQUE,
    prompt_instruction  TEXT         NOT NULL
);

COMMENT ON TABLE  evaluation_criteria                   IS 'Assessment dimensions injected as evidence-matching instructions into the LLM prompt';
COMMENT ON COLUMN evaluation_criteria.criteria_name     IS 'Human-readable name shown in the UI and stored in evidence_items JSON';
COMMENT ON COLUMN evaluation_criteria.prompt_instruction IS 'Zero-shot instruction injected into the assessment LLM prompt for this criterion';

-- ============================================================
-- Table 3: category_criteria_mapping
-- Junction table linking categories to criteria with weights.
-- seniority_level allows different weight sets for the same
-- category at different experience levels.
-- ============================================================
CREATE TABLE IF NOT EXISTS category_criteria_mapping (
    job_category_id  BIGINT  NOT NULL REFERENCES job_categories(id)    ON DELETE CASCADE,
    criteria_id      BIGINT  NOT NULL REFERENCES evaluation_criteria(id) ON DELETE CASCADE,
    weight_percentage DOUBLE PRECISION NOT NULL
        CHECK (weight_percentage > 0 AND weight_percentage <= 100),
    seniority_level  VARCHAR(20) NOT NULL
        CHECK (seniority_level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD','ALL')),

    PRIMARY KEY (job_category_id, criteria_id, seniority_level)
);

COMMENT ON TABLE  category_criteria_mapping                  IS 'Maps criteria to categories with per-seniority weight percentages';
COMMENT ON COLUMN category_criteria_mapping.weight_percentage IS 'Relative weight of this criterion for scoring (all weights for a category+level need not sum to 100; ScoringService normalises)';
COMMENT ON COLUMN category_criteria_mapping.seniority_level   IS 'ALL = applies to every level; specific value overrides ALL for that level';

-- Indexes for the WITH RECURSIVE query hot path
CREATE INDEX IF NOT EXISTS idx_job_categories_parent_id
    ON job_categories(parent_id);

CREATE INDEX IF NOT EXISTS idx_ccm_category_seniority
    ON category_criteria_mapping(job_category_id, seniority_level);
