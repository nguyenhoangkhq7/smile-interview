WITH analyses AS (
    SELECT user_id, skill ->> 'jd_skill_id' AS skill_id,
           nullif(btrim(skill ->> 'jd_skill_name'), '') AS title,
           skill ->> 'semantic_alignment' AS alignment
    FROM sessions
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN pg_input_is_valid(skill_gap_json, 'jsonb') THEN
            CASE WHEN jsonb_typeof(skill_gap_json::jsonb) = 'array' THEN skill_gap_json::jsonb END
        END
    ) AS skill
    WHERE started_at >= :start AND started_at < :end AND attempt_number IS NULL
      AND user_id IS NOT NULL
), skill_names AS (
    SELECT skill_id, min(title) AS title FROM analyses WHERE skill_id IS NOT NULL GROUP BY skill_id
), report_inputs AS (
    SELECT s.user_id,
           CASE WHEN pg_input_is_valid(r.public_json, 'jsonb') THEN r.public_json::jsonb -> 'report'
                WHEN pg_input_is_valid(s.interview_report_json, 'jsonb') THEN s.interview_report_json::jsonb
           END AS report
    FROM sessions s
    LEFT JOIN interview_runs r ON r.session_id = s.id
    WHERE s.ended_at >= :start AND s.ended_at < :end AND s.user_id IS NOT NULL
      AND s.status IN ('Completed', 'Stopped early', 'Cancelled')
), interview_evidence AS (
    SELECT user_id, objective ->> 'skill_id' AS skill_id, objective ->> 'assessment' AS assessment
    FROM report_inputs
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(report -> 'objectives') = 'array' THEN report -> 'objectives' END
    ) AS objective
), candidates AS (
    SELECT user_id FROM analyses WHERE alignment IN ('MATCH', 'PARTIAL', 'MISSING')
    UNION
    SELECT user_id FROM interview_evidence
    WHERE assessment IN ('DEMONSTRATED_ABOVE_TARGET', 'DEMONSTRATED_AT_TARGET',
                         'DEMONSTRATED_BELOW_TARGET', 'NOT_DEMONSTRATED', 'INSUFFICIENT_EVIDENCE')
), gaps AS (
    SELECT user_id, coalesce(nullif(btrim(skill_id), ''), lower(title)) AS skill_key, title
    FROM analyses WHERE alignment IN ('PARTIAL', 'MISSING')
    UNION ALL
    SELECT e.user_id, nullif(btrim(e.skill_id), ''), n.title
    FROM interview_evidence e
    LEFT JOIN skill_names n ON n.skill_id = e.skill_id
    WHERE e.assessment IN ('DEMONSTRATED_BELOW_TARGET', 'NOT_DEMONSTRATED')
), ranked AS (
    SELECT coalesce(min(title), replace(skill_key, '_', ' ')) AS title,
           count(DISTINCT user_id) AS candidate_count
    FROM gaps
    WHERE skill_key IS NOT NULL
    GROUP BY skill_key
    ORDER BY candidate_count DESC, title, skill_key
    LIMIT 5
)
SELECT title, candidate_count, (SELECT count(*) FROM candidates) AS total_candidates
FROM ranked
ORDER BY candidate_count DESC, title
