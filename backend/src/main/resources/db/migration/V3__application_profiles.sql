CREATE TABLE application_profiles (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(200) NOT NULL,
    company VARCHAR(200),
    role_title VARCHAR(255) NOT NULL,
    resume_id UUID NOT NULL REFERENCES resumes(id),
    jd_id UUID NOT NULL REFERENCES job_descriptions(id),
    cv_filename VARCHAR(255) NOT NULL,
    jd_title VARCHAR(255) NOT NULL,
    cv_text TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    skill_gap_json TEXT NOT NULL,
    gap_report_json TEXT NOT NULL,
    blueprint_json TEXT,
    policy_json TEXT,
    created_at TIMESTAMP NOT NULL
);
CREATE INDEX idx_application_profiles_user ON application_profiles(user_id, created_at DESC);
ALTER TABLE sessions ADD COLUMN application_profile_id UUID REFERENCES application_profiles(id);
ALTER TABLE sessions ADD COLUMN attempt_number INTEGER;
CREATE UNIQUE INDEX idx_profile_attempt_number ON sessions(application_profile_id, attempt_number);
CREATE UNIQUE INDEX idx_profile_active_attempt ON sessions(application_profile_id)
    WHERE application_profile_id IS NOT NULL AND status IN ('Not started', 'In progress');
