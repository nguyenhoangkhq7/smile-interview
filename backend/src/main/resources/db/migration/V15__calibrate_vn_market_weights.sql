-- ============================================================
-- V15: Calibrate VN Market Weights & Resolve ALL/Level Conflicts
--
-- Scope:
--   1. Remove 'ALL' mappings that conflict with existing specific-level rows
--      (same job_category_id + evaluation_criteria_id).
--      After V15, the scoring engine's NOT EXISTS guard ensures ALL rows
--      only act as fallback, but removing explicit conflicts keeps the DB
--      clean and prevents accidental double-counting if the guard is removed.
--
--   2. Calibrate weights for:
--        - SOFTWARE_ENGINEERING root (category_id = 1)  → Core / Soft Skills
--        - BACKEND category       (category_id = 10)    → Backend Generics
--        - JAVA_ECOSYSTEM         (category_id = 101)   → Java Core + Spring
--        - SPRING_BOOT            (category_id = 1011)  → Spring Boot deep
--        - FRONTEND               (category_id = 20)    → Frontend Generics
--        - REACT_ECOSYSTEM        (category_id = 201)   → React deep
--
-- Criteria ID reference (from V2 / V4 seeds):
--   10101 = Data Structures & Algorithms
--   10102 = Object-Oriented Programming (OOP)
--   10103 = Database Fundamentals
--   10104 = Agile & SDLC Practices
--   10106 = SOLID Principles & Clean Code          (V4)
--   10108 = System Design & Architecture           (V4)
--   10109 = Networking & Security Fundamentals     (V4)
--   10110 = Unit Testing & TDD                     (V4)
--   10114 = Git Flow & Version Control Strategy    (V4)
--   10117 = Database Optimization & ORM Practices  (V4)
--   10201 = API Design (REST/GraphQL)
--   10202 = Database Modeling & SQL
--   10203 = Microservices & Distributed Systems
--   10301 = Java Core Language
--   10302 = JVM Internals & Performance Tuning
--   10303 = Concurrency & Reactive Programming
--   10304 = Build Tools (Maven/Gradle)
--   10401 = Spring Core (IoC/DI)
--   10402 = Spring Data JPA/Hibernate
--   10403 = Spring Security
--   10404 = Spring Cloud & Microservices
--   10405 = Spring Reactive (WebFlux)
--   10701 = Semantic HTML & CSS
--   10702 = DOM Manipulation & Browser APIs
--   10703 = JavaScript / TypeScript Core
--   10801 = Component Architecture & Lifecycle (React)
--   10802 = Advanced Hook Patterns
--   10803 = State Management (Redux/Zustand)
--   10804 = Performance Optimization (React)
--   10805 = SSR/SSG (Next.js)
-- ============================================================


-- ============================================================
-- PART 1: Remove ALL-level rows that conflict with specific-level rows
-- ============================================================
-- An ALL row "conflicts" when there is already at least one specific-level row
-- for the same (job_category_id, evaluation_criteria_id) pair.
DELETE FROM category_criteria_mapping
WHERE level = 'ALL'
  AND EXISTS (
      SELECT 1
      FROM category_criteria_mapping m2
      WHERE m2.job_category_id        = category_criteria_mapping.job_category_id
        AND m2.evaluation_criteria_id = category_criteria_mapping.evaluation_criteria_id
        AND m2.level                 != 'ALL'
  );


-- ============================================================
-- PART 2: Calibrate SOFTWARE_ENGINEERING (root) core skills
--   Rationale (VN market):
--     - INTERN/FRESHER: heavy OOP + DSA foundation; Agile lightweight
--     - JUNIOR: OOP still dominant, API/DB awareness rising, SOLID intro
--     - MID:   SOLID + System Design replace raw OOP; testing matters
--     - SENIOR/LEAD: Architecture + Concurrency + Testing dominate
-- ============================================================

-- Remove stale root mappings to re-seed cleanly (only the ones we re-define below)
DELETE FROM category_criteria_mapping
WHERE job_category_id = 1
  AND evaluation_criteria_id IN (10101, 10102, 10103, 10104, 10106, 10108, 10110, 10114);

INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES
-- INTERN   (total hint: ~100% across these root criteria)
(1, 10102, 35.0, 'INTERN'),   -- OOP foundation — most important at intern stage
(1, 10101, 30.0, 'INTERN'),   -- Data Structures & Algorithms
(1, 10103, 20.0, 'INTERN'),   -- Database Fundamentals
(1, 10104, 15.0, 'INTERN'),   -- Agile & SDLC Practices

