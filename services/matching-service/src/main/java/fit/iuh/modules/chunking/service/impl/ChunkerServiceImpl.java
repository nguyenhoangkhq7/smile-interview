package fit.iuh.modules.chunking.service.impl;

import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.service.ChunkerService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Slf4j
@Service
public class ChunkerServiceImpl implements ChunkerService {

    private static final Map<String, List<String>> ONTOLOGY = Map.ofEntries(
            Map.entry("frontend", List.of(
                    "Next.js", "React", "Vue", "Nuxt", "Angular", "Svelte", "SvelteKit", "Remix", "Astro", "SolidJS",
                    "TypeScript", "JavaScript", "React Native", "Flutter", "Expo", "Ionic", "KMP", "Kotlin Multiplatform",
                    "Redux", "Redux Toolkit", "Zustand", "MobX", "Recoil", "Pinia", "TanStack Query", "React Query", "SWR",
                    "Tailwind", "TailwindCSS", "shadcn", "Radix UI", "MUI", "Material UI", "Ant Design", "Chakra UI", "DaisyUI",
                    "React Hook Form", "Formik", "Zod", "Yup", "HTML5", "CSS3", "Sass", "SCSS", "Styled Components",
                    "WebAssembly", "WASM", "Vite", "Webpack", "Turbopack", "SSR", "SSG", "ISR", "PWA"
            )),
            Map.entry("backend", List.of(
                    "Spring Boot", "Spring Cloud", "ExpressJS", "Node.js", "NestJS", "Fastify", "Hono", "Bun", "Deno",
                    "\\bJava\\b", "Java 17", "Java 21", "Python", "Golang", "\\bGo\\b", "C#", ".NET Core", ".NET 8", "ASP.NET",
                    "Rust", "PHP", "Laravel", "Ruby on Rails", "FastAPI", "Django", "Flask", "Gin", "Fiber", "Ktor", "Axum",
                    "REST", "RESTful", "GraphQL", "gRPC", "tRPC", "OpenAPI", "Swagger", "SOAP", "Webhook", "Protobuf"
            )),
            Map.entry("database", List.of(
                    "PostgreSQL", "MySQL", "MariaDB", "Oracle", "SQL Server", "SQLite", "CockroachDB", "TiDB",
                    "MongoDB", "Cassandra", "DynamoDB", "Couchbase", "Firestore", "Neo4j", "ArangoDB",
                    "Redis", "Memcached", "Dragonfly", "Valkey", "Hazelcast", "Elasticsearch", "OpenSearch", "ClickHouse",
                    "pgvector", "Pinecone", "Milvus", "Qdrant", "ChromaDB", "Weaviate", "LanceDB",
                    "Hibernate", "JPA", "Spring Data", "Prisma", "TypeORM", "Drizzle", "MyBatis", "Dapper", "SQLAlchemy", "EF Core"
            )),
            Map.entry("security", List.of(
                    "JWT", "OAuth", "OAuth2", "OpenID", "OIDC", "Spring Security", "authentication", "authorization",
                    "token blacklist", "Secured", "Bcrypt", "Argon2", "Passkeys", "WebAuthn", "SSO", "MFA", "2FA",
                    "RBAC", "ABAC", "ReBAC", "Rate Limiting", "HTTPS", "TLS", "SSL", "CORS", "CSRF", "XSS", "SQL Injection",
                    "OWASP", "Keycloak", "Auth0", "Clerk", "Supabase Auth", "Vault", "WAF", "Cloudflare"
            )),
            Map.entry("distributed_realtime", List.of(
                    "Kafka", "Apache Kafka", "Redpanda", "RabbitMQ", "Pulsar", "ActiveMQ", "NATS", "SQS", "SNS", "Redis Pub/Sub",
                    "WebSockets", "Socket.io", "SSE", "Server-Sent Events", "WebRTC", "MQTT", "Event-driven", "EDA",
                    "Circuit Breaker", "Resilience4j", "Saga Pattern", "CQRS", "Event Sourcing", "Outbox Pattern", "CDC",
                    "Debezium", "Load Balancing", "API Gateway", "Kong", "APISix"
            )),
            Map.entry("devops_cloud", List.of(
                    "Docker", "Docker Compose", "Podman", "Kubernetes", "K8s", "Helm", "Kustomize", "Istio", "Cilium",
                    "CI/CD", "Jenkins", "GitHub Actions", "GitLab CI", "CircleCI", "ArgoCD", "FluxCD",
                    "AWS", "EC2", "RDS", "S3", "Lambda", "ECS", "EKS", "CloudFront", "Route53", "GCP", "Google Cloud",
                    "Azure", "DigitalOcean", "Vercel", "Cloudflare", "Supabase", "Terraform", "OpenTofu", "Ansible", "Pulumi", "CloudFormation",
                    "Prometheus", "Grafana", "ELK", "EFK", "OpenTelemetry", "Datadog", "Jaeger", "Tempo", "Loki", "Sentry"
            )),
            Map.entry("architecture", List.of(
                    "Microservices", "Monolithic", "Modular Monolith", "Serverless", "Clean Architecture", "Hexagonal Architecture",
                    "Domain-Driven Design", "DDD", "SOLID", "Design Patterns", "Software Architecture", "High Availability",
                    "Scalability", "Fault Tolerance", "Zero-Downtime", "Blue-Green", "Canary"
            )),
            Map.entry("ai_data", List.of(
                    "AI engine", "Chatbot", "LLM", "RAG", "Prompt Engineering", "LangChain", "LlamaIndex", "Ollama", "vLLM",
                    "OpenAI", "GPT-4", "Claude", "Gemini", "Llama", "DeepSeek", "PyTorch", "TensorFlow", "Scikit-learn",
                    "HuggingFace", "OpenCV", "Spark", "Apache Spark", "Airflow", "Dagster", "dbt", "Hadoop", "ETL",
                    "Data Warehouse", "Snowflake", "BigQuery", "Redshift"
            )),
            Map.entry("testing_qa", List.of(
                    "JUnit", "Mockito", "Testcontainers", "PyTest", "Jest", "Vitest", "Cypress", "Playwright", "Selenium",
                    "Postman", "Bruno", "JMeter", "k6", "Locust", "Gatling",
                    "Unit Test", "Integration Test", "E2E Testing", "Contract Testing", "Performance Testing", "TDD", "BDD"
            )),
            Map.entry("process_management", List.of(
                    "Jira", "Confluence", "Trello", "Linear", "Notion", "Agile", "Scrum", "Kanban", "Git", "GitHub", "GitLab",
                    "Bitbucket", "Git-Flow", "Trunk-Based", "Code Review", "CI/CD Pipeline", "\\bteam\\b", "^Led\\b"
            ))
    );

