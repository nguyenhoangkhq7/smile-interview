package fit.iuh.modules.admin;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Spring Data JPA repository for {@link SystemSetting}.
 */
@Repository
public interface SystemSettingRepository extends JpaRepository<SystemSetting, String> {

    /**
     * Finds a system setting by its key.
     *
     * @param settingKey the unique setting key (e.g., "MATCH_SCORE_PIVOT")
     * @return an {@link Optional} containing the setting if found
     */
    Optional<SystemSetting> findBySettingKey(String settingKey);

    /**
     * Convenience method: reads the double value for a given key,
     * returning the provided default if the key is absent or unparseable.
     *
     * @param settingKey   the setting key to look up
     * @param defaultValue fallback value used if key is missing or malformed
     * @return parsed double value, or {@code defaultValue}
     */
    default double getDouble(String settingKey, double defaultValue) {
        return findBySettingKey(settingKey)
                .map(s -> {
                    try {
                        return Double.parseDouble(s.getSettingValue());
                    } catch (NumberFormatException e) {
                        return defaultValue;
                    }
                })
                .orElse(defaultValue);
    }
}
