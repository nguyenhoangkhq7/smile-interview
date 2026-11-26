ALTER TABLE study_tasks
    ADD COLUMN parent_task_id BIGINT,
    ADD CONSTRAINT uq_study_tasks_plan_id_id UNIQUE (plan_id, id),
    ADD CONSTRAINT ck_study_tasks_parent_not_self CHECK (parent_task_id <> id),
    ADD CONSTRAINT fk_study_tasks_parent
        FOREIGN KEY (plan_id, parent_task_id) REFERENCES study_tasks(plan_id, id)
        ON DELETE SET NULL (parent_task_id);

CREATE INDEX idx_study_tasks_parent ON study_tasks(plan_id, parent_task_id) WHERE parent_task_id IS NOT NULL;
