-- ============================================================
-- V4: Add Deep 4-Level Software Engineering Category Tree & Comprehensive Criteria
-- Complete Software Engineering Body of Knowledge (SWEBOK aligned):
-- 1. Development (Backend, Frontend, Fullstack, Mobile)
-- 2. Architecture & Design (Microservices, SOLID, Clean Arch, Patterns, DDD)
-- 3. Quality & Testing (Automation, Manual, Performance, Security, Static Analysis, Unit/TDD)
-- 4. DevOps & Platform (CI/CD, K8s, Docker, Cloud, Observability)
-- 5. Data & AI (RDBMS, NoSQL, Vector DB, RAG/LLM)
-- 6. Project Management & SDLC (Agile/Scrum, Requirements, Documentation, Estimation)
-- ============================================================

-- ------------------------------------------------------------
-- 1. Seed Deep Job Categories Hierarchy Tree (Level 1 -> Level 2 -> Level 3)
-- ------------------------------------------------------------
INSERT INTO job_categories (id, code, name, parent_id) VALUES
-- Level 1 Pillars
(100, 'SOFTWARE_ARCHITECTURE', 'SOFTWARE_ARCHITECTURE', 1),
(110, 'SOFTWARE_PROJECT_MANAGEMENT', 'SOFTWARE_PROJECT_MANAGEMENT', 1),

-- Level 2 Sub-Domains (Architecture & Design)
(1001, 'SYSTEM_DESIGN_ARCHITECTURE', 'SYSTEM_DESIGN_ARCHITECTURE', 100),
(1002, 'DESIGN_PATTERNS_PRINCIPLES', 'DESIGN_PATTERNS_PRINCIPLES', 100),
(1003, 'OOAD_SYSTEM_MODELING', 'OOAD_SYSTEM_MODELING', 100),

-- Level 2 Sub-Domains (QA & Testing - expanding under domain 80)
(804, 'CODE_QUALITY_METRICS', 'CODE_QUALITY_METRICS', 80),

-- Level 2 Sub-Domains (DevOps & Infrastructure - expanding under domain 60)
(606, 'OBSERVABILITY_SRE', 'OBSERVABILITY_SRE', 60),

-- Level 2 Sub-Domains (Data & AI - expanding under domain 40)
(405, 'VECTOR_DATABASES', 'VECTOR_DATABASES', 40),

-- Level 2 Sub-Domains (Software Project Management under domain 110)
(1101, 'AGILE_SCRUM_METHODOLOGY', 'AGILE_SCRUM_METHODOLOGY', 110),
(1102, 'REQUIREMENTS_ENGINEERING', 'REQUIREMENTS_ENGINEERING', 110),
(1103, 'TECHNICAL_DOCUMENTATION', 'TECHNICAL_DOCUMENTATION', 110),

-- Level 3 Specialized Roles & Frameworks
-- Under 1001 SYSTEM_DESIGN_ARCHITECTURE
(10011, 'MICROSERVICES_ARCHITECTURE', 'MICROSERVICES_ARCHITECTURE', 1001),
(10012, 'CLEAN_HEXAGONAL_ARCHITECTURE', 'CLEAN_HEXAGONAL_ARCHITECTURE', 1001),
(10013, 'EVENT_DRIVEN_CQRS', 'EVENT_DRIVEN_CQRS', 1001),

-- Under 1002 DESIGN_PATTERNS_PRINCIPLES
(10021, 'GOF_DESIGN_PATTERNS', 'GOF_DESIGN_PATTERNS', 1002),
(10022, 'SOLID_CLEAN_CODE', 'SOLID_CLEAN_CODE', 1002),

-- Under 1003 OOAD_SYSTEM_MODELING
(10031, 'UML_DIAGRAMMING', 'UML_DIAGRAMMING', 1003),
(10032, 'DOMAIN_DRIVEN_DESIGN', 'DOMAIN_DRIVEN_DESIGN', 1003),

