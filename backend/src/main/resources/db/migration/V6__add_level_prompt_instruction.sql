-- ============================================================
-- V6: Add level_prompt_instruction to category_criteria_mapping
-- Complete Level-Aware Prompt Instructions for Software Engineering Body of Knowledge
-- Covers: Root SE, Backend, Frontend, DevOps, Architecture, Quality & Project Management
-- Levels: FRESHER, JUNIOR, MID, SENIOR, LEAD
-- ============================================================

ALTER TABLE category_criteria_mapping
ADD COLUMN IF NOT EXISTS level_prompt_instruction TEXT;

-- ============================================================
-- 1. ROOT & CORE SOFTWARE ENGINEERING CRITERIA
-- ============================================================

-- Data Structures & Algorithms (10101)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate basic knowledge of arrays, linked lists, strings, and basic Big O awareness (O(1), O(N), O(N^2)). "matched" if candidate demonstrates basic data structure usage in coursework or personal projects.'
WHERE evaluation_criteria_id = 10101 AND level IN ('INTERN', 'FRESHER');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR/MID level: Evaluate practical application of Hash Tables, Stacks, Queues, Trees, Binary Search, and sorting algorithms in production code.'
WHERE evaluation_criteria_id = 10101 AND level IN ('JUNIOR', 'MID');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate mastery of complex data structures (Graphs, Tries, Heaps), dynamic programming, algorithmic complexity trade-offs, and memory/time optimization for high-throughput production systems.'
WHERE evaluation_criteria_id = 10101 AND level IN ('SENIOR', 'LEAD');

-- Object-Oriented Programming (OOP) (10102)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate understanding of core OOP pillars: Encapsulation, Inheritance, Polymorphism, and Abstraction. "matched" if candidate can define classes, interfaces, and inheritance hierarchy.'
WHERE evaluation_criteria_id = 10102 AND level IN ('INTERN', 'FRESHER');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate advanced OOP design, composition over inheritance, interface segregation, avoiding anti-patterns (God Class, Anemic Domain Model), and refactoring legacy object models.'
WHERE evaluation_criteria_id = 10102 AND level IN ('SENIOR', 'LEAD');

-- Database Fundamentals (10103)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate basic SQL queries (SELECT, INSERT, UPDATE, DELETE), primary/foreign keys, and basic table relationships.'
WHERE evaluation_criteria_id = 10103 AND level IN ('INTERN', 'FRESHER');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate DB schema design, normalization (1NF-3NF/BCNF), indexing strategies, transaction isolation levels (ACID), locking, execution plans, and query optimization.'
WHERE evaluation_criteria_id = 10103 AND level IN ('SENIOR', 'LEAD');

-- Software Requirements Engineering (10105)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate understanding of basic functional requirements, reading user stories, and following task specifications.'
WHERE evaluation_criteria_id = 10105 AND level IN ('INTERN', 'FRESHER');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For LEAD level: Evaluate expertise in eliciting requirements from business stakeholders, writing SRS/User Stories, defining non-functional requirements (NFRs), and managing scope changes across SDLC.'
WHERE evaluation_criteria_id = 10105 AND level = 'LEAD';

-- SOLID Principles & Clean Code (10106)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate awareness of readable naming conventions, short methods, and basic SOLID principles definition.'
WHERE evaluation_criteria_id = 10106 AND level IN ('INTERN', 'FRESHER');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR/MID level: Evaluate practical implementation of Single Responsibility (SRP) and Dependency Inversion (DIP) in daily feature development.'
WHERE evaluation_criteria_id = 10106 AND level IN ('JUNIOR', 'MID');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate architectural enforcement of all 5 SOLID principles across multi-module systems, establishing team clean code standards, and refactoring complex codebases without regressions.'
WHERE evaluation_criteria_id = 10106 AND level IN ('SENIOR', 'LEAD');

-- Software Design Patterns (10107)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic awareness of Creational patterns like Singleton and Factory.'
WHERE evaluation_criteria_id = 10107 AND level = 'FRESHER';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR/MID level: Evaluate practical application of Strategy, Observer, Builder, Adapter, and Decorator patterns in feature implementation.'
WHERE evaluation_criteria_id = 10107 AND level IN ('JUNIOR', 'MID');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate architectural pattern selection, designing custom pattern abstractions, and analyzing trade-offs between pattern complexity and code maintainability.'
WHERE evaluation_criteria_id = 10107 AND level IN ('SENIOR', 'LEAD');

