-- V6: Architectural Separation of Static Blueprint and Dynamic State for Interview Runs
ALTER TABLE interview_runs ADD COLUMN IF NOT EXISTS blueprint_json TEXT;
ALTER TABLE interview_runs ADD COLUMN IF NOT EXISTS dynamic_state_json TEXT;
