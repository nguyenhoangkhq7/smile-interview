ALTER TABLE study_tasks
    ADD COLUMN gap_source_skill_id TEXT,
    ADD COLUMN gap_source_session_id VARCHAR(128),
    ADD COLUMN gap_source_attempt_number INT,
    ADD CONSTRAINT ck_study_tasks_gap_source_attempt
        CHECK (gap_source_attempt_number IS NULL OR gap_source_attempt_number > 0);

CREATE INDEX idx_study_tasks_gap_source
    ON study_tasks(plan_id, gap_source_skill_id)
    WHERE gap_source_skill_id IS NOT NULL;
