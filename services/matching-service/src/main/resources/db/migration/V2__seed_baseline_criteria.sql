-- ============================================================
-- V2: Seed Baseline Criteria for Rule Engine (Complete)
-- Provides a working, out-of-the-box rule set for the IT industry.
-- ============================================================

-- ============================================================
-- ACTION 1: Generate the Massive job_categories Tree
-- ============================================================

-- Level 0 (Root)
INSERT INTO job_categories (id, name, parent_id) VALUES
(1, 'SOFTWARE_AND_IT_ENGINEERING', NULL)
ON CONFLICT (id) DO NOTHING;

-- Level 1 (Domains)
INSERT INTO job_categories (id, name, parent_id) VALUES
(10, 'BACKEND', 1),
(20, 'FRONTEND', 1),
(30, 'MOBILE', 1),
(40, 'DATA', 1),
(50, 'AI_AND_ML', 1),
(60, 'DEVOPS_AND_CLOUD', 1),
(70, 'CYBERSECURITY', 1),
(80, 'QA_AND_TESTING', 1),
(90, 'SYSTEM_EMBEDDED', 1)
ON CONFLICT (id) DO NOTHING;

-- Level 2 (Ecosystems) & Level 3 (Specific Roles)
-- Domain 10: BACKEND
INSERT INTO job_categories (id, name, parent_id) VALUES
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
(1071, 'RUBY_ON_RAILS', 107)
ON CONFLICT (id) DO NOTHING;

-- Domain 20: FRONTEND
INSERT INTO job_categories (id, name, parent_id) VALUES
(201, 'REACT', 20),
(202, 'ANGULAR', 20),
(203, 'VUE', 20),
(204, 'SVELTE', 20)
ON CONFLICT (id) DO NOTHING;

-- Domain 30: MOBILE
INSERT INTO job_categories (id, name, parent_id) VALUES
(301, 'IOS', 30),
(3011, 'SWIFT_UIKIT', 301),
(302, 'ANDROID', 30),
(3021, 'KOTLIN_COMPOSE', 302),
(303, 'CROSS_PLATFORM', 30),
(3031, 'FLUTTER', 303),
(3032, 'REACT_NATIVE', 303)
ON CONFLICT (id) DO NOTHING;

-- Domain 40: DATA
INSERT INTO job_categories (id, name, parent_id) VALUES
(401, 'DATA_ENGINEERING', 40),
(4011, 'SPARK_KAFKA', 401),
(402, 'DATA_SCIENCE', 40),
(4021, 'PANDAS_SCIKIT', 402),
(403, 'DATA_ANALYSIS', 40),
(404, 'DBA', 40)
ON CONFLICT (id) DO NOTHING;

-- Domain 50: AI & ML
INSERT INTO job_categories (id, name, parent_id) VALUES
(501, 'DEEP_LEARNING_CV', 50),
(5011, 'PYTORCH_TENSORFLOW', 501),
(502, 'NLP_LLM', 50),
(5021, 'LANGCHAIN_HUGGINGFACE', 502),
(503, 'MLOPS', 50)
ON CONFLICT (id) DO NOTHING;

-- Domain 60: DEVOPS & CLOUD
INSERT INTO job_categories (id, name, parent_id) VALUES
(601, 'AWS_INFRA', 60),
(602, 'GCP_INFRA', 60),
(603, 'AZURE_INFRA', 60),
(604, 'SRE', 60),
(605, 'CI_CD_AUTOMATION', 60)
ON CONFLICT (id) DO NOTHING;

-- Domain 70: CYBERSECURITY
INSERT INTO job_categories (id, name, parent_id) VALUES
(701, 'APPSEC', 70),
(702, 'PEN_TESTING', 70),
(703, 'NETWORK_SECURITY', 70),
(704, 'CLOUD_SECURITY', 70),
(705, 'DEVSECOPS', 70)
ON CONFLICT (id) DO NOTHING;

-- Domain 80: QA & TESTING
INSERT INTO job_categories (id, name, parent_id) VALUES
(801, 'MANUAL_QA', 80),
(802, 'AUTOMATION_QA', 80),
(8021, 'SELENIUM_CYPRESS', 802),
(803, 'PERFORMANCE_TESTING', 80),
(8031, 'JMETER', 803)
ON CONFLICT (id) DO NOTHING;

