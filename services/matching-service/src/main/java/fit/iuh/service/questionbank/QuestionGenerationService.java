package fit.iuh.service.questionbank;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.dto.questionbank.CandidateContextDto;
import fit.iuh.dto.questionbank.QuestionDto;
import fit.iuh.exception.LlmApiException;
import fit.iuh.exception.QuestionBankException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Service that handles sending prompts to the LLM to generate list of questions
 * per type or a single question for regeneration.
 */
@Slf4j
@Service
public class QuestionGenerationService {

    private static final String CHAT_COMPLETIONS_PATH = "/openai/v1/chat/completions";
    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private final WebClient llmWebClient;
    private final AppProperties props;
    private final ObjectMapper objectMapper;

    public QuestionGenerationService(
            @Qualifier("llmWebClient") WebClient llmWebClient,
            AppProperties props,
            ObjectMapper objectMapper) {
        this.llmWebClient = llmWebClient;
        this.props = props;
        this.objectMapper = objectMapper;
    }

    /**
     * Generates a list of questions for a specific type and difficulty distribution.
     *
     * @param type behavioural | technical | coding | system_design
     * @param context candidate context details
     * @param cvMarkdown candidates CV markdown text
     * @param jdMarkdown JD markdown text
     * @param difficultyDist map of difficulty level to count
     * @return list of question DTOs
     */
    public List<QuestionDto> generateForType(
            String type,
            CandidateContextDto context,
            String cvMarkdown,
            String jdMarkdown,
            String matchedPairsText,
            Map<String, Integer> difficultyDist) {

        int totalExpected = difficultyDist.values().stream().mapToInt(Integer::intValue).sum();
        if (totalExpected <= 0) {
            return Collections.emptyList();
        }

        log.info("[QuestionGen] Generating {} questions of type '{}'...", totalExpected, type);

        // Build difficulty target string, e.g. "1 easy, 2 medium, 1 hard"
        List<String> targetList = new ArrayList<>();
        difficultyDist.forEach((diff, count) -> {
            if (count > 0) {
                targetList.add(count + " " + diff);
            }
        });
        String difficultyTargets = String.join(", ", targetList);

        String typeFullName = switch (type) {
            case "behavioural" -> "Behavioural Interview";
            case "technical" -> "Technical Interview";
            case "coding" -> "Coding Test / Code Review";
            case "system_design" -> "System Design Interview";
            default -> type;
        };

        String systemPrompt = String.format(
                PromptTemplateConfig.SYSTEM_PROMPT_QUESTION_GENERATION,
                typeFullName,
                context.getCandidateLevel(),
                context.getOverallMatch(),
                context.getYearsOfExperience(),
                context.getRoleType(),
                context.getTargetDomain(),
                context.getStrongAreas() != null ? String.join(", ", context.getStrongAreas()) : "None",
                context.getGapAreas() != null ? String.join(", ", context.getGapAreas()) : "None",
                context.getTechStackRequired() != null ? String.join(", ", context.getTechStackRequired()) : "None",
                context.getTechStackPossessed() != null ? String.join(", ", context.getTechStackPossessed()) : "None",
                difficultyTargets,
                PromptTemplateConfig.getTypeInstructions(type),
                type,
                PromptTemplateConfig.getTypeSpecificOutputFields(type)
        );

        String userPrompt = """
                ====== SEMANTIC MATCHED EXPERIENCES ======
                %s

                Generate the requested questions for this candidate.

                CRITICAL MAPPING RULE:
                For each question generated, you MUST set the "id" field to the exact Pair ID (e.g., "pair_0", "pair_1") of the matched experience segment that inspired the question. This is required for internal mapping.
                """.formatted(matchedPairsText);

        int attempts = 0;
        int maxAttempts = props.getQuestionBank().getMaxRetries() + 1;

        while (attempts < maxAttempts) {
            attempts++;
            try {
                LlmChatRequest request = LlmChatRequest.builder()
                        .model(props.getLlm().getModel())
                        .maxTokens(props.getQuestionBank().getMaxTokens())
                        .temperature(props.getQuestionBank().getTemperature())
                        .stream(false)
                        .responseFormat(JSON_RESPONSE_FORMAT)
                        .messages(List.of(
                                LlmChatRequest.Message.system(systemPrompt),
                                LlmChatRequest.Message.user(userPrompt)
                        ))
                        .build();

                Duration timeout = Duration.ofSeconds(props.getLlm().getTimeoutSeconds());

                LlmChatResponse response = llmWebClient.post()
                        .uri(CHAT_COMPLETIONS_PATH)
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(LlmChatResponse.class)
                        .timeout(
                                timeout,
                                reactor.core.publisher.Mono.error(new LlmApiException(
                                        "Question generation LLM API call timed out after " + timeout.toSeconds() + "s"))
                        )
                        .block();

                if (response == null || response.getFirstChoiceContent() == null) {
                    throw new QuestionBankException("LLM returned an empty response for question generation.");
                }

                if (response.getUsage() != null) {
                    LlmChatResponse.Usage usage = response.getUsage();
                    log.info("[LLM_USAGE] Model: {} | Prompt (Input): {} | Completion (Output): {} | Total: {}",
                            response.getModel(),
                            usage.getPromptTokens(),
                            usage.getCompletionTokens(),
                            usage.getTotalTokens());
                }

                String rawJson = response.getFirstChoiceContent().strip();
                List<QuestionDto> questions = parseQuestionsJson(rawJson, type);

                if (questions.size() != totalExpected) {
                    log.warn("[QuestionGen] Count mismatch on attempt {} for type {}: expected {}, got {}",
                            attempts, type, totalExpected, questions.size());
                    if (attempts >= maxAttempts) {
                        // Fallback: trim or pad if we are out of retries
                        if (questions.size() > totalExpected) {
                            questions = questions.subList(0, totalExpected);
                        }
                    } else {
                        throw new QuestionBankException("Expected " + totalExpected + " questions, but LLM returned " + questions.size());
                    }
                }

                // Verify difficulty distribution
                Map<String, Integer> actualDist = new HashMap<>();
                actualDist.put("easy", 0);
                actualDist.put("medium", 0);
                actualDist.put("hard", 0);
                for (QuestionDto q : questions) {
                    String diff = q.getDifficulty() != null ? q.getDifficulty().toLowerCase().strip() : "medium";
                    actualDist.put(diff, actualDist.getOrDefault(diff, 0) + 1);
                }

                boolean distributionMatch = true;
                for (String diff : difficultyDist.keySet()) {
                    if (!Objects.equals(difficultyDist.get(diff), actualDist.get(diff))) {
                        distributionMatch = false;
                        break;
                    }
                }

                if (!distributionMatch) {
                    log.warn("[QuestionGen] Difficulty mismatch on attempt {} for type {}: expected {}, got {}",
                            attempts, type, difficultyDist, actualDist);
                    if (attempts >= maxAttempts) {
                        // Force-align difficulty labels
                        log.info("[QuestionGen] Out of retries. Force-balancing the difficulty distribution.");
                        List<String> targetDiffs = new ArrayList<>();
                        difficultyDist.forEach((diff, count) -> {
                            for (int i = 0; i < count; i++) {
                                targetDiffs.add(diff);
                            }
                        });
                        for (int i = 0; i < questions.size() && i < targetDiffs.size(); i++) {
                            questions.get(i).setDifficulty(targetDiffs.get(i));
                        }
                    } else {
                        throw new QuestionBankException("Difficulty distribution does not match requested targets.");
                    }
                }

                return questions;

            } catch (WebClientResponseException e) {
                log.error("[QuestionGen] HTTP Error from LLM API: {}", e.getResponseBodyAsString());
                if (e.getStatusCode().value() == 429 && attempts < maxAttempts) {
                    log.warn("[QuestionGen] Rate limit hit (429) for type {}. Sleeping for 15 seconds before attempt {}/{}", type, attempts + 1, maxAttempts);
                    try {
                        Thread.sleep(15000);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new QuestionBankException("Question generation interrupted during backoff", ie);
                    }
                    continue;
                }
                if (attempts >= maxAttempts) {
                    throw new LlmApiException("LLM API HTTP " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
                }
            } catch (Exception e) {
                log.warn("[QuestionGen] Attempt {} failed for type {}: {}", attempts, type, e.getMessage());
                if (attempts >= maxAttempts) {
                    throw e instanceof RuntimeException ? (RuntimeException) e : new QuestionBankException(e.getMessage(), e);
                }
            }
        }

        throw new QuestionBankException("Failed to generate questions for type: " + type);
    }

    /**
     * Regenerates a single question with the same type and difficulty, avoiding topics
     * already present in existing questions.
     */
    public QuestionDto regenerateSingle(
            String type,
            String difficulty,
            CandidateContextDto context,
            String cvMarkdown,
            String jdMarkdown,
            List<QuestionDto> existingQuestions) {

        log.info("[QuestionGen] Regenerating 1 question of type '{}' (difficulty: '{}')...", type, difficulty);

        String typeFullName = switch (type) {
            case "behavioural" -> "Behavioural Interview";
            case "technical" -> "Technical Interview";
            case "coding" -> "Coding Test / Code Review";
            case "system_design" -> "System Design Interview";
            default -> type;
        };

        String systemPrompt = String.format(
                PromptTemplateConfig.SYSTEM_PROMPT_QUESTION_GENERATION,
                typeFullName,
                context.getCandidateLevel(),
                context.getOverallMatch(),
                context.getYearsOfExperience(),
                context.getRoleType(),
                context.getTargetDomain(),
                context.getStrongAreas() != null ? String.join(", ", context.getStrongAreas()) : "None",
                context.getGapAreas() != null ? String.join(", ", context.getGapAreas()) : "None",
                context.getTechStackRequired() != null ? String.join(", ", context.getTechStackRequired()) : "None",
                context.getTechStackPossessed() != null ? String.join(", ", context.getTechStackPossessed()) : "None",
                "1 " + difficulty,
                PromptTemplateConfig.getTypeInstructions(type),
                type,
                PromptTemplateConfig.getTypeSpecificOutputFields(type)
        );

        // Tell LLM which topics to avoid duplicating
        String existingTopics = existingQuestions.stream()
                .map(q -> "- " + q.getTopic())
                .collect(Collectors.joining("\n"));

        String userPrompt = """
                ====== CANDIDATE RESUME (CV) ======
                %s

                ====== JOB DESCRIPTION (JD) ======
                %s

                ====== EXISTING TOPICS TO AVOID ======
                %s

                Generate exactly 1 new question for this candidate of type '%s' and difficulty '%s'.
                Do not generate any questions on the existing topics listed above.
                """.formatted(cvMarkdown, jdMarkdown, existingTopics, type, difficulty);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(props.getLlm().getModel())
                .maxTokens(props.getQuestionBank().getMaxTokens())
                .temperature(props.getQuestionBank().getTemperature() + 0.1) // slightly higher temperature to encourage diversity
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(systemPrompt),
                        LlmChatRequest.Message.user(userPrompt)
                ))
                .build();

