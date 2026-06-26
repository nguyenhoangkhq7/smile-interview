package fit.iuh.dto.embedding;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Response DTO for Ollama /api/embed API.
 *
 * <p>Ollama response format:
 * <pre>
 * {
 *   "model": "qwen3-embedding-4b",
 *   "embeddings": [
 *     [0.0123, -0.0456, ...]
 *   ]
 * }
 * </pre>
 */
@Data
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class VectorEmbeddingResponse {

    @JsonProperty("model")
    private String model;

    /**
     * The generated embedding vectors.
     * Ollama returns a 2D list of double precision values (one array of floats per input string).
     */
    @JsonProperty("embeddings")
    private List<List<Double>> embeddings;

    /**
     * Convenience helper to extract the first embedding vector and convert it
     * from Double List to primitive float[].
     *
     * @return the first float[] embedding, or null if none exist
     */
    public float[] getFirstEmbedding() {
        if (embeddings == null || embeddings.isEmpty()) {
            return null;
        }
        List<Double> firstVector = embeddings.get(0);
        if (firstVector == null || firstVector.isEmpty()) {
            return null;
        }

        float[] result = new float[firstVector.size()];
        for (int i = 0; i < firstVector.size(); i++) {
            result[i] = firstVector.get(i).floatValue();
        }
        return result;
    }
}
