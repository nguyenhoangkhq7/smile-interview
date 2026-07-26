package fit.iuh.modules.assessment.service.impl;

import fit.iuh.modules.assessment.service.CriteriaLoaderService;
import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.repository.DocumentChunkRepository;
import fit.iuh.modules.chunking.service.EmbeddingService;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Service
public class CriteriaLoaderServiceImpl implements CriteriaLoaderService {

    private final JobCriteriaRepository jobCriteriaRepository;
    private final DocumentChunkRepository documentChunkRepository;
    private final EmbeddingService embeddingService;
    private final fit.iuh.modules.assessment.service.JdCriteriaClassifierService jdCriteriaClassifierService;

    @Autowired
    public CriteriaLoaderServiceImpl(
            JobCriteriaRepository jobCriteriaRepository,
            @Autowired(required = false) DocumentChunkRepository documentChunkRepository,
            @Autowired(required = false) EmbeddingService embeddingService,
            @Autowired(required = false) fit.iuh.modules.assessment.service.JdCriteriaClassifierService jdCriteriaClassifierService) {
        this.jobCriteriaRepository = jobCriteriaRepository;
        this.documentChunkRepository = documentChunkRepository;
        this.embeddingService = embeddingService;
        this.jdCriteriaClassifierService = jdCriteriaClassifierService;
    }

    @Override
    public fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle loadAndClassifyCriteria(
            String categoryName,
            String seniorityLevelName,
            String fullJdMarkdown) {

        List<CriteriaWeightProjection> dbCriteria = loadCriteriaWithFallback(categoryName, seniorityLevelName);

        if (jdCriteriaClassifierService != null) {
            // Pass seniorityLevel so the classifier can apply seniority-aware rules
            return jdCriteriaClassifierService.classify(fullJdMarkdown, dbCriteria, seniorityLevelName);
        } else {
            List<fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.ClassifiedCriteria> list = dbCriteria.stream()
                    .map(c -> new fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle.ClassifiedCriteria(
                            c.getCriteriaId(), c.getCriteriaName(), c.getPromptInstruction(), c.getWeightPercentage(), "required"))
                    .collect(Collectors.toList());
            return new fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle(list, List.of());
        }
    }


    @Override
    public List<CriteriaWeightProjection> loadAndFilterCriteria(
            String categoryName,
            String seniorityLevelName,
            String sessionId,
            String fullJdMarkdown,
            boolean shouldIncludeNotApp) {

        List<CriteriaWeightProjection> criteriaList = loadCriteriaWithFallback(categoryName, seniorityLevelName);

        if (!shouldIncludeNotApp) {
            List<CriteriaWeightProjection> preFiltered = preFilterCriteriaForJd(sessionId, fullJdMarkdown, criteriaList);
            if (!preFiltered.isEmpty()) {
                criteriaList = preFiltered;
            }
        }

        return criteriaList;
    }

    /**
     * 3-level fallback hierarchy for loading criteria:
     * 1. category + specific seniorityLevel  (most precise)
     * 2. category + 'ALL'                    (covers categories seeded only with ALL)
     * 3. SOFTWARE_ENGINEERING + 'ALL'        (last-resort generic fallback)
     *
     * <p>The SQL query already includes {@code OR m.level = 'ALL'} so step 1 already
     * picks up ALL-level rows. Step 2 is therefore a targeted retry that broadens only
     * the level dimension, while step 3 is the final safety net.
     */
    private List<CriteriaWeightProjection> loadCriteriaWithFallback(String categoryName, String seniorityLevelName) {
        // Step 1: category + specific level (query already includes ALL rows via OR)
        List<CriteriaWeightProjection> criteriaList = jobCriteriaRepository
                .findCriteriaTreeByCategory(categoryName, seniorityLevelName);

        if (!criteriaList.isEmpty()) {
            log.debug("[CriteriaLoader] Loaded {} criteria for category='{}' level='{}'",
                    criteriaList.size(), categoryName, seniorityLevelName);
            return criteriaList;
        }

        // Step 2: category + ALL (for categories that only have ALL-level mappings)
        if (!"ALL".equalsIgnoreCase(seniorityLevelName)) {
            log.warn("[CriteriaLoader] No criteria found for category='{}' level='{}'. Retrying with level='ALL'.",
                    categoryName, seniorityLevelName);
            criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory(categoryName, "ALL");
        }

        if (!criteriaList.isEmpty()) {
            log.info("[CriteriaLoader] Loaded {} criteria for category='{}' level='ALL' (level-fallback)",
                    criteriaList.size(), categoryName);
            return criteriaList;
        }

        // Step 3: SOFTWARE_ENGINEERING + ALL (generic last-resort)
        log.warn("[CriteriaLoader] No criteria found for category='{}' at any level. FALLING BACK to 'SOFTWARE_ENGINEERING' / 'ALL'.",
                categoryName);
        criteriaList = jobCriteriaRepository.findCriteriaTreeByCategory("SOFTWARE_ENGINEERING", "ALL");
        log.info("[CriteriaLoader] Loaded {} criteria from generic SOFTWARE_ENGINEERING fallback.", criteriaList.size());
        return criteriaList;
    }


