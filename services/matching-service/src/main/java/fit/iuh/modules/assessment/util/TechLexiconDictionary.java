package fit.iuh.modules.assessment.util;

import java.util.*;

/**
 * Domain Lexicon Dictionary for IT & Software Engineering terminology,
 * acronyms, abbreviations, frameworks, and bilingual aliases.
 *
 * <p>Provides bidirectional synonym mapping (e.g. k8s <-> kubernetes,
 * golang <-> go, postgres <-> postgresql, gcp <-> google cloud,
 * vi dịch vụ <-> microservices, học máy <-> machine learning) to prevent
 * false-positive grounding penalties in {@link fit.iuh.modules.assessment.service.EvidenceGroundingValidator}
 * and enhance lexical matching across the matching engine.
 */
public final class TechLexiconDictionary {

    private TechLexiconDictionary() {
        throw new UnsupportedOperationException("Utility lexicon dictionary class");
    }

    private static final Map<String, Set<String>> SYNONYM_MAP = new HashMap<>();
    private static final Map<String, String> CANONICAL_MAP = new HashMap<>();
    private static final Set<String> SHORT_TERMS = new HashSet<>();

    static {
        // =========================================================================
        // 1. Programming Languages & Core Runtimes
        // =========================================================================
        registerGroup("java", "jvm", "j2ee", "jee", "jakarta ee", "core java", "java 8", "java 11", "java 17", "java 21", "openjdk", "oracle jdk");
        registerGroup("golang", "go", "go-lang", "go lang");
        registerGroup("python", "python3", "python 3", "py", "python2", "cpython", "pypy");
        registerGroup("javascript", "js", "ecmascript", "es6", "es2015", "es2016", "es2017", "es2018", "es2019", "es2020", "es2021", "es2022", "es2023", "esnext", "vanilla js", "vanillajs");
        registerGroup("typescript", "ts", "typescript 5");
        registerGroup("c++", "cpp", "c/c++", "c plus plus", "cxx", "modern c++", "c++11", "c++14", "c++17", "c++20", "c++23");
        registerGroup("c#", "csharp", "c-sharp", "c sharp", ".net", "dotnet", ".net core", "dotnet core", ".net framework", "dotnet framework", ".net 6", ".net 7", ".net 8", ".net 9");
        registerGroup("c", "c language", "c programming", "ansi c", "c99", "c11");
        registerGroup("php", "php7", "php8", "php 8", "php 7", "php-fpm", "modern php");
        registerGroup("rust", "rustlang", "rust-lang");
        registerGroup("kotlin", "kotlin/jvm", "kotlin multiplatform", "kmp", "kotlin/native", "kotlin coroutines");
        registerGroup("swift", "swiftlang", "ios swift", "swiftui", "swift 5");
        registerGroup("objective-c", "objc", "obj-c", "objective c");
        registerGroup("ruby", "rubylang", "mruby");
        registerGroup("dart", "dartlang", "flutter/dart");
        registerGroup("scala", "scalalang", "scala 3", "scala 2");
        registerGroup("r language", "r", "r programming", "r-project", "rstats");
        registerGroup("matlab", "gnu octave", "octave");
        registerGroup("perl", "perl5", "perl 5");
        registerGroup("bash", "shell script", "shell scripting", "sh", "zsh", "powershell", "pwsh", "posix shell");
        registerGroup("sql", "structured query language", "ansi sql", "t-sql", "tsql", "pl/sql", "plsql");
        registerGroup("lua", "luajit");
        registerGroup("elixir", "erlang", "beam", "otp", "elixirlang");
        registerGroup("haskell", "ghc");
        registerGroup("clojure", "clojurescript");
        registerGroup("groovy", "apache groovy");
        registerGroup("solidity", "sol", "smart contract", "smart contracts", "web3", "evm", "ethereum virtual machine");
        registerGroup("zig", "ziglang");
        registerGroup("julia", "julialang");
        registerGroup("assembly", "asm", "x86", "x86_64", "arm assembly", "nasm", "masm");
        registerGroup("html", "html5", "semantic html");
        registerGroup("css", "css3", "vanilla css");
        registerGroup("ui/ux", "ui", "ux", "user interface", "user experience", "giao diện người dùng");
        registerGroup("operating system", "os", "hệ điều hành");
        registerGroup("tcp/ip", "ip", "tcp", "udp", "networking", "mạng máy tính");
        registerGroup("database", "db", "dbms", "cơ sở dữ liệu", "hệ quản trị cơ sở dữ liệu");

        // =========================================================================
        // 2. Frontend Frameworks, Libraries & UI Technologies
        // =========================================================================
        registerGroup("react", "reactjs", "react.js", "react-native", "react native");
        registerGroup("vue", "vuejs", "vue.js", "vue2", "vue3", "vue 3", "vue 2");
        registerGroup("angular", "angularjs", "angular.js", "angular 2+", "angular 17", "angular 18", "angular v2+");
        registerGroup("next.js", "nextjs", "next", "next.js 14", "next.js 15");
        registerGroup("nuxt.js", "nuxtjs", "nuxt", "nuxt 3", "nuxt3");
        registerGroup("svelte", "sveltekit", "svelte.js", "svelte 5");
        registerGroup("solidjs", "solid.js", "solid");
        registerGroup("astro", "astro.build");
        registerGroup("remix", "remix.run", "remix js");
        registerGroup("gatsby", "gatsbyjs");
        registerGroup("jquery", "jquery ui");
        registerGroup("htmx", "hyperscript");
        registerGroup("alpine.js", "alpinejs", "alpine");
        registerGroup("web components", "lit", "lit-html", "stencil", "stenciljs", "shadow dom");

        // =========================================================================
        // 3. Frontend Styling, UI Component Libraries & Web Graphics
        // =========================================================================
        registerGroup("tailwind", "tailwindcss", "tailwind-css", "tailwind css");
        registerGroup("bootstrap", "bootstrap 5", "bootstrap 4", "react-bootstrap");
        registerGroup("sass", "scss", "syntactically awesome stylesheets");
        registerGroup("less", "less.js", "less css");
        registerGroup("material ui", "material-ui", "mui", "@mui", "material design");
        registerGroup("ant design", "antd", "ant-design");
        registerGroup("shadcn", "shadcn/ui", "shadcn ui");
        registerGroup("chakra ui", "chakra-ui", "chakra");
        registerGroup("mantine", "mantine ui");
        registerGroup("styled-components", "styled components", "emotion", "css-in-js", "linaria");
        registerGroup("css modules", "css-modules");
        registerGroup("three.js", "threejs", "webgl", "webgpu", "canvas api");

        // =========================================================================
        // 4. Frontend State Management, Build Tools & Package Managers
        // =========================================================================
        registerGroup("redux", "redux-toolkit", "rtk", "redux saga", "redux thunk", "react-redux");
        registerGroup("zustand");
        registerGroup("mobx", "mobx-state-tree", "mobx-react");
        registerGroup("recoil");
        registerGroup("jotai");
        registerGroup("pinia", "vuex");
        registerGroup("react query", "tanstack query", "tanstack-query", "react-query");
        registerGroup("swr", "stale-while-revalidate");
        registerGroup("vite", "vitejs");
        registerGroup("webpack", "webpack 5", "webpack 4");
        registerGroup("rollup", "rollup.js");
        registerGroup("turbopack", "turborepo", "turbo");
        registerGroup("babel", "babeljs");
        registerGroup("parcel", "parcel-bundler");
        registerGroup("esbuild");
        registerGroup("npm", "yarn", "pnpm", "node package manager");

        // =========================================================================
        // 5. Backend Frameworks & Runtimes
        // =========================================================================
        registerGroup("spring boot", "spring", "springboot", "spring-boot", "spring framework", "spring cloud", "spring security", "spring data", "spring mvc", "spring webflux", "spring batch");
        registerGroup("quarkus", "quarkus.io");
        registerGroup("micronaut");
        registerGroup("vert.x", "vertx", "eclipse vert.x");
        registerGroup("node.js", "nodejs", "node", "node runtime");
        registerGroup("bun", "bunjs", "bun runtime");
        registerGroup("deno", "denojs");
        registerGroup("express", "expressjs", "express.js");
        registerGroup("nestjs", "nest.js", "nest", "nest framework");
        registerGroup("fastify");
        registerGroup("koa", "koajs");
        registerGroup("hono", "honojs");
        registerGroup("django", "django rest framework", "drf", "django-rest-framework");
        registerGroup("fastapi", "fast api", "fast-api");
        registerGroup("flask", "flask restplus", "flask restful");
        registerGroup("asp.net", "asp.net core", "aspnet", "aspnetcore", "asp.net mvc", "asp.net web api", "blazor", "wpf", "wcf", "winforms");
        registerGroup("laravel", "laravel framework", "lumen", "livewire", "blade");
        registerGroup("symfony", "symfony framework");
        registerGroup("codeigniter", "codeigniter 4");
        registerGroup("ruby on rails", "rails", "ror");
        registerGroup("gin", "gin-gonic", "gin framework");
        registerGroup("fiber", "gofiber");
        registerGroup("echo", "echo framework", "labstack echo");
        registerGroup("chi", "go-chi");
        registerGroup("ktor", "ktor framework");
        registerGroup("actix", "actix-web", "actix web");
        registerGroup("axum", "tokio-axum");
        registerGroup("rocket", "rocket.rs");
        registerGroup("phoenix", "phoenix framework");

        // =========================================================================
        // 6. ORM, Database Access & Migrations
        // =========================================================================
        registerGroup("hibernate", "jpa", "java persistence api", "jakarta persistence", "hibernate orm", "spring data jpa");
        registerGroup("mybatis", "ibatis", "mybatis-plus");
        registerGroup("entity framework", "ef core", "entity framework core", "ef", "linq");
        registerGroup("prisma", "prisma orm", "prisma client");
        registerGroup("typeorm");
        registerGroup("drizzle", "drizzle orm");
        registerGroup("sequelize");
        registerGroup("mongoose", "mongoose odm");
        registerGroup("sqlalchemy");
        registerGroup("tortoise-orm", "tortoise orm");
        registerGroup("gorm", "go-gorm");
        registerGroup("jdbc", "spring jdbc", "jdbctemplate", "jooq");
        registerGroup("flyway", "liquibase", "database migration", "db migration");

        // =========================================================================
        // 7. Databases (Relational, NoSQL, NewSQL, Graph, Vector)
        // =========================================================================
        registerGroup("postgresql", "postgres", "psql", "pgsql", "postgre");
        registerGroup("mysql", "my-sql", "mariadb", "percona");
        registerGroup("mongodb", "mongo", "mongo-db", "nosql document db");
        registerGroup("oracle", "oracle db", "oracle database", "pl/sql", "plsql", "oracle 19c", "oracle 11g", "oracle 12c");
        registerGroup("sql server", "mssql", "ms sql", "microsoft sql server", "t-sql", "tsql", "ssms");
        registerGroup("sqlite", "sqlite3");
        registerGroup("redis", "redis cache", "valkey", "redis stack", "redis enterprise");
        registerGroup("memcached");
        registerGroup("elasticsearch", "elastic search", "es", "elk", "elk stack", "opensearch", "kibana", "logstash");
        registerGroup("cassandra", "apache cassandra", "scylladb", "scylla", "cql");
        registerGroup("dynamodb", "dynamo db", "aws dynamodb");
        registerGroup("cosmos db", "cosmosdb", "azure cosmos db");
        registerGroup("firestore", "cloud firestore", "firebase realtime database", "firebase firestore", "firebase");
        registerGroup("couchbase", "couchdb");
        registerGroup("neo4j", "cypher", "graph database", "graphdb");
        registerGroup("influxdb", "timescaledb", "timescale", "time series database", "tsdb");
        registerGroup("clickhouse");
        registerGroup("cockroachdb", "cockroach", "crdb");
        registerGroup("tidb", "pingcap");
        registerGroup("supabase");
        registerGroup("pocketbase");
        registerGroup("vector database", "vectordb", "pinecone", "milvus", "qdrant", "weaviate", "chroma", "chromadb", "pgvector", "faiss");

        // =========================================================================
        // 8. Message Brokers & Distributed Streaming
        // =========================================================================
        registerGroup("kafka", "apache kafka", "kafka streams", "kafka connect", "confluent kafka", "event streaming");
        registerGroup("rabbitmq", "rabbit mq", "amqp");
        registerGroup("activemq", "apache activemq", "artemis");
        registerGroup("pulsar", "apache pulsar");
        registerGroup("nats", "nats.io", "nats streaming", "jetstream");
        registerGroup("sqs", "simple queue service", "aws sqs");
        registerGroup("sns", "simple notification service", "aws sns");
        registerGroup("eventbridge", "aws eventbridge");
        registerGroup("pub/sub", "pubsub", "cloud pub/sub", "gcp pubsub", "google pubsub");
        registerGroup("azure service bus", "service bus", "azure event hubs", "event hubs");
        registerGroup("zeromq", "0mq", "zmq");
        registerGroup("hazelcast", "apache ignite", "ignite", "in-memory data grid", "imdg");

        // =========================================================================
        // 9. Cloud Computing (AWS, GCP, Azure, Multi-Cloud)
        // =========================================================================
        registerGroup("aws", "amazon web services", "amazon aws", "amazon cloud");
        registerGroup("ec2", "amazon ec2", "elastic compute cloud");
        registerGroup("s3", "amazon s3", "simple storage service");
        registerGroup("rds", "amazon rds", "relational database service", "aurora", "amazon aurora");
        registerGroup("lambda", "aws lambda", "serverless computing");
        registerGroup("ecs", "amazon ecs", "elastic container service", "fargate", "aws fargate");
        registerGroup("eks", "amazon eks", "elastic kubernetes service");
        registerGroup("iam", "identity and access management", "vpc", "virtual private cloud", "route 53", "route53", "cloudfront", "api gateway", "aws api gateway", "ses", "simple email service", "step functions", "kinesis", "glue", "athena", "elb", "alb", "nlb");
        registerGroup("cloudformation", "aws cdk", "cloudwatch", "aws cloudwatch");
        registerGroup("google cloud", "gcp", "google cloud platform", "google cloud services");
        registerGroup("gke", "google kubernetes engine");
        registerGroup("cloud run", "google cloud run");
        registerGroup("compute engine", "gce");
        registerGroup("cloud functions", "google cloud functions");
        registerGroup("cloud storage", "gcs", "google cloud storage");
        registerGroup("cloud sql", "cloud spanner", "cloud bigtable", "cloud logging", "cloud monitoring");
        registerGroup("azure", "microsoft azure", "ms azure");
        registerGroup("aks", "azure kubernetes service");
        registerGroup("azure app service", "app services");
        registerGroup("azure functions", "azure function");
        registerGroup("azure blob storage", "blob storage");
        registerGroup("azure sql", "azure sql database");
        registerGroup("azure devops", "vsts", "tfs");
        registerGroup("digitalocean", "droplets", "do");
        registerGroup("heroku");
        registerGroup("vercel");
        registerGroup("netlify");
        registerGroup("cloudflare", "cloudflare workers", "cloudflare pages", "cloudflare cdn");
        registerGroup("openstack", "vmware", "vsphere", "esxi", "virtualization", "virtual machine", "vm");

        // =========================================================================
        // 10. Containerization, Orchestration & DevOps / GitOps / IaC
        // =========================================================================
        registerGroup("kubernetes", "k8s", "k8-s", "kube", "kubectl", "helm", "helm charts", "k9s", "minikube", "kind", "k3s", "openshift", "red hat openshift");
        registerGroup("docker", "dockerfile", "docker compose", "docker-compose", "containerization", "containers", "container", "podman", "containerd");
        registerGroup("ci/cd", "ci-cd", "cicd", "ci", "cd", "continuous integration", "continuous deployment", "continuous delivery");
        registerGroup("jenkins", "jenkins pipeline", "jenkinsfile");
        registerGroup("github actions", "gh actions", "github action");
        registerGroup("gitlab ci", "gitlab ci/cd", "gitlab-ci", ".gitlab-ci.yml");
        registerGroup("bitbucket pipelines", "bitbucket ci");
        registerGroup("circleci", "circle ci");
        registerGroup("argocd", "argo cd", "gitops", "flux", "fluxcd");
        registerGroup("terraform", "tf", "iac", "infrastructure as code", "opentofu");
        registerGroup("ansible", "ansible playbook", "ansible playbooks");
        registerGroup("pulumi");
        registerGroup("linux", "ubuntu", "debian", "centos", "rhel", "red hat enterprise linux", "alpine", "arch linux", "fedora", "rocky linux", "alma linux", "unix", "posix", "windows server");
        registerGroup("nginx", "apache", "apache http server", "httpd", "caddy", "traefik", "envoy", "haproxy", "kong", "kong api gateway", "apisix");

        // =========================================================================
        // 11. API Architectures, Protocols & Web Standards
        // =========================================================================
        registerGroup("rest", "restful", "rest api", "rest apis", "restful api", "restful web services");
        registerGroup("graphql", "graph-ql", "apollo", "apollo graphql", "apollo server", "apollo client", "relay");
        registerGroup("grpc", "g-rpc", "protocol buffers", "protobuf", "proto3");
        registerGroup("websocket", "websockets", "ws", "socket.io", "sockjs", "sse", "server-sent events");
        registerGroup("webhook", "webhooks");
        registerGroup("soap", "wsdl", "xml-rpc");
        registerGroup("openapi", "swagger", "swagger ui", "openapi 3.0", "oas");
        registerGroup("service mesh", "istio", "linkerd", "consul", "eureka", "feign", "spring cloud openfeign", "resilience4j", "hystrix", "circuit breaker");

        // =========================================================================
        // 12. Software Architecture, Patterns & Methodologies
        // =========================================================================
        registerGroup("microservices", "microservice", "micro-services", "micro-service", "distributed systems", "distributed architecture", "vi dịch vụ");
        registerGroup("monolith", "monolithic", "monolithic architecture", "modular monolith");
        registerGroup("serverless", "faas", "function as a service", "lambda architecture");
        registerGroup("event-driven", "event driven architecture", "eda", "event sourcing", "cqrs", "command query responsibility segregation");
        registerGroup("clean architecture", "onion architecture", "hexagonal architecture", "ports and adapters");
        registerGroup("ddd", "domain driven design", "domain-driven design", "ubiquitous language", "bounded context", "aggregate root");
        registerGroup("oop", "object oriented programming", "object-oriented", "object-oriented design", "ood", "lập trình hướng đối tượng");
        registerGroup("functional programming", "fp", "immutability", "pure functions");
        registerGroup("design patterns", "gang of four", "gof", "factory pattern", "singleton", "observer pattern", "strategy pattern", "adapter pattern", "repository pattern", "unit of work", "dependency injection", "di", "inversion of control", "ioc");
        registerGroup("solid", "solid principles", "single responsibility", "open-closed", "liskov substitution", "interface segregation", "dependency inversion");
        registerGroup("clean code", "dry", "kiss", "yagni", "don't repeat yourself", "keep it simple");
        registerGroup("multithreading", "concurrency", "async/await", "asynchronous programming", "reactive programming", "rxjava", "project reactor", "coroutines", "thread safety", "parallel programming", "đa luồng");

        // =========================================================================
        // 13. Testing, QA & Automation
        // =========================================================================
        registerGroup("unit test", "unit testing", "unittests", "tdd", "test driven development", "unit tests");
        registerGroup("bdd", "behavior driven development", "cucumber", "gherkin");
        registerGroup("integration test", "integration testing", "e2e testing", "end-to-end testing", "regression testing", "sanity testing", "smoke testing", "system testing", "kiểm thử tự động", "kiểm thử phần mềm");
        registerGroup("junit", "junit5", "junit4", "mockito", "powermock", "assertj", "testng", "hamcrest");
        registerGroup("jest", "jestjs", "vitest", "mocha", "chai", "jasmine", "sinon", "supertest", "testing library", "react testing library");
        registerGroup("pytest", "unittest", "pytest-mock", "robot framework");
        registerGroup("xunit", "nunit", "mstest", "moq");
        registerGroup("gotest", "testify", "gomock");
        registerGroup("selenium", "selenium webdriver", "cypress", "cypress.io", "playwright", "puppeteer", "webdriverio", "appium");
        registerGroup("postman", "newman", "jmeter", "apache jmeter", "gatling", "k6", "locust", "artillery", "load testing", "stress testing", "performance testing");
        registerGroup("sonarqube", "sonar", "sonarlint", "eslint", "prettier", "checkstyle", "spotbugs", "pmd", "rubocop", "flake8", "black formatter", "pylint", "golangci-lint");

        // =========================================================================
        // 14. Monitoring, Observability & APM
        // =========================================================================
        registerGroup("prometheus", "grafana", "promql", "grafana dashboards", "cortex", "thanos");
        registerGroup("elk", "elk stack", "elasticsearch", "logstash", "kibana", "filebeat", "metricbeat", "fluentd", "fluentbit");
        registerGroup("opentelemetry", "otel", "jaeger", "zipkin");
        registerGroup("datadog", "new relic", "dynatrace", "appdynamics", "sentry", "signalfx", "splunk");
        registerGroup("pagerduty", "opsgenie", "alertmanager", "victorops");

        // =========================================================================
        // 15. Security, Auth & Identity
        // =========================================================================
        registerGroup("jwt", "json web token", "jwt token", "bearer token");
        registerGroup("oauth", "oauth2", "oauth 2.0", "openid connect", "oidc", "sso", "single sign-on", "saml", "saml 2.0");
        registerGroup("mfa", "2fa", "multi-factor authentication", "two-factor authentication", "otp", "totp");
        registerGroup("keycloak", "auth0", "okta", "firebase auth", "aws cognito", "cognito", "microsoft entra id", "azure ad", "active directory", "ldap");
        registerGroup("spring security", "cors", "csrf", "xss", "sql injection", "sqli", "owasp", "owasp top 10", "penetration testing", "pen testing", "vulnerability assessment", "bảo mật", "an toàn thông tin");
        registerGroup("hashicorp vault", "vault", "cert-manager", "ssl/tls", "tls", "https", "encryption", "aes", "rsa", "pki", "ssh", "ssl");
        registerGroup("snyk", "trivy", "dependabot", "sast", "dast");

        // =========================================================================
        // 16. Data Engineering, Big Data & Analytics
        // =========================================================================
        registerGroup("spark", "apache spark", "pyspark", "spark sql", "spark streaming");
        registerGroup("hadoop", "hdfs", "mapreduce", "hive", "apache hive", "hbase", "apache hbase");
        registerGroup("flink", "apache flink", "stream processing");
        registerGroup("airflow", "apache airflow", "prefect", "dagster", "dbt", "data build tool", "luigi");
        registerGroup("snowflake", "bigquery", "redshift", "databricks", "delta lake", "apache iceberg", "apache hudi", "trino", "presto", "duckdb");
        registerGroup("etl", "elt", "data pipeline", "data pipelines", "data warehousing", "data warehouse", "data lake", "data lakehouse", "data modeling", "star schema", "snowflake schema");

        // =========================================================================
        // 17. AI, Machine Learning, Data Science & GenAI / LLM
        // =========================================================================
        registerGroup("machine learning", "ml", "deep learning", "dl", "artificial intelligence", "ai", "data science", "neural networks", "cnn", "rnn", "lstm", "học máy", "học sâu", "trí tuệ nhân tạo", "khoa học dữ liệu");
        registerGroup("pytorch", "torch", "tensorflow", "tf", "keras", "scikit-learn", "sklearn", "xgboost", "lightgbm", "catboost");
        registerGroup("pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly", "polars");
        registerGroup("nlp", "natural language processing", "xử lý ngôn ngữ tự nhiên", "spacy", "nltk", "bert", "transformers");
        registerGroup("llm", "large language models", "genai", "generative ai", "gpt", "chatgpt", "claude", "gemini", "llama", "huggingface", "hugging face", "prompt engineering", "langchain", "llamaindex", "llama index", "crewai", "autogen", "ollama", "vllm", "rag", "retrieval augmented generation");
        registerGroup("computer vision", "cv", "thị giác máy tính", "opencv", "yolo", "yolov8", "object detection", "image processing", "image segmentation");
        registerGroup("mlops", "mlflow", "kubeflow", "weights & biases", "wandb", "dvc", "tensorboard", "triton", "model serving");

        // =========================================================================
        // 18. Mobile & Cross-Platform Development
        // =========================================================================
        registerGroup("flutter", "flutter/dart", "dart flutter");
        registerGroup("react-native", "react native", "rn", "expo");
        registerGroup("ios", "ios development", "swift", "swiftui", "uikit", "xcode", "cocoapods", "spm");
        registerGroup("android", "android development", "kotlin", "jetpack compose", "compose", "android sdk", "android studio", "room db");
        registerGroup("ionic", "cordova", "capacitor", "xamarin", ".net maui", "maui", "unity");

        // =========================================================================
        // 19. Version Control, Collaboration & Agile / Scrum
        // =========================================================================
        registerGroup("git", "github", "gitlab", "bitbucket", "svn", "subversion", "mercurial", "version control", "quản lý mã nguồn");
        registerGroup("agile", "scrum", "kanban", "waterfall", "lean", "extreme programming", "xp", "safe", "scaled agile framework", "sprint planning", "daily standup", "retrospective");
        registerGroup("jira", "atlassian jira", "confluence", "trello", "asana", "linear", "notion", "clickup", "monday.com");

        // =========================================================================
        // 20. Bilingual Soft Skills & Languages
        // =========================================================================
        registerGroup("english", "tiếng anh", "english communication", "toeic", "ielts", "toefl", "cefr", "business english", "fluent english");
        registerGroup("japanese", "tiếng nhật", "jlpt", "n1", "n2", "n3", "n4", "n5");
        registerGroup("communication", "giao tiếp", "teamwork", "làm việc nhóm", "collaboration", "presentation", "thuyết trình", "active listening", "kỹ năng giao tiếp");
        registerGroup("problem solving", "giải quyết vấn đề", "troubleshooting", "critical thinking", "tư duy phản biện", "analytical thinking", "tư duy phân tích");
        registerGroup("leadership", "lãnh đạo", "mentoring", "hướng dẫn", "mentorship", "team lead", "tech lead", "engineering management", "code review", "peer review");
        registerGroup("time management", "quản lý thời gian", "adaptability", "khả năng thích ứng", "self-learning", "tự học", "fast learner", "can-do attitude");

        // Collect all short terms (length <= 3) for efficient validation
        for (String term : SYNONYM_MAP.keySet()) {
            if (term.length() <= 3) {
                SHORT_TERMS.add(term.toUpperCase(Locale.ROOT));
            }
        }
    }

