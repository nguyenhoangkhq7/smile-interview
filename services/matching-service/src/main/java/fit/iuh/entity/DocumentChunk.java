package fit.iuh.entity;

import fit.iuh.config.FloatArrayVectorType;
import fit.iuh.entity.enums.DocumentType;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Type;
import org.hibernate.annotations.UuidGenerator;

import java.util.UUID;
@Entity
@Table(
        name = "document_chunks",
        indexes = {
                @Index(name = "idx_doc_chunks_session_id", columnList = "session_id"),
                @Index(name = "idx_doc_chunks_doc_type",   columnList = "document_type")
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DocumentChunk {

    /**
     * Auto-generated UUID primary key.
     * Uses Hibernate's {@link UuidGenerator} which maps to PostgreSQL {@code uuid} type.
     */
    @Id
    @UuidGenerator
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /**
     * Links this chunk to a specific interview session.
     * All chunks (CV + JD) that belong to the same ingest call share the same
     * {@code sessionId}.
     */
    @Column(name = "session_id", nullable = false, length = 128)
    private String sessionId;

    /**
     * Indicates whether this chunk originated from the candidate's CV or the
     * job description (JD). Stored as a plain VARCHAR in the database.
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "document_type", nullable = false, length = 10)
    private DocumentType documentType;

    /**
     * The raw text content of this chunk after Markdown standardization and
     * token-based splitting. Stored as PostgreSQL {@code TEXT} (unlimited length).
     */
    @Column(name = "chunk_text", nullable = false, columnDefinition = "TEXT")
    private String chunkText;

    /**
     * The 2560-dimensional embedding vector produced by Ollama
     * {@code qwen3-embedding:4b}. Stored as PostgreSQL {@code vector(2560)}.
     *
     * <p>The {@link FloatArrayVectorType} Hibernate {@code UserType} handles the
     * mapping between Java {@code float[]} and the PostgreSQL {@code vector} extension
     * type via the {@code pgvector} JDBC library.
     */
    @Type(FloatArrayVectorType.class)
    @Column(name = "embedding", columnDefinition = "vector(2560)")
    private float[] embedding;
}
