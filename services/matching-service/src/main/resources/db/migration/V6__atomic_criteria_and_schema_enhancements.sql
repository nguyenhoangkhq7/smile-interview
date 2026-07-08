-- ============================================================
-- V6: Deepen Criteria Hierarchy & Add Schema Enhancements
-- Replaces old criteria with atomic multi-level criteria for 4 target domains.
-- ============================================================

-- 1. DELETE OLD DATA to prevent incompatibility with new DTO/JSON schema
DELETE FROM resume_assessments;

-- Delete mappings for the specific domains we are replacing
DELETE FROM category_criteria_mapping WHERE job_category_id IN (1, 10, 101, 1011, 102, 1021, 20, 201, 60, 601);

-- Delete old criteria that we are replacing
DELETE FROM evaluation_criteria WHERE id IN (1001, 1002, 2001, 2002, 2101, 2501, 3001, 3002, 3011, 3012, 3101, 3501);

-- 2. EXPLANATION OF MULTI-LEVEL WEIGHT NORMALIZATION
-- The scoring formula dynamically calculates: SUM(weight * points) / SUM(weight).
-- Because criteria are collected recursively from Leaf -> Root (via CTE in JobCriteriaRepository),
-- weights DO NOT need to sum to 100 per node or category.
-- The formula self-normalizes based on the total weights of all activated criteria across the inheritance tree.

-- 3. CREATE suggested_criteria TABLE
CREATE TABLE IF NOT EXISTS suggested_criteria (
    id              BIGSERIAL PRIMARY KEY,
    job_category    VARCHAR(50)  NOT NULL,
    criteria_name   VARCHAR(200) NOT NULL,
    occurrence_count INT         NOT NULL DEFAULT 1,
    last_seen_at    TIMESTAMP    NOT NULL,
    sample_jd_text  TEXT,
    promoted        BOOLEAN      NOT NULL DEFAULT FALSE
);

-- 4. INSERT ATOMIC CRITERIA (4 TARGET BRANCHES)
INSERT INTO evaluation_criteria (id, criteria_name, prompt_instruction) VALUES
-- ROOT L1 CRITERIA
(10101, 'Data Structures & Algorithms', 'Evaluate knowledge of fundamental data structures (arrays, linked lists, hash tables, trees, graphs) and algorithms (sorting, searching, Big O notation). Status must be "matched" if demonstrated, "weak" if basic, "missing" if absent.'),
(10102, 'Object-Oriented Programming (OOP)', 'Evaluate understanding of OOP principles (Encapsulation, Inheritance, Polymorphism, Abstraction) and common design patterns. Status must be "matched" if demonstrated, "weak" if basic, "missing" if absent.'),
(10103, 'Database Fundamentals', 'Evaluate basic knowledge of databases (SQL vs NoSQL), schema design, simple queries, and normal forms. Status="matched|weak|missing".'),

-- A. BACKEND
(10201, 'API Design (REST/GraphQL)', 'Evaluate experience designing RESTful APIs (HTTP methods, status codes, URIs) or GraphQL endpoints. Status="matched|weak|missing".'),
(10202, 'Database Modeling & SQL', 'Evaluate ability to design DB schemas, write complex queries, use transactions, and optimize indexes. Status="matched|weak|missing".'),
(10203, 'Message Queuing Basics', 'Evaluate understanding of async communication, publish/subscribe patterns, and basic message brokers (RabbitMQ/Kafka). Status="matched|weak|missing".'),

-- JAVA ECOSYSTEM
(10301, 'Java Core Language', 'Evaluate knowledge of Java syntax, collections framework, exception handling, and streams. Status="matched|weak|missing".'),
(10302, 'JVM Internals & Garbage Collection', 'Evaluate understanding of JVM architecture, memory management, and Garbage Collection tuning. Status="matched|weak|missing".'),
(10303, 'Java Concurrency', 'Evaluate experience with multithreading, synchronization, ExecutorService, and CompletableFuture. Status="matched|weak|missing".'),
(10304, 'Build Tools (Maven/Gradle)', 'Evaluate experience managing dependencies, build lifecycles, and plugins using Maven or Gradle. Status="matched|weak|missing".'),