    private static void registerGroup(String primary, String... aliases) {
        String canonical = primary.trim().toLowerCase(Locale.ROOT);
        Set<String> allVariants = new LinkedHashSet<>();
        allVariants.add(canonical);

        for (String alias : aliases) {
            if (alias != null && !alias.isBlank()) {
                allVariants.add(alias.trim().toLowerCase(Locale.ROOT));
            }
        }

        // Merge with existing variants if canonical or any variant was previously registered
        Set<String> merged = new LinkedHashSet<>(allVariants);
        for (String variant : allVariants) {
            Set<String> existing = SYNONYM_MAP.get(variant);
            if (existing != null) {
                merged.addAll(existing);
            }
        }

        Set<String> immutableVariants = Collections.unmodifiableSet(merged);
        for (String variant : merged) {
            SYNONYM_MAP.put(variant, immutableVariants);
            CANONICAL_MAP.putIfAbsent(variant, canonical);
        }
    }

    /**
     * Checks whether a term is registered in the technical lexicon dictionary.
     */
    public static boolean isRegistered(String term) {
        if (term == null || term.isBlank()) return false;
        return SYNONYM_MAP.containsKey(term.trim().toLowerCase(Locale.ROOT));
    }

    /**
     * Checks whether a short term (length <= 3) is a recognized tech term in the dictionary.
     */
    public static boolean isKnownShortTerm(String term) {
        if (term == null || term.isBlank()) return false;
        return SHORT_TERMS.contains(term.trim().toUpperCase(Locale.ROOT));
    }

