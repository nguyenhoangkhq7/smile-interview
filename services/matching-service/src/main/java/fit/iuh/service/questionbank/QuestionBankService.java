package fit.iuh.service.questionbank;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.dto.questionbank.*;
import fit.iuh.entity.QuestionBank;
import fit.iuh.entity.ResumeAssessment;
import fit.iuh.entity.SessionDocument;
import fit.iuh.entity.enums.DocumentType;
import fit.iuh.entity.DocumentChunk;
import fit.iuh.exception.QuestionBankException;
import fit.iuh.repository.DocumentChunkRepository;
import fit.iuh.repository.QuestionBankRepository;
import fit.iuh.repository.ResumeAssessmentRepository;
import fit.iuh.repository.SessionDocumentRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Orchestrates the full Question Bank generation pipeline: loading data,
 * extracting context, determining distribution, generating questions, and saving.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class QuestionBankService {

    private final QuestionGenerationService questionGenerationService;
    private final DifficultyDistributor difficultyDistributor;
    private final ResumeAssessmentRepository assessmentRepo;
    private final SessionDocumentRepository documentRepo;
    private final DocumentChunkRepository documentChunkRepository;
    private final QuestionBankRepository questionBankRepo;
    private final ObjectMapper objectMapper;
    private final SemanticCacheKeyGenerator cacheKeyGenerator;
    private final SemanticCacheService cacheService;

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

        // Step 0: Load prerequisites from DB
        ResumeAssessment assessment = assessmentRepo.findBySessionId(sessionId)
                .orElseThrow(() -> new QuestionBankException("Resume assessment not found for session: " + sessionId + ". Please generate an assessment first."));

        SessionDocument cvDoc = documentRepo.findBySessionIdAndDocumentType(sessionId, DocumentType.CV)
                .orElseThrow(() -> new QuestionBankException("CV document not found for session: " + sessionId));

        SessionDocument jdDoc = documentRepo.findBySessionIdAndDocumentType(sessionId, DocumentType.JD)
                .orElseThrow(() -> new QuestionBankException("JD document not found for session: " + sessionId));

        // Load CV & JD chunks to identify semantic matched pairs
        List<DocumentChunk> cvChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
        List<DocumentChunk> jdChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
        List<ExperienceRequirementPair> matchedPairs = findMatchedPairs(cvChunks, jdChunks);

        log.info("[QuestionBank] Semantic matching completed. Found {} matched pairs for session {}.", matchedPairs.size(), sessionId);

        // Step 1: Programmatic Context Extraction from Assessment (saves LLM call & costs 0 tokens!)
        List<String> strongAreas = assessment.getStrongAreas() != null ? assessment.getStrongAreas() : Collections.emptyList();
        List<String> gapAreas = assessment.getGapAreas() != null ? assessment.getGapAreas() : Collections.emptyList();

        List<String> techStackRequired = new ArrayList<>();
        List<String> techStackPossessed = new ArrayList<>();
        if (assessment.getSectionWiseFeedback() != null && assessment.getSectionWiseFeedback().techStackAlignment() != null) {
            var alignment = assessment.getSectionWiseFeedback().techStackAlignment();
            if (alignment.matched() != null) {
                techStackRequired.addAll(alignment.matched());
                techStackPossessed.addAll(alignment.matched());
            }
            if (alignment.missing() != null) {
                techStackRequired.addAll(alignment.missing());
            }
            if (alignment.weakEvidence() != null) {
                techStackPossessed.addAll(alignment.weakEvidence());
            }
        }

        // Simple domain heuristic from CV and JD text to avoid calling LLM
        String cvJdText = ((cvDoc.getMarkdownContent() != null ? cvDoc.getMarkdownContent() : "") + " " 
                + (jdDoc.getMarkdownContent() != null ? jdDoc.getMarkdownContent() : "")).toLowerCase();
        String targetDomain = "other";
        if (cvJdText.contains("wallet") || cvJdText.contains("transaction") || cvJdText.contains("payment") || cvJdText.contains("bank") || cvJdText.contains("fintech")) {
            targetDomain = "fintech";
        } else if (cvJdText.contains("cart") || cvJdText.contains("shop") || cvJdText.contains("checkout") || cvJdText.contains("e-commerce") || cvJdText.contains("order")) {
            targetDomain = "e-commerce";
        } else if (cvJdText.contains("health") || cvJdText.contains("hospital") || cvJdText.contains("medical") || cvJdText.contains("patient")) {
            targetDomain = "healthcare";
        } else if (cvJdText.contains("saas") || cvJdText.contains("multi-tenant") || cvJdText.contains("billing")) {
            targetDomain = "saas";
        } else if (cvJdText.contains("enterprise") || cvJdText.contains("b2b")) {
            targetDomain = "enterprise";
        } else if (cvJdText.contains("startup") || cvJdText.contains("funding") || cvJdText.contains("mvp")) {
            targetDomain = "startup";
        }

        CandidateContextDto context = CandidateContextDto.builder()
                .candidateLevel(assessment.getCandidateLevel())
                .overallMatch(assessment.getMatchLevel())
                .yearsOfExperience(assessment.getYearsOfExperienceEstimate())
                .strongAreas(strongAreas)
                .gapAreas(gapAreas)
                .techStackRequired(techStackRequired)
                .techStackPossessed(techStackPossessed)
                .targetDomain(targetDomain)
                .roleType(assessment.getRoleTypeDetected())
                .build();

        // Step 2: Difficulty Distribution Calculation
        Map<String, Map<String, Integer>> distributions = new LinkedHashMap<>();
        if (config.getBehavioural() > 0) {
            distributions.put("behavioural", difficultyDistributor.distribute(
                    context.getCandidateLevel(), context.getOverallMatch(), config.getBehavioural()));
        }
        if (config.getTechnical() > 0) {
            distributions.put("technical", difficultyDistributor.distribute(
                    context.getCandidateLevel(), context.getOverallMatch(), config.getTechnical()));
        }
        if (config.getCoding() > 0) {
            distributions.put("coding", difficultyDistributor.distribute(
                    context.getCandidateLevel(), context.getOverallMatch(), config.getCoding()));
        }
        if (config.getSystemDesign() > 0) {
            distributions.put("system_design", difficultyDistributor.distribute(
                    context.getCandidateLevel(), context.getOverallMatch(), config.getSystemDesign()));
        }

        // Step 3: Question Generation (with Redis Cache-Aside)
        List<QuestionDto> allQuestions = new ArrayList<>();
        int typeIndex = 0;
        for (var entry : distributions.entrySet()) {
            typeIndex++;
            String type = entry.getKey();
            Map<String, Integer> originalDist = entry.getValue();

            // Make a copy of the distribution to adjust as we get cache hits
            Map<String, Integer> remainingDist = new LinkedHashMap<>(originalDist);
            List<QuestionDto> typeQuestions = new ArrayList<>();
            List<ExperienceRequirementPair> missedPairs = new ArrayList<>();
            Map<String, String> cacheKeyMap = new HashMap<>(); // pair_index -> cacheKey

            // Step 3.1: Check Cache for each pair
            for (int i = 0; i < matchedPairs.size(); i++) {
                ExperienceRequirementPair pair = matchedPairs.get(i);
                String cacheKey = cacheKeyGenerator.generateKey(pair.jdChunkText(), pair.cvChunkText());
                List<QuestionDto> cachedList = cacheService.get(cacheKey);

                if (cachedList != null && !cachedList.isEmpty()) {
                    // Filter cached questions of this type
                    List<QuestionDto> matchingCached = cachedList.stream()
                            .filter(q -> type.equalsIgnoreCase(q.getType()))
                            .collect(Collectors.toList());

                    if (!matchingCached.isEmpty()) {
                        // Re-use matching cached questions if they fit the difficulty distribution
                        for (QuestionDto q : matchingCached) {
                            String diff = q.getDifficulty() != null ? q.getDifficulty().toLowerCase().strip() : "medium";
                            int remainingCount = remainingDist.getOrDefault(diff, 0);
                            if (remainingCount > 0) {
                                remainingDist.put(diff, remainingCount - 1);
                                typeQuestions.add(q);
                                log.info("[QuestionBank] Cache HIT reused: {} question for topic '{}'", diff, q.getTopic());
                            }
                        }
                    } else {
                        // Cache hit for other types, but miss for this type
                        missedPairs.add(pair);
                        cacheKeyMap.put("pair_" + (missedPairs.size() - 1), cacheKey);
                    }
                } else {
                    // Cache miss
                    missedPairs.add(pair);
                    cacheKeyMap.put("pair_" + (missedPairs.size() - 1), cacheKey);
                }
            }

            int totalRemaining = remainingDist.values().stream().mapToInt(Integer::intValue).sum();
            log.info("[QuestionBank] Type '{}' distribution: requested={}, remaining to generate={}", 
                    type, originalDist, remainingDist);

            // Step 3.2: Generate remaining questions from LLM using missed pairs
            if (totalRemaining > 0) {
                if (typeIndex > 1) {
                    // Introduce a 5-second delay to prevent rate limits
                    try {
                        log.info("[QuestionBank] Pacing LLM calls: sleeping for 5 seconds...");
                        Thread.sleep(5000);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new QuestionBankException("Question generation pacing interrupted", ie);
                    }
                }

                // Format missed pairs with explicit Pair IDs for the LLM mapping
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < missedPairs.size(); i++) {
                    ExperienceRequirementPair pair = missedPairs.get(i);
                    sb.append(String.format(
                            "### Pair ID: pair_%d\n- **Required Job Description segment**: %s\n- **Matched Candidate Experience segment**: %s\n\n",
                            i, pair.jdChunkText(), pair.cvChunkText()
                    ));
                }
                String missedPairsText = sb.toString();

                List<QuestionDto> generatedQs = questionGenerationService.generateForType(
                        type, context, cvDoc.getMarkdownContent(), jdDoc.getMarkdownContent(), missedPairsText, remainingDist);

                typeQuestions.addAll(generatedQs);

                // Group generated questions by the Pair ID returned by the LLM (in the id field)
                Map<String, List<QuestionDto>> newQuestionsByPair = new HashMap<>();
                for (QuestionDto q : generatedQs) {
                    String pairId = q.getId(); // e.g. "pair_0"
                    if (pairId != null && pairId.startsWith("pair_")) {
                        newQuestionsByPair.computeIfAbsent(pairId, k -> new ArrayList<>()).add(q);
                    } else {
                        // Fallback: associate with the first missed pair
                        newQuestionsByPair.computeIfAbsent("pair_0", k -> new ArrayList<>()).add(q);
                    }
                }

                // Step 3.3: Write new questions to Redis (merge with existing types)
                newQuestionsByPair.forEach((pairId, newQs) -> {
                    String cacheKey = cacheKeyMap.get(pairId);
                    if (cacheKey != null) {
                        List<QuestionDto> existing = cacheService.get(cacheKey);
                        List<QuestionDto> merged = new ArrayList<>();
                        if (existing != null) {
                            merged.addAll(existing);
                        }
                        for (QuestionDto nq : newQs) {
                            nq.setType(type); // Force type to match current generation context
                            boolean duplicate = merged.stream().anyMatch(eq ->
                                    Objects.equals(eq.getType(), nq.getType()) &&
                                    Objects.equals(eq.getQuestion(), nq.getQuestion())
                            );
                            if (!duplicate) {
                                merged.add(nq);
                            }
                        }
                        cacheService.put(cacheKey, merged, Duration.ofDays(7));
                    }
                });
            }

            allQuestions.addAll(typeQuestions);
        }

        // Step 4: Assembly & Sequencing
        for (int i = 0; i < allQuestions.size(); i++) {
            allQuestions.get(i).setId(String.format("Q%03d", i + 1));
        }

        // Step 5: Build metadata
        int totalEasy = 0;
        int totalMedium = 0;
        int totalHard = 0;
        for (QuestionDto q : allQuestions) {
            if ("easy".equalsIgnoreCase(q.getDifficulty())) totalEasy++;
            else if ("medium".equalsIgnoreCase(q.getDifficulty())) totalMedium++;
            else if ("hard".equalsIgnoreCase(q.getDifficulty())) totalHard++;
        }
        int total = allQuestions.size();
        Map<String, String> diffDistMap = new LinkedHashMap<>();
        if (total > 0) {
            diffDistMap.put("easy", Math.round((totalEasy * 100.0) / total) + "%");
            diffDistMap.put("medium", Math.round((totalMedium * 100.0) / total) + "%");
            diffDistMap.put("hard", Math.round((totalHard * 100.0) / total) + "%");
        } else {
            diffDistMap.put("easy", "0%");
            diffDistMap.put("medium", "0%");
            diffDistMap.put("hard", "0%");
        }

        String generationRationale = String.format(
                "%s-level %s candidate with %s CV-JD match. Strong areas: %s. Gap areas: %s.",
                context.getCandidateLevel() != null ? context.getCandidateLevel() : "mid",
                context.getRoleType() != null ? context.getRoleType() : "backend",
                context.getOverallMatch() != null ? context.getOverallMatch() : "medium",
                context.getStrongAreas() != null ? String.join(", ", context.getStrongAreas()) : "None",
                context.getGapAreas() != null ? String.join(", ", context.getGapAreas()) : "None"
        );

        QuestionBankMetadataDto metadata = QuestionBankMetadataDto.builder()
                .candidateLevel(context.getCandidateLevel())
                .overallMatch(context.getOverallMatch())
                .yearsOfExperience(context.getYearsOfExperience())
                .roleType(context.getRoleType())
                .targetDomain(context.getTargetDomain())
                .strongAreas(context.getStrongAreas())
                .gapAreas(context.getGapAreas())
                .difficultyDistribution(diffDistMap)
                .totalQuestions(total)
                .generationRationale(generationRationale)
                .build();

        // Step 6: Persist
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
     * @param questionId sequential ID of the question (e.g. Q003)
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

        final String sessionId = bank.getSessionId();
        // Load CV/JD Markdown
        SessionDocument cvDoc = documentRepo.findBySessionIdAndDocumentType(sessionId, DocumentType.CV)
                .orElseThrow(() -> new QuestionBankException("CV document not found for session " + sessionId));
        SessionDocument jdDoc = documentRepo.findBySessionIdAndDocumentType(sessionId, DocumentType.JD)
                .orElseThrow(() -> new QuestionBankException("JD document not found for session " + sessionId));

        QuestionDto regenerated = questionGenerationService.regenerateSingle(
                target.getType(),
                target.getDifficulty(),
                bank.getCandidateContext(),
                cvDoc.getMarkdownContent(),
                jdDoc.getMarkdownContent(),
                questions
        );

        // Keep same ID
        regenerated.setId(questionId);

        // Replace it in list
        int index = questions.indexOf(target);
        questions.set(index, regenerated);

        // Update database
        bank.setQuestionBankJson(questions);
        bank = questionBankRepo.save(bank);

        log.info("[QuestionBank] Question {} successfully regenerated in bank {}", questionId, questionBankId);
        return toResponseDto(bank);
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

    private List<ExperienceRequirementPair> findMatchedPairs(List<DocumentChunk> cvChunks, List<DocumentChunk> jdChunks) {
        final double SIMILARITY_THRESHOLD = 0.65;
        final int GLOBAL_LIMIT = 7;

        record ChunkMatch(DocumentChunk jdChunk, DocumentChunk cvChunk, double score) {}

        List<ChunkMatch> allMatches = new ArrayList<>();

        for (DocumentChunk jdChunk : jdChunks) {
            if (jdChunk.getEmbedding() == null) continue;
            for (DocumentChunk cvChunk : cvChunks) {
                if (cvChunk.getEmbedding() == null) continue;
                double score = calculateCosineSimilarity(jdChunk.getEmbedding(), cvChunk.getEmbedding());
                if (score >= SIMILARITY_THRESHOLD) {
                    allMatches.add(new ChunkMatch(jdChunk, cvChunk, score));
                }
            }
        }

        // Sort globally by similarity score descending
        allMatches.sort((a, b) -> Double.compare(b.score(), a.score()));

        List<ExperienceRequirementPair> matchedPairs = new ArrayList<>();
        int pairCount = 0;
        for (ChunkMatch match : allMatches) {
            pairCount++;
            matchedPairs.add(new ExperienceRequirementPair(
                    match.jdChunk().getChunkText(),
                    match.cvChunk().getChunkText(),
                    match.jdChunk().getEmbedding(),
                    match.cvChunk().getEmbedding(),
                    match.score()
            ));
            if (pairCount >= GLOBAL_LIMIT) {
                break;
            }
        }
        return matchedPairs;
    }

    private double calculateCosineSimilarity(float[] vectorA, float[] vectorB) {
        if (vectorA.length != vectorB.length) return 0.0;
        double dotProduct = 0.0, normA = 0.0, normB = 0.0;
        for (int i = 0; i < vectorA.length; i++) {
            dotProduct += (double) vectorA[i] * vectorB[i];
            normA += Math.pow(vectorA[i], 2);
            normB += Math.pow(vectorB[i], 2);
        }
        if (normA == 0.0 || normB == 0.0) return 0.0;
        return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
    }
}
