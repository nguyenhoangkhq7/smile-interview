package fit.iuh.modules.chunking.service;

import fit.iuh.modules.chunking.entity.DocumentChunk;

import java.util.List;

public interface RetrievalService {

    /**
     * Perform Hybrid Search (Dense Vector + Full-Text Keyword FTS + Java RRF Fusion)
     * to retrieve relevant chunks for a query string.
     *
     * @param sessionId session ID
     * @param docType   "cv" or "jd"
     * @param queryText search query or skill name
     * @param topK      maximum chunks to retrieve
     * @return top-K DocumentChunks
     */
    List<DocumentChunk> retrieveRelevantChunks(String sessionId, String docType, String queryText, int topK);

    /**
     * Retrieve a targeted, concise CV Markdown context snippet for a batch of evaluation criteria skills.
     * Guaranteed to return ORIGINAL raw CV text (content field), NEVER enriched_content.
     *
     * @param sessionId      session ID
     * @param criteriaSkills list of criteria names or skill keywords in the current batch
     * @param maxChunks      maximum total child chunks to assemble
     * @return formatted CV text snippet containing relevant child chunks and parent project overviews
     */
    String retrieveRelevantCvContext(String sessionId, List<String> criteriaSkills, int maxChunks);
}
