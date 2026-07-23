package fit.iuh.modules.chunking.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Entity
@Table(
        name = "document_chunks",
        indexes = {
                @Index(name = "idx_document_chunks_session_doc", columnList = "session_id, doc_type")
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DocumentChunk {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "session_id", nullable = false, length = 128)
    private String sessionId;

    @Column(name = "doc_type", nullable = false, length = 10)
    private String docType; // "cv" | "jd"

    @Column(name = "parent_id")
    private UUID parentId;

    @Column(name = "chunk_type", nullable = false, length = 50)
    private String chunkType; // "project_overview" | "domain_child" | "flat_section"

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "domain", columnDefinition = "jsonb")
    private List<String> domain;

    @Column(name = "content", nullable = false, columnDefinition = "text")
    private String content; // Original CV/JD text. MUST be used for Assessment & Grounding.

    @Column(name = "enriched_content", columnDefinition = "text")
    private String enrichedContent; // Context-enriched text. Used ONLY for embeddings.

    @Column(name = "embedding", columnDefinition = "vector(1024)")
    private float[] embedding;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    void onPrePersist() {
        this.createdAt = LocalDateTime.now();
    }
}