        Duration timeout = Duration.ofSeconds(props.getLlm().getTimeoutSeconds());

        int attempts = 0;
        int maxAttempts = 3;

        while (attempts < maxAttempts) {
            attempts++;
            try {
                LlmChatResponse response = llmWebClient.post()
                        .uri(CHAT_COMPLETIONS_PATH)
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(LlmChatResponse.class)
                        .timeout(
                                timeout,
                                reactor.core.publisher.Mono.error(new LlmApiException(
                                        "Question regeneration LLM API call timed out after " + timeout.toSeconds() + "s"))
                        )
                        .block();

                if (response == null || response.getFirstChoiceContent() == null) {
                    throw new QuestionBankException("LLM returned an empty response for question regeneration.");
                }

                if (response.getUsage() != null) {
                    LlmChatResponse.Usage usage = response.getUsage();
                    log.info("[LLM_USAGE] Model: {} | Prompt (Input): {} | Completion (Output): {} | Total: {}",
                            response.getModel(),
                            usage.getPromptTokens(),
                            usage.getCompletionTokens(),
                            usage.getTotalTokens());
                }

                String rawJson = response.getFirstChoiceContent().strip();
                List<QuestionDto> questions = parseQuestionsJson(rawJson, type);

                if (questions.isEmpty()) {
                    throw new QuestionBankException("No questions generated by LLM for regeneration.");
                }

                QuestionDto generated = questions.get(0);
                generated.setType(type);
                generated.setDifficulty(difficulty);
                return generated;

            } catch (WebClientResponseException e) {
                if (e.getStatusCode().value() == 429 && attempts < maxAttempts) {
                    log.warn("[QuestionGen] Rate limit hit (429) during regeneration. Sleeping for 15 seconds before attempt {}/{}", attempts + 1, maxAttempts);
                    try {
                        Thread.sleep(15000);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new QuestionBankException("Question regeneration interrupted during backoff", ie);
                    }
                    continue;
                }
                throw new LlmApiException("LLM API HTTP " + e.getStatusCode() + " while regenerating: " + e.getResponseBodyAsString(), e);
            } catch (Exception e) {
                if (attempts >= maxAttempts) {
                    if (e instanceof QuestionBankException || e instanceof LlmApiException) {
                        throw e;
                    }
                    throw new QuestionBankException("Unexpected error during question regeneration: " + e.getMessage(), e);
                }
            }
        }
        throw new QuestionBankException("Failed to regenerate question after " + maxAttempts + " attempts due to rate limiting or timeouts.");
    }

    private List<QuestionDto> parseQuestionsJson(String rawJson, String type) {
        String cleanJson = rawJson
                .replaceAll("(?s)^```json\\s*", "")
                .replaceAll("(?s)\\s*```$", "")
                .strip();

        try {
            JsonNode root = objectMapper.readTree(cleanJson);
            JsonNode questionsNode = root.get("questions");
            if (questionsNode == null || !questionsNode.isArray()) {
                throw new QuestionBankException("LLM JSON root does not contain an array under 'questions' key.");
            }

            List<QuestionDto> list = objectMapper.convertValue(questionsNode, new TypeReference<List<QuestionDto>>() {});
            for (QuestionDto q : list) {
                q.setType(type); // Ensure type is strictly set
                
                // Simple validation of required fields
                if (q.getQuestion() == null || q.getQuestion().isBlank()) {
                    throw new QuestionBankException("Question text is empty in generated question object.");
                }
                if (q.getTopic() == null || q.getTopic().isBlank()) {
                    q.setTopic("General " + type);
                }
                if (q.getDifficulty() == null || q.getDifficulty().isBlank()) {
                    q.setDifficulty("medium");
                }
            }
            return list;
        } catch (JsonProcessingException e) {
            log.error("[QuestionGen] Failed to parse question list JSON: {}", cleanJson, e);
            throw new QuestionBankException("LLM returned invalid questions JSON: " + e.getMessage(), e);
        }
    }
}