-- Domain 90: SYSTEM/EMBEDDED
INSERT INTO job_categories (id, name, parent_id) VALUES
(901, 'C_CPP_EMBEDDED', 90),
(902, 'IOT', 90),
(903, 'FIRMWARE', 90)
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- ACTION 2: Generate Comprehensive evaluation_criteria
-- ============================================================

INSERT INTO evaluation_criteria (id, criteria_name, prompt_instruction) VALUES
-- ROOT L1 CRITERIA
(1001, 'Computer Science Fundamentals', 'Evaluate understanding of core CS concepts (Big O, sorting, hashing, trees). Status must be "matched" if demonstrated, "weak" if basic, "missing" if absent.'),
(1002, 'Agile & SDLC', 'Evaluate mentions of Agile, Scrum, Kanban, sprints, or CI/CD phases. Status must be "matched" if experienced, "weak" if barely mentioned, "missing" if absent.'),

-- BACKEND L1 CRITERIA
(2001, 'API Design (REST/GraphQL)', 'Evaluate experience designing RESTful APIs or GraphQL endpoints. Look for verbs, status codes, and pagination. Status="matched|weak|missing".'),
(2002, 'Database Management (SQL/NoSQL)', 'Evaluate ability to design DB schemas, write complex queries, use transactions, and optimize indexes. Status="matched|weak|missing".'),

-- FRONTEND L1 CRITERIA
(2101, 'UI/UX & Web Fundamentals', 'Evaluate knowledge of semantic HTML, responsive CSS, DOM events, and basic a11y standards. Status="matched|weak|missing".'),

-- MOBILE L1 CRITERIA
(2201, 'Mobile App Lifecycle & State', 'Evaluate understanding of mobile app lifecycles (foreground/background), state management, and resource constraints. Status="matched|weak|missing".'),

-- DATA L1 CRITERIA
(2301, 'Data Modeling & Pipeline Fundamentals', 'Evaluate understanding of ETL/ELT pipelines, data modeling (star schema, snowflake), and data quality checks. Status="matched|weak|missing".'),

-- AI & ML L1 CRITERIA
(2401, 'Machine Learning Fundamentals', 'Evaluate foundational ML knowledge including classification, regression, clustering, and evaluation metrics (F1, AUC). Status="matched|weak|missing".'),

-- DEVOPS L1 CRITERIA
(2501, 'Infrastructure as Code (IaC) & OS', 'Evaluate Linux fundamentals, scripting ability, and understanding of declarative IaC principles. Status="matched|weak|missing".'),

-- CYBERSECURITY L1 CRITERIA
(2601, 'Security Fundamentals & Threat Modeling', 'Evaluate knowledge of basic cryptography, identity and access management, and threat modeling methodologies. Status="matched|weak|missing".'),

-- QA & TESTING L1 CRITERIA
(2701, 'Testing Fundamentals', 'Evaluate knowledge of testing pyramids, test planning, bug lifecycle, and edge case identification. Status="matched|weak|missing".'),

-- SYSTEM/EMBEDDED L1 CRITERIA
(2801, 'Computer Architecture & OS', 'Evaluate understanding of low-level memory, pointers, bitwise operations, RTOS concepts, and hardware interaction. Status="matched|weak|missing".'),

-- ECOSYSTEM L2 & L3 CRITERIA
-- Java L2 & L3
(3001, 'Java Core & Concurrency', 'Evaluate deep Java core concepts: JVM internals, GC tuning, concurrency (Threads, ExecutorService, CompletableFuture). Status="matched|weak|missing".'),
(3002, 'Spring Framework Ecosystem', 'Evaluate mastery of Spring Boot auto-configuration, Spring Data JPA/Hibernate, Spring Security filters, and Spring Webflux. Status="matched|weak|missing".'),

-- Node L2 & L3
(3011, 'Node.js Core & Async Programming', 'Evaluate understanding of the Node.js event loop, promises, async/await, streams, and V8 memory management. Status="matched|weak|missing".'),
(3012, 'NestJS Architecture', 'Evaluate experience with NestJS modular architecture, custom decorators, guards, interceptors, and RxJS integration. Status="matched|weak|missing".'),

-- React L2/L3
(3101, 'React Hook Patterns & State', 'Evaluate advanced React Hook patterns, Next.js SSR metrics, component memoization, and complex state management (Redux/Zustand). Status="matched|weak|missing".'),

