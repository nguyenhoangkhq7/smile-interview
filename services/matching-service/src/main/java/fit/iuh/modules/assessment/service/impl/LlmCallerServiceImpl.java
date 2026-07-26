package fit.iuh.modules.assessment.service.impl;

import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.exception.LlmApiException;
import fit.iuh.modules.assessment.service.LlmCallerService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;


import java.util.List;
import java.util.Map;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
public class LlmCallerServiceImpl implements LlmCallerService {

    private static final Map<String, String> JSON_RESPONSE_FORMAT = Map.of("type", "json_object");

    private final AppProperties appProperties;
    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;
    private final Semaphore globalLlmSemaphore = new Semaphore(10, true);

    public LlmCallerServiceImpl(
            AppProperties appProperties,
            @Qualifier("llmWebClient") WebClient llmWebClient,
            ObjectMapper objectMapper) {
        this.appProperties = appProperties;
        this.llmWebClient = llmWebClient;
        this.objectMapper = objectMapper;
    }

    @Override
    public String callLlmBlockingWithSemaphore(String systemPrompt, String userPrompt) {
        boolean acquired = false;
        try {
            acquired = globalLlmSemaphore.tryAcquire(60, TimeUnit.SECONDS);
            if (!acquired) {
                throw new LlmApiException("System LLM concurrency limit reached. Please try again later.");
            }
            return callLlmBlocking(systemPrompt, userPrompt);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new LlmApiException("Interrupted waiting for LLM concurrency permit.", e);
        } finally {
            if (acquired) {
                globalLlmSemaphore.release();
            }
        }
    }

    @Override
    public String callLlmBlocking(String systemPrompt, String userPrompt) {
        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .maxTokens(appProperties.getLlm().getMaxTokens())
                .temperature(0.2)
                .stream(false)
                .responseFormat(JSON_RESPONSE_FORMAT)
                .messages(List.of(
                        LlmChatRequest.Message.system(systemPrompt),
                        LlmChatRequest.Message.user(userPrompt)
                ))
                .build();

        int maxRetries = 3;
        for (int i = 0; i <= maxRetries; i++) {
            try {
                String responseBody = llmWebClient.post()
                        .uri(appProperties.getLlm().getChatPath())
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(String.class)
                        .block();

                if (responseBody == null || responseBody.isBlank()) {
                    throw new LlmApiException("LLM API returned empty HTTP body during assessment.");
                }

                if (responseBody.contains("\"error\"") && (responseBody.contains("\"message\"") || responseBody.contains("\"code\""))) {
                    throw new LlmApiException("LLM API returned error JSON during assessment: " + responseBody);
                }

                // Deserialise from the already-fetched responseBody string — no second HTTP call.
                LlmChatResponse response;
                try {
                    response = objectMapper.readValue(responseBody, LlmChatResponse.class);
                } catch (Exception parseEx) {
                    throw new LlmApiException("LLM response parse failed: " + parseEx.getMessage() + " | body=" + responseBody, parseEx);
                }

                if (response.getFirstChoiceContent() == null) {
                    throw new LlmApiException("LLM API returned empty assessment response. Response: " + responseBody);
                }

                if (response.getUsage() != null) {
                    var usage = response.getUsage();
                    log.info("[LLM_USAGE] Model={} | Input={} | Output={} | Total={}",
                            response.getModel(),
                            usage.getPromptTokens(),
                            usage.getCompletionTokens(),
                            usage.getTotalTokens());
                }

                return response.getFirstChoiceContent().strip();

            } catch (WebClientResponseException e) {
                if (e.getStatusCode().value() == 400 && request.getResponseFormat() != null) {
                    log.warn("[LlmCaller] Model '{}' rejected response_format (400 Bad Request). Retrying without response_format...", appProperties.getLlm().getModel());
                    request = LlmChatRequest.builder()
                            .model(appProperties.getLlm().getModel())
                            .maxTokens(appProperties.getLlm().getMaxTokens())
                            .temperature(0.2)
                            .stream(false)
                            .messages(request.getMessages())
                            .build();
                    continue;
                }
                if (e.getStatusCode().value() == 429 && i < maxRetries) {
                    log.warn("[LlmCaller] LLM 429 — retrying after 35s...");
                    sleepQuietly(35_000);
                    continue;
                }
                throw new LlmApiException("LLM HTTP " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
            } catch (LlmApiException e) {
                throw e;
            } catch (Exception e) {
                log.error("[LlmCaller] LLM call failed (attempt {}/{}): {}", i + 1, maxRetries + 1, e.getMessage());
                if (i >= maxRetries) {
                    throw new LlmApiException("LLM call failed after " + (maxRetries + 1) + " attempts: " + e.getMessage(), e);
                }
                sleepQuietly(2000);
            }
        }
        throw new LlmApiException("LLM call failed unexpectedly.");
    }

    private void sleepQuietly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
