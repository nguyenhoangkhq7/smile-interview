CREATE TABLE skill_gap_jobs (
    id UUID PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    input_key VARCHAR(64) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_until TIMESTAMPTZ,
    result_json TEXT
);

CREATE UNIQUE INDEX skill_gap_active_input ON skill_gap_jobs(session_id, owner_id, input_key)
    WHERE status IN ('PENDING','RUNNING');
CREATE INDEX skill_gap_jobs_ready ON skill_gap_jobs(available_at) WHERE status = 'PENDING';
CREATE INDEX skill_gap_jobs_expired ON skill_gap_jobs(lease_until) WHERE status = 'RUNNING';
ALTER TABLE sessions ADD COLUMN skill_gap_input_key VARCHAR(64);