-- SPRING BOOT
(10401, 'Spring Core (IoC/DI)', 'Evaluate mastery of Inversion of Control, Dependency Injection, bean scopes, and context configuration. Status="matched|weak|missing".'),
(10402, 'Spring Data JPA/Hibernate', 'Evaluate experience with ORM mapping, entity relationships, Spring Data repositories, and lazy/eager fetching. Status="matched|weak|missing".'),
(10403, 'Spring Security', 'Evaluate ability to implement authentication and authorization, JWT, OAuth2, and security filter chains. Status="matched|weak|missing".'),
(10404, 'Spring Boot Actuator & Observability', 'Evaluate experience configuring health checks, metrics, tracing, and logging in Spring Boot. Status="matched|weak|missing".'),
(10405, 'Spring WebFlux (Reactive)', 'Evaluate understanding of reactive programming, Project Reactor, Mono/Flux, and non-blocking I/O. Status="matched|weak|missing".'),

-- B. NODE ECOSYSTEM
(10501, 'Event Loop & Async/Await', 'Evaluate deep understanding of the Node.js event loop phases, micro/macro tasks, Promises, and async/await. Status="matched|weak|missing".'),
(10502, 'V8 Memory Management', 'Evaluate understanding of V8 engine internals, memory limits, heap allocation, and preventing memory leaks. Status="matched|weak|missing".'),
(10503, 'Node Streams & Buffers', 'Evaluate experience processing large files or data streams using Streams API and Buffers. Status="matched|weak|missing".'),
(10504, 'Package Management', 'Evaluate experience with npm/yarn/pnpm, handling package.json, semantic versioning, and resolving conflicts. Status="matched|weak|missing".'),

-- NESTJS
(10601, 'NestJS Architecture (Modules/DI)', 'Evaluate experience structuring NestJS applications, defining Modules, and utilizing Dependency Injection. Status="matched|weak|missing".'),
(10602, 'Guards, Interceptors, Pipes', 'Evaluate ability to implement custom routing logic, request validation (Pipes), authentication (Guards), and request/response transformation (Interceptors). Status="matched|weak|missing".'),
(10603, 'TypeORM/Prisma Integration', 'Evaluate experience integrating NestJS with ORMs like TypeORM or Prisma for database interactions. Status="matched|weak|missing".'),
(10604, 'NestJS Microservices', 'Evaluate experience building microservices with NestJS using transports like TCP, Redis, or Kafka. Status="matched|weak|missing".'),

-- C. FRONTEND
(10701, 'Semantic HTML & CSS', 'Evaluate mastery of semantic HTML5 tags, CSS3, Flexbox/Grid layouts, and responsive design. Status="matched|weak|missing".'),
(10702, 'DOM Manipulation & Browser APIs', 'Evaluate vanilla JavaScript skills, DOM event handling, Web Storage, and Fetch API. Status="matched|weak|missing".'),
(10703, 'Web Performance Basics', 'Evaluate knowledge of Critical Rendering Path, minimizing layout thrashing, and basic asset optimization. Status="matched|weak|missing".'),

-- REACT
(10801, 'Component Architecture & Lifecycle', 'Evaluate understanding of React components, props/state, component lifecycle, and virtual DOM. Status="matched|weak|missing".'),
(10802, 'Advanced Hook Patterns', 'Evaluate proficiency with custom hooks, useReducer, useContext, and managing complex side effects (useEffect). Status="matched|weak|missing".'),
(10803, 'State Management (Redux/Zustand)', 'Evaluate experience with global state management libraries like Redux, Zustand, or Jotai. Status="matched|weak|missing".'),
(10804, 'React Performance (Memo/useCallback)', 'Evaluate ability to profile React apps, prevent unnecessary re-renders using memoization techniques (useMemo, useCallback, React.memo). Status="matched|weak|missing".'),
(10805, 'SSR/SSG (Next.js)', 'Evaluate understanding of Server-Side Rendering, Static Site Generation, and basic Next.js features. Status="matched|weak|missing".'),

-- D. DEVOPS & CLOUD
(10901, 'Linux Administration', 'Evaluate proficiency in Linux OS, process management, file permissions, and system monitoring. Status="matched|weak|missing".'),
(10902, 'Shell Scripting', 'Evaluate ability to write Bash/Shell scripts for automating system tasks. Status="matched|weak|missing".'),
(10903, 'CI/CD Fundamentals', 'Evaluate understanding of Continuous Integration and Continuous Deployment pipelines. Status="matched|weak|missing".'),
(10904, 'Docker & Containerization', 'Evaluate experience creating Dockerfiles, building images, and managing containers. Status="matched|weak|missing".'),