-- Under 804 CODE_QUALITY_METRICS
(8041, 'STATIC_CODE_ANALYSIS', 'STATIC_CODE_ANALYSIS', 804),
(8042, 'UNIT_TESTING_TDD', 'UNIT_TESTING_TDD', 804),

-- Under 606 OBSERVABILITY_SRE
(6061, 'LOGGING_TRACING_ELK', 'LOGGING_TRACING_ELK', 606),
(6062, 'PROMETHEUS_GRAFANA', 'PROMETHEUS_GRAFANA', 606),

-- Under 1101 AGILE_SCRUM_METHODOLOGY
(11011, 'SCRUM_FRAMEWORK', 'SCRUM_FRAMEWORK', 1101),
(11012, 'KANBAN_FLOW', 'KANBAN_FLOW', 1101),

-- Under 1102 REQUIREMENTS_ENGINEERING
(11021, 'REQUIREMENT_ANALYSIS_SRS', 'REQUIREMENT_ANALYSIS_SRS', 1102),
(11022, 'ESTIMATION_PLANNING', 'ESTIMATION_PLANNING', 1102),

-- Under 1103 TECHNICAL_DOCUMENTATION
(11031, 'OPENAPI_SWAGGER', 'OPENAPI_SWAGGER', 1103),
(11032, 'ADR_ARCHITECTURE_DOCS', 'ADR_ARCHITECTURE_DOCS', 1103)
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 2. Insert Core Evaluation Criteria (IDs: 10105 - 10124)
-- ------------------------------------------------------------
INSERT INTO evaluation_criteria (id, name, category, question_type, prompt_instruction) VALUES
(10105, 'Software Requirements Engineering', 'technical', 'technical', 'Evaluate understanding of functional/non-functional requirements, writing SRS/User Stories, use cases, and managing requirement changes throughout SDLC. Status="matched|weak|missing".'),
(10106, 'SOLID Principles & Clean Code', 'technical', 'technical', 'Evaluate mastery of SOLID principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion), clean code practices, and readable naming conventions. Status="matched|weak|missing".'),
(10107, 'Software Design Patterns', 'technical', 'technical', 'Evaluate practical application of Gang of Four (GoF) design patterns including Creational (Factory, Builder, Singleton), Structural (Adapter, Decorator, Facade), and Behavioral (Observer, Strategy, Command). Status="matched|weak|missing".'),
(10108, 'Software Architecture & Microservices', 'technical', 'system_design', 'Evaluate understanding of architectural styles (Monolithic, Layered, Clean/Hexagonal Architecture, Microservices, Event-Driven Architecture, CQRS) and system scalability tradeoffs. Status="matched|weak|missing".'),
(10109, 'OOAD & UML Modeling', 'technical', 'technical', 'Evaluate proficiency in Object-Oriented Analysis & Design (OOAD), drawing and interpreting UML diagrams (Use Case, Class, Sequence, Component, ERD). Status="matched|weak|missing".'),
(10110, 'Unit Testing & TDD', 'technical', 'technical', 'Evaluate hands-on experience with unit testing frameworks (JUnit, Jest, PyTest), Test-Driven Development (TDD), mocking frameworks (Mockito), and code coverage metrics. Status="matched|weak|missing".'),
(10111, 'Integration & E2E Testing', 'technical', 'technical', 'Evaluate ability to design integration tests, REST/gRPC API testing, test data setup, and End-to-End (E2E) testing strategies. Status="matched|weak|missing".'),
(10112, 'Code Review & Static Analysis', 'technical', 'technical', 'Evaluate experience conducting peer code reviews, establishing team coding standards, and configuring static code analysis tools (SonarQube, Checkstyle, ESLint). Status="matched|weak|missing".'),
(10113, 'Refactoring & Code Smells', 'technical', 'technical', 'Evaluate ability to identify code smells (Duplicated Code, Long Method, Large Class, Feature Envy) and perform safe refactoring without altering system behavior. Status="matched|weak|missing".'),
(10114, 'Git Flow & Version Control Strategy', 'technical', 'technical', 'Evaluate mastery of Git version control, branching models (Git Flow, Trunk-Based Development), pull request workflows, interactive rebase, and resolving complex merge conflicts. Status="matched|weak|missing".'),
(10115, 'CI/CD & Release Engineering', 'technical', 'technical', 'Evaluate experience building automated CI/CD pipelines (GitHub Actions, GitLab CI, Jenkins), build automation (Maven/Gradle/npm), artifact management, and release deployment strategies. Status="matched|weak|missing".'),
(10116, 'Software Security & OWASP Top 10', 'technical', 'technical', 'Evaluate awareness and prevention of software security vulnerabilities (SQL Injection, XSS, CSRF, Broken Access Control, Sensitive Data Exposure) and secure coding standards. Status="matched|weak|missing".'),
(10117, 'Database Optimization & ORM Practices', 'technical', 'technical', 'Evaluate skills in DB schema normalization (1NF-3NF), writing efficient SQL queries, indexing strategies, handling transaction isolation, and avoiding ORM N+1 query problems. Status="matched|weak|missing".'),
(10118, 'Debugging & Observability', 'technical', 'technical', 'Evaluate systematic debugging skills, log analysis, structured logging (SLF4J/Winston), APM tools, distributed tracing, and memory/thread dump analysis. Status="matched|weak|missing".'),
(10119, 'Technical Documentation & OpenAPI', 'technical', 'technical', 'Evaluate ability to write clear technical documentation, API specifications (OpenAPI/Swagger), Architecture Decision Records (ADR), and developer guides. Status="matched|weak|missing".'),
(10120, 'Software Estimation & Project Planning', 'technical', 'behavioral', 'Evaluate techniques for effort estimation (Story Points, Planning Poker, PERT), risk management, technical debt tracking, and task breakdown. Status="matched|weak|missing".'),
(10121, 'Domain-Driven Design (DDD)', 'technical', 'system_design', 'Evaluate understanding of DDD concepts: Bounded Contexts, Ubiquitous Language, Aggregates, Entities, Value Objects, and Domain Events. Status="matched|weak|missing".'),
(10122, 'Event-Driven Architecture & Messaging', 'technical', 'system_design', 'Evaluate experience with asynchronous messaging, event buses, Kafka/RabbitMQ integration, event sourcing, and eventual consistency. Status="matched|weak|missing".'),
(10123, 'Site Reliability & Observability (SRE)', 'technical', 'technical', 'Evaluate metrics monitoring (Prometheus/Grafana), distributed tracing (OpenTelemetry/Jaeger), SLO/SLA management, and incident response. Status="matched|weak|missing".'),
(10124, 'Agile Scrum & Kanban Execution', 'soft_skill', 'behavioral', 'Evaluate active participation in Scrum ceremonies, WIP limit management, sprint delivery, and continuous team improvement. Status="matched|weak|missing".')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 3. Mappings for SOFTWARE_ENGINEERING (Root Category id: 1) across Seniority Levels
-- ------------------------------------------------------------

