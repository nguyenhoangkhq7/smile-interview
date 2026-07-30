-- ============================================================
-- V1: Initial Database Schema (Normalized based on ERD)
-- Creates all tables for the smile-interview application.
-- ============================================================

-- Enable UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id                UUID PRIMARY KEY,
    username          VARCHAR(255) NOT NULL,
    email             VARCHAR(255) NOT NULL UNIQUE,
    password_hash     VARCHAR(255) NOT NULL,
    role              VARCHAR(50) NOT NULL,
    phone_number      VARCHAR(50),
    avatar_url        VARCHAR(255),
    default_resume_id UUID,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table: resumes
CREATE TABLE IF NOT EXISTS resumes (
    id             UUID PRIMARY KEY,
    user_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    file_name      VARCHAR(255) NOT NULL,
    parsed_content TEXT,
    raw_text       TEXT,
    file_url       VARCHAR(500),
    cloudinary_id  VARCHAR(255),
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table: job_descriptions
CREATE TABLE IF NOT EXISTS job_descriptions (
    id             UUID PRIMARY KEY,
    user_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    title          VARCHAR(255) NOT NULL,
    parsed_content TEXT,
    raw_text       TEXT,
    file_url       VARCHAR(500),
    cloudinary_id  VARCHAR(255),
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- Table: resume_assessments
CREATE TABLE IF NOT EXISTS resume_assessments (
    id                             UUID PRIMARY KEY,
    session_id                     VARCHAR(128) UNIQUE,
    job_category                   VARCHAR(50) CHECK (job_category IN (
                                       'SOFTWARE_ENGINEERING', 'BACKEND', 'FRONTEND', 'FULLSTACK', 'DEVOPS',
                                       'DATA_ENGINEERING', 'AI_ML', 'MOBILE', 'QA_TESTING', 'OTHER'
                                   )),
    seniority_level                VARCHAR(20) CHECK (seniority_level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD')),
    overall_match_score            INTEGER CHECK (overall_match_score >= 0 AND overall_match_score <= 100),
    eligibility                    VARCHAR(50) CHECK (eligibility IN ('ELIGIBILITY', 'PARTIAL', 'NOT_ELIGIBILITY')),
    created_at                     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assessment_session_id ON resume_assessments(session_id);

-- Table: evidence_items
CREATE TABLE IF NOT EXISTS evidence_items (
    id             UUID PRIMARY KEY,
    assessment_id  UUID NOT NULL REFERENCES resume_assessments(id) ON DELETE CASCADE,
    criteria_id    INTEGER,
    criteria_name  VARCHAR(255),
    importance     VARCHAR(50),
    jd_requirement TEXT,
    cv_evidence    TEXT,
    status         VARCHAR(50),
    reasoning      TEXT,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table: score_breakdowns
CREATE TABLE IF NOT EXISTS score_breakdowns (
    id             UUID PRIMARY KEY,
    assessment_id  UUID NOT NULL REFERENCES resume_assessments(id) ON DELETE CASCADE,
    category       VARCHAR(100),
    score          INTEGER,
    max_score      INTEGER,
    feedback       TEXT,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table: improvements
CREATE TABLE IF NOT EXISTS improvements (
    id                 UUID PRIMARY KEY,
    assessment_id      UUID NOT NULL REFERENCES resume_assessments(id) ON DELETE CASCADE,
    priority_rank      INTEGER,
    topic              VARCHAR(255),
    suggestion_details TEXT,
    created_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table: sessions (from web-app)
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(128) PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
    jd_id UUID REFERENCES job_descriptions(id) ON DELETE SET NULL,
    assessment_id UUID REFERENCES resume_assessments(id) ON DELETE SET NULL,
    status VARCHAR(50),
    interview_type VARCHAR(50),
    role_title VARCHAR(255),
    overall_score INTEGER,
    overall_feedback TEXT,
    user_rating INTEGER,
    user_feedback_text TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Table: session_questions (replacing question_banks)
CREATE TABLE IF NOT EXISTS session_questions (
    id                 UUID PRIMARY KEY,
    session_id         VARCHAR(128) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    question_config    TEXT,
    candidate_context  TEXT,
    total_questions    INTEGER,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sq_session_id ON session_questions(session_id);

-- Table: questions
CREATE TABLE IF NOT EXISTS questions (
    id                  UUID PRIMARY KEY,
    session_question_id UUID NOT NULL REFERENCES session_questions(id) ON DELETE CASCADE,
    category            VARCHAR(100),
    question_text       TEXT,
    expected_answer     TEXT,
    difficulty_level    INTEGER,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table: session_metadata
CREATE TABLE IF NOT EXISTS session_metadata (
    id                  UUID PRIMARY KEY,
    session_question_id UUID NOT NULL REFERENCES session_questions(id) ON DELETE CASCADE,
    metadata_key        VARCHAR(100),
    metadata_value      TEXT
);

-- Table: session_turns
CREATE TABLE IF NOT EXISTS session_turns (
    id UUID PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    question_id UUID REFERENCES questions(id) ON DELETE SET NULL,
    dynamic_question_text TEXT,
    answer TEXT,
    score INTEGER,
    strengths TEXT,
    improvements TEXT,
    suggested_answer TEXT,
    topic_tag VARCHAR(100),
    is_deep_dive BOOLEAN DEFAULT FALSE,
    latency_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, turn_number)
);


-- Table: job_categories
CREATE TABLE IF NOT EXISTS job_categories (
    id        BIGSERIAL PRIMARY KEY,
    code      VARCHAR(50) NOT NULL UNIQUE,
    name      VARCHAR(100) NOT NULL,
    parent_id BIGINT       REFERENCES job_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_job_categories_parent_id ON job_categories(parent_id);

-- Table: evaluation_criteria
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(150) NOT NULL UNIQUE,
    category            VARCHAR(50)  NOT NULL,
    question_type       VARCHAR(50)  NOT NULL,
    prompt_instruction  TEXT
);

-- Table: category_criteria_mapping
CREATE TABLE IF NOT EXISTS category_criteria_mapping (
    id                     BIGSERIAL PRIMARY KEY,
    job_category_id        BIGINT           NOT NULL REFERENCES job_categories(id) ON DELETE CASCADE,
    evaluation_criteria_id BIGINT           NOT NULL REFERENCES evaluation_criteria(id) ON DELETE CASCADE,
    weight_percentage      DOUBLE PRECISION NOT NULL CHECK (weight_percentage > 0 AND weight_percentage <= 100),
    level                  VARCHAR(20)      NOT NULL CHECK (level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD','ALL')),
    CONSTRAINT uk_cat_crit_level UNIQUE (job_category_id, evaluation_criteria_id, level)
);

CREATE INDEX IF NOT EXISTS idx_ccm_category_seniority ON category_criteria_mapping(job_category_id, level);

-- Table: suggested_criteria
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

-- Table: level_distribution_rules
CREATE TABLE IF NOT EXISTS level_distribution_rules (
    id                BIGSERIAL        PRIMARY KEY,
    level             VARCHAR(20)      NOT NULL UNIQUE
                          CHECK (level IN ('INTERN','FRESHER','JUNIOR','MID','SENIOR','LEAD')),
    behavioral_pct    DOUBLE PRECISION NOT NULL CHECK (behavioral_pct    >= 0),
    technical_pct     DOUBLE PRECISION NOT NULL CHECK (technical_pct     >= 0),
    coding_pct        DOUBLE PRECISION NOT NULL CHECK (coding_pct        >= 0),
    system_design_pct DOUBLE PRECISION NOT NULL CHECK (system_design_pct >= 0)
);

-- Table: system_settings
CREATE TABLE IF NOT EXISTS system_settings (
    id            BIGSERIAL PRIMARY KEY,
    setting_key   VARCHAR(100) NOT NULL UNIQUE,
    setting_value VARCHAR(255) NOT NULL,
    description   VARCHAR(500),
    updated_at    TIMESTAMP
);

