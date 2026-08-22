package fit.iuh.modules.assessment.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle;
import fit.iuh.modules.assessment.dto.PreparedJdContext;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.gate.EligibilityGateService;
import fit.iuh.modules.assessment.gate.EligibilityGateService.GateCheckDto;
import fit.iuh.modules.assessment.gate.EligibilityGateService.EligibilityEvaluationResult;
import fit.iuh.modules.assessment.util.ResumeHeuristicsUtil;
import fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.DateRange;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Facade Coordinator unifying specialized assessment preparation sub-services:
 * - {@link JdMetadataExtractor}: Job category & seniority level extraction.
 * - {@link CriteriaClassifier}: DB criteria loading, vector pre-filtering, and LLM classification.
 * - {@link EligibilityGateService}: Strategy-driven eligibility gates.
 * - {@link SuggestedCriteriaRecorder}: Ad-hoc criteria persistence.
 * - {@link ResumeHeuristicsUtil}: Pure CV heuristic parsing algorithms.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AssessmentCriteriaPreparer {

    private final JdMetadataExtractor metadataExtractor;
    private final CriteriaClassifier criteriaClassifier;
    private final EligibilityGateService eligibilityGateService;
    private final SuggestedCriteriaRecorder suggestedCriteriaRecorder;
    private final StringRedisTemplate stringRedisTemplate;
    private final ObjectMapper objectMapper;

    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record MetadataResult(JobCategory category, SeniorityLevel level) {}

    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record JdRawMetadata(JobCategory category, List<SeniorityLevel> acceptedLevels) {}

    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record CriteriaFilterDebugDetail(
            Long criteriaId,
            String criteriaName,
            boolean isMatched,
            String reason
    ) {}

    // =========================================================================
    // 1. 2-TIER CONSOLIDATED PIPELINE PREPARATION & REDIS CACHING
    // =========================================================================

    /**
     * Primary decoupled method to retrieve or prepare JD Criteria Context.
     * Tier-1: Cache raw JD LLM extraction (category, accepted levels, gate requirements, raw bundle) by JD.
     * Tier-2: Cache finalized PreparedJdContext by (JD + targetLevel).
     */
    public PreparedJdContext getOrPrepareJdContext(
            String jdId,
            String fullJdMarkdown,
            String preStoredJobCategory,
            String preStoredAcceptedLevelsJson,
            String candidateSeniorityStr,
            String fullCvMarkdown,
            boolean forceRefresh) {

        String jdHash = computeSha256(fullJdMarkdown);

        if (forceRefresh) {
            evictJdCache(jdId, jdHash);
        }

        // 1. Resolve Candidate Seniority Level
        SeniorityLevel candidateLevel = (candidateSeniorityStr != null && !candidateSeniorityStr.isBlank())
                ? parseSeniorityLevel(candidateSeniorityStr)
                : extractCvSeniorityLevel(fullCvMarkdown);
        if (candidateLevel == null) {
            candidateLevel = SeniorityLevel.MID;
        }

        // 2. Get or Compute Tier-1 Base JD Profile (Cached per JD)
        PreparedJdContext.JdBaseProfile baseProfile = getOrComputeBaseProfile(
                jdId, jdHash, fullJdMarkdown, preStoredJobCategory, preStoredAcceptedLevelsJson, forceRefresh
        );

        // 3. Resolve Target Seniority Level for this candidate
        SeniorityLevel targetLevel = resolveTargetSeniorityLevel(baseProfile.acceptedLevels(), candidateLevel);

        // 4. Check Tier-2 Cache: PreparedJdContext for (JD + targetLevel)
        String directContextKey = (jdId != null && !jdId.isBlank())
                ? ("jd_context:v6:" + jdId + ":" + targetLevel.name())
                : null;
        String hashContextKey = "jd_context:v6:hash:" + jdHash + ":" + targetLevel.name();

        if (!forceRefresh) {
            PreparedJdContext cachedContext = checkContextCache(directContextKey, hashContextKey);
            if (cachedContext != null) {
                log.info("[JD-Context-Cache] HIT! Reusing criteria profile for JD {} with Level {} (0ms, 0 LLM calls).", jdId, targetLevel);
                return cachedContext;
            }
        }

        // 5. Build and Cache Tier-2 Context for targetLevel
        PreparedJdContext context = buildContextForTargetLevel(baseProfile, targetLevel, fullJdMarkdown);
        saveContextCache(directContextKey, hashContextKey, context);
        return context;
    }

    private PreparedJdContext.JdBaseProfile getOrComputeBaseProfile(
            String jdId,
            String jdHash,
            String fullJdMarkdown,
            String preStoredJobCategory,
            String preStoredAcceptedLevelsJson,
            boolean forceRefresh) {

        String directBaseKey = (jdId != null && !jdId.isBlank()) ? ("jd_base:v6:" + jdId) : null;
        String hashBaseKey = "jd_base:v6:hash:" + jdHash;

        if (!forceRefresh) {
            PreparedJdContext.JdBaseProfile cachedBase = checkBaseProfileCache(directBaseKey, hashBaseKey);
            if (cachedBase != null) {
                log.info("[JD-Base-Cache] HIT! Reusing base JD analysis for JD {} (0ms, 0 LLM calls).", jdId);
                return cachedBase;
            }
        }

        log.info("[AssessmentCriteriaPreparer] Base JD analysis cache MISS for jdId: {}. Computing Base Profile...", jdId);

        PreparedJdContext.JdBaseProfile baseProfile = computeBaseProfileInternal(
                jdId, fullJdMarkdown, preStoredJobCategory, preStoredAcceptedLevelsJson
        );
        saveBaseProfileCache(directBaseKey, hashBaseKey, baseProfile);
        recordAdHocCriteriaPreAssessment(baseProfile.category(), baseProfile.rawBundle());
        return baseProfile;
    }

    private PreparedJdContext.JdBaseProfile computeBaseProfileInternal(
            String jdId,
            String fullJdMarkdown,
            String preStoredJobCategory,
            String preStoredAcceptedLevelsJson) {

        JobCategory preCategory = (preStoredJobCategory != null && !preStoredJobCategory.isBlank())
                ? parseJobCategory(preStoredJobCategory) : null;
        List<SeniorityLevel> preLevels = parseAcceptedLevels(preStoredAcceptedLevelsJson);

        try {
            List<CriteriaWeightProjection> initialDbCriteria = criteriaClassifier.loadCriteriaWithFallback("SOFTWARE_ENGINEERING", "MID");
            var consolidated = criteriaClassifier.classifyConsolidatedSinglePass(fullJdMarkdown, initialDbCriteria);
            if (consolidated != null) {
                JobCategory category = (preCategory != null) ? preCategory : consolidated.category();
                List<SeniorityLevel> acceptedLevels = (!preLevels.isEmpty()) ? preLevels : consolidated.acceptedLevels();
                if (acceptedLevels == null || acceptedLevels.isEmpty()) {
                    acceptedLevels = List.of(SeniorityLevel.MID);
                }

                log.info("[AssessmentCriteriaPreparer] Single-Pass Base Profile SUCCESS for jdId: {} (Category: {}, AcceptedLevels: {})",
                        jdId, category, acceptedLevels);

                return new PreparedJdContext.JdBaseProfile(
                        category,
                        acceptedLevels,
                        consolidated.gateRequirements(),
                        consolidated.criteriaBundle()
                );
            }
        } catch (Exception e) {
            log.warn("[AssessmentCriteriaPreparer] Single-Pass consolidated analysis failed, falling back: {}", e.getMessage());
        }

        // Multi-pass fallback
        JobCategory fallbackCategory = (preCategory != null) ? preCategory : JobCategory.SOFTWARE_ENGINEERING;
        List<SeniorityLevel> fallbackLevels = (!preLevels.isEmpty()) ? preLevels : List.of(SeniorityLevel.MID);
        SeniorityLevel representativeLevel = fallbackLevels.get(0);

        List<CriteriaWeightProjection> filteredDbCriteria = criteriaClassifier.loadAndFilterCriteria(
                fallbackCategory.name(), representativeLevel.name(), jdId, fullJdMarkdown, false
        );
        ClassifiedCriteriaBundle criteriaBundle = criteriaClassifier.classifyCriteria(
                fullJdMarkdown, filteredDbCriteria, representativeLevel.name()
        );
        List<GateCheckDto> rawGates = eligibilityGateService.extractGateFromJd(fullJdMarkdown);

        return new PreparedJdContext.JdBaseProfile(
                fallbackCategory,
                fallbackLevels,
                rawGates,
                criteriaBundle
        );
    }

    private PreparedJdContext buildContextForTargetLevel(
            PreparedJdContext.JdBaseProfile baseProfile,
            SeniorityLevel targetLevel,
            String fullJdMarkdown) {

        List<CriteriaWeightProjection> actualDbCriteria = criteriaClassifier.loadCriteriaWithFallback(
                baseProfile.category().name(), targetLevel.name()
        );
        ClassifiedCriteriaBundle realignedBundle = criteriaClassifier.realignBundleWithActualCategory(
                baseProfile.rawBundle(), actualDbCriteria, fullJdMarkdown
        );

        List<PreparedJdContext.CriteriaWeightDto> criteriaList = buildCriteriaList(realignedBundle);

        return new PreparedJdContext(
                baseProfile.category(),
                targetLevel,
                baseProfile.acceptedLevels(),
                realignedBundle,
                criteriaList,
                baseProfile.gateRequirements()
        );
    }

    private List<PreparedJdContext.CriteriaWeightDto> buildCriteriaList(ClassifiedCriteriaBundle bundle) {
        if (bundle == null || bundle.activeDbCriteria() == null) return List.of();
        return bundle.activeDbCriteria().stream()
                .map(c -> new PreparedJdContext.CriteriaWeightDto(
                        c.criteriaId(),
                        c.criteriaName(),
                        c.promptInstruction(),
                        c.promptInstruction(),
                        c.weightPercentage() != null ? c.weightPercentage() : 10.0,
                        null
                ))
                .toList();
    }

    private void recordAdHocCriteriaPreAssessment(JobCategory category, ClassifiedCriteriaBundle bundle) {
        if (bundle == null || bundle.jdExtras() == null || bundle.jdExtras().isEmpty()) return;
        try {
            List<AssessmentResponseDto.AdHocEvidenceItem> jdExtrasForRecording = bundle.jdExtras().stream()
                    .map(e -> new AssessmentResponseDto.AdHocEvidenceItem(
                            null, e.name(), e.importance(), e.promptInstruction(), null, null, null, null, null))
                    .collect(Collectors.toList());
            recordAdHocCriteria(category, jdExtrasForRecording);
        } catch (Exception e) {
            log.warn("[AssessmentCriteriaPreparer] Non-blocking warning recording ad-hoc criteria: {}", e.getMessage());
        }
    }

    // =========================================================================
    // 2. CACHE HELPERS
    // =========================================================================

    private PreparedJdContext.JdBaseProfile checkBaseProfileCache(String directKey, String hashKey) {
        if (stringRedisTemplate == null) return null;
        try {
            String json = null;
            if (directKey != null) {
                json = stringRedisTemplate.opsForValue().get(directKey);
            }
            if (json == null && hashKey != null) {
                json = stringRedisTemplate.opsForValue().get(hashKey);
            }
            if (json != null) {
                return objectMapper.readValue(json, PreparedJdContext.JdBaseProfile.class);
            }
        } catch (Exception e) {
            log.warn("[JD-Base-Cache] Failed to read from Redis: {}", e.getMessage());
        }
        return null;
    }

    private void saveBaseProfileCache(String directKey, String hashKey, PreparedJdContext.JdBaseProfile profile) {
        if (stringRedisTemplate == null || profile == null) return;
        try {
            String json = objectMapper.writeValueAsString(profile);
            if (hashKey != null) {
                stringRedisTemplate.opsForValue().set(hashKey, json, Duration.ofDays(30));
            }
            if (directKey != null) {
                stringRedisTemplate.opsForValue().set(directKey, json, Duration.ofDays(30));
            }
        } catch (Exception e) {
            log.warn("[JD-Base-Cache] Failed to save to Redis: {}", e.getMessage());
        }
    }

    private PreparedJdContext checkContextCache(String directKey, String hashKey) {
        if (stringRedisTemplate == null) return null;
        try {
            String json = null;
            if (directKey != null) {
                json = stringRedisTemplate.opsForValue().get(directKey);
            }
            if (json == null && hashKey != null) {
                json = stringRedisTemplate.opsForValue().get(hashKey);
            }
            if (json != null) {
                return objectMapper.readValue(json, PreparedJdContext.class);
            }
        } catch (Exception e) {
            log.warn("[JD-Context-Cache] Failed to read from Redis: {}", e.getMessage());
        }
        return null;
    }

    private void saveContextCache(String directKey, String hashKey, PreparedJdContext context) {
        if (stringRedisTemplate == null || context == null) return;
        try {
            String json = objectMapper.writeValueAsString(context);
            if (hashKey != null) {
                stringRedisTemplate.opsForValue().set(hashKey, json, Duration.ofDays(30));
            }
            if (directKey != null) {
                stringRedisTemplate.opsForValue().set(directKey, json, Duration.ofDays(30));
            }
        } catch (Exception e) {
            log.warn("[JD-Context-Cache] Failed to save to Redis: {}", e.getMessage());
        }
    }

    public void evictJdCache(String jdId, String jdHash) {
        if (stringRedisTemplate == null) return;
        try {
            List<String> keysToDelete = new ArrayList<>();
            if (jdId != null && !jdId.isBlank()) {
                keysToDelete.add("jd_base:v6:" + jdId);
                for (SeniorityLevel lvl : SeniorityLevel.values()) {
                    keysToDelete.add("jd_context:v6:" + jdId + ":" + lvl.name());
                }
            }
            if (jdHash != null && !jdHash.isBlank()) {
                keysToDelete.add("jd_base:v6:hash:" + jdHash);
                for (SeniorityLevel lvl : SeniorityLevel.values()) {
                    keysToDelete.add("jd_context:v6:hash:" + jdHash + ":" + lvl.name());
                }
            }
            stringRedisTemplate.delete(keysToDelete);
            log.info("[JD-Cache] Evicted {} Redis cache keys for jdId={} jdHash={}", keysToDelete.size(), jdId, jdHash);
        } catch (Exception e) {
            log.warn("[JD-Cache] Failed to evict Redis cache: {}", e.getMessage());
        }
    }

    public String computeSha256(String text) {
        if (text == null) return "null";
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.substring(0, 16);
        } catch (Exception e) {
            return String.valueOf(text.hashCode());
        }
    }

    public MetadataResult resolvePreStoredMetadata(JobDescription jd, Resume resume) {
        if (jd == null && resume == null) return null;

        String rawRole = null;
        if (jd != null && jd.getJobCategory() != null && !jd.getJobCategory().isBlank()) {
            rawRole = jd.getJobCategory();
        } else if (resume != null && resume.getJobCategory() != null && !resume.getJobCategory().isBlank()) {
            rawRole = resume.getJobCategory();
        }

        JobCategory category = rawRole != null ? parseJobCategory(rawRole) : null;
        List<SeniorityLevel> jdLevels = parseAcceptedLevels(jd != null ? jd.getAcceptedLevels() : null);
        SeniorityLevel cvLevel = (resume != null && resume.getSeniorityLevel() != null)
                ? parseSeniorityLevel(resume.getSeniorityLevel()) : null;

        if (category != null && !jdLevels.isEmpty() && cvLevel != null) {
            SeniorityLevel targetLevel = resolveTargetSeniorityLevel(jdLevels, cvLevel);
            return new MetadataResult(category, targetLevel);
        }
        return null;
    }

    public List<SeniorityLevel> parseAcceptedLevels(String acceptedLevelsJson) {
        if (acceptedLevelsJson == null || acceptedLevelsJson.isBlank()) return List.of();
        try {
            List<String> list = objectMapper.readValue(acceptedLevelsJson, new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {});
            return list.stream().map(this::parseSeniorityLevel).distinct().sorted().toList();
        } catch (Exception e) {
            String[] parts = acceptedLevelsJson.replaceAll("[\\[\\]\"]", "").split(",");
            List<SeniorityLevel> res = new ArrayList<>();
            for (String p : parts) {
                if (!p.isBlank()) res.add(parseSeniorityLevel(p.trim()));
            }
            return res.stream().distinct().sorted().toList();
        }
    }

    // =========================================================================
    // 3. METADATA DELEGATIONS
    // =========================================================================

    public MetadataResult extractMetadata(String jdMarkdown, String cvMarkdown) {
        if (metadataExtractor == null) {
            return new MetadataResult(JobCategory.SOFTWARE_ENGINEERING, SeniorityLevel.MID);
        }
        var res = metadataExtractor.extractMetadata(jdMarkdown, cvMarkdown);
        return new MetadataResult(res.category(), res.level());
    }

    public JdRawMetadata extractJdRawMetadata(String jdMarkdown) {
        if (metadataExtractor == null) {
            return new JdRawMetadata(JobCategory.SOFTWARE_ENGINEERING, List.of(SeniorityLevel.MID));
        }
        var res = metadataExtractor.extractJdRawMetadata(jdMarkdown);
        return new JdRawMetadata(res.category(), res.acceptedLevels());
    }

    public SeniorityLevel extractCvSeniorityLevel(String cvMarkdown) {
        if (metadataExtractor == null) return SeniorityLevel.MID;
        return metadataExtractor.extractCvSeniorityLevel(cvMarkdown);
    }

    public SeniorityLevel resolveTargetSeniorityLevel(List<SeniorityLevel> jdLevels, SeniorityLevel cvLevel) {
        if (metadataExtractor == null) return SeniorityLevel.MID;
        return metadataExtractor.resolveTargetSeniorityLevel(jdLevels, cvLevel);
    }

    public JobCategory parseJobCategory(String value) {
        if (metadataExtractor == null) return JobCategory.SOFTWARE_ENGINEERING;
        return metadataExtractor.parseJobCategory(value);
    }

    public SeniorityLevel parseSeniorityLevel(String value) {
        if (metadataExtractor == null) return SeniorityLevel.MID;
        return metadataExtractor.parseSeniorityLevel(value);
    }

    // =========================================================================
    // 4. CRITERIA CLASSIFIER DELEGATIONS
    // =========================================================================

    public List<CriteriaWeightProjection> loadAndFilterCriteria(
            String categoryName, String seniorityLevelName, String sessionId, String jdText, boolean isJdTextExtracted) {
        if (criteriaClassifier == null) return List.of();
        return criteriaClassifier.loadAndFilterCriteria(categoryName, seniorityLevelName, sessionId, jdText, isJdTextExtracted);
    }

    public List<CriteriaWeightProjection> loadCriteriaWithFallback(String categoryName, String seniorityLevelName) {
        if (criteriaClassifier == null) return List.of();
        return criteriaClassifier.loadCriteriaWithFallback(categoryName, seniorityLevelName);
    }

    public List<CriteriaFilterDebugDetail> debugFilterCriteriaDetails(
            String categoryName, String seniorityLevelName, String jdText, double threshold) {
        if (criteriaClassifier == null) return List.of();
        var details = criteriaClassifier.debugFilterCriteriaDetails(categoryName, seniorityLevelName, jdText, threshold);
        List<CriteriaFilterDebugDetail> mapped = new ArrayList<>();
        for (var d : details) {
            mapped.add(new CriteriaFilterDebugDetail(d.criteriaId(), d.criteriaName(), d.isMatched(), d.reason()));
        }
        return mapped;
    }

    public ClassifiedCriteriaBundle classifyCriteria(
            String jdMarkdown, List<CriteriaWeightProjection> dbCriteria, String seniorityLevel) {
        if (criteriaClassifier == null) return new ClassifiedCriteriaBundle(List.of(), List.of());
        return criteriaClassifier.classifyCriteria(jdMarkdown, dbCriteria, seniorityLevel);
    }

    // =========================================================================
    // 5. ELIGIBILITY GATE DELEGATIONS
    // =========================================================================

    public EligibilityEvaluationResult evaluateEligibility(String jdContent, String cvContent) {
        if (eligibilityGateService == null) {
            return new EligibilityEvaluationResult(fit.iuh.modules.assessment.entity.EligibilityStatus.PARTIAL, List.of());
        }
        return eligibilityGateService.evaluateEligibility(jdContent, cvContent);
    }

    public EligibilityEvaluationResult evaluateEligibilityWithRawGates(
            List<GateCheckDto> preExtractedGates, String jdContent, String cvContent) {
        if (eligibilityGateService == null) {
            return new EligibilityEvaluationResult(fit.iuh.modules.assessment.entity.EligibilityStatus.PARTIAL, List.of());
        }
        return eligibilityGateService.evaluateEligibilityWithRawGates(preExtractedGates, jdContent, cvContent);
    }

    // =========================================================================
    // 6. CV HEURISTICS DELEGATIONS
    // =========================================================================

    public double calculateCandidateYoe(String cvContent) {
        return ResumeHeuristicsUtil.calculateCandidateYoe(cvContent);
    }

    public List<DateRange> extractDateRanges(String text) {
        return ResumeHeuristicsUtil.extractDateRanges(text);
    }

    public boolean checkDegreeInCv(String cvContent) {
        return ResumeHeuristicsUtil.checkDegreeInCv(cvContent);
    }

    // =========================================================================
    // 7. AD-HOC CRITERIA DELEGATIONS
    // =========================================================================

    public void recordAdHocCriteria(JobCategory jobCategory, List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems) {
        if (suggestedCriteriaRecorder != null) {
            suggestedCriteriaRecorder.recordAdHocCriteria(jobCategory, adHocItems);
        }
    }
}