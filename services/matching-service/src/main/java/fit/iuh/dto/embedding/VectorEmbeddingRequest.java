package fit.iuh.dto.embedding;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VectorEmbeddingRequest {

    /**
     * The embedding model identifier (e.g., {@code text-embedding-3-small}).
     * Must produce {@code 1536}-dimensional vectors to match the database schema.
     */
    @JsonProperty("model")
    private String model;

    /**
     * One or more text strings to embed. Each entry maps to one embedding vector
     * in the response {@code data} array. We always send as a list for consistency.
     */
    @JsonProperty("input")
    private List<String> input;
}
