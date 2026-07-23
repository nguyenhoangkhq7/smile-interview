package fit.iuh.modules.chunking.service;

import fit.iuh.modules.chunking.entity.DocumentChunk;

import java.util.List;

public interface EmbeddingService {

    /**
     * Generates vector embeddings for a list of document chunks using Ollama batch /api/embed API.
     * Uses enrichedContent if present, otherwise falls back to content.
     *
     * @param chunks list of document chunks
     * @return list of document chunks populated with vector embeddings
     */
    List<DocumentChunk> embedBatch(List<DocumentChunk> chunks);

    /**
     * Generates vector embedding for a single query text (e.g. skill/criteria name).
     *
     * @param queryText query string
     * @return float array vector
     */
    float[] embedQuery(String queryText);
}
