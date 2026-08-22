package fit.iuh.modules.questionbank.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.QuestionBankException;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.repository.ResumeAssessmentRepository;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.questionbank.dto.*;
import fit.iuh.modules.questionbank.entity.QuestionBank;
import fit.iuh.modules.questionbank.repository.QuestionBankRepository;
import fit.iuh.modules.questionbank.service.*;
import fit.iuh.modules.rulengine.entity.EvaluationCriteria;
import fit.iuh.modules.rulengine.repository.EvaluationCriteriaRepository;
import fit.iuh.modules.chunking.repository.DocumentChunkRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class QuestionBankServiceImpl implements QuestionBankService {

    private static final int MAX_EVIDENCE_ITEMS = 15;

    private final QuestionGenerationService questionGenerationService;
    private final DifficultyDistributor difficultyDistributor;
    private final ResumeAssessmentRepository assessmentRepo;
    private final SessionRepository sessionRepository;
    private final DocumentChunkRepository documentChunkRepository;
    private final QuestionBankRepository questionBankRepo;
    private final ObjectMapper objectMapper;
    private final SemanticCacheKeyGenerator cacheKeyGenerator;
    private final SemanticCacheService cacheService;
    private final EvaluationCriteriaRepository evaluationCriteriaRepository;
    private final fit.iuh.config.AppProperties appProperties;

    @Override
    @Transactional
    public QuestionBankResponseDto generate(GenerateQuestionBankRequest request) {
        String sessionId = request.getSessionId();
        QuestionConfigDto config = request.getQuestionConfig() != null
                ? request.getQuestionConfig()
                : QuestionConfigDto.builder().total(10).build();

        int rawTotal = config.getTotalQuestions();
        if (rawTotal <= 0) {
            config.setTotal(10);
        } else if (rawTotal > 30) {
            log.warn("[QuestionBank] Requested total questions {} exceeds maximum limit 30, clamping to 30", rawTotal);
            config.setTotal(30);
        }

        log.info("[QuestionBank] Starting generation for session={}, total questions={}", sessionId, config.getTotalQuestions());

        ResumeAssessment assessment = assessmentRepo.findBySessionId(sessionId)
                .orElseThrow(() -> new QuestionBankException(
                        "Resume assessment not found for session: " + sessionId + ". Please generate an assessment first."));

        List<EvidenceItemPair> allEvidencePairs = buildEvidencePairs(assessment);

        log.info("[QuestionBank] Loaded {} evidence pairs from assessment for session {}.",
                allEvidencePairs.size(), sessionId);

        List<String> strongAreas = allEvidencePairs.stream()
                .filter(p -> "matched".equalsIgnoreCase(p.status()))
                .map(EvidenceItemPair::criteriaName)
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());

        List<String> gapAreas = allEvidencePairs.stream()
                .filter(p -> "missing".equalsIgnoreCase(p.status()) || "weak".equalsIgnoreCase(p.status()) || "partial".equalsIgnoreCase(p.status()))
                .map(EvidenceItemPair::criteriaName)
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());

        List<String> rawTechPossessed = new ArrayList<>();
        List<String> rawTechRequired = new ArrayList<>();
        if (assessment.getEvidenceItems() != null) {
            for (var e : assessment.getEvidenceItems()) {
                if (e.getCriteriaName() != null) {
                    if ("matched".equalsIgnoreCase(e.getStatus()) || "weak".equalsIgnoreCase(e.getStatus()) || "partial".equalsIgnoreCase(e.getStatus())) {
                        rawTechPossessed.add(e.getCriteriaName());
                    }
                    rawTechRequired.add(e.getCriteriaName());
                }
                if (e.getCvEvidence() != null && !e.getCvEvidence().isBlank()) {
                    rawTechPossessed.add(e.getCvEvidence());
                }
                if (e.getJdRequirement() != null && !e.getJdRequirement().isBlank()) {
                    rawTechRequired.add(e.getJdRequirement());
                }
            }
        }
        List<String> techStackPossessed = extractTechKeywords(rawTechPossessed);
        List<String> techStackRequired = extractTechKeywords(rawTechRequired);

        Session session = (sessionRepository != null) ? sessionRepository.findById(sessionId).orElse(null) : null;

        String cvContent = (session != null && session.getResume() != null) ? session.getResume().getParsedContent() : null;
        String jdContent = (session != null && session.getJobDescription() != null) ? session.getJobDescription().getParsedContent() : null;

        // Fallback to DocumentChunks if parsedContent on Resume/JD entity is null
        if ((cvContent == null || cvContent.isBlank()) && documentChunkRepository != null) {
            var chunks = documentChunkRepository.findBySessionIdAndDocType(sessionId, "cv");
            if (chunks != null && !chunks.isEmpty()) {
                cvContent = chunks.stream().map(c -> c.getContent()).collect(Collectors.joining("\n"));
            }
        }
        if ((jdContent == null || jdContent.isBlank()) && documentChunkRepository != null) {
            var chunks = documentChunkRepository.findBySessionIdAndDocType(sessionId, "jd");
            if (chunks != null && !chunks.isEmpty()) {
                jdContent = chunks.stream().map(c -> c.getContent()).collect(Collectors.joining("\n"));
            }
        }

        String targetDomain = detectTargetDomain(cvContent, jdContent);

        Integer calculatedYoe = null;
        if (cvContent != null && !cvContent.isBlank()) {
            double yoeDouble = fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.calculateCandidateYoe(cvContent);
            if (yoeDouble > 0) {
                calculatedYoe = (int) Math.round(yoeDouble);
            }
        }

        List<String> projectHighlights = extractProjectHighlights(cvContent);

        CandidateContextDto context = CandidateContextDto.builder()
                .candidateLevel(assessment.getSeniorityLevel())
                .overallMatch(assessment.getOverallMatchScore() != null
                        ? (assessment.getOverallMatchScore() >= 80 ? "high"
                           : assessment.getOverallMatchScore() >= 50 ? "medium" : "low")
                        : "medium")
                .yearsOfExperience(calculatedYoe)
                .strongAreas(strongAreas)
                .gapAreas(gapAreas)
                .techStackRequired(techStackRequired)
                .techStackPossessed(techStackPossessed)
                .targetDomain(targetDomain)
                .roleType(assessment.getJobCategory())
                .cvProjectHighlights(projectHighlights)
                .build();

        List<QuestionAssignment> assignments = difficultyDistributor.distribute(
                config,
                context.getCandidateLevel(),
                assessment.getOverallMatchScore(),
                allEvidencePairs
        );

        Map<String, List<QuestionAssignment>> assignmentsByCategory = assignments.stream()
                .collect(Collectors.groupingBy(QuestionAssignment::category, LinkedHashMap::new, Collectors.toList()));

        Set<String> chosenQuestionTexts = Collections.synchronizedSet(new HashSet<>());
        Map<String, List<QuestionDto>> cachedQuestionsByCategory = new LinkedHashMap<>();
        Map<String, List<QuestionAssignment>> missedAssignmentsByCategory = new LinkedHashMap<>();

        boolean isDeepDive = "DEEP_DIVE".equalsIgnoreCase(config.getMode());

        // First pass: Check Redis Semantic Cache for each category (bypassed if DEEP_DIVE mode)
        for (var entry : assignmentsByCategory.entrySet()) {
            String type = entry.getKey();
            List<QuestionAssignment> typeAssignments = entry.getValue();

            List<QuestionDto> typeCached = new ArrayList<>();
            List<QuestionAssignment> missed = new ArrayList<>();

            for (QuestionAssignment qa : typeAssignments) {
                boolean hit = false;
                if (!isDeepDive) {
                    String cacheKey = resolveCacheKey(qa.item(), assessment.getSeniorityLevel(), type);
                    if (qa.isFollowUp()) {
                        cacheKey += "|followup:true";
                    }

                    if (cacheKey != null) {
                        List<QuestionDto> cachedList = cacheService.get(cacheKey);
                        if (cachedList != null && !cachedList.isEmpty()) {
                            List<QuestionDto> matchingPool = cachedList.stream()
                                    .filter(q -> type.equalsIgnoreCase(q.getType())
                                            && qa.difficulty().equalsIgnoreCase(q.getDifficulty())
                                            && q.getQuestion() != null
                                            && !chosenQuestionTexts.contains(q.getQuestion().strip()))
                                    .collect(Collectors.toList());

                            if (!matchingPool.isEmpty()) {
                                // Random sampling from question pool to prevent duplicate questions across candidates
                                int randomIndex = java.util.concurrent.ThreadLocalRandom.current().nextInt(matchingPool.size());
                                QuestionDto cachedQuestion = matchingPool.get(randomIndex);
                                chosenQuestionTexts.add(cachedQuestion.getQuestion().strip());
                                typeCached.add(cachedQuestion);
                                hit = true;
                                log.info("[QuestionBank] Cache HIT (pool size {}): picked random {} '{}' question for criteria '{}'",
                                        matchingPool.size(), qa.difficulty(), type, qa.item() != null ? qa.item().criteriaName() : "generic");
                            }
                        }
                    }
                }

                if (!hit) {
                    missed.add(qa);
                }
            }

            cachedQuestionsByCategory.put(type, typeCached);
            missedAssignmentsByCategory.put(type, missed);
        }

        // Second pass: Generate missing questions in parallel via CompletableFuture
        Map<String, java.util.concurrent.CompletableFuture<List<QuestionDto>>> futuresByCategory = new LinkedHashMap<>();
        for (var entry : missedAssignmentsByCategory.entrySet()) {
            String type = entry.getKey();
            List<QuestionAssignment> missed = entry.getValue();
            if (!missed.isEmpty()) {
                log.info("[QuestionBank] Scheduling async generation of {} missing '{}' questions (mode: {}) via LLM...",
                        missed.size(), type, config.getMode());
                futuresByCategory.put(type, java.util.concurrent.CompletableFuture.supplyAsync(() -> {
                    List<QuestionDto> generated = questionGenerationService.generateForCategory(
                            type, context, missed, config);

                    // Write newly generated questions to cache only if in SCREENING mode (keep generic questions cached)
                    if (!isDeepDive) {
                        Map<String, List<QuestionDto>> generatedByItem = generated.stream()
                                .filter(q -> (q.getId() != null && q.getId().startsWith("item_")) ||
                                             (q.getExpectedCompetency() != null && q.getExpectedCompetency().startsWith("item_")))
                                .collect(Collectors.groupingBy(q -> (q.getId() != null && q.getId().startsWith("item_"))
                                        ? q.getId() : q.getExpectedCompetency()));

                        if (!generatedByItem.isEmpty()) {
                            generatedByItem.forEach((itemId, itemQuestions) -> {
                                int assignmentIdx = parseItemIndex(itemId);
                                if (assignmentIdx >= 0 && assignmentIdx < missed.size()) {
                                    QuestionAssignment qa = missed.get(assignmentIdx);
                                    String cacheKey = resolveCacheKey(qa.item(), assessment.getSeniorityLevel(), type);
                                    if (qa.isFollowUp()) {
                                        cacheKey += "|followup:true";
                                    }

                                    List<QuestionDto> existing = cacheService.get(cacheKey);
                                    List<QuestionDto> merged = (existing != null) ? new ArrayList<>(existing) : new ArrayList<>();

                                    for (QuestionDto nq : itemQuestions) {
                                        nq.setType(type);
                                        boolean duplicate = merged.stream().anyMatch(eq ->
                                                Objects.equals(eq.getType(), nq.getType()) &&
                                                Objects.equals(eq.getQuestion(), nq.getQuestion())
                                        );
                                        if (!duplicate) merged.add(nq);
                                    }
                                    // Keep up to 5 questions in pool per key
                                    if (merged.size() > 5) {
                                        merged = merged.subList(merged.size() - 5, merged.size());
                                    }
                                    cacheService.put(cacheKey, merged, Duration.ofDays(7));
                                }
                            });
                        } else if (generated.size() == missed.size()) {
                            for (int i = 0; i < generated.size(); i++) {
                                QuestionDto nq = generated.get(i);
                                QuestionAssignment qa = missed.get(i);
                                String cacheKey = resolveCacheKey(qa.item(), assessment.getSeniorityLevel(), type);
                                if (qa.isFollowUp()) {
                                    cacheKey += "|followup:true";
                                }
                                List<QuestionDto> existing = cacheService.get(cacheKey);
                                List<QuestionDto> merged = (existing != null) ? new ArrayList<>(existing) : new ArrayList<>();

                                nq.setType(type);
                                boolean duplicate = merged.stream().anyMatch(eq ->
                                        Objects.equals(eq.getType(), nq.getType()) &&
                                        Objects.equals(eq.getQuestion(), nq.getQuestion())
                                );
                                if (!duplicate) {
                                    merged.add(nq);
                                }
                                if (merged.size() > 5) {
                                    merged = merged.subList(merged.size() - 5, merged.size());
                                }
                                cacheService.put(cacheKey, merged, Duration.ofDays(7));
                            }
                        }
                    }

                    return generated;
                }));
            }
        }

        // Wait for all async generation tasks
        if (!futuresByCategory.isEmpty()) {
            try {
                java.util.concurrent.CompletableFuture.allOf(futuresByCategory.values().toArray(new java.util.concurrent.CompletableFuture[0])).join();
            } catch (Exception e) {
                log.warn("[QuestionBank] One or more category generation tasks encountered an error: {}", e.getMessage());
            }
        }

        // Assemble all questions in order of categories with graceful degradation
        List<QuestionDto> allQuestions = new ArrayList<>();
        for (var entry : assignmentsByCategory.entrySet()) {
            String type = entry.getKey();
            List<QuestionDto> cachedPart = cachedQuestionsByCategory.getOrDefault(type, Collections.emptyList());
            allQuestions.addAll(cachedPart);

            if (futuresByCategory.containsKey(type)) {
                try {
                    List<QuestionDto> generatedPart = futuresByCategory.get(type).join();
                    if (generatedPart != null) {
                        for (QuestionDto gq : generatedPart) {
                            if (gq.getQuestion() != null) {
                                chosenQuestionTexts.add(gq.getQuestion().strip());
                            }
                            allQuestions.add(gq);
                        }
                    }
                } catch (Exception e) {
                    log.error("[QuestionBank] Category '{}' generation failed, proceeding with remaining categories: {}", type, e.getMessage(), e);
                }
            }
        }

        if (allQuestions.isEmpty()) {
            throw new QuestionBankException("Failed to generate any questions for session " + sessionId + ". Please try again.");
        }

        for (int i = 0; i < allQuestions.size(); i++) {
            allQuestions.get(i).setId(String.format("Q%03d", i + 1));
        }

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

        // Delete any previous question bank for this session to keep clean state
        try {
            List<QuestionBank> existingBanks = questionBankRepo.findBySessionIdOrderByCreatedAtDesc(sessionId);
            if (existingBanks != null && !existingBanks.isEmpty()) {
                questionBankRepo.deleteAll(existingBanks);
                questionBankRepo.flush();
            }
        } catch (Exception e) {
            log.warn("[QuestionBank] Failed to clear previous question bank for session {}: {}", sessionId, e.getMessage());
        }

        QuestionBank entity = QuestionBank.builder()
                .sessionId(sessionId)
                .questionConfig(config)
                .candidateContext(context)
                .totalQuestions(total)
                .build();

        List<fit.iuh.modules.questionbank.entity.SessionMetadata> metaEntities = new ArrayList<>();
        try {
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("candidateLevel").metadataValue(metadata.getCandidateLevel()).build());
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("overallMatch").metadataValue(metadata.getOverallMatch()).build());
            if (metadata.getYearsOfExperience() != null) {
                metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("yearsOfExperience").metadataValue(String.valueOf(metadata.getYearsOfExperience())).build());
            }
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("roleType").metadataValue(metadata.getRoleType()).build());
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("targetDomain").metadataValue(metadata.getTargetDomain()).build());
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("strongAreas").metadataValue(objectMapper.writeValueAsString(metadata.getStrongAreas())).build());
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("gapAreas").metadataValue(objectMapper.writeValueAsString(metadata.getGapAreas())).build());
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("difficultyDistribution").metadataValue(objectMapper.writeValueAsString(metadata.getDifficultyDistribution())).build());
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("totalQuestions").metadataValue(String.valueOf(metadata.getTotalQuestions())).build());
            metaEntities.add(fit.iuh.modules.questionbank.entity.SessionMetadata.builder().questionBank(entity).metadataKey("generationRationale").metadataValue(metadata.getGenerationRationale()).build());
        } catch (Exception e) {
            log.warn("[QuestionBank] Failed to serialize metadata: {}", e.getMessage());
        }
        entity.setMetadataItems(metaEntities);

        List<fit.iuh.modules.questionbank.entity.Question> questionEntities = new ArrayList<>();
        for (QuestionDto dto : allQuestions) {
            String uniqueQId = (dto.getId() != null && dto.getId().contains("_")) 
                    ? dto.getId() 
                    : (sessionId + "_" + (dto.getId() != null ? dto.getId() : UUID.randomUUID().toString()));
            
            String detailsJson = null;
            try {
                Map<String, Object> detailsMap = new LinkedHashMap<>();
                if (dto.getHints() != null && !dto.getHints().isEmpty()) {
                    detailsMap.put("hints", dto.getHints());
                }
                if (dto.getStarPrompt() != null && !dto.getStarPrompt().isBlank()) {
                    detailsMap.put("star_prompt", dto.getStarPrompt());
                }
                if (dto.getComponentsToCover() != null && !dto.getComponentsToCover().isEmpty()) {
                    detailsMap.put("components_to_cover", dto.getComponentsToCover());
                }
                if (dto.getFollowUpQuestions() != null && !dto.getFollowUpQuestions().isEmpty()) {
                    detailsMap.put("follow_up_questions", dto.getFollowUpQuestions());
                }
                if (dto.getRationale() != null && !dto.getRationale().isBlank()) {
                    detailsMap.put("rationale", dto.getRationale());
                }
                if (!detailsMap.isEmpty()) {
                    detailsJson = objectMapper.writeValueAsString(detailsMap);
                }
            } catch (Exception e) {
                log.warn("[QuestionBank] Failed to serialize details for question {}: {}", dto.getId(), e.getMessage());
            }

            questionEntities.add(fit.iuh.modules.questionbank.entity.Question.builder()
                    .questionBank(entity)
                    .id(uniqueQId)
                    .category(dto.getType())
                    .questionType(dto.getType())
                    .topic(dto.getTopic())
                    .expectedCompetency(dto.getExpectedCompetency())
                    .questionText(dto.getQuestion())
                    .expectedAnswer(dto.getEvaluationCriteria())
                    .difficulty(dto.getDifficulty())
                    .details(detailsJson)
                    .build());
        }
        entity.setQuestions(questionEntities);

        entity = questionBankRepo.save(entity);
        log.info("[QuestionBank] Saved generated QuestionBank id={} for session={}", entity.getId(), sessionId);

        return toResponseDto(entity);
    }

    @Override
    @Transactional(readOnly = true)
    public List<QuestionBankResponseDto> getBySessionId(String sessionId) {
        log.info("[QuestionBank] Retrieving question banks for session: {}", sessionId);
        List<QuestionBank> list = questionBankRepo.findBySessionIdOrderByCreatedAtDesc(sessionId);
        List<QuestionBankResponseDto> responses = new ArrayList<>();
        for (QuestionBank qb : list) {
            responses.add(toResponseDto(qb));
        }
        return responses;
    }

    @Override
    @Transactional(readOnly = true)
    public QuestionBankResponseDto getQuestionBankBySessionId(String sessionId) {
        log.info("[QuestionBank] Retrieving latest question bank for sessionId: {}", sessionId);
        return questionBankRepo.findBySessionIdOrderByCreatedAtDesc(sessionId)
                .stream()
                .findFirst()
                .map(this::toResponseDto)
                .orElseThrow(() -> new ResourceNotFoundException(
                        "QuestionBank", "sessionId", sessionId));
    }

    @Override
    @Transactional(readOnly = true)
    public QuestionBankResponseDto getById(UUID id) {
        log.info("[QuestionBank] Retrieving question bank by ID: {}", id);
        QuestionBank qb = questionBankRepo.findById(id)
                .orElseThrow(() -> new QuestionBankException("Question bank not found with ID: " + id));
        return toResponseDto(qb);
    }

    @Override
    @Transactional
    public QuestionBankResponseDto regenerateQuestion(UUID questionBankId, String questionId) {
        log.info("[QuestionBank] Regenerating question {} inside bank {}", questionId, questionBankId);

        QuestionBank bank = questionBankRepo.findById(questionBankId)
                .orElseThrow(() -> new QuestionBankException("Question bank not found: " + questionBankId));

        List<fit.iuh.modules.questionbank.entity.Question> questions = bank.getQuestions();
        fit.iuh.modules.questionbank.entity.Question targetEntity = null;
        if (questions != null) {
            for (var q : questions) {
                if (questionId.equalsIgnoreCase(q.getId()) || (q.getId() != null && q.getId().endsWith("_" + questionId))) {
                    targetEntity = q;
                    break;
                }
            }
        }
        if (targetEntity == null) {
            throw new QuestionBankException("Question with ID " + questionId + " not found in bank " + questionBankId);
        }

        final String sessionId = bank.getSessionId();
        ResumeAssessment assessment = assessmentRepo.findBySessionId(sessionId)
                .orElseThrow(() -> new QuestionBankException(
                        "Assessment not found for session " + sessionId + ". Cannot regenerate."));

        List<EvidenceItemPair> allEvidencePairs = buildEvidencePairs(assessment);
        
        QuestionBankResponseDto dto = toResponseDto(bank);
        List<QuestionDto> dtoList = dto.getQuestionBank();

        QuestionDto regenerated = questionGenerationService.regenerateSingle(
                targetEntity.getQuestionType(),
                targetEntity.getDifficulty(),
                bank.getCandidateContext(),
                allEvidencePairs,
                dtoList
        );

        targetEntity.setQuestionText(regenerated.getQuestion());
        targetEntity.setExpectedAnswer(regenerated.getEvaluationCriteria());
        targetEntity.setExpectedCompetency(regenerated.getExpectedCompetency());
        if (regenerated.getTopic() != null && !regenerated.getTopic().isBlank()) {
            targetEntity.setTopic(regenerated.getTopic());
        }

        try {
            Map<String, Object> detailsMap = new LinkedHashMap<>();
            if (regenerated.getHints() != null && !regenerated.getHints().isEmpty()) {
                detailsMap.put("hints", regenerated.getHints());
            }
            if (regenerated.getStarPrompt() != null && !regenerated.getStarPrompt().isBlank()) {
                detailsMap.put("star_prompt", regenerated.getStarPrompt());
            }
            if (regenerated.getComponentsToCover() != null && !regenerated.getComponentsToCover().isEmpty()) {
                detailsMap.put("components_to_cover", regenerated.getComponentsToCover());
            }
            if (regenerated.getFollowUpQuestions() != null && !regenerated.getFollowUpQuestions().isEmpty()) {
                detailsMap.put("follow_up_questions", regenerated.getFollowUpQuestions());
            }
            if (regenerated.getRationale() != null && !regenerated.getRationale().isBlank()) {
                detailsMap.put("rationale", regenerated.getRationale());
            }
            if (!detailsMap.isEmpty()) {
                targetEntity.setDetails(objectMapper.writeValueAsString(detailsMap));
            }
        } catch (Exception e) {
            log.warn("[QuestionBank] Failed to update details for regenerated question: {}", e.getMessage());
        }

        bank = questionBankRepo.save(bank);

        log.info("[QuestionBank] Question {} successfully regenerated in bank {}", questionId, questionBankId);
        return toResponseDto(bank);
    }

    private List<EvidenceItemPair> buildEvidencePairs(ResumeAssessment assessment) {
        List<EvidenceItemPair> pairs = new ArrayList<>();

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

        int maxEvidenceItems = (appProperties != null && appProperties.getQuestionBank() != null && appProperties.getQuestionBank().getMaxEvidenceItems() > 0)
                ? appProperties.getQuestionBank().getMaxEvidenceItems() : 15;

        if (assessment.getEvidenceItems() != null) {
            List<fit.iuh.modules.assessment.entity.EvidenceItem> mustHave = assessment.getEvidenceItems().stream()
                    .filter(e -> !"PREFERRED".equalsIgnoreCase(e.getImportance()))
                    .collect(Collectors.toList());
                    
            mustHave.stream()
                    .filter(item -> !"not_applicable".equalsIgnoreCase(item.getStatus()))
                    .limit(maxEvidenceItems)
                    .forEach(item -> pairs.add(new EvidenceItemPair(
                            item.getCriteriaId() != null ? item.getCriteriaId().longValue() : null,
                            item.getCriteriaName(),
                            item.getJdRequirement(),
                            item.getCvEvidence(),
                            item.getStatus(),
                            item.getReasoning(),
                            10.0, // Default weight since it's not stored
                            criteriaIdToTypeMap.getOrDefault(item.getCriteriaId() != null ? item.getCriteriaId().longValue() : null, "technical")
                    )));
        }

        if (assessment.getEvidenceItems() != null && pairs.size() < maxEvidenceItems) {
            int remaining = maxEvidenceItems - pairs.size();
            List<fit.iuh.modules.assessment.entity.EvidenceItem> preferToHave = assessment.getEvidenceItems().stream()
                    .filter(e -> "PREFERRED".equalsIgnoreCase(e.getImportance()))
                    .collect(Collectors.toList());
                    
            preferToHave.stream()
                    .filter(item -> !"not_applicable".equalsIgnoreCase(item.getStatus()))
                    .limit(remaining)
                    .forEach(item -> pairs.add(new EvidenceItemPair(
                            null,
                            item.getCriteriaName(),
                            item.getJdRequirement(),
                            item.getCvEvidence(),
                            item.getStatus(),
                            item.getReasoning(),
                            null,
                            "technical"
                    )));
        }

        return pairs;
    }

    private String resolveCacheKey(EvidenceItemPair pair, SeniorityLevel level, String category) {
        if (pair != null) {
            if (pair.criteriaId() != null) {
                return cacheKeyGenerator.generateKey(pair.criteriaId(), pair.status(), level);
            } else {
                return cacheKeyGenerator.generateKeyForAdHoc(pair.criteriaName(), pair.status(), level);
            }
        } else {
            return cacheKeyGenerator.generateKeyForGeneric(category, level);
        }
    }

    private int parseItemIndex(String itemId) {
        if (itemId == null || !itemId.startsWith("item_")) return -1;
        try {
            return Integer.parseInt(itemId.substring("item_".length()));
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    public static String detectTargetDomain(String cvMarkdown, String jdMarkdown) {
        return fit.iuh.modules.questionbank.util.DomainTaxonomyDictionary.detectDomain(cvMarkdown, jdMarkdown);
    }

    public static List<String> extractProjectHighlights(String cvContent) {
        if (cvContent == null || cvContent.isBlank()) {
            return Collections.emptyList();
        }
        List<String> highlights = new ArrayList<>();
        String[] lines = cvContent.split("\\r?\\n");
        boolean inProjectSection = false;

        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.isBlank()) continue;

            String lower = trimmed.toLowerCase();
            if (lower.contains("project") || lower.contains("dự án") || lower.contains("kinh nghiệm") || lower.contains("experience")) {
                inProjectSection = true;
            }

            if (inProjectSection && (trimmed.startsWith("-") || trimmed.startsWith("*") || trimmed.startsWith("•") || trimmed.startsWith("#"))) {
                String cleanLine = trimmed.replaceAll("^[\\-*#•\\s]+", "").trim();
                if (cleanLine.length() >= 20 && cleanLine.length() <= 300) {
                    highlights.add(cleanLine);
                    if (highlights.size() >= 8) break;
                }
            }
        }

        if (highlights.isEmpty()) {
            for (String line : lines) {
                String trimmed = line.trim();
                if (trimmed.length() >= 25 && (trimmed.startsWith("-") || trimmed.startsWith("*") || trimmed.startsWith("•"))) {
                    highlights.add(trimmed.replaceAll("^[\\-*#•\\s]+", "").trim());
                    if (highlights.size() >= 5) break;
                }
            }
        }
        return highlights;
    }

    private QuestionBankResponseDto toResponseDto(QuestionBank entity) {
        QuestionBankMetadataDto metadataDto = null;
        if (entity.getMetadataItems() != null && !entity.getMetadataItems().isEmpty()) {
            Map<String, String> metaMap = entity.getMetadataItems().stream()
                    .collect(Collectors.toMap(
                            fit.iuh.modules.questionbank.entity.SessionMetadata::getMetadataKey,
                            fit.iuh.modules.questionbank.entity.SessionMetadata::getMetadataValue,
                            (v1, v2) -> v2
                    ));
            try {
                Map<String, String> diffMap = new HashMap<>();
                if (metaMap.containsKey("difficultyDistribution")) {
                    diffMap = objectMapper.readValue(metaMap.get("difficultyDistribution"), Map.class);
                }
                List<String> strongAreas = metaMap.containsKey("strongAreas")
                        ? objectMapper.readValue(metaMap.get("strongAreas"), List.class) : List.of();
                List<String> gapAreas = metaMap.containsKey("gapAreas")
                        ? objectMapper.readValue(metaMap.get("gapAreas"), List.class) : List.of();

                metadataDto = QuestionBankMetadataDto.builder()
                        .candidateLevel(metaMap.get("candidateLevel"))
                        .overallMatch(metaMap.get("overallMatch"))
                        .yearsOfExperience(metaMap.containsKey("yearsOfExperience") ? Integer.parseInt(metaMap.get("yearsOfExperience")) : null)
                        .roleType(metaMap.get("roleType"))
                        .targetDomain(metaMap.get("targetDomain"))
                        .strongAreas(strongAreas)
                        .gapAreas(gapAreas)
                        .difficultyDistribution(diffMap)
                        .totalQuestions(metaMap.containsKey("totalQuestions") ? Integer.parseInt(metaMap.get("totalQuestions")) : 0)
                        .generationRationale(metaMap.get("generationRationale"))
                        .build();
            } catch (Exception e) {
                log.warn("[QuestionBank] Failed to parse metadata for bank {}: {}", entity.getId(), e.getMessage());
            }
        }

        List<QuestionDto> questionDtos = new ArrayList<>();
        if (entity.getQuestions() != null) {
            for (var q : entity.getQuestions()) {
                QuestionDto dto = new QuestionDto();
                String cleanId = q.getId();
                if (cleanId != null && cleanId.contains("_")) {
                    cleanId = cleanId.substring(cleanId.indexOf("_") + 1);
                }
                dto.setId(cleanId);
                dto.setQuestion(q.getQuestionText());
                dto.setEvaluationCriteria(q.getExpectedAnswer());
                dto.setDifficulty(q.getDifficulty());
                dto.setType(q.getQuestionType() != null ? q.getQuestionType() : q.getCategory());
                dto.setExpectedCompetency(q.getExpectedCompetency());
                dto.setTopic(q.getTopic());

                if (q.getDetails() != null && !q.getDetails().isBlank()) {
                    try {
                        Map<String, Object> detailsMap = objectMapper.readValue(q.getDetails(), Map.class);
                        if (detailsMap.containsKey("hints")) {
                            dto.setHints(objectMapper.convertValue(detailsMap.get("hints"), new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {}));
                        }
                        if (detailsMap.containsKey("star_prompt")) {
                            dto.setStarPrompt((String) detailsMap.get("star_prompt"));
                        }
                        if (detailsMap.containsKey("components_to_cover")) {
                            dto.setComponentsToCover(objectMapper.convertValue(detailsMap.get("components_to_cover"), new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {}));
                        }
                        if (detailsMap.containsKey("follow_up_questions")) {
                            dto.setFollowUpQuestions(objectMapper.convertValue(detailsMap.get("follow_up_questions"), new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {}));
                        }
                        if (detailsMap.containsKey("rationale")) {
                            dto.setRationale((String) detailsMap.get("rationale"));
                        }
                    } catch (Exception e) {
                        log.warn("[QuestionBank] Failed to parse details JSON for question {}: {}", q.getId(), e.getMessage());
                    }
                }

                questionDtos.add(dto);
            }
        }

        return QuestionBankResponseDto.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .metadata(metadataDto)
                .questionBank(questionDtos)
                .createdAt(entity.getCreatedAt())
                .build();
    }

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
