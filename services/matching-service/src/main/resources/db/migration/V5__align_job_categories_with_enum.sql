-- ============================================================
-- V5: Align job_categories table with JobCategory enum values
-- Fixes category tree matching failures for FULLSTACK, DEVOPS, SECURITY, QA, ML_ENGINEERING.
-- Also renames the root category to match SOFTWARE_ENGINEERING.
-- ============================================================

-- 1) Rename root category to match the Java fallback (SOFTWARE_ENGINEERING)
UPDATE job_categories 
SET name = 'SOFTWARE_ENGINEERING' 
WHERE name = 'SOFTWARE_AND_IT_ENGINEERING';

-- 2) Rename other L1 categories to match their corresponding JobCategory enum values
UPDATE job_categories 
SET name = 'DEVOPS' 
WHERE name = 'DEVOPS_AND_CLOUD';

UPDATE job_categories 
SET name = 'SECURITY' 
WHERE name = 'CYBERSECURITY';

UPDATE job_categories 
SET name = 'QA' 
WHERE name = 'QA_AND_TESTING';

UPDATE job_categories 
SET name = 'ML_ENGINEERING' 
WHERE name = 'AI_AND_ML';

-- 3) Insert FULLSTACK and OTHER categories
INSERT INTO job_categories (id, name, parent_id) VALUES 
(25, 'FULLSTACK', 1),
(99, 'OTHER', 1)
ON CONFLICT (id) DO NOTHING;

-- 4) Add baseline criteria mappings for FULLSTACK (uses Backend API/DB + Frontend UI/Web)
-- This ensures FULLSTACK roles are evaluated on API Design, DB Management, and UI/UX fundamentals
INSERT INTO category_criteria_mapping (job_category_id, criteria_id, weight_percentage, seniority_level) VALUES
(25, 2001, 25.0, 'ALL'), -- API Design (REST/GraphQL)
(25, 2002, 25.0, 'ALL'), -- Database Management (SQL/NoSQL)
(25, 2101, 25.0, 'ALL')  -- UI/UX & Web Fundamentals
ON CONFLICT (job_category_id, criteria_id, seniority_level) DO NOTHING;
