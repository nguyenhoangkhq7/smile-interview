package fit.iuh.modules.rulengine;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * JPA Entity for the {@code job_categories} table.
 *
 * <p>Implements an <strong>Adjacency List</strong> self-referencing tree where each node
 * knows its direct parent. The {@code JobCriteriaRepository} uses a PostgreSQL
 * {@code WITH RECURSIVE} CTE to traverse from any leaf node up to the root, aggregating
 * all applicable evaluation criteria along the way.
 *
 * <p>Example tree:
 * <pre>
 *   SOFTWARE_ENGINEERING (root, id=1)
 *     └─ BACKEND (id=2, parent=1)
 *     └─ FRONTEND (id=3, parent=1)
 *     └─ DEVOPS (id=5, parent=1)
 * </pre>
 */
@Entity
@Table(name = "job_categories")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class JobCategoryEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", updatable = false, nullable = false)
    private Long id;

    /**
     * Category name — must match one of the {@link fit.iuh.modules.assessment.JobCategory}
     * enum constants (e.g., "BACKEND", "FRONTEND").
     */
    @Column(name = "name", nullable = false, unique = true, length = 100)
    private String name;

    /**
     * Self-referencing parent — {@code null} for root nodes (e.g., SOFTWARE_ENGINEERING).
     * Fetched lazily to avoid N+1 issues; the recursive CTE handles tree traversal in SQL.
     */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "parent_id")
    private JobCategoryEntity parent;

    /**
     * Direct children of this category node.
     * Used for tree-building utilities — not used in the hot-path CTE query.
     */
    @OneToMany(mappedBy = "parent", fetch = FetchType.LAZY)
    private List<JobCategoryEntity> children;
}
