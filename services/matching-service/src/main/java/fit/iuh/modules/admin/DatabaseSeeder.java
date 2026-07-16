package fit.iuh.modules.admin;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Application startup seeder that inserts default data if the tables are empty.
 *
 * <h2>What It Seeds</h2>
 * <ol>
 *   <li><strong>Super Admin user</strong> — {@code admin@smileinterview.com} /
 *       {@code admin123} (BCrypt-hashed) / role {@code ADMIN}, created only if no
 *       user with that email already exists.</li>
 *   <li><strong>System settings</strong> — {@code MATCH_SCORE_PIVOT} and
 *       {@code STATUS_WEAK_COEFF}, inserted only if the table is empty.</li>
 *   <li><strong>Level distribution rules</strong> — one row per seniority level
 *       (INTERN → LEAD), inserted only if the table is empty.</li>
 * </ol>
 *
 * <h2>Idempotency</h2>
 * All inserts are guarded by existence checks so running the seeder twice
 * (e.g., during development hot-reloads) does not create duplicate records.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DatabaseSeeder implements CommandLineRunner {

    private final UserRepository                userRepository;
    private final SystemSettingRepository       systemSettingRepository;
    private final LevelDistributionRuleRepository levelDistributionRuleRepository;
    private final PasswordEncoder               passwordEncoder;

    // ─────────────────────────────────────────────────────────────────────────
    // CommandLineRunner entry point
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public void run(String... args) {
        seedAdminUser();
        seedSystemSettings();
        seedLevelDistributionRules();
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Seed: Super Admin User
    // ─────────────────────────────────────────────────────────────────────────

    private void seedAdminUser() {
        final String adminEmail = "admin@smileinterview.com";

        if (userRepository.existsByEmail(adminEmail)) {
            log.debug("[Seeder] Admin user already exists — skipping.");
            return;
        }

        User admin = User.builder()
                .username("Admin")
                .email(adminEmail)
                .password(passwordEncoder.encode("admin123"))
                .role("ADMIN")
                .build();

        userRepository.save(admin);
        log.info("[Seeder] Super Admin user created: {}", adminEmail);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Seed: System Settings
    // ─────────────────────────────────────────────────────────────────────────

    private void seedSystemSettings() {
        seedSettingIfMissing("MATCH_SCORE_PIVOT", "50.0");
        seedSettingIfMissing("STATUS_WEAK_COEFF", "0.3");
        seedSettingIfMissing("WEAK_COEFF_INTERN_FRESHER", "0.5");
        seedSettingIfMissing("WEAK_COEFF_SENIOR_LEAD", "0.1");
        seedSettingIfMissing("MUST_HAVE_WEIGHT_RATIO", "0.8");
        seedSettingIfMissing("PREFER_TO_HAVE_WEIGHT_RATIO", "0.2");

        // Difficulty Matrix Settings
        seedSettingIfMissing("DIFF_INTERN_FRESHER_MISSING", "easy");
        seedSettingIfMissing("DIFF_INTERN_FRESHER_WEAK", "easy");
        seedSettingIfMissing("DIFF_INTERN_FRESHER_MATCHED", "medium");

        seedSettingIfMissing("DIFF_JUNIOR_MISSING", "easy");
        seedSettingIfMissing("DIFF_JUNIOR_WEAK", "medium");
        seedSettingIfMissing("DIFF_JUNIOR_MATCHED", "medium");

        seedSettingIfMissing("DIFF_MID_MISSING", "medium");
        seedSettingIfMissing("DIFF_MID_WEAK", "medium");
        seedSettingIfMissing("DIFF_MID_MATCHED", "hard");

        seedSettingIfMissing("DIFF_SENIOR_LEAD_MISSING", "medium");
        seedSettingIfMissing("DIFF_SENIOR_LEAD_WEAK", "medium");
        seedSettingIfMissing("DIFF_SENIOR_LEAD_MATCHED", "hard");
    }

    private void seedSettingIfMissing(String key, String defaultValue) {
        if (systemSettingRepository.findBySettingKey(key).isEmpty()) {
            systemSettingRepository.save(SystemSetting.builder()
                    .settingKey(key)
                    .settingValue(defaultValue)
                    .build());
            log.info("[Seeder] Seeded system setting: {} = {}", key, defaultValue);
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Seed: Level Distribution Rules
    // Mirrors the original hardcoded values in DifficultyDistributor.
    // ─────────────────────────────────────────────────────────────────────────

    private void seedLevelDistributionRules() {
        if (levelDistributionRuleRepository.count() > 0) {
            log.debug("[Seeder] Level distribution rules already seeded — skipping.");
            return;
        }

        List<LevelDistributionRule> defaults = List.of(
                // INTERN — same as FRESHER (no system-design)
                LevelDistributionRule.builder()
                        .level("INTERN")
                        .behavioralPct(40.0)
                        .technicalPct(50.0)
                        .codingPct(10.0)
                        .systemDesignPct(0.0)
                        .build(),
                // FRESHER — entry-level, no system design
                LevelDistributionRule.builder()
                        .level("FRESHER")
                        .behavioralPct(40.0)
                        .technicalPct(50.0)
                        .codingPct(10.0)
                        .systemDesignPct(0.0)
                        .build(),
                // JUNIOR — slightly more coding, still no system design
                LevelDistributionRule.builder()
                        .level("JUNIOR")
                        .behavioralPct(30.0)
                        .technicalPct(50.0)
                        .codingPct(20.0)
                        .systemDesignPct(0.0)
                        .build(),
                // MID — balanced, introduces system design
                LevelDistributionRule.builder()
                        .level("MID")
                        .behavioralPct(20.0)
                        .technicalPct(40.0)
                        .codingPct(20.0)
                        .systemDesignPct(20.0)
                        .build(),
                // SENIOR — more system design, less technical
                LevelDistributionRule.builder()
                        .level("SENIOR")
                        .behavioralPct(20.0)
                        .technicalPct(30.0)
                        .codingPct(10.0)
                        .systemDesignPct(40.0)
                        .build(),
                // LEAD — heavily system-design focused
                LevelDistributionRule.builder()
                        .level("LEAD")
                        .behavioralPct(20.0)
                        .technicalPct(20.0)
                        .codingPct(10.0)
                        .systemDesignPct(50.0)
                        .build()
        );

        levelDistributionRuleRepository.saveAll(defaults);
        log.info("[Seeder] Level distribution rules seeded for {} levels.", defaults.size());
    }
}
