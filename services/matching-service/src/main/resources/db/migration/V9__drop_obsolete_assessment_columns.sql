-- ============================================================
-- V9: Drop Obsolete Columns from resume_assessments Table
-- Removes columns left over from V3 refactoring (competency_fit_score, actionable_suggestions)
-- to prevent null constraint violations since these columns are no longer in JPA entity.
-- ============================================================

ALTER TABLE resume_assessments DROP COLUMN IF EXISTS competency_fit_score;
ALTER TABLE resume_assessments DROP COLUMN IF EXISTS actionable_suggestions;
