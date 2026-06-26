package fit.iuh.repository;

import fit.iuh.entity.DocumentChunk;
import fit.iuh.entity.enums.DocumentType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

/**
 * Spring Data JPA repository for {@link DocumentChunk} entities.
 *
 * <p>Provides standard CRUD operations via {@link JpaRepository} as well as
 * custom queries to retrieve and manage chunks per interview session.
 */
@Repository
public interface DocumentChunkRepository extends JpaRepository<DocumentChunk, UUID> {

    /**
     * Returns all chunks belonging to a specific interview session,
     * ordered by document type (CV before JD) for predictable retrieval.
     *
     * @param sessionId the unique interview session identifier
     * @return ordered list of {@link DocumentChunk} for that session
     */
    List<DocumentChunk> findBySessionIdOrderByDocumentTypeAsc(String sessionId);

    /**
     * Returns all chunks of a given type (CV or JD) for a specific session.
     *
     * @param sessionId    the unique interview session identifier
     * @param documentType the document type filter ({@code CV} or {@code JD})
     * @return list of matching {@link DocumentChunk} entities
     */
    List<DocumentChunk> findBySessionIdAndDocumentType(String sessionId, DocumentType documentType);

    /**
     * Counts how many chunks exist for a given session and document type.
     * Used primarily for validation and response building.
     *
     * @param sessionId    the unique interview session identifier
     * @param documentType the document type ({@code CV} or {@code JD})
     * @return the count of matching chunks
     */
    long countBySessionIdAndDocumentType(String sessionId, DocumentType documentType);

    /**
     * Deletes all chunks associated with a session. Useful for re-ingestion.
     *
     * @param sessionId the unique interview session identifier
     */
    @Modifying
    @Query("DELETE FROM DocumentChunk dc WHERE dc.sessionId = :sessionId")
    void deleteAllBySessionId(@Param("sessionId") String sessionId);

    /**
     * Checks whether any chunks have already been stored for a given session.
     *
     * @param sessionId the unique interview session identifier
     * @return {@code true} if at least one chunk exists for this session
     */
    boolean existsBySessionId(String sessionId);
}
