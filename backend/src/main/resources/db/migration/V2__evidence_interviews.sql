-- V2 state is committed by the backend; existing sessions and reports remain readable.
CREATE TABLE interview_runs (
    session_id VARCHAR(128) PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    state_version BIGINT NOT NULL,
    config_json TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    public_json TEXT NOT NULL
);

CREATE TABLE interview_commands (
    id UUID PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL REFERENCES interview_runs(session_id) ON DELETE CASCADE,
    request_id UUID NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    response_json TEXT NOT NULL,
    UNIQUE(session_id, request_id)
);

ALTER TABLE session_turns ADD COLUMN external_turn_id VARCHAR(128);
CREATE UNIQUE INDEX idx_session_external_turn ON session_turns(session_id, external_turn_id);