-- Software Architecture & Microservices (10108)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR level: Evaluate understanding of layered (controller-service-repository) architecture within monolithic applications.'
WHERE evaluation_criteria_id = 10108 AND level = 'JUNIOR';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For MID level: Evaluate experience defining module boundaries, RESTful inter-service communication, Clean/Hexagonal Architecture, and basic microservice deployment.'
WHERE evaluation_criteria_id = 10108 AND level = 'MID';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate distributed systems architecture, microservices decomposition, Saga pattern for distributed transactions, CQRS, Event-Driven Architecture, Service Mesh, high availability, fault tolerance (Circuit Breaker, Bulkhead), and scalability trade-offs.'
WHERE evaluation_criteria_id = 10108 AND level IN ('SENIOR', 'LEAD');

-- OOAD & UML Modeling (10109)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate ability to read basic UML Class diagrams and Use Case diagrams.'
WHERE evaluation_criteria_id = 10109 AND level IN ('INTERN', 'FRESHER');

-- Unit Testing & TDD (10110)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate basic unit testing knowledge (JUnit, Jest) for simple utility logic.'
WHERE evaluation_criteria_id = 10110 AND level IN ('INTERN', 'FRESHER');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR/MID level: Evaluate writing comprehensive unit tests, mock objects (Mockito/Jest mocks), test coverage tools, and Test-Driven Development (TDD) workflow.'
WHERE evaluation_criteria_id = 10110 AND level IN ('JUNIOR', 'MID');

-- Integration & E2E Testing (10111)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR/MID level: Evaluate experience writing API integration tests (RestAssured/Supertest), test data setup, and basic E2E testing.'
WHERE evaluation_criteria_id = 10111 AND level IN ('JUNIOR', 'MID');

-- Code Review & Static Analysis (10112)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR/MID level: Evaluate participation in peer code reviews and fixing static analysis issues (SonarQube, ESLint).'
WHERE evaluation_criteria_id = 10112 AND level IN ('JUNIOR', 'MID');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate establishing team code review guidelines, automated static analysis quality gate setup, and mentoring junior developers through code reviews.'
WHERE evaluation_criteria_id = 10112 AND level IN ('SENIOR', 'LEAD');

-- Refactoring & Code Smells (10113)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR/MID level: Evaluate ability to identify basic code smells (duplicated code, long methods) and perform simple refactoring.'
WHERE evaluation_criteria_id = 10113 AND level IN ('JUNIOR', 'MID');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate systematic refactoring of complex legacy systems, extracting microservices, and eliminating architectural debt safely without breaking production functionality.'
WHERE evaluation_criteria_id = 10113 AND level IN ('SENIOR', 'LEAD');

-- Git Flow & Version Control Strategy (10114)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate basic Git commands (clone, commit, push, pull, branch creation) and submitting pull requests.'
WHERE evaluation_criteria_id = 10114 AND level IN ('INTERN', 'FRESHER');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR/MID level: Evaluate Git Flow / Trunk-Based Development workflows, resolving merge conflicts, and interactive rebase.'
WHERE evaluation_criteria_id = 10114 AND level IN ('JUNIOR', 'MID');

-- CI/CD & Release Engineering (10115)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For MID level: Evaluate experience configuring CI build pipelines (GitHub Actions, GitLab CI, Jenkins) and automated test execution.'
WHERE evaluation_criteria_id = 10115 AND level = 'MID';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate designing end-to-end zero-downtime deployment pipelines (Blue/Green, Canary), automated rollback, artifact versioning, and Infrastructure-as-Code integration.'
WHERE evaluation_criteria_id = 10115 AND level IN ('SENIOR', 'LEAD');

-- Software Security & OWASP Top 10 (10116)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR level: Evaluate basic security awareness (preventing SQL Injection, XSS, and avoiding hardcoded credentials).'
WHERE evaluation_criteria_id = 10116 AND level = 'JUNIOR';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For MID/SENIOR level: Evaluate mastery of OWASP Top 10, SAST/DAST pipeline integration, OAuth2/OIDC authentication architecture, secrets management (HashiCorp Vault), and secure software development lifecycle (SSDLC).'
WHERE evaluation_criteria_id = 10116 AND level IN ('MID', 'SENIOR', 'LEAD');

