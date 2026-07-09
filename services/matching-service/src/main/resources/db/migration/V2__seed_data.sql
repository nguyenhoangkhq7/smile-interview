-- ============================================================
-- V2: Seed Baseline Data (Squashed)
-- Seeds the initial job categories, evaluation criteria,
-- and category-criteria mappings for the rule engine.
-- ============================================================

-- 1. Insert Job Categories Tree
INSERT INTO job_categories (id, name, parent_id) VALUES
-- Level 0 (Root)
(1, 'SOFTWARE_ENGINEERING', NULL),

-- Level 1 (Domains)
(10, 'BACKEND', 1),
(20, 'FRONTEND', 1),
(25, 'FULLSTACK', 1),
(30, 'MOBILE', 1),
(40, 'DATA', 1),
(50, 'ML_ENGINEERING', 1),
(60, 'DEVOPS', 1),
(70, 'SECURITY', 1),
(80, 'QA', 1),
(90, 'SYSTEM_EMBEDDED', 1),
(99, 'OTHER', 1),

-- Level 2 (Ecosystems) & Level 3 (Specific Roles)
-- Domain 10: BACKEND
(101, 'JAVA_ECOSYSTEM', 10),
(1011, 'SPRING_BOOT', 101),
(102, 'NODE_ECOSYSTEM', 10),
(1021, 'NESTJS', 102),
(1022, 'EXPRESS', 102),
(103, 'PYTHON_ECOSYSTEM', 10),
(1031, 'DJANGO', 103),
(1032, 'FASTAPI', 103),
(104, 'GO_ECOSYSTEM', 10),
(105, 'DOTNET_ECOSYSTEM', 10),
(1051, 'DOTNET_CORE', 105),
(106, 'PHP_ECOSYSTEM', 10),
(1061, 'LARAVEL', 106),
(107, 'RUBY_ECOSYSTEM', 10),
(1071, 'RUBY_ON_RAILS', 107),

-- Domain 20: FRONTEND
(201, 'REACT', 20),
(202, 'ANGULAR', 20),
(203, 'VUE', 20),
(204, 'SVELTE', 20),

-- Domain 30: MOBILE
(301, 'IOS', 30),
(3011, 'SWIFT_UIKIT', 301),
(302, 'ANDROID', 30),
(3021, 'KOTLIN_COMPOSE', 302),
(303, 'CROSS_PLATFORM', 30),
(3031, 'FLUTTER', 303),
(3032, 'REACT_NATIVE', 303),

-- Domain 40: DATA
(401, 'DATA_ENGINEERING', 40),
(4011, 'SPARK_KAFKA', 401),
(402, 'DATA_SCIENCE', 40),
(4021, 'PANDAS_SCIKIT', 402),
(403, 'DATA_ANALYSIS', 40),
(404, 'DBA', 40),

-- Domain 50: ML_ENGINEERING
(501, 'DEEP_LEARNING_CV', 50),
(5011, 'PYTORCH_TENSORFLOW', 501),
(502, 'NLP_LLM', 50),
(5021, 'LANGCHAIN_HUGGINGFACE', 502),
(503, 'MLOPS', 50),

-- Domain 60: DEVOPS
(601, 'AWS_INFRA', 60),
(602, 'GCP_INFRA', 60),
(603, 'AZURE_INFRA', 60),
(604, 'SRE', 60),
(605, 'CI_CD_AUTOMATION', 60),

-- Domain 70: SECURITY
(701, 'APPSEC', 70),
(702, 'PEN_TESTING', 70),
(703, 'NETWORK_SECURITY', 70),
(704, 'CLOUD_SECURITY', 70),
(705, 'DEVSECOPS', 70),

-- Domain 80: QA
(801, 'MANUAL_QA', 80),
(802, 'AUTOMATION_QA', 80),
(8021, 'SELENIUM_CYPRESS', 802),
(803, 'PERFORMANCE_TESTING', 80),
(8031, 'JMETER', 803),

-- Domain 90: SYSTEM_EMBEDDED
(901, 'C_CPP_EMBEDDED', 90),
(902, 'IOT', 90),
(903, 'FIRMWARE', 90)
ON CONFLICT (id) DO NOTHING;

-- 2. Insert Evaluation Criteria
INSERT INTO evaluation_criteria (id, criteria_name, prompt_instruction) VALUES
-- Mobile L1 & L2 (unreplaced)
(2201, 'Mobile App Lifecycle & State', 'Evaluate understanding of mobile app lifecycles (foreground/background), state management, and resource constraints. Status="matched|weak|missing".'),
(3201, 'iOS Memory Management & Swift', 'Evaluate understanding of iOS memory management (ARC, weak/unowned), Swift Protocol-Oriented Programming, and concurrency (GCD/async-await). Status="matched|weak|missing".'),

