CREATE TABLE admin_audit_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    actor_id UUID NOT NULL,
    actor_name TEXT NOT NULL,
    peer_address VARCHAR(64),
    action VARCHAR(48) NOT NULL,
    target_type VARCHAR(32) NOT NULL,
    target_code VARCHAR(140) NOT NULL,
    summary TEXT NOT NULL,
    changes JSONB NOT NULL DEFAULT '[]',
    details JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_admin_audit_recent ON admin_audit_log(occurred_at DESC, id DESC);
CREATE INDEX idx_admin_audit_actor ON admin_audit_log(actor_id, occurred_at DESC, id DESC);
CREATE INDEX idx_admin_audit_action ON admin_audit_log(action, occurred_at DESC, id DESC);
