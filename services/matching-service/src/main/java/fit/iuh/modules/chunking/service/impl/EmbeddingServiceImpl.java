package fit.iuh.modules.chunking.service.impl;

import fit.iuh.config.AppProperties;
import fit.iuh.modules.chunking.entity.DocumentChunk;
import fit.iuh.modules.chunking.service.EmbeddingService;
import lombok.Builder;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
public class EmbeddingServiceImpl implements EmbeddingService {

    private final WebClient ollamaWebClient;
    private final AppProperties appProperties;

    public EmbeddingServiceImpl(AppProperties appProperties) {
        this.appProperties = appProperties;
        this.ollamaWebClient = WebClient.builder()
                .baseUrl(appProperties.getOllama().getBaseUrl())
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(10 * 1024 * 1024))
                .build();
    }

    @Override
    public List<DocumentChunk> embedBatch(List<DocumentChunk> chunks) {
        if (chunks == null || chunks.isEmpty()) {
            return List.of();
        }

        long start = System.currentTimeMillis();
        String model = resolveEmbeddingModel();

        List<String> inputTexts = new ArrayList<>();
        for (DocumentChunk chunk : chunks) {
            inputTexts.add(chunk.getContent() != null ? chunk.getContent() : "");
        }

        try {
            OllamaEmbedRequest request = OllamaEmbedRequest.builder()
                    .model(model)
                    .input(inputTexts)
                    .build();

            OllamaEmbedResponse response = ollamaWebClient.post()
                    .uri("/api/embed")
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(OllamaEmbedResponse.class)
                    .timeout(Duration.ofSeconds(180))
                    .block();

            if (response != null && response.getEmbeddings() != null && response.getEmbeddings().size() == chunks.size()) {
                List<float[]> embeddings = response.getEmbeddings();
                for (int i = 0; i < chunks.size(); i++) {
                    chunks.get(i).setEmbedding(normalizeTo1024(embeddings.get(i)));
                }
                int rawDim = embeddings.isEmpty() ? 0 : embeddings.get(0).length;
                log.info("[Embedding] Batch embedded {} chunks via Ollama /api/embed (model: {}, raw dim: {}, normalized dim: 1024) in {}ms",
                        chunks.size(), model, rawDim, System.currentTimeMillis() - start);
            } else {
                log.warn("[Embedding] Ollama /api/embed response count mismatch or empty for batch of size {} using model {}", chunks.size(), model);
            }

        } catch (org.springframework.web.reactive.function.client.WebClientResponseException.NotFound e) {
            log.warn("[Embedding] Ollama model '{}' not found (HTTP 404). If container just started, model pull may still be in progress. Run: docker exec -it ollama_local ollama pull {}", model, model);
        } catch (Exception e) {
            log.error("[Embedding] Error calling Ollama /api/embed for model {}: {}", model, e.getMessage());
        }

        return chunks;
    }

    @Override
    public float[] embedQuery(String queryText) {
        if (queryText == null || queryText.isBlank()) {
            return null;
        }

        String model = resolveEmbeddingModel();

        try {
            OllamaEmbedRequest request = OllamaEmbedRequest.builder()
                    .model(model)
                    .input(List.of(queryText))
                    .build();

            OllamaEmbedResponse response = ollamaWebClient.post()
                    .uri("/api/embed")
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(OllamaEmbedResponse.class)
                    .timeout(Duration.ofSeconds(30))
                    .block();

            if (response != null && response.getEmbeddings() != null && !response.getEmbeddings().isEmpty()) {
                return normalizeTo1024(response.getEmbeddings().get(0));
            }
        } catch (org.springframework.web.reactive.function.client.WebClientResponseException.NotFound e) {
            log.warn("[Embedding] Ollama model '{}' not found (HTTP 404) for query embedding.", model);
        } catch (Exception e) {
            log.error("[Embedding] Error embedding query string: {}", e.getMessage());
        }

        return null;
    }

    private String resolveEmbeddingModel() {
        if (appProperties != null && appProperties.getOllama() != null) {
            String m = appProperties.getOllama().getEmbeddingModel();
            if (m != null && !m.isBlank()) {
                return m;
            }
        }
        return "bge-m3";
    }

    private float[] normalizeTo1024(float[] vector) {
        if (vector == null) {
            return null;
        }
        if (vector.length == 1024) {
            return vector;
        }
        return java.util.Arrays.copyOf(vector, 1024);
    }

    @Data
    @Builder
    private static class OllamaEmbedRequest {
        private String model;
        private List<String> input;
    }

    @Data
    private static class OllamaEmbedResponse {
        private String model;
        private List<float[]> embeddings;
    }
}
