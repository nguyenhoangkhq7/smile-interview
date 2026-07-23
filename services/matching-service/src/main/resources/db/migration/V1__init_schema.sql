-- ============================================================
-- V1: Initial Database Schema (Squashed and Aligned with JPA Entities)
-- Creates all tables for the smile-interview application.
-- ============================================================

-- Table 1: session_documents
CREATE TABLE IF NOT EXISTS session_documents (
    id               BIGSERIAL PRIMARY KEY,
    session_id       VARCHAR(128) NOT NULL,
    document_type    VARCHAR(10) NOT NULL,
    markdown_content TEXT NOT NULL,
    created_at       TIMESTAMP NOT NULL,
    updated_at       TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_doc_session_id ON session_documents(session_id);
CREATE UNIQUE INDEX IF NOT EXISTS uk_session_doc_type ON session_documents(session_id, document_type);

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

-- Table 3: resume_assessments (Aligned with ResumeAssessment JPA Entity)
CREATE TABLE IF NOT EXISTS resume_assessments (
    id                             UUID PRIMARY KEY,
    session_id                     VARCHAR(128) NOT NULL UNIQUE,
    job_category                   VARCHAR(50) CHECK (job_category IN (
                                       'SOFTWARE_ENGINEERING', 'BACKEND', 'FRONTEND', 'FULLSTACK', 'DEVOPS',
                                       'DATA_ENGINEERING', 'AI_ML', 'MOBILE', 'QA_TESTING', 'OTHER'
                                   )),
    seniority_level                VARCHAR(20) CHECK (seniority_level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD')),
    overall_match_score            INTEGER CHECK (overall_match_score >= 0 AND overall_match_score <= 100),
    eligibility_json               JSONB,
    evidence_items_json            JSONB NOT NULL,
    additional_evidence_items_json JSONB,
    top_priority_improvements_json JSONB,
    created_at                     TIMESTAMP NOT NULL,
    updated_at                     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assessment_session_id ON resume_assessments(session_id);

-- Table 4: job_categories (Aligned with JobCategoryEntity JPA Entity)
CREATE TABLE IF NOT EXISTS job_categories (
    id        BIGSERIAL PRIMARY KEY,
    code      VARCHAR(50) NOT NULL UNIQUE,
    name      VARCHAR(100) NOT NULL,
    parent_id BIGINT       REFERENCES job_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_job_categories_parent_id ON job_categories(parent_id);

-- Table 5: evaluation_criteria (Aligned with EvaluationCriteria JPA Entity)
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(150) NOT NULL UNIQUE,
    category            VARCHAR(50)  NOT NULL,
    question_type       VARCHAR(50)  NOT NULL,
    prompt_instruction  TEXT
);

-- Table 6: category_criteria_mapping (Aligned with CategoryCriteriaMapping JPA Entity)
CREATE TABLE IF NOT EXISTS category_criteria_mapping (
    id                     BIGSERIAL PRIMARY KEY,
    job_category_id        BIGINT           NOT NULL REFERENCES job_categories(id) ON DELETE CASCADE,
    evaluation_criteria_id BIGINT           NOT NULL REFERENCES evaluation_criteria(id) ON DELETE CASCADE,
    weight_percentage      DOUBLE PRECISION NOT NULL CHECK (weight_percentage > 0 AND weight_percentage <= 100),
    level                  VARCHAR(20)      NOT NULL CHECK (level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD','ALL')),
    CONSTRAINT uk_cat_crit_level UNIQUE (job_category_id, evaluation_criteria_id, level)
);

CREATE INDEX IF NOT EXISTS idx_ccm_category_seniority ON category_criteria_mapping(job_category_id, level);

-- Table 7: suggested_criteria (Aligned with SuggestedCriteria JPA Entity)
CREATE TABLE IF NOT EXISTS suggested_criteria (
    id               BIGSERIAL PRIMARY KEY,
    job_category     VARCHAR(50)  NOT NULL,
    criteria_name    VARCHAR(200) NOT NULL,
    occurrence_count INT          NOT NULL DEFAULT 1,
    last_seen_at     TIMESTAMP    NOT NULL,
    sample_jd_text   TEXT,
    promoted         BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT uk_suggested_criteria_cat_name UNIQUE (job_category, criteria_name)
);

-- Table 8: users (Aligned with User JPA Entity)
CREATE TABLE IF NOT EXISTS users (
    id                UUID PRIMARY KEY,
    username          VARCHAR(255) NOT NULL,
    email             VARCHAR(255) NOT NULL UNIQUE,
    password_hash     VARCHAR(255) NOT NULL,
    role              VARCHAR(50) NOT NULL,
    phone_number      VARCHAR(50),
    avatar_url        VARCHAR(255),
    default_resume_id VARCHAR(255),
    created_at        TIMESTAMP NOT NULL
);

-- Table 9: level_distribution_rules (Aligned with LevelDistributionRule JPA Entity)
CREATE TABLE IF NOT EXISTS level_distribution_rules (
    id                BIGSERIAL        PRIMARY KEY,
    level             VARCHAR(20)      NOT NULL UNIQUE
                          CHECK (level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD')),
    behavioral_pct    DOUBLE PRECISION NOT NULL CHECK (behavioral_pct    >= 0),
    technical_pct     DOUBLE PRECISION NOT NULL CHECK (technical_pct     >= 0),
    coding_pct        DOUBLE PRECISION NOT NULL CHECK (coding_pct        >= 0),
    system_design_pct DOUBLE PRECISION NOT NULL CHECK (system_design_pct >= 0)
);

-- Table 10: system_settings (Aligned with SystemSetting JPA Entity)
CREATE TABLE IF NOT EXISTS system_settings (
    id            BIGSERIAL PRIMARY KEY,
    setting_key   VARCHAR(100) NOT NULL UNIQUE,
    setting_value VARCHAR(255) NOT NULL,
    description   VARCHAR(500),
    updated_at    TIMESTAMP
);

-- Table 11: resumes (Used by Next.js app)
CREATE TABLE IF NOT EXISTS resumes (
    id             SERIAL PRIMARY KEY,
    user_id        VARCHAR(255),
    file_name      VARCHAR(255) NOT NULL,
    extracted_text TEXT,
    raw_text       TEXT,
    file_url       VARCHAR(500),
    cloudinary_id  VARCHAR(255),
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table 12: job_descriptions (Used by Next.js app)
CREATE TABLE IF NOT EXISTS job_descriptions (
    id             SERIAL PRIMARY KEY,
    user_id        VARCHAR(255),
    title          VARCHAR(255) NOT NULL,
    extracted_text TEXT,
    raw_text       TEXT,
    file_url       VARCHAR(500),
    cloudinary_id  VARCHAR(255),
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