    private List<CriteriaWeightProjection> preFilterCriteriaForJd(
            String sessionId,
            String fullJdMarkdown,
            List<CriteriaWeightProjection> criteriaList) {

        if (fullJdMarkdown == null || fullJdMarkdown.isBlank() || criteriaList == null || criteriaList.isEmpty()) {
            return criteriaList != null ? criteriaList : List.of();
        }

        String jdLower = fullJdMarkdown.toLowerCase(Locale.ROOT);
        boolean hasVectorIndex = false;

        if (documentChunkRepository != null && embeddingService != null && sessionId != null && !sessionId.isBlank()) {
            try {
                List<DocumentChunk> jdChunks = documentChunkRepository.findBySessionIdAndDocType(sessionId, "JD");
                hasVectorIndex = jdChunks.stream().anyMatch(c -> c.getEmbedding() != null);
            } catch (Exception e) {
                log.warn("[CriteriaLoader] Vector index lookup warning for sessionId={}: {}", sessionId, e.getMessage());
            }
        }

        final boolean useVectorSearch = hasVectorIndex;
        if (useVectorSearch) {
            log.info("[CriteriaLoader] Pre-filtering criteria using Vector Embedding Search for sessionId={}", sessionId);
        } else {
            log.info("[CriteriaLoader] Pre-filtering criteria using Keyword & Synonym Matching for sessionId={}", sessionId);
        }

        return criteriaList.stream()
                .filter(criteria -> isCriteriaRelevantToJd(jdLower, criteria))
                .collect(Collectors.toList());
    }

    private boolean isCriteriaRelevantToJd(String jdLower, CriteriaWeightProjection criteria) {
        if (criteria == null || criteria.getCriteriaName() == null) {
            return false;
        }

        String nameLower = criteria.getCriteriaName().toLowerCase(Locale.ROOT);

        if (jdLower.contains(nameLower)) {
            return true;
        }

        String[] keywords = nameLower.split("[^a-zA-Z0-9+#]+");
        int matchedKeywords = 0;

        for (String kw : keywords) {
            if (kw.length() <= 2 && !isSpecialShortTechTerm(kw)) {
                continue;
            }
            if (jdLower.contains(kw)) {
                matchedKeywords++;
            }
        }

        if (matchedKeywords > 0) {
            return true;
        }

        return checkSynonymRelevance(jdLower, nameLower);
    }

    private boolean isSpecialShortTechTerm(String kw) {
        return Set.of("c", "go", "qa", "db", "ui", "ai", "ml", "ci", "cd", "js", "ts", "r8", "s3", "ec2").contains(kw);
    }

    private boolean checkSynonymRelevance(String jdLower, String nameLower) {
        if (nameLower.contains("database") || nameLower.contains("sql")) {
            return jdLower.contains("postgres") || jdLower.contains("mysql") || jdLower.contains("oracle")
                    || jdLower.contains("mongodb") || jdLower.contains("redis") || jdLower.contains("database")
                    || jdLower.contains("sql") || jdLower.contains("jpa") || jdLower.contains("hibernate") || jdLower.contains("orm");
        }
        if (nameLower.contains("api") || nameLower.contains("rest")) {
            return jdLower.contains("api") || jdLower.contains("rest") || jdLower.contains("graphql")
                    || jdLower.contains("endpoint") || jdLower.contains("http") || jdLower.contains("grpc");
        }
        if (nameLower.contains("testing") || nameLower.contains("qa") || nameLower.contains("tdd")) {
            return jdLower.contains("test") || jdLower.contains("junit") || jdLower.contains("jest")
                    || jdLower.contains("cypress") || jdLower.contains("selenium") || jdLower.contains("postman");
        }
        if (nameLower.contains("ci/cd") || nameLower.contains("pipeline") || nameLower.contains("devops")) {
            return jdLower.contains("ci/cd") || jdLower.contains("pipeline") || jdLower.contains("jenkins")
                    || jdLower.contains("github actions") || jdLower.contains("gitlab") || jdLower.contains("docker");
        }
        if (nameLower.contains("agile") || nameLower.contains("sdlc")) {
            return jdLower.contains("agile") || jdLower.contains("scrum") || jdLower.contains("kanban")
                    || jdLower.contains("sprint") || jdLower.contains("jira") || jdLower.contains("sdlc");
        }
        if (nameLower.contains("solid") || nameLower.contains("clean code")) {
            return jdLower.contains("solid") || jdLower.contains("clean code") || jdLower.contains("maintainable")
                    || jdLower.contains("refactor") || jdLower.contains("design pattern");
        }
        if (nameLower.contains("microservice") || nameLower.contains("architecture")) {
            return jdLower.contains("microservice") || jdLower.contains("architecture") || jdLower.contains("distributed")
                    || jdLower.contains("system design") || jdLower.contains("event-driven") || jdLower.contains("kafka");
        }
        return false;
    }
}
