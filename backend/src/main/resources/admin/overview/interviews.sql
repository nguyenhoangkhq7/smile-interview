WITH role_counts AS (
    SELECT min(btrim(s.role_title)) AS title,
           count(*) FILTER (WHERE s.started_at >= :start) AS current_count,
           count(*) FILTER (WHERE s.started_at < :start) AS previous_count
    FROM sessions s
    WHERE s.started_at >= :previous AND s.started_at < :end
      AND nullif(btrim(s.role_title), '') IS NOT NULL
      AND (s.ai_interview_session_id IS NOT NULL
           OR s.status IN ('In progress', 'Completed', 'Stopped early', 'Cancelled')
           OR EXISTS (SELECT 1 FROM interview_runs r WHERE r.session_id = s.id))
    GROUP BY lower(btrim(s.role_title))
    HAVING count(*) FILTER (WHERE s.started_at >= :start) > 0
    ORDER BY current_count DESC, title
    LIMIT 5
), finished AS (
    SELECT s.status,
           CASE WHEN pg_input_is_valid(r.public_json, 'jsonb') THEN r.public_json::jsonb -> 'report'
                WHEN pg_input_is_valid(s.interview_report_json, 'jsonb') THEN s.interview_report_json::jsonb
           END AS report
    FROM sessions s
    LEFT JOIN interview_runs r ON r.session_id = s.id
    WHERE s.ended_at >= :start AND s.ended_at < :end
      AND s.status IN ('Completed', 'Stopped early', 'Cancelled')
), reasons AS (
    SELECT CASE
               WHEN report ->> 'termination_reason' IN ('PLAN_COMPLETE', 'ALL_COMPATIBLE_SKILLS_MASTERED')
                   THEN 'PLAN_COMPLETE'
               WHEN report ->> 'termination_reason' IN ('QUESTION_BUDGET', 'TIME_BUDGET', 'USER_STOP')
                   THEN report ->> 'termination_reason'
               WHEN status IN ('Stopped early', 'Cancelled') THEN 'USER_STOP'
               ELSE 'OTHER'
           END AS code
    FROM finished
), assessments AS (
    SELECT objective ->> 'assessment' AS code
    FROM finished
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(report -> 'objectives') = 'array' THEN report -> 'objectives' END
    ) AS objective
    WHERE objective ->> 'assessment' IN (
        'DEMONSTRATED_ABOVE_TARGET', 'DEMONSTRATED_AT_TARGET', 'DEMONSTRATED_BELOW_TARGET',
        'NOT_DEMONSTRATED', 'INSUFFICIENT_EVIDENCE', 'NOT_ASSESSED'
    )
)
SELECT 'termination' AS category, code, count(*) AS current_count, 0 AS previous_count
FROM reasons GROUP BY code
UNION ALL
SELECT 'assessment', code, count(*), 0 FROM assessments GROUP BY code
UNION ALL
SELECT 'role', title, current_count, previous_count FROM role_counts
