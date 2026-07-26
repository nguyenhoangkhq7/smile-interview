package fit.iuh.modules.questionbank.service.impl;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.exception.QuestionBankException;
import fit.iuh.modules.questionbank.dto.*;
import fit.iuh.modules.questionbank.prompt.QuestionBankPrompts;
import fit.iuh.modules.questionbank.service.QuestionGenerationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
public class QuestionGenerationServiceImpl implements QuestionGenerationService {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private final WebClient llmWebClient;
    private final AppProperties props;
    private final ObjectMapper objectMapper;
    private final fit.iuh.modules.chunking.service.RetrievalService retrievalService;

    public QuestionGenerationServiceImpl(
            @Qualifier("llmWebClient") WebClient llmWebClient,
            AppProperties props,
            ObjectMapper objectMapper,
            fit.iuh.modules.chunking.service.RetrievalService retrievalService) {
        this.llmWebClient = llmWebClient;
        this.props = props;
        this.objectMapper = objectMapper;
        this.retrievalService = retrievalService;
    }

    @Override
    public List<QuestionDto> generateForCategory(
            String type,
            CandidateContextDto context,
            List<QuestionAssignment> assignments,
            QuestionConfigDto config) {

        int totalExpected = assignments.size();
        if (totalExpected <= 0) {
            return Collections.emptyList();
        }

        log.info("[QuestionGen] Generating {} questions of type '{}'...", totalExpected, type);

        String typeFullName = switch (type) {
            case "behavioural" -> "Behavioural Interview";
            case "technical" -> "Technical Interview";
            case "coding" -> "Coding Test / Code Review";
            case "system_design" -> "System Design Interview";
            default -> type;
        };

        String systemPrompt = String.format(
                QuestionBankPrompts.SYSTEM_PROMPT_QUESTION_GENERATION,
                context.getCandidateLevel() != null ? context.getCandidateLevel().name() : "MID",
                context.getRoleType() != null ? context.getRoleType().name() : "OTHER",
                context.getTargetDomain() != null ? context.getTargetDomain() : "other",
                context.getStrongAreas() != null ? String.join(", ", context.getStrongAreas()) : "None",
                context.getGapAreas() != null ? String.join(", ", context.getGapAreas()) : "None",
                context.getTechStackPossessed() != null ? String.join(", ", context.getTechStackPossessed()) : "None",
                context.getTechStackRequired() != null ? String.join(", ", context.getTechStackRequired()) : "None",
                typeFullName,
                QuestionBankPrompts.getTypeInstructions(type),
                QuestionBankPrompts.getTypeSpecificOutputFields(type)
        );

        String evidenceItemsText = buildEvidenceAssignmentsText(assignments);

        String userPrompt = """
                ====== ASSESSMENT EVIDENCE ITEMS ======
                %s

                Generate the requested questions for this candidate.

                CRITICAL MAPPING RULE:
                For each question generated, you MUST set the "id" field to the exact Item ID (e.g., "item_0", "item_1") of the evidence item that inspired the question. This is required for internal mapping.
                """.formatted(evidenceItemsText);

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
                        .uri(props.getLlm().getChatPath())
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
                        if (questions.size() > totalExpected) {
                            questions = questions.subList(0, totalExpected);
                        }
                    } else {
                        throw new QuestionBankException("Expected " + totalExpected + " questions, but LLM returned " + questions.size());
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

    @Override
    public QuestionDto regenerateSingle(
            String type,
            String difficulty,
            CandidateContextDto context,
            List<EvidenceItemPair> allEvidenceItems,
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
                QuestionBankPrompts.SYSTEM_PROMPT_QUESTION_GENERATION,
                context.getCandidateLevel() != null ? context.getCandidateLevel().name() : "MID",
                context.getRoleType() != null ? context.getRoleType().name() : "OTHER",
                context.getTargetDomain() != null ? context.getTargetDomain() : "other",
                context.getStrongAreas() != null ? String.join(", ", context.getStrongAreas()) : "None",
                context.getGapAreas() != null ? String.join(", ", context.getGapAreas()) : "None",
                context.getTechStackPossessed() != null ? String.join(", ", context.getTechStackPossessed()) : "None",
                context.getTechStackRequired() != null ? String.join(", ", context.getTechStackRequired()) : "None",
                typeFullName,
                QuestionBankPrompts.getTypeInstructions(type),
                QuestionBankPrompts.getTypeSpecificOutputFields(type)
        );

        String existingTopics = existingQuestions.stream()
                .map(q -> "- " + q.getTopic())
                .collect(Collectors.joining("\n"));

        String evidenceItemsText = buildEvidenceItemsText(allEvidenceItems);

        String userPrompt = """
                ====== ASSESSMENT EVIDENCE ITEMS ======
                %s

                ====== EXISTING TOPICS TO AVOID ======
                %s

                Generate exactly 1 new question for this candidate of type '%s' and difficulty '%s'.
                Do not generate any questions on the existing topics listed above.
                """.formatted(evidenceItemsText, existingTopics, type, difficulty);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(props.getLlm().getModel())
                .maxTokens(props.getQuestionBank().getMaxTokens())
                .temperature(props.getQuestionBank().getTemperature() + 0.1)
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
                        .uri(props.getLlm().getChatPath())
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

    private String buildEvidenceAssignmentsText(List<QuestionAssignment> assignments) {
        if (assignments == null || assignments.isEmpty()) {
            return "(No evidence items available)";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < assignments.size(); i++) {
            QuestionAssignment qa = assignments.get(i);
            EvidenceItemPair item = qa.item();
            sb.append(String.format(
                    "### Item ID: item_%d [status: %s] [target_difficulty: %s]%n",
                    i,
                    item != null && item.status() != null ? item.status() : "unknown",
                    qa.difficulty()
            ));
            if (item != null) {
                sb.append(String.format("- Criteria: %s%n", item.criteriaName() != null ? item.criteriaName() : "Ad-hoc"));
                sb.append(String.format("- JD Requirement: %s%n", item.jdRequirement() != null ? item.jdRequirement() : "N/A"));
                sb.append(String.format("- CV Evidence: %s%n",
                        item.cvEvidence() != null ? item.cvEvidence() : "None (missing from CV)"));
                if (item.reasoning() != null && !item.reasoning().isBlank()) {
                    sb.append(String.format("- Reasoning: %s%n", item.reasoning()));
                }
            } else {
                sb.append("- Criteria: General Behavioral / Catch-all\n");
                sb.append("- JD Requirement: N/A\n");
                sb.append("- CV Evidence: N/A\n");
            }
            sb.append("\n");
        }
        return sb.toString().strip();
    }

    private String buildEvidenceItemsText(List<EvidenceItemPair> evidenceItems) {
        if (evidenceItems == null || evidenceItems.isEmpty()) {
            return "(No evidence items available)";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < evidenceItems.size(); i++) {
            EvidenceItemPair item = evidenceItems.get(i);
            sb.append(String.format(
                    "### Item ID: item_%d [status: %s]%n",
                    i, item.status() != null ? item.status() : "unknown"
            ));
            sb.append(String.format("- Criteria: %s%n", item.criteriaName() != null ? item.criteriaName() : "Ad-hoc"));
            sb.append(String.format("- JD Requirement: %s%n", item.jdRequirement() != null ? item.jdRequirement() : "N/A"));
            sb.append(String.format("- CV Evidence: %s%n",
                    item.cvEvidence() != null ? item.cvEvidence() : "None (missing from CV)"));
            if (item.reasoning() != null && !item.reasoning().isBlank()) {
                sb.append(String.format("- Reasoning: %s%n", item.reasoning()));
            }
            sb.append("\n");
        }
        return sb.toString().strip();
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
                q.setType(type);

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