    /**
     * Returns an unmodifiable set of all short technical acronyms/terms.
     */
    public static Set<String> getKnownShortTerms() {
        return Collections.unmodifiableSet(SHORT_TERMS);
    }

    /**
     * Returns an unmodifiable set of all registered technical terms and aliases.
     */
    public static Set<String> getAllKnownTerms() {
        return Collections.unmodifiableSet(SYNONYM_MAP.keySet());
    }

    /**
     * Retrieves all synonyms/aliases for the given term (including the term itself).
     * Returns a set containing just the normalized term if no synonyms are registered.
     */
    public static Set<String> getSynonyms(String term) {
        if (term == null || term.isBlank()) return Set.of();
        String norm = term.trim().toLowerCase(Locale.ROOT);
        return SYNONYM_MAP.getOrDefault(norm, Set.of(norm));
    }

    /**
     * Resolves the canonical form of a tech term (e.g. "k8s" -> "kubernetes").
     */
    public static String getCanonical(String term) {
        if (term == null || term.isBlank()) return term;
        String norm = term.trim().toLowerCase(Locale.ROOT);
        return CANONICAL_MAP.getOrDefault(norm, norm);
    }

    /**
     * Checks whether {@code haystack} contains the specified {@code techTerm}
     * OR any of its registered synonyms/aliases using word-boundary safe matching.
     *
     * <p>Example: {@code containsTechOrSynonym("Experience in K8s", "Kubernetes")} -> {@code true}
     */
    public static boolean containsTechOrSynonym(String haystack, String techTerm) {
        if (haystack == null || techTerm == null || haystack.isBlank() || techTerm.isBlank()) {
            return false;
        }

        Set<String> synonyms = getSynonyms(techTerm);
        for (String syn : synonyms) {
            if (TextSanitizationUtil.containsSkillTerm(haystack, syn)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Expands a collection of extracted tech tokens with all their known synonyms.
     */
    public static Set<String> expandTokensWithSynonyms(Collection<String> tokens) {
        if (tokens == null || tokens.isEmpty()) return Set.of();
        Set<String> expanded = new LinkedHashSet<>();
        for (String token : tokens) {
            if (token != null && !token.isBlank()) {
                expanded.addAll(getSynonyms(token));
            }
        }
        return expanded;
    }
}
