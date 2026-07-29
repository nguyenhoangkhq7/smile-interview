package fit.iuh.modules.assessment.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.chunking.service.EmbeddingService;
import fit.iuh.modules.rulengine.entity.EvaluationCriteria;
import fit.iuh.modules.rulengine.repository.EvaluationCriteriaRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

/**
 * Pre-computes and persists vector embeddings for all EvaluationCriteria at application startup.
 *
 * <p>Strategy:
 * <ol>
 *   <li>On {@link ApplicationReadyEvent}, scan for criteria where {@code embedding IS NULL}.</li>
 *   <li>Call Ollama /api/embed in small batches (not per-item) to fill the gaps.</li>
 *   <li>Already-embedded criteria are skipped entirely — no re-computation.</li>
 * </ol>
 *
 * <p>Result: subsequent assessment requests read embeddings directly from DB (~0 ms)
 * instead of calling Ollama at runtime (was causing 30-second timeouts).
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CriteriaEmbeddingInitializer {

    /** Number of criteria texts sent to Ollama in a single /api/embed batch. */
    private static final int BATCH_SIZE = 20;

    private final EvaluationCriteriaRepository criteriaRepository;
    private final EmbeddingService embeddingService;
    private final ObjectMapper objectMapper;

    /**
     * Triggered once after the Spring context is fully started.
     * Runs asynchronously so it does not block the HTTP server from accepting requests.
     */
    @Async
    @EventListener(ApplicationReadyEvent.class)
    @Transactional
    public void preComputeMissingEmbeddings() {
        List<EvaluationCriteria> missing = criteriaRepository.findByEmbeddingIsNull();

        if (missing.isEmpty()) {
            log.info("[CriteriaEmbedding] All {} criteria already have embeddings. Nothing to do.",
                    criteriaRepository.count());
            return;
        }

        log.info("[CriteriaEmbedding] Found {} criteria without embeddings. Starting pre-computation...", missing.size());
        long start = System.currentTimeMillis();
        int successCount = 0;

        // Process in batches to avoid overwhelming the Ollama API
        List<List<EvaluationCriteria>> batches = partition(missing, BATCH_SIZE);
        for (List<EvaluationCriteria> batch : batches) {
            List<String> texts = new ArrayList<>();
            for (EvaluationCriteria c : batch) {
                texts.add(buildCriteriaText(c));
            }

            try {
                List<float[]> vectors = embedBatchStrings(texts);
                if (vectors.size() != batch.size()) {
                    log.warn("[CriteriaEmbedding] Batch size mismatch: expected={}, got={}. Skipping batch.",
                            batch.size(), vectors.size());
                    continue;
                }

                for (int i = 0; i < batch.size(); i++) {
                    EvaluationCriteria criteria = batch.get(i);
                    String embeddingJson = serializeEmbedding(vectors.get(i));
                    if (embeddingJson != null) {
                        criteria.setEmbedding(embeddingJson);
                        criteriaRepository.save(criteria);
                        successCount++;
                    }
                }
            } catch (Exception ex) {
                log.warn("[CriteriaEmbedding] Batch embedding failed (Ollama may not be ready yet): {}. Will retry on next startup.",
                        ex.getMessage());
            }
        }

        log.info("[CriteriaEmbedding] Pre-computation complete: {}/{} criteria embedded in {}ms.",
                successCount, missing.size(), System.currentTimeMillis() - start);
    }

    /**
     * Manually triggers re-computation for a single criteria after create/update via Admin API.
     * Skips if embedding already exists and text has not changed (caller is responsible for
     * nullifying the embedding field before calling this when the text changes).
     */
    @Transactional
    public void computeAndPersistEmbedding(EvaluationCriteria criteria) {
        if (criteria.getEmbedding() != null) {
            return; // Already computed, skip
        }
        try {
            float[] vector = embeddingService.embedQuery(buildCriteriaText(criteria));
            String embeddingJson = serializeEmbedding(vector);
            if (embeddingJson != null) {
                criteria.setEmbedding(embeddingJson);
                criteriaRepository.save(criteria);
                log.info("[CriteriaEmbedding] Computed embedding for criteria id={}, name={}",
                        criteria.getId(), criteria.getName());
            }
        } catch (Exception ex) {
            log.warn("[CriteriaEmbedding] Could not compute embedding for criteria id={}: {}",
                    criteria.getId(), ex.getMessage());
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Builds the text fed to the embedding model for a given criteria.
     * Format mirrors what AssessmentCriteriaPreparer used at runtime before this optimisation.
     */
    public static String buildCriteriaText(EvaluationCriteria c) {
        return c.getName() + ": " + (c.getPromptInstruction() != null ? c.getPromptInstruction() : "");
    }

    /**
     * Same text format, but from a CriteriaWeightProjection (used by AssessmentCriteriaPreparer).
     */
    public static String buildCriteriaText(String name, String promptInstruction) {
        return name + ": " + (promptInstruction != null ? promptInstruction : "");
    }

    /**
     * Deserializes a JSON embedding string into a float array.
     * Returns null if the string is null or malformed.
     */
    public float[] deserializeEmbedding(String json) {
        if (json == null || json.isBlank()) return null;
        try {
            float[] vector = objectMapper.readValue(json, float[].class);
            return vector.length > 0 ? vector : null;
        } catch (JsonProcessingException ex) {
            log.warn("[CriteriaEmbedding] Failed to deserialize embedding JSON: {}", ex.getMessage());
            return null;
        }
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    /**
     * Calls Ollama to embed a list of plain strings by using EmbeddingService.embedQuery
     * one by one (sequential but still avoids the N+1 problem because this runs only at startup,
     * not on every assessment request).
     *
     * If the underlying EmbeddingService ever exposes a String-list batch API we can switch here.
     */
    private List<float[]> embedBatchStrings(List<String> texts) {
        List<float[]> results = new ArrayList<>(texts.size());
        for (String text : texts) {
            results.add(embeddingService.embedQuery(text));
        }
        return results;
    }

    private String serializeEmbedding(float[] vector) {
        if (vector == null || vector.length == 0) return null;
        try {
            return objectMapper.writeValueAsString(vector);
        } catch (JsonProcessingException ex) {
            log.warn("[CriteriaEmbedding] Failed to serialize embedding vector: {}", ex.getMessage());
            return null;
        }
    }

    private <T> List<List<T>> partition(List<T> list, int size) {
        List<List<T>> parts = new ArrayList<>();
        for (int i = 0; i < list.size(); i += size) {
            parts.add(list.subList(i, Math.min(i + size, list.size())));
        }
        return parts;
    }
}