-- Data L1 & L3 (unreplaced)
(2301, 'Data Modeling & Pipeline Fundamentals', 'Evaluate understanding of ETL/ELT pipelines, data modeling (star schema, snowflake), and data quality checks. Status="matched|weak|missing".'),
(3301, 'Spark & Kafka Streaming', 'Evaluate experience building distributed pipelines using Apache Spark and building scalable real-time streaming with Kafka. Status="matched|weak|missing".'),

-- ML L1 & L3 (unreplaced)
(2401, 'Machine Learning Fundamentals', 'Evaluate foundational ML knowledge including classification, regression, clustering, and evaluation metrics (F1, AUC). Status="matched|weak|missing".'),
(3401, 'LLM RAG Pipelines & Vectors', 'Evaluate understanding of LLM RAG pipelines, chunking strategies, embeddings, vector databases (e.g., pgvector, Pinecone), and prompt engineering. Status="matched|weak|missing".'),

-- Security L1 & L2 (unreplaced)
(2601, 'Security Fundamentals & Threat Modeling', 'Evaluate knowledge of basic cryptography, identity and access management, and threat modeling methodologies. Status="matched|weak|missing".'),
(3601, 'OWASP Top 10 & AppSec', 'Evaluate mastery of the OWASP Top 10, performing code reviews for security vulnerabilities, and implementing SAST/DAST tools in pipelines. Status="matched|weak|missing".'),

-- QA L1 & L2 & L3 (unreplaced)
(2701, 'Testing Fundamentals', 'Evaluate knowledge of testing pyramids, test planning, bug lifecycle, and edge case identification. Status="matched|weak|missing".'),
(3701, 'UI/API Test Automation', 'Evaluate experience with automation frameworks, page object models, and API testing (RestAssured/Postman). Status="matched|weak|missing".'),
(3702, 'Selenium & Cypress Mastery', 'Evaluate mastery of web element locators, explicit waits, Cypress custom commands, and handling flaky tests. Status="matched|weak|missing".'),

-- System L1 & L2 (unreplaced)
(2801, 'Computer Architecture & OS', 'Evaluate understanding of low-level memory, pointers, bitwise operations, RTOS concepts, and hardware interaction. Status="matched|weak|missing".'),
(3801, 'C/C++ Systems Programming', 'Evaluate expertise in C/C++ system programming, memory leaks (Valgrind), mutexes, IPC, and optimizing for resource constraints. Status="matched|weak|missing".'),

-- Root L1 (Atomic V6)
(10101, 'Data Structures & Algorithms', 'Evaluate knowledge of fundamental data structures (arrays, linked lists, hash tables, trees, graphs) and algorithms (sorting, searching, Big O notation). Status must be "matched" if demonstrated, "weak" if basic, "missing" if absent.'),
(10102, 'Object-Oriented Programming (OOP)', 'Evaluate understanding of OOP principles (Encapsulation, Inheritance, Polymorphism, Abstraction) and common design patterns. Status must be "matched" if demonstrated, "weak" if basic, "missing" if absent.'),
(10103, 'Database Fundamentals', 'Evaluate basic knowledge of databases (SQL vs NoSQL), schema design, simple queries, and normal forms. Status="matched|weak|missing".'),
(10104, 'Agile & SDLC Practices', 'Evaluate mentions of Agile, Scrum, Kanban, sprints, or CI/CD phases. Status must be "matched" if experienced, "weak" if barely mentioned, "missing" if absent.'),

-- Backend (Atomic V6)
(10201, 'API Design (REST/GraphQL)', 'Evaluate experience designing RESTful APIs (HTTP methods, status codes, URIs) or GraphQL endpoints. Status="matched|weak|missing".'),
(10202, 'Database Modeling & SQL', 'Evaluate ability to design DB schemas, write complex queries, use transactions, and optimize indexes. Status="matched|weak|missing".'),
(10203, 'Message Queuing Basics', 'Evaluate understanding of async communication, publish/subscribe patterns, and basic message brokers (RabbitMQ/Kafka). Status="matched|weak|missing".'),

-- Java Ecosystem (Atomic V6)
(10301, 'Java Core Language', 'Evaluate knowledge of Java syntax, collections framework, exception handling, and streams. Status="matched|weak|missing".'),
(10302, 'JVM Internals & Garbage Collection', 'Evaluate understanding of JVM architecture, memory management, and Garbage Collection tuning. Status="matched|weak|missing".'),
(10303, 'Java Concurrency', 'Evaluate experience with multithreading, synchronization, ExecutorService, and CompletableFuture. Status="matched|weak|missing".'),
(10304, 'Build Tools (Maven/Gradle)', 'Evaluate experience managing dependencies, build lifecycles, and plugins using Maven or Gradle. Status="matched|weak|missing".'),

