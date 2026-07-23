package fit.iuh.modules.chunking.repository;

import fit.iuh.modules.chunking.entity.DocumentChunk;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface DocumentChunkRepository extends JpaRepository<DocumentChunk, UUID> {

    List<DocumentChunk> findBySessionIdAndDocType(String sessionId, String docType);

    void deleteBySessionId(String sessionId);

    boolean existsBySessionId(String sessionId);

    /**
     * Dense Vector Cosine Similarity Search using pgvector (<=>).
     */
    @Query(value = """
            SELECT id, session_id, doc_type, parent_id, chunk_type, domain, content, enriched_content, created_at, NULL as embedding
            FROM document_chunks
            WHERE session_id = :sessionId
              AND doc_type = :docType
              AND embedding IS NOT NULL
            ORDER BY embedding <=> cast(cast(:queryVector as text) as vector) ASC
            LIMIT :topK
            """, nativeQuery = true)
    List<DocumentChunk> searchDense(
            @Param("sessionId") String sessionId,
            @Param("docType") String docType,
            @Param("queryVector") String queryVector,
            @Param("topK") int topK
    );

    /**
     * Sparse Keyword Search using PostgreSQL Simple Full-Text Search and ILIKE.
     */
    @Query(value = """
            SELECT id, session_id, doc_type, parent_id, chunk_type, domain, content, enriched_content, created_at, NULL as embedding
            FROM document_chunks
            WHERE session_id = :sessionId
              AND doc_type = :docType
              AND (
                to_tsvector('simple', content) @@ plainto_tsquery('simple', :queryText)
                OR LOWER(content) LIKE LOWER(CONCAT('%', :queryText, '%'))
              )
            ORDER BY ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', :queryText)) DESC
            LIMIT :topK
            """, nativeQuery = true)
    List<DocumentChunk> searchSparse(
            @Param("sessionId") String sessionId,
            @Param("docType") String docType,
            @Param("queryText") String queryText,
            @Param("topK") int topK
    );
}
