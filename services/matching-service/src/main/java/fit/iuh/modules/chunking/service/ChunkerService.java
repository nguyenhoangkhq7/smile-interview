package fit.iuh.modules.chunking.service;

import fit.iuh.modules.chunking.entity.DocumentChunk;

import java.util.List;

public interface ChunkerService {

    /**
     * Parse and chunk a standardized Markdown CV or JD document into structure-aware chunks.
     *
     * @param markdownContent standardized Markdown text
     * @param sessionId       session ID
     * @param docType         "cv" or "jd"
     * @return list of DocumentChunk entities ready to be enriched/embedded/persisted
     */
    List<DocumentChunk> chunk(String markdownContent, String sessionId, String docType);
}
