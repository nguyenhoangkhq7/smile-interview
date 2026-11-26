INSERT INTO sessions(id, status) VALUES ('legacy', 'Completed'), ('v2', 'Not started');
INSERT INTO session_turns(session_id, question) VALUES ('legacy', 'old question'), ('legacy', 'old follow-up');
INSERT INTO interview_runs VALUES ('v2', 1, '{}', '{}', '{}');
INSERT INTO interview_commands VALUES ('00000000-0000-0000-0000-000000000001', 'v2',
    '00000000-0000-0000-0000-000000000002', 'hash', '{}');
INSERT INTO session_turns(session_id, external_turn_id) VALUES ('v2', 'turn-1');
DO $$
BEGIN
    BEGIN
        INSERT INTO session_turns(session_id, external_turn_id) VALUES ('v2', 'turn-1');
        RAISE EXCEPTION 'duplicate turn accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO interview_commands VALUES ('00000000-0000-0000-0000-000000000003', 'v2',
            '00000000-0000-0000-0000-000000000002', 'hash', '{}');
        RAISE EXCEPTION 'duplicate request accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    IF (SELECT count(*) FROM session_turns WHERE session_id = 'legacy') <> 2 THEN
        RAISE EXCEPTION 'legacy turns changed';
    END IF;
END $$;
DELETE FROM sessions WHERE id = 'v2';
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM interview_runs) OR EXISTS (SELECT 1 FROM interview_commands)
        OR EXISTS (SELECT 1 FROM session_turns WHERE session_id = 'v2') THEN
        RAISE EXCEPTION 'cascade deletion failed';
    END IF;
END $$;
