ALTER TABLE study_tasks ADD COLUMN gap_source_objective_id VARCHAR(128);

ALTER TABLE study_task_checklist_items
    ADD COLUMN source_criterion_id VARCHAR(128),
    ADD COLUMN source_session_id VARCHAR(128),
    ADD COLUMN source_attempt_number INT,
    ADD CONSTRAINT ck_study_checklist_source_attempt
        CHECK (source_attempt_number IS NULL OR source_attempt_number > 0);

CREATE INDEX idx_study_tasks_objective ON study_tasks(plan_id, gap_source_objective_id)
    WHERE gap_source_objective_id IS NOT NULL;
