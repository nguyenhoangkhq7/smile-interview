-- ============================================================
-- V8: Fix Criteria Gaps and FULLSTACK Resolution
-- ============================================================

-- 1. Re-add Agile & SDLC Practices to ROOT criteria
INSERT INTO evaluation_criteria (id, criteria_name, prompt_instruction) VALUES
(10104, 'Agile & SDLC Practices', 'Evaluate mentions of Agile, Scrum, Kanban, sprints, or CI/CD phases. Status must be "matched" if experienced, "weak" if barely mentioned, "missing" if absent.')
ON CONFLICT (id) DO NOTHING;

-- Map Agile to ROOT (job_category_id = 1) for all seniorities
INSERT INTO category_criteria_mapping (job_category_id, criteria_id, weight_percentage, seniority_level) VALUES
(1, 10104, 20.0, 'INTERN'),
(1, 10104, 20.0, 'FRESHER'),
(1, 10104, 20.0, 'JUNIOR'),
(1, 10104, 20.0, 'MID'),
(1, 10104, 20.0, 'SENIOR'),
(1, 10104, 20.0, 'LEAD')
ON CONFLICT (job_category_id, criteria_id, seniority_level) DO NOTHING;

-- 2. Map core criteria to FULLSTACK (job_category_id = 25)
-- FULLSTACK is a direct child of ROOT in V5, but lost its original criteria mappings in V6.
-- We must explicitly map Backend, Frontend, and DevOps core atomic criteria so it evaluates a full stack.
INSERT INTO category_criteria_mapping (job_category_id, criteria_id, weight_percentage, seniority_level) VALUES
-- BACKEND
(25, 10201, 20.0, 'ALL'), -- API Design
(25, 10202, 20.0, 'ALL'), -- DB Modeling & SQL
-- FRONTEND
(25, 10701, 20.0, 'ALL'), -- HTML & CSS
(25, 10702, 20.0, 'ALL'), -- DOM & Browser APIs
-- DEVOPS & CLOUD
(25, 10903, 10.0, 'ALL'), -- CI/CD
(25, 10904, 10.0, 'ALL'), -- Docker
(25, 11001, 10.0, 'ALL')  -- AWS Compute
ON CONFLICT (job_category_id, criteria_id, seniority_level) DO NOTHING;
