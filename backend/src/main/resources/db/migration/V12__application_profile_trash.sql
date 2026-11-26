ALTER TABLE application_profiles ADD COLUMN deleted_at TIMESTAMP;

CREATE INDEX idx_application_profiles_deleted_at
    ON application_profiles(deleted_at)
    WHERE deleted_at IS NOT NULL;
