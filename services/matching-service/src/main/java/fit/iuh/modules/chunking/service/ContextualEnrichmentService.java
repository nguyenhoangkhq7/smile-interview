package fit.iuh.modules.chunking.service;

import fit.iuh.modules.chunking.entity.DocumentChunk;

import java.util.List;

public interface ContextualEnrichmentService {

    /**
     * Generates 1-2 sentence contextual headers for chunks and sets their enrichedContent.
     * Original content field is NEVER modified.
     *
     * @param chunks list of document chunks
     * @return enriched list of document chunks
     */
    List<DocumentChunk> enrich(List<DocumentChunk> chunks);
}