    private static final Set<String> STOPWORDS = Set.of(
            "a", "an", "the", "and", "to", "of", "with", "for", "using", "from", "is", "in", "on", "via", "that", "this", "by"
    );

    @Override
    public List<DocumentChunk> chunk(String markdownContent, String sessionId, String docType) {
        if (markdownContent == null || markdownContent.isBlank()) {
            return Collections.emptyList();
        }

        List<DocumentChunk> chunks = new ArrayList<>();
        Map<String, String> h1Sections = splitByHeading(markdownContent, 1);

        if ("cv".equalsIgnoreCase(docType)) {
            // Process Technical Projects with Parent-Child Domain Chunking
            if (h1Sections.containsKey("Technical Projects")) {
                String projectsSection = h1Sections.get("Technical Projects");
                Map<String, String> projectBlocks = splitByHeading(projectsSection, 2);

                for (var entry : projectBlocks.entrySet()) {
                    String projName = entry.getKey();
                    String projBody = entry.getValue();

                    Map<String, List<String>> fields = parseProjectFields(projBody);
                    buildProjectChunks(projName, fields, sessionId, docType, chunks);
                }
            }

            // Process Flat Sections (Summary, Skills, Experience, Education, Certifications)
            for (var entry : h1Sections.entrySet()) {
                String sectionName = entry.getKey();
                if ("Technical Projects".equalsIgnoreCase(sectionName)) continue;

                chunks.add(DocumentChunk.builder()
                        .sessionId(sessionId)
                        .docType(docType)
                        .parentId(null)
                        .chunkType("flat_section")
                        .domain(extractDomainsFromText(entry.getValue()))
                        .content("# " + sectionName + "\n" + entry.getValue().strip())
                        .enrichedContent(null)
                        .build());
            }

        } else {
            // For JD: Split into flat section chunks
            for (var entry : h1Sections.entrySet()) {
                String sectionName = entry.getKey();
                chunks.add(DocumentChunk.builder()
                        .sessionId(sessionId)
                        .docType(docType)
                        .parentId(null)
                        .chunkType("flat_section")
                        .domain(extractDomainsFromText(entry.getValue()))
                        .content("# " + sectionName + "\n" + entry.getValue().strip())
                        .enrichedContent(null)
                        .build());
            }
        }

        log.info("[Chunker] Created {} chunks for session={} docType={}", chunks.size(), sessionId, docType);
        return chunks;
    }

