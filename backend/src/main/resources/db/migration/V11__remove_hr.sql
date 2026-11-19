-- Remove HR evaluation tables, turn HR feedback columns, and seeded HR accounts.
DROP TABLE IF EXISTS hr_evaluations;

ALTER TABLE session_turns
    DROP COLUMN IF EXISTS hr_rating,
    DROP COLUMN IF EXISTS hr_feedback;

DELETE FROM users WHERE role = 'HR';
