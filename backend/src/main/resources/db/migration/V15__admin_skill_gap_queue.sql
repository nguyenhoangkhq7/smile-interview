ALTER TABLE skill_gap_jobs
    ADD COLUMN claim_token UUID,
    ADD COLUMN priority_at TIMESTAMPTZ,
    ADD COLUMN claimed_at TIMESTAMPTZ,
    ADD COLUMN finished_at TIMESTAMPTZ,
    ADD COLUMN failure_code VARCHAR(32);

UPDATE skill_gap_jobs SET claim_token = gen_random_uuid() WHERE status = 'RUNNING';

CREATE INDEX idx_skill_gap_job_history ON skill_gap_jobs
    (session_id, owner_id, input_key, created_at DESC, id DESC);

CREATE INDEX idx_skill_gap_job_priority ON skill_gap_jobs (priority_at)
    WHERE status = 'PENDING' AND priority_at IS NOT NULL;