    private Map<String, String> splitByHeading(String text, int level) {
        Map<String, String> result = new LinkedHashMap<>();
        String marker = "#".repeat(level) + " ";
        Pattern pattern = Pattern.compile("^" + Pattern.quote(marker) + "(.+)$", Pattern.MULTILINE);
        Matcher matcher = pattern.matcher(text);

        List<Integer> starts = new ArrayList<>();
        List<String> titles = new ArrayList<>();

        while (matcher.find()) {
            titles.add(matcher.group(1).trim());
            starts.add(matcher.end());
        }

        for (int i = 0; i < titles.size(); i++) {
            int start = starts.get(i);
            int end = (i + 1 < titles.size()) ? matcherStart(pattern, text, i + 1) : text.length();
            result.put(titles.get(i), text.substring(start, end).strip());
        }

        return result;
    }

    private int matcherStart(Pattern pattern, String text, int index) {
        Matcher m = pattern.matcher(text);
        int count = 0;
        while (m.find()) {
            if (count == index) return m.start();
            count++;
        }
        return text.length();
    }

    private Map<String, List<String>> parseProjectFields(String body) {
        Map<String, List<String>> fields = new LinkedHashMap<>();
        String currentField = null;

        for (String rawLine : body.split("\n")) {
            String line = rawLine.strip();
            if (line.isBlank()) continue;

            Matcher fieldMatcher = Pattern.compile("^\\*\\s*([\\w &/#]+):\\s*(.*)$").matcher(line);
            Matcher bulletMatcher = Pattern.compile("^-\\s*(.+)$").matcher(line);

            if (fieldMatcher.find()) {
                currentField = fieldMatcher.group(1).trim();
                String val = fieldMatcher.group(2).trim();
                fields.put(currentField, new ArrayList<>());
                if (!val.isBlank()) {
                    fields.get(currentField).add(val);
                }
            } else if (bulletMatcher.find() && currentField != null) {
                fields.get(currentField).add(bulletMatcher.group(1).trim());
            }
        }

        return fields;
    }

