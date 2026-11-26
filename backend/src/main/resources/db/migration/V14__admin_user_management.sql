ALTER TABLE users
    ADD COLUMN locked_at TIMESTAMPTZ,
    ADD COLUMN lock_reason VARCHAR(500),
    ADD COLUMN token_version BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN row_version BIGINT NOT NULL DEFAULT 0;

CREATE TABLE user_password_setup_tokens (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    digest VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL
);