-- FRESHER
(1, 10102, 30.0, 'FRESHER'),  -- OOP still primary
(1, 10101, 25.0, 'FRESHER'),  -- DSA
(1, 10103, 20.0, 'FRESHER'),  -- Database Fundamentals
(1, 10104, 15.0, 'FRESHER'),  -- Agile
(1, 10106,  5.0, 'FRESHER'),  -- SOLID Principles intro
(1, 10114,  5.0, 'FRESHER'),  -- Git Flow basics

-- JUNIOR
(1, 10102, 20.0, 'JUNIOR'),   -- OOP
(1, 10101, 15.0, 'JUNIOR'),   -- DSA
(1, 10103, 15.0, 'JUNIOR'),   -- Database Fundamentals
(1, 10104, 15.0, 'JUNIOR'),   -- Agile
(1, 10106, 15.0, 'JUNIOR'),   -- SOLID Principles
(1, 10114, 10.0, 'JUNIOR'),   -- Git Flow
(1, 10110, 10.0, 'JUNIOR'),   -- Unit Testing & TDD intro

-- MID
(1, 10106, 20.0, 'MID'),      -- SOLID & Clean Code
(1, 10108, 20.0, 'MID'),      -- System Design & Architecture
(1, 10110, 20.0, 'MID'),      -- Unit Testing & TDD
(1, 10102, 15.0, 'MID'),      -- OOP (still relevant)
(1, 10104, 10.0, 'MID'),      -- Agile
(1, 10103, 10.0, 'MID'),      -- DB Fundamentals
(1, 10114,  5.0, 'MID'),      -- Git Flow

-- SENIOR
(1, 10108, 30.0, 'SENIOR'),   -- System Design (primary at senior)
(1, 10106, 20.0, 'SENIOR'),   -- SOLID
(1, 10110, 20.0, 'SENIOR'),   -- Testing
(1, 10104, 15.0, 'SENIOR'),   -- Agile / SDLC leadership
(1, 10114, 15.0, 'SENIOR'),   -- Git Flow / branching strategy

-- LEAD
(1, 10108, 40.0, 'LEAD'),     -- Architecture dominates at lead
(1, 10106, 20.0, 'LEAD'),     -- SOLID / Clean Architecture
(1, 10104, 20.0, 'LEAD'),     -- Agile / team process ownership
(1, 10110, 10.0, 'LEAD'),     -- Testing culture
(1, 10114, 10.0, 'LEAD')      -- Git Flow governance

ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO UPDATE
    SET weight_percentage = EXCLUDED.weight_percentage;


-- ============================================================
-- PART 3: Calibrate BACKEND generic skills (category_id = 10)
--   10201 = API Design, 10202 = DB Modeling, 10203 = Microservices
-- ============================================================

DELETE FROM category_criteria_mapping
WHERE job_category_id = 10
  AND evaluation_criteria_id IN (10201, 10202, 10203);

INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES
-- JUNIOR: API + DB foundations
(10, 10201, 25.0, 'JUNIOR'),   -- API Design
(10, 10202, 25.0, 'JUNIOR'),   -- DB Modeling & SQL

-- MID: balanced; microservices intro
(10, 10201, 25.0, 'MID'),      -- API Design
(10, 10202, 25.0, 'MID'),      -- DB Modeling & SQL
(10, 10203, 15.0, 'MID'),      -- Microservices intro

-- SENIOR: microservices central
(10, 10201, 20.0, 'SENIOR'),   -- API Design
(10, 10202, 20.0, 'SENIOR'),   -- DB Modeling
(10, 10203, 30.0, 'SENIOR'),   -- Microservices & Distributed Systems

-- LEAD: architecture & patterns
(10, 10203, 40.0, 'LEAD'),     -- Microservices / Distributed arch
(10, 10201, 20.0, 'LEAD'),     -- API Design (governance)
(10, 10202, 15.0, 'LEAD')      -- DB Modeling (oversight)

ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO UPDATE
    SET weight_percentage = EXCLUDED.weight_percentage;


-- ============================================================
-- PART 4: Calibrate JAVA_ECOSYSTEM (category_id = 101)
--   VN market: Spring Boot dominant; JVM perf & concurrency at mid+
-- ============================================================