    private void buildProjectChunks(
            String projName,
            Map<String, List<String>> fields,
            String sessionId,
            String docType,
            List<DocumentChunk> outChunks) {

        String role = String.join(" ", fields.getOrDefault("Role/Duration", List.of()));
        String stack = String.join(" ", fields.getOrDefault("Tech Stack", List.of()));
        String overview = String.join(" ", fields.getOrDefault("Overview", List.of()));

        String parentContent = String.format("Dự án: %s. %s. Vai trò: %s. Tech Stack: %s.", projName, overview, role, stack).strip();
        UUID parentId = UUID.randomUUID();

        DocumentChunk parentChunk = DocumentChunk.builder()
                .id(parentId)
                .sessionId(sessionId)
                .docType(docType)
                .parentId(null)
                .chunkType("project_overview")
                .domain(extractDomainsFromText(parentContent))
                .content(parentContent)
                .enrichedContent(null)
                .build();

        outChunks.add(parentChunk);

        List<String> archBullets = fields.getOrDefault("Architecture & Contributions", List.of());
        List<String> featureBullets = fields.getOrDefault("Features & Optimizations", List.of());

        List<MergedBullet> mergedItems = mergeParaphrases(archBullets, featureBullets);

        Map<List<String>, List<String>> domainGroups = new LinkedHashMap<>();
        for (MergedBullet item : mergedItems) {
            String fullText = item.text + (item.alts.isEmpty() ? "" : " (" + String.join("; ", item.alts) + ")");
            List<String> domains = extractDomainsFromText(fullText);
            domainGroups.computeIfAbsent(domains, k -> new ArrayList<>()).add(fullText);
        }

        for (var entry : domainGroups.entrySet()) {
            List<String> domains = entry.getKey();
            String childContent = String.format("Dự án %s — %s", projName, String.join(" ", entry.getValue()));

            DocumentChunk childChunk = DocumentChunk.builder()
                    .id(UUID.randomUUID())
                    .sessionId(sessionId)
                    .docType(docType)
                    .parentId(parentId)
                    .chunkType("domain_child")
                    .domain(domains)
                    .content(childContent)
                    .enrichedContent(null)
                    .build();

            outChunks.add(childChunk);
        }
    }

    private static record MergedBullet(String text, List<String> alts) {}

    private List<MergedBullet> mergeParaphrases(List<String> archBullets, List<String> featureBullets) {
        List<MergedBullet> merged = archBullets.stream()
                .map(b -> new MergedBullet(b, new ArrayList<>()))
                .collect(Collectors.toList());

        for (String fb : featureBullets) {
            int bestIdx = -1;
            double bestScore = 0.0;
            for (int i = 0; i < merged.size(); i++) {
                double score = jaccardSimilarity(fb, merged.get(i).text);
                if (score > bestScore) {
                    bestScore = score;
                    bestIdx = i;
                }
            }
            if (bestIdx >= 0 && bestScore >= 0.15) {
                merged.get(bestIdx).alts.add(fb);
            } else {
                merged.add(new MergedBullet(fb, new ArrayList<>()));
            }
        }

        return merged;
    }

    private double jaccardSimilarity(String a, String b) {
        Set<String> wa = extractWords(a);
        Set<String> wb = extractWords(b);
        if (wa.isEmpty() || wb.isEmpty()) return 0.0;

        Set<String> intersection = new HashSet<>(wa);
        intersection.retainAll(wb);

        Set<String> union = new HashSet<>(wa);
        union.addAll(wb);

        return (double) intersection.size() / union.size();
    }

    private Set<String> extractWords(String text) {
        if (text == null) return Collections.emptySet();
        Set<String> words = new HashSet<>();
        Matcher m = Pattern.compile("[a-zA-Z]+").matcher(text.toLowerCase());
        while (m.find()) {
            String w = m.group();
            if (!STOPWORDS.contains(w)) {
                words.add(w);
            }
        }
        return words;
    }

    private List<String> extractDomainsFromText(String text) {
        if (text == null || text.isBlank()) return List.of("general");

        Set<String> tags = new TreeSet<>();
        for (var entry : ONTOLOGY.entrySet()) {
            String domain = entry.getKey();
            for (String kw : entry.getValue()) {
                String patternString = (kw.contains("\\b") || kw.contains("^")) ? kw : "(?i)\\b" + Pattern.quote(kw) + "\\b";
                Pattern p = Pattern.compile(patternString, Pattern.CASE_INSENSITIVE);
                if (p.matcher(text).find()) {
                    tags.add(domain);
                    break;
                }
            }
        }

        return tags.isEmpty() ? List.of("general") : new ArrayList<>(tags);
    }
}