-- Spring Boot (Atomic V6)
(10401, 'Spring Core (IoC/DI)', 'Evaluate mastery of Inversion of Control, Dependency Injection, bean scopes, and context configuration. Status="matched|weak|missing".'),
(10402, 'Spring Data JPA/Hibernate', 'Evaluate experience with ORM mapping, entity relationships, Spring Data repositories, and lazy/eager fetching. Status="matched|weak|missing".'),
(10403, 'Spring Security', 'Evaluate ability to implement authentication and authorization, JWT, OAuth2, and security filter chains. Status="matched|weak|missing".'),
(10404, 'Spring Boot Actuator & Observability', 'Evaluate experience configuring health checks, metrics, tracing, and logging in Spring Boot. Status="matched|weak|missing".'),
(10405, 'Spring WebFlux (Reactive)', 'Evaluate understanding of reactive programming, Project Reactor, Mono/Flux, and non-blocking I/O. Status="matched|weak|missing".'),

-- Node Ecosystem (Atomic V6)
(10501, 'Event Loop & Async/Await', 'Evaluate deep understanding of the Node.js event loop phases, micro/macro tasks, Promises, and async/await. Status="matched|weak|missing".'),
(10502, 'V8 Memory Management', 'Evaluate understanding of V8 engine internals, memory limits, heap allocation, and preventing memory leaks. Status="matched|weak|missing".'),
(10503, 'Node Streams & Buffers', 'Evaluate experience processing large files or data streams using Streams API and Buffers. Status="matched|weak|missing".'),
(10504, 'Package Management', 'Evaluate experience with npm/yarn/pnpm, handling package.json, semantic versioning, and resolving conflicts. Status="matched|weak|missing".'),

-- NestJS (Atomic V6)
(10601, 'NestJS Architecture (Modules/DI)', 'Evaluate experience structuring NestJS applications, defining Modules, and utilizing Dependency Injection. Status="matched|weak|missing".'),
(10602, 'Guards, Interceptors, Pipes', 'Evaluate ability to implement custom routing logic, request validation (Pipes), authentication (Guards), and request/response transformation (Interceptors). Status="matched|weak|missing".'),
(10603, 'TypeORM/Prisma Integration', 'Evaluate experience integrating NestJS with ORMs like TypeORM or Prisma for database interactions. Status="matched|weak|missing".'),
(10604, 'NestJS Microservices', 'Evaluate experience building microservices with NestJS using transports like TCP, Redis, or Kafka. Status="matched|weak|missing".'),

-- Frontend (Atomic V6)
(10701, 'Semantic HTML & CSS', 'Evaluate mastery of semantic HTML5 tags, CSS3, Flexbox/Grid layouts, and responsive design. Status="matched|weak|missing".'),
(10702, 'DOM Manipulation & Browser APIs', 'Evaluate vanilla JavaScript skills, DOM event handling, Web Storage, and Fetch API. Status="matched|weak|missing".'),
(10703, 'Web Performance Basics', 'Evaluate knowledge of Critical Rendering Path, minimizing layout thrashing, and basic asset optimization. Status="matched|weak|missing".'),

-- React (Atomic V6)
(10801, 'Component Architecture & Lifecycle', 'Evaluate understanding of React components, props/state, component lifecycle, and virtual DOM. Status="matched|weak|missing".'),
(10802, 'Advanced Hook Patterns', 'Evaluate proficiency with custom hooks, useReducer, useContext, and managing complex side effects (useEffect). Status="matched|weak|missing".'),
(10803, 'State Management (Redux/Zustand)', 'Evaluate experience with global state management libraries like Redux, Zustand, or Jotai. Status="matched|weak|missing".'),
(10804, 'React Performance (Memo/useCallback)', 'Evaluate ability to profile React apps, prevent unnecessary re-renders using memoization techniques (useMemo, useCallback, React.memo). Status="matched|weak|missing".'),
(10805, 'SSR/SSG (Next.js)', 'Evaluate understanding of Server-Side Rendering, Static Site Generation, and basic Next.js features. Status="matched|weak|missing".'),