DELETE FROM category_criteria_mapping
WHERE job_category_id = 101
  AND evaluation_criteria_id IN (10301, 10302, 10303, 10304);

INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES
-- FRESHER: Java Core is everything
(101, 10301, 50.0, 'FRESHER'),  -- Java Core Language
(101, 10304, 30.0, 'FRESHER'),  -- Build Tools
(101, 10303, 20.0, 'FRESHER'),  -- Concurrency basics

-- JUNIOR
(101, 10301, 30.0, 'JUNIOR'),   -- Java Core
(101, 10304, 20.0, 'JUNIOR'),   -- Build Tools
(101, 10303, 25.0, 'JUNIOR'),   -- Concurrency
(101, 10302, 10.0, 'JUNIOR'),   -- JVM Internals intro

-- MID
(101, 10301, 15.0, 'MID'),      -- Java Core (assumed)
(101, 10303, 30.0, 'MID'),      -- Concurrency & Reactive
(101, 10302, 25.0, 'MID'),      -- JVM Internals
(101, 10304, 10.0, 'MID'),      -- Build Tools

-- SENIOR
(101, 10303, 35.0, 'SENIOR'),   -- Concurrency / Reactive dominates
(101, 10302, 35.0, 'SENIOR'),   -- JVM Internals & Performance
(101, 10301, 10.0, 'SENIOR'),   -- Java Core (expected)

-- LEAD
(101, 10302, 40.0, 'LEAD'),     -- JVM Performance
(101, 10303, 35.0, 'LEAD'),     -- Concurrency / Reactive
(101, 10301,  5.0, 'LEAD')      -- Java Core (implicit)

ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO UPDATE
    SET weight_percentage = EXCLUDED.weight_percentage;


-- ============================================================
-- PART 5: Calibrate SPRING_BOOT (category_id = 1011)
--   10401 = Spring Core (IoC/DI)
--   10402 = Spring Data JPA/Hibernate
--   10403 = Spring Security
--   10404 = Spring Cloud & Microservices
--   10405 = Spring Reactive (WebFlux)
-- ============================================================

DELETE FROM category_criteria_mapping
WHERE job_category_id = 1011
  AND evaluation_criteria_id IN (10401, 10402, 10403, 10404, 10405);

INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES
-- FRESHER: IoC/DI + JPA basics
(1011, 10401, 40.0, 'FRESHER'),  -- Spring Core IoC/DI
(1011, 10402, 35.0, 'FRESHER'),  -- Spring Data JPA
(1011, 10403, 25.0, 'FRESHER'),  -- Spring Security basics

-- JUNIOR
(1011, 10401, 25.0, 'JUNIOR'),   -- Spring Core
(1011, 10402, 30.0, 'JUNIOR'),   -- Spring Data JPA
(1011, 10403, 25.0, 'JUNIOR'),   -- Spring Security
(1011, 10404, 10.0, 'JUNIOR'),   -- Spring Cloud intro

-- MID
(1011, 10401, 15.0, 'MID'),      -- Spring Core
(1011, 10402, 20.0, 'MID'),      -- Spring Data JPA
(1011, 10403, 20.0, 'MID'),      -- Spring Security
(1011, 10404, 25.0, 'MID'),      -- Spring Cloud
(1011, 10405, 10.0, 'MID'),      -- Spring WebFlux intro

-- SENIOR
(1011, 10404, 30.0, 'SENIOR'),   -- Spring Cloud / Microservices
(1011, 10403, 25.0, 'SENIOR'),   -- Spring Security (OAuth2/JWT deep)
(1011, 10405, 20.0, 'SENIOR'),   -- WebFlux / Reactive
(1011, 10402, 15.0, 'SENIOR'),   -- Spring Data JPA
(1011, 10401, 10.0, 'SENIOR'),   -- Spring Core

-- LEAD
(1011, 10404, 35.0, 'LEAD'),     -- Spring Cloud architecture
(1011, 10405, 30.0, 'LEAD'),     -- Reactive/WebFlux advanced
(1011, 10403, 20.0, 'LEAD'),     -- Security governance
(1011, 10402, 10.0, 'LEAD'),     -- Spring Data
(1011, 10401,  5.0, 'LEAD')      -- Spring Core (implicit)

ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO UPDATE
    SET weight_percentage = EXCLUDED.weight_percentage;


