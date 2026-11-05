-- ============================================================
-- V8: Add user_id column to hr_evaluations table
-- Links HR evaluation records to the user who submitted them.
-- ============================================================

ALTER TABLE hr_evaluations ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_hr_eval_user_id ON hr_evaluations(user_id);

COMMENT ON COLUMN hr_evaluations.user_id IS 'References the HR user who submitted the evaluation.';
