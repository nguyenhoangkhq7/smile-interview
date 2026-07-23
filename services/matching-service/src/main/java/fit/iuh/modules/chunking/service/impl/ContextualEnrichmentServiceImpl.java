package fit.iuh.modules.chunking.service.impl;

import fit.iuh.config.AppProperties;
import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.service.ContextualEnrichmentService;
import lombok.Builder;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;

@Slf4j
@Service
public class ContextualEnrichmentServiceImpl implements ContextualEnrichmentService {

    private final WebClient ollamaWebClient;
    private final AppProperties appProperties;

    public ContextualEnrichmentServiceImpl(AppProperties appProperties) {
        this.appProperties = appProperties;
        this.ollamaWebClient = WebClient.builder()
                .baseUrl(appProperties.getOllama().getBaseUrl())
                .build();
    }

    private final java.util.concurrent.Semaphore concurrencySemaphore = new java.util.concurrent.Semaphore(2, true);

    @Override
    public List<DocumentChunk> enrich(List<DocumentChunk> chunks) {
        if (chunks == null || chunks.isEmpty()) {
            return List.of();
        }

        long start = System.currentTimeMillis();
        String model = resolveContextModel();

        List<CompletableFuture<Void>> futures = new ArrayList<>();

        for (DocumentChunk chunk : chunks) {
            if ("project_overview".equalsIgnoreCase(chunk.getChunkType()) || chunk.getContent() == null) {
                chunk.setEnrichedContent(chunk.getContent());
                continue;
            }

            CompletableFuture<Void> future = CompletableFuture.runAsync(() -> {
                try {
                    concurrencySemaphore.acquire();
                    try {
                        String prompt = String.format(
                                "Here is a snippet from a candidate's CV:\n\"%s\"\n\nProvide 1 brief summary sentence placing this engineering snippet into context. Write in English. Output ONLY the 1 sentence, no fluff.",
                                chunk.getContent()
                        );

                        OllamaGenerateRequest request = OllamaGenerateRequest.builder()
                                .model(model)
                                .prompt(prompt)
                                .stream(false)
                                .build();

                        OllamaGenerateResponse response = ollamaWebClient.post()
                                .uri("/api/generate")
                                .bodyValue(request)
                                .retrieve()
                                .bodyToMono(OllamaGenerateResponse.class)
                                .timeout(Duration.ofSeconds(120))
                                .block();

                        if (response != null && response.getResponse() != null && !response.getResponse().isBlank()) {
                            String contextHeader = response.getResponse().strip();
                            chunk.setEnrichedContent(contextHeader + "\n" + chunk.getContent());
                        } else {
                            chunk.setEnrichedContent(chunk.getContent());
                        }
                    } finally {
                        concurrencySemaphore.release();
                    }
                } catch (Exception e) {
                    log.warn("[Enrichment] Fallback for chunk id={} due to: {}", chunk.getId(), e.getMessage());
                    chunk.setEnrichedContent(chunk.getContent());
                }
            });

            futures.add(future);
        }

        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
        log.info("[Enrichment] Enriched {} chunks in {}ms using model {}", chunks.size(), System.currentTimeMillis() - start, model);

        return chunks;
    }

    private String resolveContextModel() {
        if (appProperties != null && appProperties.getOllama() != null) {
            String m = appProperties.getOllama().getContextModel();
            if (m != null && !m.isBlank()) {
                return m;
            }
        }
        return "qwen2.5:3b-instruct";
    }

    @Data
    @Builder
    private static class OllamaGenerateRequest {
        private String model;
        private String prompt;
        private boolean stream;
    }

    @Data
    private static class OllamaGenerateResponse {
        private String response;
    }
}
