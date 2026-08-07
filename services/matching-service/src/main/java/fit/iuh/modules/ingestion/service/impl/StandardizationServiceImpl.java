package fit.iuh.modules.ingestion.service.impl;

import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.ingestion.prompt.IngestionPrompts;
import fit.iuh.modules.ingestion.service.StandardizationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.List;

@Slf4j
@Service
public class StandardizationServiceImpl implements StandardizationService {

    private final AppProperties appProperties;
    private final WebClient llmWebClient;

    public StandardizationServiceImpl(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
    }

    @Override
    public String standardizeCv(String rawCvText) {
        log.info("Standardizing CV ({} chars) via LLM API...", rawCvText.length());
        return callLlmApi(IngestionPrompts.SYSTEM_PROMPT_CV, rawCvText, "CV");
    }

    @Override
    public String standardizeJd(String rawJdText) {
        log.info("Standardizing JD ({} chars) via LLM API...", rawJdText.length());
        return callLlmApi(IngestionPrompts.SYSTEM_PROMPT_JD, rawJdText, "JD");
    }

    private String callLlmApi(String systemPrompt, String userContent, String documentLabel) {
        var taskConfig = appProperties.getLlm().getTasks().getStandardization();
        List<String> models = appProperties.getLlm().resolveModels(taskConfig);
        String model = models.isEmpty() ? appProperties.getLlm().resolveModel(taskConfig) : models.get(0);
        int maxTokens = appProperties.getLlm().resolveMaxTokens(taskConfig);
        double temperature = appProperties.getLlm().resolveTemperature(taskConfig);
        long timeoutSeconds = appProperties.getLlm().resolveTimeoutSeconds(taskConfig);

        LlmChatRequest request = LlmChatRequest.builder()
                .model(model)
                .models(models)
                .maxTokens(maxTokens)
                .temperature(temperature)
                .stream(false)
                .messages(List.of(
                        LlmChatRequest.Message.system(systemPrompt),
                        LlmChatRequest.Message.user(userContent)
                ))
                .build();

        try {
            LlmChatResponse response = llmWebClient.post()
                    .uri(appProperties.getLlm().getChatPath())
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(LlmChatResponse.class)
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .block();

            log.info("[RAW_LLM_RESPONSE_DIAGNOSTIC] Doc={} | ReqMaxTokens={} | ResponseObj={} | ChoicesCount={} | FirstFinishReason={} | Usage={}",
                    documentLabel, request.getMaxTokens(),
                    response,
                    (response != null && response.getChoices() != null) ? response.getChoices().size() : null,
                    (response != null && response.getChoices() != null && !response.getChoices().isEmpty()) ? response.getChoices().get(0).getFinishReason() : null,
                    (response != null) ? response.getUsage() : null);

            if (response == null || response.getFirstChoiceContent() == null) {
                throw new LlmApiException(
                        "LLM API returned an empty choice list for " + documentLabel + " standardization.");
            }

            String markdownOutput = response.getFirstChoiceContent().strip();

            if (markdownOutput.isBlank()) {
                throw new LlmApiException(
                        "LLM API returned blank text for " + documentLabel + " standardization.");
            }

            if (markdownOutput.equals("INVALID_JD")) {
                throw new LlmApiException(
                        "LLM could not extract any valid Job Description information from the provided input text. Please ensure the JD is not empty or corrupted.");
            }

            if (response.getUsage() != null) {
                var usage = response.getUsage();
                log.info("[LLM_USAGE] Document={} | Model={} | PromptTokens={} | CompletionTokens={} | TotalTokens={}",
                        documentLabel, response.getModel(),
                        usage.getPromptTokens(), usage.getCompletionTokens(), usage.getTotalTokens());
            }

            return markdownOutput;

        } catch (WebClientResponseException e) {
            String responseBody = e.getResponseBodyAsString();
            log.error("LLM API HTTP {} during {} standardization: {}",
                    e.getStatusCode(), documentLabel, responseBody);

            if (e.getStatusCode().value() == 401) {
                throw new LlmApiException(
                        "LLM API Authentication failed (HTTP 401). Please check the API key configuration.", e);
            }
            if (e.getStatusCode().value() == 429) {
                throw new LlmApiException(
                        "LLM API Rate Limit Exceeded (HTTP 429). Please try again in a few moments.", e);
            }
            throw new LlmApiException(
                    "LLM API error (HTTP " + e.getStatusCode() + ") during " + documentLabel +
                    " standardization: " + responseBody, e);

        } catch (LlmApiException e) {
            throw e;
        } catch (Exception e) {
            log.error("Unexpected error during {} LLM standardization: {}", documentLabel, e.getMessage(), e);
            throw new LlmApiException(
                    "Failed to standardize " + documentLabel + " via LLM: " + e.getMessage(), e);
        }
    }
}
