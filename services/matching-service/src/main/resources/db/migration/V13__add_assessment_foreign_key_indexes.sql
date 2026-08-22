-- ============================================================
-- V13: Add indexes on assessment_id foreign key columns and session lookups
-- Improves performance when joining/loading sub-collections and cascading deletes.
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_evidence_items_assessment_id ON evidence_items(assessment_id);
CREATE INDEX IF NOT EXISTS idx_score_breakdowns_assessment_id ON score_breakdowns(assessment_id);
CREATE INDEX IF NOT EXISTS idx_improvements_assessment_id ON improvements(assessment_id);

CREATE INDEX IF NOT EXISTS idx_sessions_resume_jd ON sessions(resume_id, jd_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