-- iOS L3
(3201, 'iOS Memory Management & Swift', 'Evaluate understanding of iOS memory management (ARC, weak/unowned), Swift Protocol-Oriented Programming, and concurrency (GCD/async-await). Status="matched|weak|missing".'),

-- Data Eng L3
(3301, 'Spark & Kafka Streaming', 'Evaluate experience building distributed pipelines using Apache Spark and building scalable real-time streaming with Kafka. Status="matched|weak|missing".'),

-- NLP LLM L3
(3401, 'LLM RAG Pipelines & Vectors', 'Evaluate understanding of LLM RAG pipelines, chunking strategies, embeddings, vector databases (e.g., pgvector, Pinecone), and prompt engineering. Status="matched|weak|missing".'),

-- AWS L2
(3501, 'AWS Core Services & Networking', 'Evaluate deep hands-on experience with AWS core services, VPC design, IAM policies, and cloud cost optimization. Status="matched|weak|missing".'),

-- AppSec L2
(3601, 'OWASP Top 10 & AppSec', 'Evaluate mastery of the OWASP Top 10, performing code reviews for security vulnerabilities, and implementing SAST/DAST tools in pipelines. Status="matched|weak|missing".'),

-- Automation QA L2 & L3
(3701, 'UI/API Test Automation', 'Evaluate experience with automation frameworks, page object models, and API testing (RestAssured/Postman). Status="matched|weak|missing".'),
(3702, 'Selenium & Cypress Mastery', 'Evaluate mastery of web element locators, explicit waits, Cypress custom commands, and handling flaky tests. Status="matched|weak|missing".'),

-- C/C++ Embedded L2
(3801, 'C/C++ Systems Programming', 'Evaluate expertise in C/C++ system programming, memory leaks (Valgrind), mutexes, IPC, and optimizing for resource constraints. Status="matched|weak|missing".')

ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- ACTION 3: Generate the category_criteria_mapping
-- DYNAMIC WEIGHT DISTRIBUTION BY SENIORITY
-- ============================================================

INSERT INTO category_criteria_mapping (job_category_id, criteria_id, weight_percentage, seniority_level) VALUES

-- ==============================================
-- 1) ROOT MAPPINGS (Applies across all IT Engineering)
-- ==============================================
-- INTERN/FRESHER: High emphasis on fundamentals
(1, 1001, 35.0, 'INTERN'),
(1, 1001, 30.0, 'FRESHER'),
(1, 1002, 15.0, 'INTERN'),
(1, 1002, 20.0, 'FRESHER'),

-- JUNIOR/MID: Balanced fundamentals
(1, 1001, 25.0, 'JUNIOR'),
(1, 1001, 20.0, 'MID'),
(1, 1002, 20.0, 'JUNIOR'),
(1, 1002, 25.0, 'MID'),

-- SENIOR/LEAD: Fundamentals are assumed/lower direct weight, focusing on architecture instead
(1, 1001, 10.0, 'SENIOR'),
(1, 1001, 5.0,  'LEAD'),
(1, 1002, 20.0, 'SENIOR'),
(1, 1002, 25.0, 'LEAD'),


-- ==============================================
-- 2) BACKEND MAPPINGS
-- ==============================================
-- L1 BACKEND: API Design (2001) & DB Management (2002)
-- Junior/Mid leans heavily on doing APIs & DBs right
(10, 2001, 20.0, 'JUNIOR'),
(10, 2002, 25.0, 'JUNIOR'),
(10, 2001, 25.0, 'MID'),
(10, 2002, 30.0, 'MID'),
-- Senior/Lead needs absolute mastery of APIs and DB scaling
(10, 2001, 30.0, 'SENIOR'),
(10, 2002, 35.0, 'SENIOR'),
(10, 2001, 30.0, 'LEAD'),
(10, 2002, 35.0, 'LEAD'),

-- L2 JAVA ECOSYSTEM (101): Java Core & Concurrency (3001)
(101, 3001, 30.0, 'INTERN'),
(101, 3001, 30.0, 'FRESHER'),
(101, 3001, 25.0, 'JUNIOR'),
(101, 3001, 20.0, 'MID'),
(101, 3001, 25.0, 'SENIOR'),
(101, 3001, 30.0, 'LEAD'),

