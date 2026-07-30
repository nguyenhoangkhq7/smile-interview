-- ============================================================
-- V9: Add rating_matching_accuracy column to hr_evaluations table
-- Stores HR evaluation rating (1-5) for CV-JD matching accuracy.
-- ============================================================

ALTER TABLE hr_evaluations ADD COLUMN IF NOT EXISTS rating_matching_accuracy INT CHECK (rating_matching_accuracy BETWEEN 1 AND 5);

COMMENT ON COLUMN hr_evaluations.rating_matching_accuracy IS 'HR score (1-5) for CV-JD matching accuracy.';