-- Level: INTERN
INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES
(1, 10105, 15.0, 'INTERN'),
(1, 10106, 25.0, 'INTERN'),
(1, 10109, 15.0, 'INTERN'),
(1, 10110, 15.0, 'INTERN'),
(1, 10114, 15.0, 'INTERN'),
(1, 10119, 15.0, 'INTERN'),

-- Level: FRESHER
(1, 10106, 20.0, 'FRESHER'),
(1, 10107, 15.0, 'FRESHER'),
(1, 10109, 10.0, 'FRESHER'),
(1, 10110, 15.0, 'FRESHER'),
(1, 10114, 15.0, 'FRESHER'),
(1, 10117, 15.0, 'FRESHER'),
(1, 10119, 10.0, 'FRESHER'),

-- Level: JUNIOR
(1, 10106, 15.0, 'JUNIOR'),
(1, 10107, 15.0, 'JUNIOR'),
(1, 10110, 15.0, 'JUNIOR'),
(1, 10111, 10.0, 'JUNIOR'),
(1, 10112, 10.0, 'JUNIOR'),
(1, 10113, 10.0, 'JUNIOR'),
(1, 10116, 15.0, 'JUNIOR'),
(1, 10117, 10.0, 'JUNIOR'),

-- Level: MID
(1, 10107, 15.0, 'MID'),
(1, 10108, 15.0, 'MID'),
(1, 10112, 10.0, 'MID'),
(1, 10113, 15.0, 'MID'),
(1, 10115, 15.0, 'MID'),
(1, 10116, 15.0, 'MID'),
(1, 10118, 15.0, 'MID'),

