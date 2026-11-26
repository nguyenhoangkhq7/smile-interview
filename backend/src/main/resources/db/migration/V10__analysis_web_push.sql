CREATE TABLE analysis_push_subscriptions (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint VARCHAR(2048) NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth_key TEXT NOT NULL
);
CREATE INDEX analysis_push_owner ON analysis_push_subscriptions(owner_id);

CREATE TABLE analysis_push_deliveries (
    job_id UUID NOT NULL REFERENCES skill_gap_jobs(id) ON DELETE CASCADE,
    subscription_id UUID NOT NULL REFERENCES analysis_push_subscriptions(id) ON DELETE CASCADE,
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY(job_id, subscription_id)
);
CREATE INDEX analysis_push_due ON analysis_push_deliveries(available_at) WHERE available_at IS NOT NULL;
