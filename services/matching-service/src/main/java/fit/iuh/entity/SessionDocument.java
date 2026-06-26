package fit.iuh.entity;

import fit.iuh.entity.enums.DocumentType;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * JPA Entity persisting the full Markdown content of a CV or JD document for a given session.
 *
 * <h3>Purpose</h3>
 * During ingestion, the raw PDF is converted to structured Markdown via the LLM
 * (Step 2 of the pipeline). This entity stores that Markdown verbatim — before chunking —
 * so that downstream modules can retrieve the complete, un-fragmented document
 * without having to re-join the chunks from {@link DocumentChunk}.
 *
 * <h3>Why Not Just Re-join Chunks?</h3>
 * The chunking step introduces 150-token overlaps between adjacent chunks. Re-joining
 * chunks would duplicate content and produce text that differs from the original Markdown.
 * Storing the source Markdown here is the canonical, zero-loss approach.
 *
 * <h3>Module Usage</h3>
 * <ul>
 *   <li><strong>Module 2 (Assessment):</strong> {@code AssessmentService} reads the full
 *       CV + JD Markdown directly from this table — 2 DB lookups, no chunk reassembly.</li>
 *   <li><strong>Module 3 (Question Bank):</strong> May still use {@link DocumentChunk} for
 *       semantic cross-matching via pgvector cosine similarity.</li>
 * </ul>
 *
 * <h3>Unique Constraint</h3>
 * A composite unique index on {@code (session_id, document_type)} ensures each session
 * has exactly one CV document and one JD document.
 */
@Entity
@Table(
        name = "session_documents",
        indexes = {
                @Index(name = "idx_session_docs_session_id", columnList = "session_id"),
                @Index(
                        name = "idx_session_docs_session_type_unique",
                        columnList = "session_id, document_type",
                        unique = true
                )
        }
)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SessionDocument {

    /** Auto-generated UUID primary key. */
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /**
     * Links this document to a specific interview session.
     * All session_documents for the same session share this value.
     */
    @Column(name = "session_id", nullable = false, length = 128)
    private String sessionId;

    /**
     * Indicates whether this document is the candidate's CV or the Job Description.
     * Together with {@code sessionId}, forms the unique key for this table.
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "document_type", nullable = false, length = 10)
    private DocumentType documentType;

    /**
     * The full Markdown content produced by the LLM standardization step.
     *
     * <p>Stored as PostgreSQL {@code TEXT} (unlimited length) to accommodate
     * lengthy CVs or verbose job descriptions without truncation.
     *
     * <p>This field contains the complete, un-chunked document — no overlapping
     * content, no missing sections. It is the single source of truth for the
     * document's content within this session.
     */
    @Column(name = "markdown_content", nullable = false, columnDefinition = "TEXT")
    private String markdownContent;

    /**
     * Timestamp when this document was first persisted.
     * Set automatically in the {@link PrePersist} lifecycle callback; never updated.
     */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** Automatically sets {@link #createdAt} before the initial DB insert. */
    @PrePersist
    void onPrePersist() {
        this.createdAt = LocalDateTime.now();
    }
}