-- Level: SENIOR
(1, 10108, 25.0, 'SENIOR'),
(1, 10112, 10.0, 'SENIOR'),
(1, 10113, 15.0, 'SENIOR'),
(1, 10115, 15.0, 'SENIOR'),
(1, 10116, 15.0, 'SENIOR'),
(1, 10118, 10.0, 'SENIOR'),
(1, 10120, 10.0, 'SENIOR'),

-- Level: LEAD
(1, 10105, 15.0, 'LEAD'),
(1, 10108, 30.0, 'LEAD'),
(1, 10112, 10.0, 'LEAD'),
(1, 10115, 15.0, 'LEAD'),
(1, 10119, 15.0, 'LEAD'),
(1, 10120, 15.0, 'LEAD')
ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO NOTHING;

-- ------------------------------------------------------------
-- 4. Specific Mappings for Sub-Categories (Level 2 & Level 3)
-- ------------------------------------------------------------
INSERT INTO category_criteria_mapping (job_category_id, evaluation_criteria_id, weight_percentage, level) VALUES
-- SOFTWARE_ARCHITECTURE (id: 100) & Sub-nodes
(100, 10107, 25.0, 'ALL'),
(100, 10108, 40.0, 'ALL'),
(100, 10119, 20.0, 'ALL'),
(100, 10121, 15.0, 'ALL'),

(10011, 10108, 50.0, 'ALL'), -- Microservices Architecture
(10011, 10122, 50.0, 'ALL'), -- Event-Driven Messaging

(10022, 10106, 60.0, 'ALL'), -- SOLID & Clean Code
(10022, 10113, 40.0, 'ALL'), -- Refactoring

(10032, 10121, 100.0, 'ALL'), -- Domain-Driven Design

-- SOFTWARE_PROJECT_MANAGEMENT (id: 110) & Sub-nodes
(110, 10105, 30.0, 'ALL'),
(110, 10120, 40.0, 'ALL'),
(110, 10124, 30.0, 'ALL'),

(11021, 10105, 100.0, 'ALL'), -- Requirement Analysis SRS
(11031, 10119, 100.0, 'ALL'), -- OpenAPI Swagger

-- CODE_QUALITY_METRICS (id: 804) & Sub-nodes
(804, 10110, 40.0, 'ALL'),
(804, 10112, 30.0, 'ALL'),
(804, 10113, 30.0, 'ALL'),

-- OBSERVABILITY_SRE (id: 606) & Sub-nodes
(606, 10118, 50.0, 'ALL'),
(606, 10123, 50.0, 'ALL')
ON CONFLICT (job_category_id, evaluation_criteria_id, level) DO NOTHING;

-- ------------------------------------------------------------
-- 5. System Settings Configuration
-- Set default CRITERIA_BATCH_SIZE to 5 (Optimal precision & latency balance)
-- ------------------------------------------------------------
INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('CRITERIA_BATCH_SIZE', '5', 'Max criteria count per LLM assessment batch for optimal precision and low latency', NOW())
ON CONFLICT (setting_key) DO UPDATE SET setting_value = '5', updated_at = NOW();

INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
VALUES ('INCLUDE_NOT_APPLICABLE_CRITERIA', 'false', 'Whether to include NOT_APPLICABLE criteria in assessment results (true = 360 degree audit, false = strict JD matching)', NOW())
ON CONFLICT (setting_key) DO NOTHING;
