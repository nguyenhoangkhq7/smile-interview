package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.assessment.AssessmentResponseDto;
import fit.iuh.modules.assessment.ResumeAssessment;
import fit.iuh.modules.assessment.ResumeAssessmentRepository;
import fit.iuh.modules.ingestion.DocumentType;
import fit.iuh.modules.ingestion.SessionDocument;
import fit.iuh.modules.ingestion.SessionDocumentRepository;
import fit.iuh.exception.QuestionBankException;
import fit.iuh.modules.rulengine.EvaluationCriteria;
import fit.iuh.modules.rulengine.EvaluationCriteriaRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;
import java.util.regex.Pattern;
import java.util.regex.Matcher;

/**
 * Orchestrates the full Question Bank generation pipeline: loading data,
 * extracting context, determining distribution, generating questions, and saving.
 *
 * <h3>Pipeline (v2 — evidence-item based)</h3>
 * <ol>
 *   <li><b>Bước 0:</b> Load {@link ResumeAssessment} and read {@code evidence_items} +
 *       {@code additional_evidence_items} directly — no cosine similarity recalculation.</li>
 *   <li><b>Bước 1:</b> Extract {@link CandidateContextDto} from structured evidence items
 *       (strong/gap/tech stack) — no keyword heuristic on raw text.</li>
 *   <li><b>Bước 2:</b> {@link DifficultyDistributor} calculates easy/medium/hard counts.</li>
 *   <li><b>Bước 3:</b> Cache-aside with Redis. Keys are based on
 *       {@code (criteria_id, status, seniority_level)} for stable cross-candidate hit rates.</li>
 *   <li><b>Bước 4-5:</b> Assign sequential IDs (Q001...) and build metadata.</li>
 *   <li><b>Bước 6:</b> Persist {@link QuestionBank} to DB.</li>
 * </ol>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class QuestionBankService {

    /** Maximum number of evidence items to pass to the LLM per generation call. */
    private static final int MAX_EVIDENCE_ITEMS = 15;

    private final QuestionGenerationService questionGenerationService;
    private final DifficultyDistributor difficultyDistributor;
    private final ResumeAssessmentRepository assessmentRepo;
    private final SessionDocumentRepository documentRepo;
    private final QuestionBankRepository questionBankRepo;
    private final ObjectMapper objectMapper;
    private final SemanticCacheKeyGenerator cacheKeyGenerator;
    private final SemanticCacheService cacheService;
    private final EvaluationCriteriaRepository evaluationCriteriaRepository;

    /**
     * Generates a personalized question bank for a session.
     *
     * @param request session ID and question config DTO
     * @return generated question bank DTO
     */
    @Transactional
    public QuestionBankResponseDto generate(GenerateQuestionBankRequest request) {
        String sessionId = request.getSessionId();
        QuestionConfigDto config = request.getQuestionConfig();

        if (config.total() <= 0) {
            throw new QuestionBankException("Total requested questions count must be at least 1.");
        }

        log.info("[QuestionBank] Starting generation for session={}, total questions={}", sessionId, config.total());

        // ── Bước 0: Load ResumeAssessment and extract evidence items ─────────
        ResumeAssessment assessment = assessmentRepo.findBySessionId(sessionId)
                .orElseThrow(() -> new QuestionBankException(
                        "Resume assessment not found for session: " + sessionId + ". Please generate an assessment first."));

        // Build EvidenceItemPair list from structured assessment output — no vector DB needed.
        List<EvidenceItemPair> allEvidencePairs = buildEvidencePairs(assessment);

        log.info("[QuestionBank] Loaded {} evidence pairs from assessment for session {}.",
                allEvidencePairs.size(), sessionId);

        // ── Bước 1: Context Extraction from structured evidence items ─────────
        // strongAreas: all items with status = "matched"
        List<String> strongAreas = allEvidencePairs.stream()
                .filter(p -> "matched".equalsIgnoreCase(p.status()))
                .map(EvidenceItemPair::criteriaName)
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());

        // gapAreas: items with status = "missing" or "weak"
        List<String> gapAreas = allEvidencePairs.stream()
                .filter(p -> "missing".equalsIgnoreCase(p.status()) || "weak".equalsIgnoreCase(p.status()))
                .map(EvidenceItemPair::criteriaName)
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());

        // techStackPossessed: cvEvidence of ALL matched/weak items (normalized via regex dictionary)
        List<String> rawTechPossessed = allEvidencePairs.stream()
                .filter(p -> "matched".equalsIgnoreCase(p.status()) || "weak".equalsIgnoreCase(p.status()))
                .map(EvidenceItemPair::cvEvidence)
                .filter(s -> s != null && !s.isBlank())
                .distinct()
                .collect(Collectors.toList());
        List<String> techStackPossessed = extractTechKeywords(rawTechPossessed);

        // techStackRequired: jdRequirement of ALL missing items (normalized via regex dictionary)
        List<String> rawTechRequired = allEvidencePairs.stream()
                .filter(p -> "missing".equalsIgnoreCase(p.status()))
                .map(EvidenceItemPair::jdRequirement)
                .filter(s -> s != null && !s.isBlank())
                .distinct()
                .collect(Collectors.toList());
        List<String> techStackRequired = extractTechKeywords(rawTechRequired);

        // targetDomain: keyword heuristic on CV/JD markdown (kept as-is until AssessmentService stores it)
        SessionDocument cvDoc = documentRepo.findBySessionIdAndDocumentType(sessionId, DocumentType.CV)
                .orElseThrow(() -> new QuestionBankException("CV document not found for session: " + sessionId));
        SessionDocument jdDoc = documentRepo.findBySessionIdAndDocumentType(sessionId, DocumentType.JD)
                .orElseThrow(() -> new QuestionBankException("JD document not found for session: " + sessionId));

        String targetDomain = detectTargetDomain(cvDoc.getMarkdownContent(), jdDoc.getMarkdownContent());

        CandidateContextDto context = CandidateContextDto.builder()
                .candidateLevel(assessment.getSeniorityLevel())
                .overallMatch(assessment.getOverallMatchScore() != null
                        ? (assessment.getOverallMatchScore() >= 80 ? "high"
                           : assessment.getOverallMatchScore() >= 50 ? "medium" : "low")
                        : "medium")
                .yearsOfExperience(null) // Not stored in schema; LLM will infer from context
                .strongAreas(strongAreas)
                .gapAreas(gapAreas)
                .techStackRequired(techStackRequired)
                .techStackPossessed(techStackPossessed)
                .targetDomain(targetDomain)
                .roleType(assessment.getJobCategory())
                .build();

        // ── Bước 2: Difficulty Distribution Calculation ───────────────────────
        List<QuestionAssignment> assignments = difficultyDistributor.distribute(
                config.getTotalQuestions(),
                context.getCandidateLevel(),
                assessment.getOverallMatchScore(),
                allEvidencePairs
        );

        Map<String, List<QuestionAssignment>> assignmentsByCategory = assignments.stream()
                .collect(Collectors.groupingBy(QuestionAssignment::category, LinkedHashMap::new, Collectors.toList()));

        // ── Bước 3: Question Generation with Redis Cache-Aside ────────────────
        List<QuestionDto> allQuestions = new ArrayList<>();
        int typeIndex = 0;
        
        for (var entry : assignmentsByCategory.entrySet()) {
            typeIndex++;
            String type = entry.getKey();
            List<QuestionAssignment> typeAssignments = entry.getValue();

            List<QuestionDto> typeQuestions = new ArrayList<>();
            List<QuestionAssignment> missedAssignments = new ArrayList<>();
            
            // Step 3.1: Check Cache for each assignment
            for (QuestionAssignment qa : typeAssignments) {
                String cacheKey = null;
                if (qa.item() != null) {
                    cacheKey = resolveCacheKey(qa.item(), assessment.getSeniorityLevel());
                    if (qa.isFollowUp()) {
                        cacheKey += "|followup:true";
                    }
                }
                
                boolean hit = false;
                if (cacheKey != null) {
                    List<QuestionDto> cachedList = cacheService.get(cacheKey);
                    if (cachedList != null && !cachedList.isEmpty()) {
                        Optional<QuestionDto> match = cachedList.stream()
                                .filter(q -> type.equalsIgnoreCase(q.getType()) && qa.difficulty().equalsIgnoreCase(q.getDifficulty()))
                                .findFirst();
                                
                        if (match.isPresent()) {
                            typeQuestions.add(match.get());
                            hit = true;
                            log.info("[QuestionBank] Cache HIT reused: {} '{}' question for criteria '{}' (followUp={})",
                                    qa.difficulty(), type, qa.item().criteriaName(), qa.isFollowUp());
                        }
                    }
                }
                
                if (!hit) {
                    missedAssignments.add(qa);
                }
            }

            int totalRemaining = missedAssignments.size();
            log.info("[QuestionBank] Type '{}' distribution: requested={}, remaining to generate={}",
                    type, typeAssignments.size(), totalRemaining);

            // Step 3.2: Generate remaining questions from LLM using missed assignments
            if (totalRemaining > 0) {
                if (typeIndex > 1) {
                    try {
                        log.info("[QuestionBank] Pacing LLM calls: sleeping for 5 seconds...");
                        Thread.sleep(5000);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new QuestionBankException("Question generation pacing interrupted", ie);
                    }
                }

                List<QuestionDto> generatedQs = questionGenerationService.generateForType(
                        type, context, missedAssignments);

                typeQuestions.addAll(generatedQs);

                // Group generated questions by the "item_N" id returned by LLM
                Map<String, List<QuestionDto>> newQuestionsByItemId = new HashMap<>();
                for (QuestionDto q : generatedQs) {
                    String itemId = q.getId(); // e.g. "item_0"
                    if (itemId != null && itemId.startsWith("item_")) {
                        newQuestionsByItemId.computeIfAbsent(itemId, k -> new ArrayList<>()).add(q);
                    } else {
                        // Fallback: associate with the first missed assignment
                        newQuestionsByItemId.computeIfAbsent("item_0", k -> new ArrayList<>()).add(q);
                    }
                }

                // Step 3.3: Write new questions to Redis (merge with existing cache for this key)
                newQuestionsByItemId.forEach((itemId, newQs) -> {
                    int assignmentIdx = parseItemIndex(itemId);
                    if (assignmentIdx >= 0 && assignmentIdx < missedAssignments.size()) {
                        QuestionAssignment qa = missedAssignments.get(assignmentIdx);
                        if (qa.item() != null) {
                            String cacheKey = resolveCacheKey(qa.item(), assessment.getSeniorityLevel());
                            if (qa.isFollowUp()) {
                                cacheKey += "|followup:true";
                            }
                            
                            List<QuestionDto> existing = cacheService.get(cacheKey);
                            List<QuestionDto> merged = new ArrayList<>();
                            if (existing != null) merged.addAll(existing);
                            
                            for (QuestionDto nq : newQs) {
                                nq.setType(type);
                                boolean duplicate = merged.stream().anyMatch(eq ->
                                        Objects.equals(eq.getType(), nq.getType()) &&
                                        Objects.equals(eq.getQuestion(), nq.getQuestion())
                                );
                                if (!duplicate) merged.add(nq);
                            }
                            cacheService.put(cacheKey, merged, Duration.ofDays(7));
                        }
                    }
                });
            }

            allQuestions.addAll(typeQuestions);
        }

        // ── Bước 4: Assembly & Sequencing ────────────────────────────────────
        for (int i = 0; i < allQuestions.size(); i++) {
            allQuestions.get(i).setId(String.format("Q%03d", i + 1));
        }

        // ── Bước 5: Build metadata ────────────────────────────────────────────
        int totalEasy = 0, totalMedium = 0, totalHard = 0;
        for (QuestionDto q : allQuestions) {
            if ("easy".equalsIgnoreCase(q.getDifficulty()))        totalEasy++;
            else if ("medium".equalsIgnoreCase(q.getDifficulty())) totalMedium++;
            else if ("hard".equalsIgnoreCase(q.getDifficulty()))   totalHard++;
        }
        int total = allQuestions.size();
        Map<String, String> diffDistMap = new LinkedHashMap<>();
        if (total > 0) {
            diffDistMap.put("easy",   Math.round((totalEasy   * 100.0) / total) + "%");
            diffDistMap.put("medium", Math.round((totalMedium * 100.0) / total) + "%");
            diffDistMap.put("hard",   Math.round((totalHard   * 100.0) / total) + "%");
        } else {
            diffDistMap.put("easy", "0%"); diffDistMap.put("medium", "0%"); diffDistMap.put("hard", "0%");
        }

        String generationRationale = String.format(
                "%s-level %s candidate with %s CV-JD match. Strong areas: %s. Gap areas: %s.",
                context.getCandidateLevel() != null ? context.getCandidateLevel().name() : "MID",
                context.getRoleType() != null ? context.getRoleType().name() : "BACKEND",
                context.getOverallMatch() != null ? context.getOverallMatch() : "medium",
                context.getStrongAreas() != null ? String.join(", ", context.getStrongAreas()) : "None",
                context.getGapAreas() != null ? String.join(", ", context.getGapAreas()) : "None"
        );

        QuestionBankMetadataDto metadata = QuestionBankMetadataDto.builder()
                .candidateLevel(context.getCandidateLevel() != null ? context.getCandidateLevel().name() : "MID")
                .overallMatch(context.getOverallMatch())
                .yearsOfExperience(context.getYearsOfExperience())
                .roleType(context.getRoleType() != null ? context.getRoleType().name() : "OTHER")
                .targetDomain(context.getTargetDomain())
                .strongAreas(context.getStrongAreas())
                .gapAreas(context.getGapAreas())
                .difficultyDistribution(diffDistMap)
                .totalQuestions(total)
                .generationRationale(generationRationale)
                .build();

        // ── Bước 6: Persist ───────────────────────────────────────────────────
        QuestionBank entity = QuestionBank.builder()
                .sessionId(sessionId)
                .metadata(metadata)
                .questionBankJson(allQuestions)
                .questionConfig(config)
                .candidateContext(context)
                .totalQuestions(total)
                .build();

        entity = questionBankRepo.save(entity);
        log.info("[QuestionBank] Saved generated QuestionBank id={} for session={}", entity.getId(), sessionId);

        return toResponseDto(entity);
    }

    /**
     * Retrieves question banks by sessionId.
     */
    public List<QuestionBankResponseDto> getBySessionId(String sessionId) {
        log.info("[QuestionBank] Retrieving question banks for session: {}", sessionId);
        List<QuestionBank> list = questionBankRepo.findBySessionIdOrderByCreatedAtDesc(sessionId);
        List<QuestionBankResponseDto> responses = new ArrayList<>();
        for (QuestionBank qb : list) {
            responses.add(toResponseDto(qb));
        }
        return responses;
    }

    /**
     * Retrieves question bank by ID.
     */
    public QuestionBankResponseDto getById(UUID id) {
        log.info("[QuestionBank] Retrieving question bank by ID: {}", id);
        QuestionBank qb = questionBankRepo.findById(id)
                .orElseThrow(() -> new QuestionBankException("Question bank not found with ID: " + id));
        return toResponseDto(qb);
    }

    /**
     * Regenerates a single question in the bank.
     *
     * @param questionBankId ID of the question bank
     * @param questionId     sequential ID of the question (e.g. Q003)
     * @return updated question bank DTO
     */
    @Transactional
    public QuestionBankResponseDto regenerateQuestion(UUID questionBankId, String questionId) {
        log.info("[QuestionBank] Regenerating question {} inside bank {}", questionId, questionBankId);

        QuestionBank bank = questionBankRepo.findById(questionBankId)
                .orElseThrow(() -> new QuestionBankException("Question bank not found: " + questionBankId));

        List<QuestionDto> questions = bank.getQuestionBankJson();
        QuestionDto target = null;
        for (QuestionDto q : questions) {
            if (q.getId().equalsIgnoreCase(questionId)) {
                target = q;
                break;
            }
        }
        if (target == null) {
            throw new QuestionBankException("Question with ID " + questionId + " not found in bank " + questionBankId);
        }

        // Load assessment to get evidence items for context
        final String sessionId = bank.getSessionId();
        ResumeAssessment assessment = assessmentRepo.findBySessionId(sessionId)
                .orElseThrow(() -> new QuestionBankException(
                        "Assessment not found for session " + sessionId + ". Cannot regenerate."));

        List<EvidenceItemPair> allEvidencePairs = buildEvidencePairs(assessment);

        QuestionDto regenerated = questionGenerationService.regenerateSingle(
                target.getType(),
                target.getDifficulty(),
                bank.getCandidateContext(),
                allEvidencePairs,
                questions
        );

        // Keep same sequential ID
        regenerated.setId(questionId);

        // Replace in list
        int index = questions.indexOf(target);
        questions.set(index, regenerated);

        bank.setQuestionBankJson(questions);
        bank = questionBankRepo.save(bank);

        log.info("[QuestionBank] Question {} successfully regenerated in bank {}", questionId, questionBankId);
        return toResponseDto(bank);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Private helpers
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Builds a flat list of {@link EvidenceItemPair} from a {@link ResumeAssessment}.
     *
     * <p>Standard {@code evidence_items} are sorted by {@code weight_used} descending so
     * that the most important criteria come first. If the total exceeds
     * {@link #MAX_EVIDENCE_ITEMS}, the lowest-weight items are dropped.
     * Ad-hoc {@code additional_evidence_items} are appended after standard items
     * (they have no weight to sort by) until the cap is reached.
     */
    private List<EvidenceItemPair> buildEvidencePairs(ResumeAssessment assessment) {
        List<EvidenceItemPair> pairs = new ArrayList<>();

        // Load all evaluation criteria to map criteriaId -> questionType
        Map<Long, String> criteriaIdToTypeMap = new HashMap<>();
        try {
            List<EvaluationCriteria> allCriteria = evaluationCriteriaRepository.findAll();
            for (EvaluationCriteria ec : allCriteria) {
                if (ec.getId() != null) {
                    criteriaIdToTypeMap.put(ec.getId(), ec.getQuestionType() != null ? ec.getQuestionType() : "technical");
                }
            }
        } catch (Exception e) {
            log.error("[QuestionBank] Failed to load evaluation criteria for question types", e);
        }

        // 1. Standard evidence items — sorted by weight descending, capped at MAX
        if (assessment.getEvidenceItems() != null) {
            assessment.getEvidenceItems().stream()
                    .filter(item -> !"not_applicable".equalsIgnoreCase(item.status()))
                    .sorted(Comparator.comparingDouble(
                            (AssessmentResponseDto.EvidenceItem item) ->
                                    item.weightUsed() != null ? item.weightUsed() : 0.0
                    ).reversed())
                    .limit(MAX_EVIDENCE_ITEMS)
                    .forEach(item -> pairs.add(new EvidenceItemPair(
                            item.criteriaId(),
                            item.criteriaName(),
                            item.jdRequirement(),
                            item.cvEvidence(),
                            item.status(),
                            item.reasoning(),
                            item.weightUsed(),
                            criteriaIdToTypeMap.getOrDefault(item.criteriaId(), "technical")
                    )));
        }

        // 2. Ad-hoc evidence items — appended after standard items, up to cap
        if (assessment.getAdditionalEvidenceItems() != null && pairs.size() < MAX_EVIDENCE_ITEMS) {
            int remaining = MAX_EVIDENCE_ITEMS - pairs.size();
            assessment.getAdditionalEvidenceItems().stream()
                    .filter(item -> !"not_applicable".equalsIgnoreCase(item.status()))
                    .limit(remaining)
                    .forEach(item -> pairs.add(new EvidenceItemPair(
                            null,           // no criteria_id for ad-hoc items
                            item.criteriaName(),
                            item.jdRequirement(),
                            item.cvEvidence(),
                            item.status(),
                            item.reasoning(),
                            null,            // no weight for ad-hoc items
                            "technical"      // default question type for ad-hoc is technical
                    )));
        }

        return pairs;
    }

    /**
     * Resolves the Redis cache key for an evidence pair using the v2 key strategy:
     * <ul>
     *   <li>Standard items (have {@code criteriaId}): key = hash(criteriaId + status + level)</li>
     *   <li>Ad-hoc items ({@code criteriaId = null}): key = hash(normalizedName + status + level)</li>
     * </ul>
     */
    private String resolveCacheKey(EvidenceItemPair pair, fit.iuh.modules.assessment.SeniorityLevel level) {
        if (pair.criteriaId() != null) {
            return cacheKeyGenerator.generateKey(pair.criteriaId(), pair.status(), level);
        } else {
            return cacheKeyGenerator.generateKeyForAdHoc(pair.criteriaName(), pair.status(), level);
        }
    }

    /**
     * Parses the numeric index from an LLM-generated item ID string (e.g., "item_3" → 3).
     * Returns 0 as fallback if parsing fails.
     */
    private int parseItemIndex(String itemId) {
        if (itemId == null || !itemId.startsWith("item_")) return 0;
        try {
            return Integer.parseInt(itemId.substring("item_".length()));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    /**
     * Detects target business domain from CV and JD markdown using keyword heuristics.
     * This logic is kept here until {@code AssessmentService} stores the domain as a
     * typed field in {@link ResumeAssessment}.
     */
    private String detectTargetDomain(String cvMarkdown, String jdMarkdown) {
        String combined = ((cvMarkdown != null ? cvMarkdown : "") + " "
                + (jdMarkdown != null ? jdMarkdown : "")).toLowerCase();

        if (combined.contains("wallet") || combined.contains("transaction")
                || combined.contains("payment") || combined.contains("bank")
                || combined.contains("fintech")) {
            return "fintech";
        } else if (combined.contains("cart") || combined.contains("shop")
                || combined.contains("checkout") || combined.contains("e-commerce")
                || combined.contains("order")) {
            return "e-commerce";
        } else if (combined.contains("health") || combined.contains("hospital")
                || combined.contains("medical") || combined.contains("patient")) {
            return "healthcare";
        } else if (combined.contains("saas") || combined.contains("multi-tenant")
                || combined.contains("billing")) {
            return "saas";
        } else if (combined.contains("enterprise") || combined.contains("b2b")) {
            return "enterprise";
        } else if (combined.contains("startup") || combined.contains("funding")
                || combined.contains("mvp")) {
            return "startup";
        }
        return "other";
    }

    private QuestionBankResponseDto toResponseDto(QuestionBank entity) {
        return QuestionBankResponseDto.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .metadata(entity.getMetadata())
                .questionBank(entity.getQuestionBankJson())
                .createdAt(entity.getCreatedAt())
                .build();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Technology Dictionary & Regex Extraction Helpers
    // ──────────────────────────────────────────────────────────────────────────

    private static final Set<String> TECH_DICTIONARY = Set.of(
        "java", "spring boot", "spring", "hibernate", "jpa", "mybatis", "kotlin", "scala", "groovy", "maven", "gradle",
        "node.js", "nodejs", "express", "koa", "nestjs", "typescript", "javascript", "react", "redux", "next.js", "nextjs",
        "vue", "vuex", "nuxtjs", "nuxt", "angular", "html", "css", "sass", "less", "tailwind", "bootstrap", "python",
        "django", "flask", "fastapi", "pytorch", "tensorflow", "keras", "numpy", "pandas", "scikit-learn", "golang", "go",
        "ruby", "rails", "php", "laravel", "symfony", "c#", ".net", "asp.net", "entity framework", "c++", "c", "rust",
        "swift", "objective-c", "flutter", "react native", "xamarin", "cordova", "ionic", "mysql", "postgresql", "postgres",
        "oracle", "sql server", "sqlite", "mongodb", "redis", "memcached", "cassandra", "dynamodb", "neo4j", "elasticsearch",
        "solr", "rabbitmq", "kafka", "activemq", "sqs", "aws", "ecr", "ecs", "eks", "lambda", "s3", "rds", "azure", "gcp",
        "docker", "kubernetes", "k8s", "jenkins", "gitlab ci", "github actions", "travis ci", "circleci", "ansible", "terraform",
        "cloudformation", "git", "svn", "agile", "scrum", "kanban", "jira", "confluence", "junit", "mockito", "selenium",
        "cypress", "playwright", "jest", "mocha", "chai", "postman", "restassured", "jmeter", "prometheus", "grafana",
        "elk", "splunk", "sonarqube", "rest", "graphql", "grpc", "ci/cd", "microservices", "api", "etl", "elt", "rag", "star schema",
        "snowflake", "arc"
    );

    private static final Map<String, String> TECH_CAPITALIZATION_MAP;
    static {
        Map<String, String> m = new HashMap<>();
        m.put("java", "Java");
        m.put("spring boot", "Spring Boot");
        m.put("spring", "Spring");
        m.put("hibernate", "Hibernate");
        m.put("jpa", "JPA");
        m.put("mybatis", "MyBatis");
        m.put("kotlin", "Kotlin");
        m.put("scala", "Scala");
        m.put("groovy", "Groovy");
        m.put("maven", "Maven");
        m.put("gradle", "Gradle");
        m.put("node.js", "Node.js");
        m.put("nodejs", "Node.js");
        m.put("express", "Express");
        m.put("koa", "Koa");
        m.put("nestjs", "NestJS");
        m.put("typescript", "TypeScript");
        m.put("javascript", "JavaScript");
        m.put("react", "React");
        m.put("redux", "Redux");
        m.put("next.js", "Next.js");
        m.put("nextjs", "Next.js");
        m.put("vue", "Vue");
        m.put("vuex", "Vuex");
        m.put("nuxtjs", "Nuxt.js");
        m.put("nuxt", "Nuxt.js");
        m.put("angular", "Angular");
        m.put("html", "HTML");
        m.put("css", "CSS");
        m.put("sass", "SASS");
        m.put("less", "LESS");
        m.put("tailwind", "Tailwind CSS");
        m.put("bootstrap", "Bootstrap");
        m.put("python", "Python");
        m.put("django", "Django");
        m.put("flask", "Flask");
        m.put("fastapi", "FastAPI");
        m.put("pytorch", "PyTorch");
        m.put("tensorflow", "TensorFlow");
        m.put("keras", "Keras");
        m.put("numpy", "NumPy");
        m.put("pandas", "Pandas");
        m.put("scikit-learn", "Scikit-Learn");
        m.put("golang", "Go");
        m.put("go", "Go");
        m.put("ruby", "Ruby");
        m.put("rails", "Ruby on Rails");
        m.put("php", "PHP");
        m.put("laravel", "Laravel");
        m.put("symfony", "Symfony");
        m.put("c#", "C#");
        m.put(".net", ".NET");
        m.put("asp.net", "ASP.NET");
        m.put("entity framework", "Entity Framework");
        m.put("c++", "C++");
        m.put("c", "C");
        m.put("rust", "Rust");
        m.put("swift", "Swift");
        m.put("objective-c", "Objective-C");
        m.put("flutter", "Flutter");
        m.put("react native", "React Native");
        m.put("xamarin", "Xamarin");
        m.put("cordova", "Cordova");
        m.put("ionic", "Ionic");
        m.put("mysql", "MySQL");
        m.put("postgresql", "PostgreSQL");
        m.put("postgres", "PostgreSQL");
        m.put("oracle", "Oracle DB");
        m.put("sql server", "SQL Server");
        m.put("sqlite", "SQLite");
        m.put("mongodb", "MongoDB");
        m.put("redis", "Redis");
        m.put("memcached", "Memcached");
        m.put("cassandra", "Cassandra");
        m.put("dynamodb", "DynamoDB");
        m.put("neo4j", "Neo4j");
        m.put("elasticsearch", "Elasticsearch");
        m.put("solr", "Solr");
        m.put("rabbitmq", "RabbitMQ");
        m.put("kafka", "Apache Kafka");
        m.put("activemq", "ActiveMQ");
        m.put("sqs", "AWS SQS");
        m.put("aws", "AWS");
        m.put("ecr", "AWS ECR");
        m.put("ecs", "AWS ECS");
        m.put("eks", "AWS EKS");
        m.put("lambda", "AWS Lambda");
        m.put("s3", "AWS S3");
        m.put("rds", "AWS RDS");
        m.put("azure", "Azure");
        m.put("gcp", "GCP");
        m.put("docker", "Docker");
        m.put("kubernetes", "Kubernetes");
        m.put("k8s", "Kubernetes");
        m.put("jenkins", "Jenkins");
        m.put("gitlab ci", "GitLab CI");
        m.put("github actions", "GitHub Actions");
        m.put("travis ci", "Travis CI");
        m.put("circleci", "CircleCI");
        m.put("ansible", "Ansible");
        m.put("terraform", "Terraform");
        m.put("cloudformation", "CloudFormation");
        m.put("git", "Git");
        m.put("svn", "SVN");
        m.put("agile", "Agile");
        m.put("scrum", "Scrum");
        m.put("kanban", "Kanban");
        m.put("jira", "Jira");
        m.put("confluence", "Confluence");
        m.put("junit", "JUnit");
        m.put("mockito", "Mockito");
        m.put("selenium", "Selenium");
        m.put("cypress", "Cypress");
        m.put("playwright", "Playwright");
        m.put("jest", "Jest");
        m.put("mocha", "Mocha");
        m.put("chai", "Chai");
        m.put("postman", "Postman");
        m.put("restassured", "RestAssured");
        m.put("jmeter", "JMeter");
        m.put("prometheus", "Prometheus");
        m.put("grafana", "Grafana");
        m.put("elk", "ELK Stack");
        m.put("splunk", "Splunk");
        m.put("sonarqube", "SonarQube");
        m.put("rest", "REST API");
        m.put("graphql", "GraphQL");
        m.put("grpc", "gRPC");
        m.put("ci/cd", "CI/CD");
        m.put("microservices", "Microservices");
        m.put("api", "API");
        m.put("etl", "ETL");
        m.put("elt", "ELT");
        m.put("rag", "RAG");
        m.put("star schema", "Star Schema");
        m.put("snowflake", "Snowflake");
        m.put("arc", "ARC");
        TECH_CAPITALIZATION_MAP = Collections.unmodifiableMap(m);
    }

    public static List<String> extractTechKeywords(List<String> rawTexts) {
        if (rawTexts == null || rawTexts.isEmpty()) {
            return Collections.emptyList();
        }
        
        Set<String> matchedTechs = new LinkedHashSet<>();
        
        for (String text : rawTexts) {
            if (text == null || text.isBlank()) continue;
            
            String lowerText = text.toLowerCase();
            
            for (String tech : TECH_DICTIONARY) {
                String escapedTech = Pattern.quote(tech);
                String regex;
                if (tech.endsWith("+") || tech.endsWith("#") || tech.startsWith(".")) {
                    regex = "(?i)(?<=^|[^a-zA-Z0-9])" + escapedTech + "(?=$|[^a-zA-Z0-9])";
                } else {
                    regex = "(?i)\\b" + escapedTech + "\\b";
                }
                
                if (Pattern.compile(regex).matcher(lowerText).find()) {
                    matchedTechs.add(capitalizeTech(tech));
                }
            }
        }
        return new ArrayList<>(matchedTechs);
    }

    private static String capitalizeTech(String tech) {
        if (tech == null) return "";
        String mapped = TECH_CAPITALIZATION_MAP.get(tech.toLowerCase());
        if (mapped != null) {
            return mapped;
        }
        return tech.substring(0, 1).toUpperCase() + tech.substring(1);
    }
}