-- AWS INFRA
(11001, 'AWS Compute & Auto-scaling', 'Evaluate experience with EC2, Auto Scaling Groups, and serverless compute (Lambda). Status="matched|weak|missing".'),
(11002, 'AWS IAM & Security Policies', 'Evaluate ability to design least-privilege IAM roles, policies, and managing access to AWS resources. Status="matched|weak|missing".'),
(11003, 'VPC & Networking', 'Evaluate knowledge of VPCs, subnets, route tables, security groups, and NAT gateways. Status="matched|weak|missing".'),
(11004, 'AWS Storage Strategies', 'Evaluate experience choosing and configuring AWS storage services (S3, EBS, EFS) for different use cases. Status="matched|weak|missing".'),
(11005, 'Cost Optimization & Monitoring', 'Evaluate experience using AWS CloudWatch, Cost Explorer, and optimizing infrastructure spend. Status="matched|weak|missing".')
ON CONFLICT (id) DO NOTHING;

-- 5. INSERT CATEGORY CRITERIA MAPPINGS
INSERT INTO category_criteria_mapping (job_category_id, criteria_id, weight_percentage, seniority_level) VALUES

-- ROOT (1)
(1, 10101, 40.0, 'INTERN'),
(1, 10102, 40.0, 'INTERN'),
(1, 10103, 20.0, 'INTERN'),
(1, 10101, 30.0, 'FRESHER'),
(1, 10102, 30.0, 'FRESHER'),
(1, 10103, 30.0, 'FRESHER'),
(1, 10101, 20.0, 'JUNIOR'),
(1, 10102, 20.0, 'JUNIOR'),
(1, 10103, 20.0, 'JUNIOR'),
(1, 10101, 10.0, 'MID'),
(1, 10102, 10.0, 'MID'),
(1, 10103, 10.0, 'MID'),
(1, 10101, 5.0, 'SENIOR'),
(1, 10102, 5.0, 'SENIOR'),
(1, 10103, 5.0, 'SENIOR'),
(1, 10101, 5.0, 'LEAD'),
(1, 10102, 5.0, 'LEAD'),
(1, 10103, 5.0, 'LEAD'),

-- BACKEND (10)
(10, 10201, 20.0, 'JUNIOR'),
(10, 10202, 20.0, 'JUNIOR'),
(10, 10201, 20.0, 'MID'),
(10, 10202, 20.0, 'MID'),
(10, 10203, 10.0, 'MID'),
(10, 10201, 20.0, 'SENIOR'),
(10, 10202, 20.0, 'SENIOR'),
(10, 10203, 20.0, 'SENIOR'),
(10, 10201, 20.0, 'LEAD'),
(10, 10202, 20.0, 'LEAD'),
(10, 10203, 20.0, 'LEAD'),

-- JAVA ECOSYSTEM (101)
(101, 10301, 40.0, 'FRESHER'),
(101, 10303, 20.0, 'FRESHER'),
(101, 10304, 20.0, 'FRESHER'),
(101, 10301, 20.0, 'JUNIOR'),
(101, 10302, 10.0, 'JUNIOR'),
(101, 10303, 20.0, 'JUNIOR'),
(101, 10304, 15.0, 'JUNIOR'),
(101, 10301, 10.0, 'MID'),
(101, 10302, 15.0, 'MID'),
(101, 10303, 20.0, 'MID'),
(101, 10302, 20.0, 'SENIOR'),
(101, 10303, 20.0, 'SENIOR'),
(101, 10302, 25.0, 'LEAD'),
(101, 10303, 25.0, 'LEAD'),

-- SPRING BOOT (1011)
(1011, 10401, 30.0, 'FRESHER'),
(1011, 10402, 20.0, 'FRESHER'),
(1011, 10401, 20.0, 'JUNIOR'),
(1011, 10402, 20.0, 'JUNIOR'),
(1011, 10403, 10.0, 'JUNIOR'),
(1011, 10401, 15.0, 'MID'),
(1011, 10402, 15.0, 'MID'),
(1011, 10403, 15.0, 'MID'),
(1011, 10404, 10.0, 'MID'),
(1011, 10401, 10.0, 'SENIOR'),
(1011, 10402, 15.0, 'SENIOR'),
(1011, 10403, 20.0, 'SENIOR'),
(1011, 10404, 20.0, 'SENIOR'),
(1011, 10405, 10.0, 'SENIOR'),
(1011, 10403, 20.0, 'LEAD'),
(1011, 10404, 25.0, 'LEAD'),
(1011, 10405, 20.0, 'LEAD'),

