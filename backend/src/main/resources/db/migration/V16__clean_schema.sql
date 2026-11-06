-- =============================================================================
-- V15__nckh_clean_schema.sql
-- Drop legacy assessment, rule-engine, question-bank, and chunking tables.
-- Add NCKH pipeline JSON/session columns to `sessions`.
-- =============================================================================

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS skill_gap_json TEXT,
    ADD COLUMN IF NOT EXISTS gap_report_json TEXT,
    ADD COLUMN IF NOT EXISTS ai_interview_session_id VARCHAR(128),
    ADD COLUMN IF NOT EXISTS interview_report_json TEXT;

DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS session_metadata CASCADE;
DROP TABLE IF EXISTS questions CASCADE;
DROP TABLE IF EXISTS session_questions CASCADE;
DROP TABLE IF EXISTS improvements CASCADE;
DROP TABLE IF EXISTS score_breakdowns CASCADE;
DROP TABLE IF EXISTS evidence_items CASCADE;
DROP TABLE IF EXISTS resume_assessments CASCADE;
DROP TABLE IF EXISTS suggested_criteria CASCADE;
DROP TABLE IF EXISTS category_criteria_mapping CASCADE;
DROP TABLE IF EXISTS evaluation_criteria CASCADE;
DROP TABLE IF EXISTS job_categories CASCADE;
DROP TABLE IF EXISTS level_distribution_rules CASCADE;
DROP TABLE IF EXISTS system_settings CASCADE;
