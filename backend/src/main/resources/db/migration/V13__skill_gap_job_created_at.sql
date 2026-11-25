-- available_at also moves on retry, so preserve a separate submission time going forward.
ALTER TABLE skill_gap_jobs ADD COLUMN created_at TIMESTAMPTZ;
-- For older jobs the latest scheduled time is the only recorded timestamp.
UPDATE skill_gap_jobs SET created_at = available_at;
ALTER TABLE skill_gap_jobs ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE skill_gap_jobs ALTER COLUMN created_at SET NOT NULL;

CREATE INDEX idx_skill_gap_jobs_created_at ON skill_gap_jobs(created_at);