-- Database Optimization & ORM Practices (10117)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic ORM mapping and simple database queries.'
WHERE evaluation_criteria_id = 10117 AND level = 'FRESHER';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR level: Evaluate writing efficient SQL queries, understanding indexes, and basic ORM usage.'
WHERE evaluation_criteria_id = 10117 AND level = 'JUNIOR';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate resolving ORM N+1 query problems, EXPLAIN query execution plan analysis, composite index optimization, table partitioning, connection pool tuning (HikariCP), and DB migration strategies.'
WHERE evaluation_criteria_id = 10117 AND level IN ('SENIOR', 'LEAD');

-- Debugging & Observability (10118)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For MID level: Evaluate log analysis, structured logging, local debugging with breakpoints, and using APM monitoring tools.'
WHERE evaluation_criteria_id = 10118 AND level = 'MID';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate distributed tracing (OpenTelemetry/Jaeger), production thread dump & heap dump analysis, memory leak resolution, and setting up SLI/SLO alerts.'
WHERE evaluation_criteria_id = 10118 AND level IN ('SENIOR', 'LEAD');

-- Technical Documentation & OpenAPI (10119)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate ability to write clear code comments, README files, and basic API documentation.'
WHERE evaluation_criteria_id = 10119 AND level IN ('INTERN', 'FRESHER');

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For LEAD level: Evaluate authoring Architecture Decision Records (ADR), OpenAPI/Swagger specs, system architecture diagrams, and developer onboarding guides.'
WHERE evaluation_criteria_id = 10119 AND level = 'LEAD';

-- Software Estimation & Project Planning (10120)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate sprint estimation (Planning Poker/Story Points), technical debt management, task breakdown, risk assessment, and project roadmap planning.'
WHERE evaluation_criteria_id = 10120 AND level IN ('SENIOR', 'LEAD');

-- Agile & SDLC Practices (10104)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER/INTERN level: Evaluate basic awareness of Agile Scrum concepts, daily standups, and sprint planning.'
WHERE evaluation_criteria_id = 10104 AND level IN ('INTERN', 'FRESHER');

-- ============================================================
-- 2. BACKEND & FRAMEWORK SPECIFIC CRITERIA
-- ============================================================

-- API Design (REST/GraphQL) (10201)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR level: Evaluate basic HTTP methods (GET, POST, PUT, DELETE), status codes, and RESTful resource naming.'
WHERE evaluation_criteria_id = 10201 AND level = 'JUNIOR';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate API versioning strategies, HATEOAS, OpenAPI specifications, rate limiting, gRPC vs REST vs GraphQL trade-off analysis, and API Gateway integration.'
WHERE evaluation_criteria_id = 10201 AND level IN ('SENIOR', 'LEAD');

-- Database Modeling & SQL (10202)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR level: Evaluate writing complex SELECT queries with JOINs, GROUP BY, subqueries, and table schema creation.'
WHERE evaluation_criteria_id = 10202 AND level = 'JUNIOR';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate advanced DB modeling, CTEs, Window Functions, denormalization trade-offs, Flyway/Liquibase schema migrations, and multi-tenant DB architecture.'
WHERE evaluation_criteria_id = 10202 AND level IN ('SENIOR', 'LEAD');

-- Message Queuing Basics (10203)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For MID level: Evaluate basic async communication, pub/sub patterns, and consuming/producing messages with RabbitMQ or Kafka.'
WHERE evaluation_criteria_id = 10203 AND level = 'MID';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate designing event schemas, message deduplication, idempotent consumers, Outbox pattern, Kafka partition tuning, and eventual consistency handling.'
WHERE evaluation_criteria_id = 10203 AND level IN ('SENIOR', 'LEAD');

-- Spring Core (IoC/DI) (10401)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic understanding of Inversion of Control, @Component, @Autowired annotations, and basic dependency injection setup in Spring Boot.'
WHERE evaluation_criteria_id = 10401 AND level = 'FRESHER';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate Bean lifecycles, custom scopes, circular dependency resolution, proxy mechanisms (JDK dynamic vs CGLIB), and advanced ApplicationContext configuration in enterprise applications.'
WHERE evaluation_criteria_id = 10401 AND level IN ('SENIOR', 'LEAD');

