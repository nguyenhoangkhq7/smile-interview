-- ============================================================
-- V7: Add additional_evidence_items column to resume_assessments
-- ============================================================

ALTER TABLE resume_assessments ADD COLUMN additional_evidence_items JSONB;
