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

import java.time.LocalDateTime;
import java.util.*;

/**
 * Orchestrates the full Question Bank generation pipeline: loading data,
 * extracting context, determining distribution, generating questions, and saving.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class QuestionBankService {

    private final ContextExtractionService contextExtractionService;
    private final QuestionGenerationService questionGenerationService;
    private final DifficultyDistributor difficultyDistributor;
    private final ResumeAssessmentRepository assessmentRepo;
    private final SessionDocumentRepository documentRepo;
    private final DocumentChunkRepository documentChunkRepository;
    private final QuestionBankRepository questionBankRepo;
    private final ObjectMapper objectMapper;

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

        String assessmentJson;
        try {
            assessmentJson = objectMapper.writeValueAsString(assessment);
        } catch (JsonProcessingException e) {
            throw new QuestionBankException("Failed to serialize assessment data: " + e.getMessage(), e);
        }

        // Load CV & JD chunks to identify semantic matched pairs
        List<DocumentChunk> cvChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.CV);
        List<DocumentChunk> jdChunks = documentChunkRepository.findBySessionIdAndDocumentType(sessionId, DocumentType.JD);
        List<String> matchedPairs = findMatchedPairs(cvChunks, jdChunks);
        String matchedPairsText = matchedPairs.isEmpty() ? "No direct semantic matches found." : String.join("\n", matchedPairs);

        log.info("[QuestionBank] Semantic matching completed. Found {} matched pairs for session {}.", matchedPairs.size(), sessionId);

        // Step 1: Context Extraction
        CandidateContextDto context = contextExtractionService.extractContext(
                cvDoc.getMarkdownContent(),
                jdDoc.getMarkdownContent(),
                assessmentJson
        );

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

        // Step 3: Question Generation (parallel loop in sequence to avoid LLM rate limits/tokens)
        List<QuestionDto> allQuestions = new ArrayList<>();
        int typeIndex = 0;
        for (var entry : distributions.entrySet()) {
            typeIndex++;
            if (typeIndex > 1 || context != null) {
                // Introduce a 5-second delay between LLM calls to prevent TPM rate limits
                try {
                    log.info("[QuestionBank] Pacing LLM calls: sleeping for 5 seconds before generating next type...");
                    Thread.sleep(5000);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new QuestionBankException("Question generation pacing interrupted", ie);
                }
            }
            String type = entry.getKey();
            Map<String, Integer> dist = entry.getValue();
            List<QuestionDto> typeQuestions = questionGenerationService.generateForType(
                    type, context, cvDoc.getMarkdownContent(), jdDoc.getMarkdownContent(), matchedPairsText, dist);
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

    private List<String> findMatchedPairs(List<DocumentChunk> cvChunks, List<DocumentChunk> jdChunks) {
        final double SIMILARITY_THRESHOLD = 0.65;
        final int TOP_K = 3;

        List<String> matchedPairs = new ArrayList<>();
        int pairCount = 0;

        for (DocumentChunk jdChunk : jdChunks) {
            if (jdChunk.getEmbedding() == null) continue;

            List<Map.Entry<DocumentChunk, Double>> similarities = new ArrayList<>();
            for (DocumentChunk cvChunk : cvChunks) {
                if (cvChunk.getEmbedding() == null) continue;
                double score = calculateCosineSimilarity(jdChunk.getEmbedding(), cvChunk.getEmbedding());
                if (score >= SIMILARITY_THRESHOLD) {
                    similarities.add(new AbstractMap.SimpleEntry<>(cvChunk, score));
                }
            }

            similarities.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
            List<DocumentChunk> topCvForJd = similarities.stream()
                    .limit(TOP_K)
                    .map(Map.Entry::getKey)
                    .toList();

            for (DocumentChunk cvChunk : topCvForJd) {
                pairCount++;
                matchedPairs.add(String.format(
                        "### Match Pair %d:\n- **Required Job Description segment**: %s\n- **Matched Candidate Experience segment**: %s\n",
                        pairCount, jdChunk.getChunkText(), cvChunk.getChunkText()
                ));
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
