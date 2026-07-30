-- ============================================================
-- V7: Create hr_evaluations table
-- Stores HR personnel evaluations of AI-generated question banks.
-- Each row represents one evaluation submission for a session.
-- ============================================================

CREATE TABLE IF NOT EXISTS hr_evaluations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              VARCHAR(128) NOT NULL,
    evaluator_name          VARCHAR(255),
    rating_ai_rationale     INT CHECK (rating_ai_rationale     BETWEEN 1 AND 5),
    rating_question_quality INT CHECK (rating_question_quality BETWEEN 1 AND 5),
    feedback_notes          TEXT,
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hr_eval_session_id ON hr_evaluations(session_id);

COMMENT ON TABLE  hr_evaluations                      IS 'HR evaluation ratings for AI-generated question banks.';
COMMENT ON COLUMN hr_evaluations.session_id           IS 'Links evaluation to the interview session.';
COMMENT ON COLUMN hr_evaluations.rating_ai_rationale  IS 'HR score (1-5) for the AI-generated question rationale quality.';
COMMENT ON COLUMN hr_evaluations.rating_question_quality IS 'HR score (1-5) for the overall question quality.';
COMMENT ON COLUMN hr_evaluations.feedback_notes       IS 'Free-text HR feedback about the generated questions.';
