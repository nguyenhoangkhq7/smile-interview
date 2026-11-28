ALTER TABLE interview_runs ADD COLUMN grading_due_at TIMESTAMPTZ;
ALTER TABLE interview_runs ADD COLUMN grading_attempt INTEGER NOT NULL DEFAULT 0;
CREATE INDEX interview_grading_due ON interview_runs (grading_due_at) WHERE grading_due_at IS NOT NULL;
