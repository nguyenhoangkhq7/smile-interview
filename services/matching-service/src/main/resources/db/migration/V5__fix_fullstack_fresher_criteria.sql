-- ============================================================
-- V5: Fix FULLSTACK Seniority-Level Criteria Mappings
--
-- Problem: FULLSTACK (job_category_id=25) only had 'ALL' level mappings.
-- Query findCriteriaTreeByCategory("FULLSTACK", "FRESHER") returned empty,
-- silently falling back to SOFTWARE_ENGINEERING/ALL, causing wrong criteria sets.
--
-- Solution: Add explicit INTERN, FRESHER, JUNIOR, MID, SENIOR, LEAD mappings
-- for the FULLSTACK category, weighting core fullstack skills appropriately.
--
-- Core criteria referenced (from V2 seed):
--   10101 = Data Structures & Algorithms
--   10102 = Object-Oriented Programming (OOP)
--   10103 = Database Fundamentals
--   10104 = Agile & SDLC Practices
--   10201 = API Design (REST/GraphQL)
--   10202 = Database Modeling & SQL
--   10301 = Java Core Language
--   10401 = Spring Core (IoC/DI)
--   10402 = Spring Data JPA/Hibernate
--   10403 = Spring Security
--   10701 = Semantic HTML & CSS
--   10702 = DOM Manipulation & Browser APIs
--   10801 = Component Architecture & Lifecycle (React)
--   10802 = Advanced Hook Patterns (React)
--   10803 = State Management (Redux/Zustand)
--   10805 = SSR/SSG (Next.js)
--   10903 = CI/CD Fundamentals
--   10904 = Docker & Containerization
--   11001 = AWS Compute & Auto-scaling
-- Extended criteria (from V4):
--   10106 = SOLID Principles & Clean Code
--   10110 = Unit Testing & TDD
--   10114 = Git Flow & Version Control Strategy
--   10117 = Database Optimization & ORM Practices
-- ============================================================

INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES

-- ============================================================
-- FULLSTACK / INTERN
-- Focus: OOP fundamentals, basic HTML/CSS/React, basic SQL, Git basics
-- ============================================================
(25, 10102, 20.0, 'INTERN'),   -- OOP (core foundation)
(25, 10101, 15.0, 'INTERN'),   -- Data Structures & Algorithms
(25, 10103, 15.0, 'INTERN'),   -- Database Fundamentals
(25, 10701, 15.0, 'INTERN'),   -- Semantic HTML & CSS
(25, 10801, 20.0, 'INTERN'),   -- React Component Architecture
(25, 10104, 15.0, 'INTERN'),   -- Agile & SDLC Practices

-- ============================================================
-- FULLSTACK / FRESHER
-- Focus: Spring Boot basics, React with hooks, PostgreSQL, Docker, Git workflow
-- Weights sum to 100. CI/CD and AWS are secondary (matches JD nice-to-have).
-- ============================================================
(25, 10102, 15.0, 'FRESHER'),  -- OOP (still important at fresher)
(25, 10201, 15.0, 'FRESHER'),  -- API Design REST
(25, 10202, 15.0, 'FRESHER'),  -- Database Modeling & SQL
(25, 10801, 15.0, 'FRESHER'),  -- React Component Architecture
(25, 10401, 10.0, 'FRESHER'),  -- Spring Core (IoC/DI)
(25, 10904, 10.0, 'FRESHER'),  -- Docker & Containerization
(25, 10114, 10.0, 'FRESHER'),  -- Git Flow & Version Control
(25, 10104, 10.0, 'FRESHER'),  -- Agile & SDLC Practices

-- ============================================================
-- FULLSTACK / JUNIOR
-- Focus: Spring Boot + JPA, React + State, SQL optimisation, CI/CD intro
-- ============================================================
(25, 10201, 15.0, 'JUNIOR'),   -- API Design REST
(25, 10202, 15.0, 'JUNIOR'),   -- Database Modeling & SQL
(25, 10401, 10.0, 'JUNIOR'),   -- Spring Core (IoC/DI)
(25, 10402, 10.0, 'JUNIOR'),   -- Spring Data JPA/Hibernate
(25, 10801, 10.0, 'JUNIOR'),   -- React Component Architecture
(25, 10802, 10.0, 'JUNIOR'),   -- Advanced Hook Patterns
(25, 10803, 10.0, 'JUNIOR'),   -- State Management (Zustand/Redux)
(25, 10904, 10.0, 'JUNIOR'),   -- Docker & Containerization
(25, 10903, 10.0, 'JUNIOR'),   -- CI/CD Fundamentals

-- ============================================================
-- FULLSTACK / MID
-- Focus: Security, Next.js SSR, DB optimisation, testing, cloud basics
-- ============================================================
(25, 10201, 10.0, 'MID'),      -- API Design REST
(25, 10202, 15.0, 'MID'),      -- Database Modeling & SQL
(25, 10117, 10.0, 'MID'),      -- Database Optimization & ORM Practices
(25, 10403, 10.0, 'MID'),      -- Spring Security
(25, 10805, 10.0, 'MID'),      -- SSR/SSG Next.js
(25, 10803, 10.0, 'MID'),      -- State Management
(25, 10110, 10.0, 'MID'),      -- Unit Testing & TDD
(25, 10903, 10.0, 'MID'),      -- CI/CD Fundamentals
(25, 11001, 15.0, 'MID'),      -- AWS Compute & Auto-scaling

-- ============================================================
-- FULLSTACK / SENIOR
-- Focus: Architecture, security, observability, team leadership
-- ============================================================
(25, 10106, 15.0, 'SENIOR'),   -- SOLID Principles & Clean Code
(25, 10117, 10.0, 'SENIOR'),   -- Database Optimization & ORM
(25, 10403, 10.0, 'SENIOR'),   -- Spring Security
(25, 10805, 10.0, 'SENIOR'),   -- SSR/SSG Next.js
(25, 10110, 15.0, 'SENIOR'),   -- Unit Testing & TDD
(25, 10903, 10.0, 'SENIOR'),   -- CI/CD Fundamentals
(25, 11001, 15.0, 'SENIOR'),   -- AWS Compute & Auto-scaling
(25, 10114, 15.0, 'SENIOR'),   -- Git Flow & Version Control

-- ============================================================
-- FULLSTACK / LEAD
-- Focus: Architecture decisions, mentoring, system design
-- ============================================================
(25, 10106, 20.0, 'LEAD'),     -- SOLID Principles & Clean Code
(25, 10110, 15.0, 'LEAD'),     -- Unit Testing & TDD
(25, 10903, 15.0, 'LEAD'),     -- CI/CD Fundamentals
(25, 11001, 20.0, 'LEAD'),     -- AWS Compute & Auto-scaling
(25, 10117, 15.0, 'LEAD'),     -- Database Optimization & ORM
(25, 10114, 15.0, 'LEAD')      -- Git Flow & Version Control

ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO NOTHING;

-- ============================================================
-- System Settings: Ensure sensible defaults are set
-- ============================================================
INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('WEAK_COEFF_INTERN_FRESHER', '0.5',
        'Score multiplier for ''weak'' status when candidate is INTERN or FRESHER level. Higher value is more lenient.',
        NOW())
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('EVIDENCE_GROUNDING_THRESHOLD', '0.35',
        'Minimum fuzzy similarity score for cv_evidence to be considered grounded in CV. Lowered to account for Vietnamese evidence vs English CV text.',
        NOW())
ON CONFLICT (setting_key) DO UPDATE SET setting_value = '0.35', updated_at = NOW();