-- DevOps (Atomic V6)
(10901, 'Linux Administration', 'Evaluate proficiency in Linux OS, process management, file permissions, and system monitoring. Status="matched|weak|missing".'),
(10902, 'Shell Scripting', 'Evaluate ability to write Bash/Shell scripts for automating system tasks. Status="matched|weak|missing".'),
(10903, 'CI/CD Fundamentals', 'Evaluate understanding of Continuous Integration and Continuous Deployment pipelines. Status="matched|weak|missing".'),
(10904, 'Docker & Containerization', 'Evaluate experience creating Dockerfiles, building images, and managing containers. Status="matched|weak|missing".'),

-- AWS Infra (Atomic V6)
(11001, 'AWS Compute & Auto-scaling', 'Evaluate experience with EC2, Auto Scaling Groups, and serverless compute (Lambda). Status="matched|weak|missing".'),
(11002, 'AWS IAM & Security Policies', 'Evaluate ability to design least-privilege IAM roles, policies, and managing access to AWS resources. Status="matched|weak|missing".'),
(11003, 'VPC & Networking', 'Evaluate knowledge of VPCs, subnets, route tables, security groups, and NAT gateways. Status="matched|weak|missing".'),
(11004, 'AWS Storage Strategies', 'Evaluate experience choosing and configuring AWS storage services (S3, EBS, EFS) for different use cases. Status="matched|weak|missing".'),
(11005, 'Cost Optimization & Monitoring', 'Evaluate experience using AWS CloudWatch, Cost Explorer, and optimizing infrastructure spend. Status="matched|weak|missing".')
ON CONFLICT (id) DO NOTHING;

-- 3. Insert Category Criteria Mappings
INSERT INTO category_criteria_mapping (job_category_id, criteria_id, weight_percentage, seniority_level) VALUES
-- Mobile Mappings (unreplaced)
(30, 2201, 25.0, 'ALL'),
(301, 3201, 40.0, 'ALL'),

-- Data Mappings (unreplaced)
(40, 2301, 25.0, 'ALL'),
(4011, 3301, 40.0, 'ALL'),

-- ML Mappings (unreplaced)
(50, 2401, 25.0, 'ALL'),
(5021, 3401, 40.0, 'ALL'),

-- Security Mappings (unreplaced)
(70, 2601, 25.0, 'ALL'),
(701, 3601, 40.0, 'ALL'),

-- QA Mappings (unreplaced)
(80, 2701, 50.0, 'INTERN'),
(80, 2701, 40.0, 'JUNIOR'),
(80, 2701, 25.0, 'MID'),
(80, 2701, 15.0, 'SENIOR'),
(802, 3701, 15.0, 'JUNIOR'),
(802, 3701, 30.0, 'MID'),
(802, 3701, 40.0, 'SENIOR'),
(8021, 3702, 10.0, 'JUNIOR'),
(8021, 3702, 30.0, 'MID'),
(8021, 3702, 45.0, 'SENIOR'),

-- System Embedded Mappings (unreplaced)
(90, 2801, 45.0, 'JUNIOR'),
(90, 2801, 30.0, 'MID'),
(90, 2801, 20.0, 'SENIOR'),
(901, 3801, 20.0, 'JUNIOR'),
(901, 3801, 40.0, 'MID'),
(901, 3801, 55.0, 'SENIOR'),

-- ROOT (1) (Atomic V6)
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

-- Agile & SDLC ROOT Mappings (V8)
(1, 10104, 20.0, 'INTERN'),
(1, 10104, 20.0, 'FRESHER'),
(1, 10104, 20.0, 'JUNIOR'),
(1, 10104, 20.0, 'MID'),
(1, 10104, 20.0, 'SENIOR'),
(1, 10104, 20.0, 'LEAD'),

-- BACKEND (10) (Atomic V6)
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

-- FULLSTACK (25) (V8 Mappings)
(25, 10201, 20.0, 'ALL'), -- API Design
(25, 10202, 20.0, 'ALL'), -- DB Modeling & SQL
(25, 10701, 20.0, 'ALL'), -- HTML & CSS
(25, 10702, 20.0, 'ALL'), -- DOM & Browser APIs
(25, 10903, 10.0, 'ALL'), -- CI/CD
(25, 10904, 10.0, 'ALL'), -- Docker
(25, 11001, 10.0, 'ALL'), -- AWS Compute

-- JAVA ECOSYSTEM (101) (Atomic V6)
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

-- SPRING BOOT (1011) (Atomic V6)
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

-- NODE ECOSYSTEM (102) (Atomic V6)
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

-- NESTJS (1021) (Atomic V6)
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

-- FRONTEND (20) (Atomic V6)
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

-- REACT (201) (Atomic V6)
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

-- DEVOPS & CLOUD (60) (Atomic V6)
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

-- AWS INFRA (601) (Atomic V6)
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