-- ============================================================
-- PART 6: Calibrate FRONTEND (category_id = 20)
--   10701 = Semantic HTML & CSS
--   10702 = DOM Manipulation & Browser APIs
--   10703 = JavaScript / TypeScript Core
-- ============================================================

DELETE FROM category_criteria_mapping
WHERE job_category_id = 20
  AND evaluation_criteria_id IN (10701, 10702, 10703);

INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES
-- FRESHER: HTML/CSS + DOM (no TS yet)
(20, 10701, 45.0, 'FRESHER'),  -- HTML & CSS
(20, 10702, 40.0, 'FRESHER'),  -- DOM & Browser APIs
(20, 10703, 15.0, 'FRESHER'),  -- JS basics

-- JUNIOR
(20, 10701, 25.0, 'JUNIOR'),   -- HTML & CSS
(20, 10702, 30.0, 'JUNIOR'),   -- DOM
(20, 10703, 30.0, 'JUNIOR'),   -- JS/TS (TypeScript intro)

-- MID: JS/TS core becomes primary
(20, 10703, 40.0, 'MID'),      -- JS/TS Advanced
(20, 10702, 25.0, 'MID'),      -- Browser APIs / Web Perf
(20, 10701, 15.0, 'MID'),      -- HTML & CSS (assumed)

-- SENIOR
(20, 10703, 45.0, 'SENIOR'),   -- JS/TS (deep architecture)
(20, 10702, 25.0, 'SENIOR'),   -- Browser / Runtime optimization
(20, 10701, 10.0, 'SENIOR'),   -- HTML & CSS (semantic/a11y)

-- LEAD
(20, 10703, 50.0, 'LEAD'),     -- JS/TS ecosystem leadership
(20, 10702, 25.0, 'LEAD'),     -- Browser internals
(20, 10701, 10.0, 'LEAD')      -- HTML/CSS standards

ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO UPDATE
    SET weight_percentage = EXCLUDED.weight_percentage;


-- ============================================================
-- PART 7: Calibrate REACT_ECOSYSTEM (category_id = 201)
--   10801 = Component Architecture & Lifecycle
--   10802 = Advanced Hook Patterns
--   10803 = State Management (Redux/Zustand)
--   10804 = Performance Optimization
--   10805 = SSR/SSG (Next.js)
-- ============================================================

DELETE FROM category_criteria_mapping
WHERE job_category_id = 201
  AND evaluation_criteria_id IN (10801, 10802, 10803, 10804, 10805);

INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES
-- FRESHER: Component fundamentals only
(201, 10801, 60.0, 'FRESHER'),  -- Component Architecture & Lifecycle
(201, 10802, 25.0, 'FRESHER'),  -- Basic Hooks (useState/useEffect)
(201, 10803, 15.0, 'FRESHER'),  -- State management intro

-- JUNIOR
(201, 10801, 30.0, 'JUNIOR'),   -- Component Architecture
(201, 10802, 25.0, 'JUNIOR'),   -- Hook Patterns
(201, 10803, 25.0, 'JUNIOR'),   -- State Management (Redux/Zustand)
(201, 10805, 15.0, 'JUNIOR'),   -- Next.js basics (SSR/SSG intro)

-- MID
(201, 10802, 25.0, 'MID'),      -- Advanced Hooks (custom hooks, composition)
(201, 10803, 25.0, 'MID'),      -- State Management
(201, 10804, 20.0, 'MID'),      -- Performance (memo, lazy, code-splitting)
(201, 10805, 20.0, 'MID'),      -- Next.js SSR/SSG
(201, 10801, 10.0, 'MID'),      -- Component Architecture

-- SENIOR
(201, 10804, 30.0, 'SENIOR'),   -- Performance Optimization
(201, 10805, 25.0, 'SENIOR'),   -- SSR/SSG / Next.js advanced
(201, 10802, 20.0, 'SENIOR'),   -- Advanced Hook Patterns
(201, 10803, 20.0, 'SENIOR'),   -- State Management
(201, 10801,  5.0, 'SENIOR'),   -- Component Architecture

-- LEAD
(201, 10805, 35.0, 'LEAD'),     -- Next.js / SSR architecture decisions
(201, 10804, 30.0, 'LEAD'),     -- Performance governance
(201, 10802, 20.0, 'LEAD'),     -- Hook patterns / DX
(201, 10803, 15.0, 'LEAD')      -- State architecture

ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO UPDATE
    SET weight_percentage = EXCLUDED.weight_percentage;
