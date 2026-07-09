package fit.iuh.modules.admin;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * JPA Entity for the {@code system_settings} table.
 *
 * <p>A generic key-value store for global numeric/string configuration values.
 * Replaces magic numbers scattered across service classes.
 *
 * <h3>Known Keys</h3>
 * <ul>
 *   <li>{@code MATCH_SCORE_PIVOT} — the pivot score (default {@code 50.0}) used in
 *       {@link fit.iuh.modules.questionbank.DifficultyDistributor} to calculate the
 *       shift factor {@code f}.</li>
 *   <li>{@code STATUS_WEAK_COEFF} — points coefficient for a "weak" evidence status
 *       (default {@code 0.3}) used in {@link fit.iuh.modules.assessment.ScoringService}.</li>
 * </ul>
 *
 * <h3>Type Safety</h3>
 * Values are stored as strings. Callers must cast to the appropriate type
 * (usually {@code Double}) using {@code Double.parseDouble(settingValue)}.
 * Always supply a sensible fallback in case the key is absent.
 */
@Entity
@Table(name = "system_settings")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SystemSetting {

    /**
     * Unique configuration key (e.g., {@code "MATCH_SCORE_PIVOT"}).
     * Acts as the primary key of the table.
     */
    @Id
    @Column(name = "setting_key", nullable = false, length = 100)
    private String settingKey;

    /**
     * String-encoded configuration value (e.g., {@code "50.0"}).
     * Callers are responsible for parsing to the appropriate type.
     */
    @Column(name = "setting_value", nullable = false, length = 500)
    private String settingValue;
}
