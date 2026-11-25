WITH daily_events AS (
    SELECT (created_at AT TIME ZONE :zone)::date AS event_day,
           count(*) AS analyses, 0 AS completed
    FROM skill_gap_jobs
    WHERE status = 'SUCCEEDED' AND created_at >= :jobStart AND created_at < :jobEnd
    GROUP BY 1
    UNION ALL
    SELECT s.started_at::date, count(*), 0
    FROM sessions s
    WHERE s.started_at >= :start AND s.started_at < :end
      AND s.attempt_number IS NULL AND s.skill_gap_json IS JSON ARRAY AND s.gap_report_json IS JSON OBJECT
      AND NOT EXISTS (
        SELECT 1 FROM skill_gap_jobs j WHERE j.session_id = s.id AND j.status = 'SUCCEEDED'
      )
    GROUP BY 1
    UNION ALL
    SELECT ended_at::date AS event_day, 0 AS analyses, count(*) AS completed
    FROM sessions
    WHERE status = 'Completed' AND ended_at >= :start AND ended_at < :end
    GROUP BY 1
)
SELECT event_day, sum(analyses) AS analyses, sum(completed) AS completed
FROM daily_events
GROUP BY event_day
ORDER BY event_day
