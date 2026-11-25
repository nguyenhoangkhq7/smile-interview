WITH users_by_period AS (
    SELECT count(*) FILTER (WHERE created_at >= :start) AS current_count,
           count(*) FILTER (WHERE created_at < :start) AS previous_count
    FROM users
    WHERE created_at >= :previous AND created_at < :end
), profiles_by_period AS (
    SELECT count(*) FILTER (WHERE created_at >= :start) AS current_count,
           count(*) FILTER (WHERE created_at < :start) AS previous_count
    FROM application_profiles
    WHERE created_at >= :previous AND created_at < :end AND deleted_at IS NULL
), interview_modes AS (
    SELECT s.started_at, s.status,
           CASE WHEN pg_input_is_valid(r.config_json, 'jsonb') THEN
                    coalesce(r.config_json::jsonb ->> 'interaction_mode', 'TEXT')
                ELSE upper(s.interview_type)
           END AS mode
    FROM sessions s
    LEFT JOIN interview_runs r ON r.session_id = s.id
    WHERE s.started_at >= :previous AND s.started_at < :end
      AND (r.session_id IS NOT NULL OR s.ai_interview_session_id IS NOT NULL
           OR s.status IN ('In progress', 'Completed', 'Stopped early', 'Cancelled'))
), interviews_by_period AS (
    SELECT count(*) FILTER (WHERE started_at >= :start) AS current_count,
           count(*) FILTER (WHERE started_at < :start) AS previous_count,
           count(*) FILTER (WHERE started_at >= :start AND status = 'Completed') AS completed_count,
           count(*) FILTER (WHERE started_at < :start AND status = 'Completed') AS previous_completed,
           count(*) FILTER (WHERE started_at >= :start AND mode = 'TEXT') AS text_count,
           count(*) FILTER (WHERE started_at >= :start AND mode = 'VOICE') AS voice_count
    FROM interview_modes
), job_counts AS (
    SELECT count(*) AS total, count(*) FILTER (WHERE status = 'SUCCEEDED') AS successful
    FROM skill_gap_jobs
    WHERE created_at >= :jobStart AND created_at < :jobEnd
)
SELECT u.current_count AS users, u.previous_count AS previous_users,
       p.current_count AS profiles, p.previous_count AS previous_profiles,
       i.current_count AS interviews, i.previous_count AS previous_interviews,
       i.completed_count, i.previous_completed, i.text_count, i.voice_count,
       j.total AS jobs, j.successful AS successful_jobs
FROM users_by_period u, profiles_by_period p, interviews_by_period i, job_counts j