-- NODE ECOSYSTEM (102)
(102, 10501, 40.0, 'FRESHER'),
(102, 10504, 20.0, 'FRESHER'),
(102, 10501, 20.0, 'JUNIOR'),
(102, 10503, 15.0, 'JUNIOR'),
(102, 10504, 15.0, 'JUNIOR'),
(102, 10501, 15.0, 'MID'),
(102, 10502, 15.0, 'MID'),
(102, 10503, 15.0, 'MID'),
(102, 10501, 10.0, 'SENIOR'),
(102, 10502, 25.0, 'SENIOR'),
(102, 10503, 20.0, 'SENIOR'),
(102, 10502, 30.0, 'LEAD'),
(102, 10503, 20.0, 'LEAD'),

-- NESTJS (1021)
(1021, 10601, 30.0, 'FRESHER'),
(1021, 10601, 20.0, 'JUNIOR'),
(1021, 10602, 15.0, 'JUNIOR'),
(1021, 10603, 15.0, 'JUNIOR'),
(1021, 10601, 15.0, 'MID'),
(1021, 10602, 20.0, 'MID'),
(1021, 10603, 20.0, 'MID'),
(1021, 10601, 10.0, 'SENIOR'),
(1021, 10602, 20.0, 'SENIOR'),
(1021, 10603, 15.0, 'SENIOR'),
(1021, 10604, 20.0, 'SENIOR'),
(1021, 10602, 20.0, 'LEAD'),
(1021, 10604, 30.0, 'LEAD'),

-- FRONTEND (20)
(20, 10701, 40.0, 'FRESHER'),
(20, 10702, 40.0, 'FRESHER'),
(20, 10701, 20.0, 'JUNIOR'),
(20, 10702, 30.0, 'JUNIOR'),
(20, 10703, 10.0, 'JUNIOR'),
(20, 10701, 10.0, 'MID'),
(20, 10702, 20.0, 'MID'),
(20, 10703, 20.0, 'MID'),
(20, 10702, 10.0, 'SENIOR'),
(20, 10703, 20.0, 'SENIOR'),
(20, 10703, 20.0, 'LEAD'),

-- REACT (201)
(201, 10801, 40.0, 'FRESHER'),
(201, 10801, 25.0, 'JUNIOR'),
(201, 10802, 15.0, 'JUNIOR'),
(201, 10803, 15.0, 'JUNIOR'),
(201, 10801, 10.0, 'MID'),
(201, 10802, 25.0, 'MID'),
(201, 10803, 25.0, 'MID'),
(201, 10804, 15.0, 'MID'),
(201, 10805, 10.0, 'MID'),
(201, 10802, 20.0, 'SENIOR'),
(201, 10803, 20.0, 'SENIOR'),
(201, 10804, 25.0, 'SENIOR'),
(201, 10805, 20.0, 'SENIOR'),
(201, 10804, 30.0, 'LEAD'),
(201, 10805, 30.0, 'LEAD'),

-- DEVOPS & CLOUD (60)
(60, 10901, 40.0, 'FRESHER'),
(60, 10902, 30.0, 'FRESHER'),
(60, 10901, 20.0, 'JUNIOR'),
(60, 10902, 20.0, 'JUNIOR'),
(60, 10903, 20.0, 'JUNIOR'),
(60, 10904, 20.0, 'JUNIOR'),
(60, 10901, 10.0, 'MID'),
(60, 10902, 10.0, 'MID'),
(60, 10903, 25.0, 'MID'),
(60, 10904, 25.0, 'MID'),
(60, 10903, 20.0, 'SENIOR'),
(60, 10904, 20.0, 'SENIOR'),
(60, 10903, 10.0, 'LEAD'),
(60, 10904, 10.0, 'LEAD'),

-- AWS INFRA (601)
(601, 11001, 30.0, 'FRESHER'),
(601, 11001, 20.0, 'JUNIOR'),
(601, 11002, 15.0, 'JUNIOR'),
(601, 11003, 15.0, 'JUNIOR'),
(601, 11001, 15.0, 'MID'),
(601, 11002, 20.0, 'MID'),
(601, 11003, 20.0, 'MID'),
(601, 11004, 15.0, 'MID'),
(601, 11001, 10.0, 'SENIOR'),
(601, 11002, 25.0, 'SENIOR'),
(601, 11003, 25.0, 'SENIOR'),
(601, 11004, 10.0, 'SENIOR'),
(601, 11005, 15.0, 'SENIOR'),
(601, 11002, 20.0, 'LEAD'),
(601, 11003, 20.0, 'LEAD'),
(601, 11005, 30.0, 'LEAD')
ON CONFLICT (job_category_id, criteria_id, seniority_level) DO NOTHING;