-- L3 SPRING BOOT (1011): Spring Framework (3002)
-- Interns/Freshers don't need deep Spring magic
(1011, 3002, 10.0, 'INTERN'),
(1011, 3002, 15.0, 'FRESHER'),
-- Mid/Senior MUST know framework internals
(1011, 3002, 25.0, 'JUNIOR'),
(1011, 3002, 30.0, 'MID'),
(1011, 3002, 40.0, 'SENIOR'),
(1011, 3002, 45.0, 'LEAD'),

-- L2 NODE ECOSYSTEM (102): Node.js Core (3011)
(102, 3011, 25.0, 'JUNIOR'),
(102, 3011, 25.0, 'MID'),
(102, 3011, 35.0, 'SENIOR'),

-- L3 NESTJS (1021): NestJS Architecture (3012)
(1021, 3012, 15.0, 'JUNIOR'),
(1021, 3012, 30.0, 'MID'),
(1021, 3012, 40.0, 'SENIOR'),


-- ==============================================
-- 3) FRONTEND MAPPINGS
-- ==============================================
-- L1 FRONTEND: UI/UX & Web Fundamentals (2101)
(20, 2101, 40.0, 'INTERN'),
(20, 2101, 30.0, 'JUNIOR'),
(20, 2101, 20.0, 'MID'),
(20, 2101, 15.0, 'SENIOR'),

-- L2/L3 REACT (201): React Hook Patterns (3101)
(201, 3101, 10.0, 'INTERN'),
(201, 3101, 25.0, 'JUNIOR'),
(201, 3101, 40.0, 'MID'),
(201, 3101, 50.0, 'SENIOR'),


-- ==============================================
-- 4) DEVOPS & CLOUD MAPPINGS
-- ==============================================
-- L1 DEVOPS: IaC & OS (2501)
(60, 2501, 35.0, 'JUNIOR'),
(60, 2501, 30.0, 'MID'),
(60, 2501, 20.0, 'SENIOR'),

-- L2 AWS INFRA (601): AWS Core Services (3501)
(601, 3501, 20.0, 'JUNIOR'),
(601, 3501, 35.0, 'MID'),
(601, 3501, 50.0, 'SENIOR'),
(601, 3501, 60.0, 'LEAD'),


-- ==============================================
-- 5) QA & TESTING MAPPINGS
-- ==============================================
-- L1 QA: Testing Fundamentals (2701)
(80, 2701, 50.0, 'INTERN'),
(80, 2701, 40.0, 'JUNIOR'),
(80, 2701, 25.0, 'MID'),
(80, 2701, 15.0, 'SENIOR'),

-- L2 AUTOMATION QA (802): UI/API Test Automation (3701)
(802, 3701, 15.0, 'JUNIOR'),
(802, 3701, 30.0, 'MID'),
(802, 3701, 40.0, 'SENIOR'),

-- L3 SELENIUM/CYPRESS (8021): Mastery (3702)
(8021, 3702, 10.0, 'JUNIOR'),
(8021, 3702, 30.0, 'MID'),
(8021, 3702, 45.0, 'SENIOR'),


-- ==============================================
-- 6) SYSTEM/EMBEDDED MAPPINGS
-- ==============================================
-- L1 SYSTEM: Computer Architecture & OS (2801)
(90, 2801, 45.0, 'JUNIOR'),
(90, 2801, 30.0, 'MID'),
(90, 2801, 20.0, 'SENIOR'),

-- L2 C/C++ EMBEDDED (901): C/C++ Systems Programming (3801)
(901, 3801, 20.0, 'JUNIOR'),
(901, 3801, 40.0, 'MID'),
(901, 3801, 55.0, 'SENIOR'),


-- ==============================================
-- 7) OTHER DEFAULTS (MOBILE, DATA, AI, CYBERSEC)
-- ==============================================
-- Generic fallback for domains not explicitly dynamically weighted
(30, 2201, 25.0, 'ALL'),
(301, 3201, 40.0, 'ALL'),

(40, 2301, 25.0, 'ALL'),
(4011, 3301, 40.0, 'ALL'),

(50, 2401, 25.0, 'ALL'),
(5021, 3401, 40.0, 'ALL'),

(70, 2601, 25.0, 'ALL'),
(701, 3601, 40.0, 'ALL')

ON CONFLICT (job_category_id, criteria_id, seniority_level) DO NOTHING;