-- Spring Data JPA/Hibernate (10402)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic usage of @Entity, @Repository, standard JpaRepository CRUD methods, and simple entity mappings (@OneToMany).'
WHERE evaluation_criteria_id = 10402 AND level = 'FRESHER';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate mastery of N+1 query problem solutions, batch fetching strategies, custom @Query with JPQL/native SQL, Specification API, second-level caching, transaction management propagation, and DB performance tuning.'
WHERE evaluation_criteria_id = 10402 AND level IN ('SENIOR', 'LEAD');

-- Node.js Event Loop & Async (10501)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic understanding of asynchronous JavaScript, Promises, async/await syntax, and callback functions.'
WHERE evaluation_criteria_id = 10501 AND level = 'FRESHER';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate deep understanding of V8 event loop phases (timers, I/O polling, check, close), microtask queue vs macrotask queue prioritization, unhandled rejection handling, and event loop lag monitoring in high-throughput node services.'
WHERE evaluation_criteria_id = 10501 AND level IN ('SENIOR', 'LEAD');

-- NestJS Architecture (10601)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic NestJS project setup, defining Modules, Controllers, and Providers.'
WHERE evaluation_criteria_id = 10601 AND level = 'FRESHER';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate custom dynamic modules, custom providers, NestJS microservices transport layers (TCP, Redis, Kafka), and custom decorator creation.'
WHERE evaluation_criteria_id = 10601 AND level IN ('SENIOR', 'LEAD');

-- ============================================================
-- 3. FRONTEND SPECIFIC CRITERIA
-- ============================================================

-- Semantic HTML & CSS (10701)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic HTML5 semantic tags, CSS Flexbox/Grid layouts, and responsive design.'
WHERE evaluation_criteria_id = 10701 AND level = 'FRESHER';

-- DOM Manipulation & Browser APIs (10702)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate vanilla JavaScript DOM event handling, Fetch API, and LocalStorage usage.'
WHERE evaluation_criteria_id = 10702 AND level = 'FRESHER';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate Critical Rendering Path, Web Workers, IndexedDB, Service Workers, and browser memory leak prevention.'
WHERE evaluation_criteria_id = 10702 AND level IN ('SENIOR', 'LEAD');

-- React Component Architecture (10801)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic React component structure, props, state (useState), event handling, and simple JSX layouts.'
WHERE evaluation_criteria_id = 10801 AND level = 'FRESHER';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate advanced design patterns (Compound Components, Render Props, HOCs), Virtual DOM reconciliation optimization, micro-frontends, state colocation strategies, and architectural component libraries.'
WHERE evaluation_criteria_id = 10801 AND level IN ('SENIOR', 'LEAD');

-- React Performance (Memo/useCallback) (10804)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For MID level: Evaluate basic useMemo and useCallback usage to prevent unnecessary child re-renders.'
WHERE evaluation_criteria_id = 10804 AND level = 'MID';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate React Profiler analysis, memoization strategies, list virtualization for large datasets (react-window/react-virtualized), and avoiding premature optimization.'
WHERE evaluation_criteria_id = 10804 AND level IN ('SENIOR', 'LEAD');

-- ============================================================
-- 4. DEVOPS & INFRASTRUCTURE SPECIFIC CRITERIA
-- ============================================================

-- Linux Administration (10901)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For FRESHER level: Evaluate basic Linux terminal commands (file navigation, permissions, system status).'
WHERE evaluation_criteria_id = 10901 AND level = 'FRESHER';

-- Docker & Containerization (10904)
UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For JUNIOR level: Evaluate basic Docker commands, writing simple Dockerfiles, and container execution.'
WHERE evaluation_criteria_id = 10904 AND level = 'JUNIOR';

UPDATE category_criteria_mapping
SET level_prompt_instruction = 'For SENIOR/LEAD level: Evaluate multi-stage Docker builds, minimal base images (Distroless/Alpine), container vulnerability scanning (Trivy), and container security hardening.'
WHERE evaluation_criteria_id = 10904 AND level IN ('SENIOR', 'LEAD');
