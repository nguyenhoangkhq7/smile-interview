CREATE TABLE ai_runtime_configuration (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    revision BIGINT NOT NULL DEFAULT 0,
    settings JSONB,
    credentials TEXT,
    updated_at TIMESTAMPTZ,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL
);
INSERT INTO ai_runtime_configuration(id) VALUES (1);

ALTER TABLE interview_runs ADD COLUMN created_at TIMESTAMPTZ DEFAULT clock_timestamp();
UPDATE interview_runs r SET created_at = s.started_at AT TIME ZONE current_setting('TimeZone')
FROM sessions s WHERE r.session_id = s.id;
CREATE INDEX idx_interview_runs_created ON interview_runs(created_at);

ALTER TABLE sessions ADD COLUMN skill_gap_runtime_revision BIGINT NOT NULL DEFAULT 0;
