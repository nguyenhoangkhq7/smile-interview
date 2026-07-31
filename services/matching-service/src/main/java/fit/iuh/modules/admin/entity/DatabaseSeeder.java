package fit.iuh.modules.admin.entity;

import fit.iuh.modules.admin.repository.LevelDistributionRuleRepository;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.rulengine.entity.CategoryCriteriaMapping;
import fit.iuh.modules.rulengine.entity.EvaluationCriteria;
import fit.iuh.modules.rulengine.entity.JobCategoryEntity;
import fit.iuh.modules.rulengine.repository.CategoryCriteriaMappingRepository;
import fit.iuh.modules.rulengine.repository.EvaluationCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCategoryEntityRepository;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class DatabaseSeeder implements CommandLineRunner {

    private final LevelDistributionRuleRepository levelRuleRepository;
    private final SystemSettingRepository settingRepository;
    private final JobCategoryEntityRepository jobCategoryRepository;
    private final EvaluationCriteriaRepository criteriaRepository;
    private final CategoryCriteriaMappingRepository mappingRepository;
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void run(String... args) {
        seedAdminUser();
        seedLevelRules();
        seedSystemSettings();
        seedJobCategories();
        seedEvaluationCriteria();
    }

    private void seedAdminUser() {
        String adminEmail = "admin@smile.com";
        if (userRepository.existsByEmail(adminEmail)) {
            return;
        }
        log.info("[DatabaseSeeder] Seeding default admin user: {}", adminEmail);
        User admin = User.builder()
                .username("System Admin")
                .email(adminEmail)
                .password(passwordEncoder.encode("admin123"))
                .role(Role.ADMIN)
                .phoneNumber("0900000000")
                .build();
        userRepository.save(admin);
        log.info("[DatabaseSeeder] Admin user created successfully.");
    }

    private void seedLevelRules() {
        if (levelRuleRepository.count() > 0) {
            return;
        }

        log.info("[DatabaseSeeder] Seeding initial level distribution rules...");

        List<LevelDistributionRule> rules = List.of(
                LevelDistributionRule.builder()
                        .level("INTERN")
                        .behavioralPct(30.0)
                        .technicalPct(50.0)
                        .codingPct(20.0)
                        .systemDesignPct(0.0)
                        .build(),

                LevelDistributionRule.builder()
                        .level("FRESHER")
                        .behavioralPct(25.0)
                        .technicalPct(50.0)
                        .codingPct(25.0)
                        .systemDesignPct(0.0)
                        .build(),

                LevelDistributionRule.builder()
                        .level("JUNIOR")
                        .behavioralPct(20.0)
                        .technicalPct(45.0)
                        .codingPct(25.0)
                        .systemDesignPct(10.0)
                        .build(),

                LevelDistributionRule.builder()
                        .level("MID")
                        .behavioralPct(15.0)
                        .technicalPct(40.0)
                        .codingPct(25.0)
                        .systemDesignPct(20.0)
                        .build(),

                LevelDistributionRule.builder()
                        .level("SENIOR")
                        .behavioralPct(15.0)
                        .technicalPct(30.0)
                        .codingPct(20.0)
                        .systemDesignPct(35.0)
                        .build(),

                LevelDistributionRule.builder()
                        .level("LEAD")
                        .behavioralPct(25.0)
                        .technicalPct(25.0)
                        .codingPct(10.0)
                        .systemDesignPct(40.0)
                        .build()
        );

        levelRuleRepository.saveAll(rules);
        log.info("[DatabaseSeeder] Seeded {} level distribution rules.", rules.size());
    }

    private void seedSystemSettings() {
        seedSettingIfAbsent(
                "STATUS_WEAK_COEFF",
                "0.3",
                "Weight multiplier applied to criteria evaluated as 'weak' (default 0.3 = 30% points awarded)"
        );

        seedSettingIfAbsent(
                "WEAK_COEFF_INTERN_FRESHER",
                "0.5",
                "Weight multiplier applied to criteria evaluated as 'weak' for Intern and Fresher levels (more lenient)"
        );

        seedSettingIfAbsent(
                "WEAK_COEFF_SENIOR_LEAD",
                "0.1",
                "Weight multiplier applied to criteria evaluated as 'weak' for Senior and Lead levels (stricter)"
        );

        seedSettingIfAbsent(
                "MUST_HAVE_WEIGHT_RATIO",
                "0.8",
                "Ratio of overall score derived from Must-Have criteria (default 0.8 = 80%)"
        );

        seedSettingIfAbsent(
                "PREFER_TO_HAVE_WEIGHT_RATIO",
                "0.2",
                "Ratio of overall score derived from Prefer-to-Have criteria (default 0.2 = 20%)"
        );

        seedSettingIfAbsent(
                "EVIDENCE_GROUNDING_THRESHOLD",
                "0.75",
                "Fuzzy string similarity threshold (0.0-1.0) for validating LLM evidence against CV markdown text"
        );

        seedSettingIfAbsent(
                "CRITERIA_BATCH_SIZE",
                "10",
                "Number of criteria sent per LLM batch call during evidence matching"
        );
        // Force update existing setting to 10 for optimal LLM evaluation speed and latency
        settingRepository.findBySettingKey("CRITERIA_BATCH_SIZE").ifPresent(setting -> {
            if ("5".equals(setting.getSettingValue()) || "1".equals(setting.getSettingValue())) {
                setting.setSettingValue("10");
                settingRepository.save(setting);
            }
        });

        seedSettingIfAbsent(
                "SELF_CONSISTENCY_RUNS",
                "1",
                "Number of parallel self-consistency runs per criteria batch for majority voting"
        );
        // Force update existing setting if it was previously 3
        settingRepository.findBySettingKey("SELF_CONSISTENCY_RUNS").ifPresent(setting -> {
            if ("3".equals(setting.getSettingValue())) {
                setting.setSettingValue("1");
                settingRepository.save(setting);
            }
        });

        seedSettingIfAbsent(
                "MAX_CONCURRENT_LLM_CALLS",
                "10",
                "Global concurrency semaphore limit for LLM API calls"
        );

        seedSettingIfAbsent(
                "INCLUDE_NOT_APPLICABLE_CRITERIA",
                "false",
                "Whether to include NOT_APPLICABLE criteria in assessment results (true = 360 degree audit, false = strict JD matching)"
        );
    }

    private void seedSettingIfAbsent(String key, String defaultValue, String description) {
        if (settingRepository.findBySettingKey(key).isEmpty()) {
            SystemSetting setting = SystemSetting.builder()
                    .settingKey(key)
                    .settingValue(defaultValue)
                    .description(description)
                    .build();
            settingRepository.save(setting);
            log.info("[DatabaseSeeder] Seeded system setting: {} = {}", key, defaultValue);
        }
    }

    private void seedJobCategories() {
        if (jobCategoryRepository.count() > 0) return;
        List<JobCategoryEntity> categories = List.of(
                JobCategoryEntity.builder().code("SOFTWARE_ENGINEERING").name("Software Engineering").parent(null).build(),
                JobCategoryEntity.builder().code("BACKEND").name("Backend Development").parent(null).build(),
                JobCategoryEntity.builder().code("FRONTEND").name("Frontend Development").parent(null).build(),
                JobCategoryEntity.builder().code("FULLSTACK").name("Fullstack Development").parent(null).build(),
                JobCategoryEntity.builder().code("DEVOPS").name("DevOps & Infrastructure").parent(null).build(),
                JobCategoryEntity.builder().code("DATA_ENGINEERING").name("Data Engineering").parent(null).build(),
                JobCategoryEntity.builder().code("AI_ML").name("AI & Machine Learning").parent(null).build(),
                JobCategoryEntity.builder().code("MOBILE").name("Mobile Development").parent(null).build(),
                JobCategoryEntity.builder().code("QA_TESTING").name("QA & Automated Testing").parent(null).build(),
                JobCategoryEntity.builder().code("OTHER").name("Other Engineering Roles").parent(null).build()
        );
        jobCategoryRepository.saveAll(categories);
        log.info("[DatabaseSeeder] Seeded {} job categories.", categories.size());
    }

    private void seedEvaluationCriteria() {
        if (criteriaRepository.count() > 0) return;
        List<EvaluationCriteria> criteriaList = List.of(
                EvaluationCriteria.builder().name("Programming Language Proficiency").category("technical").questionType("technical").promptInstruction("Evaluate proficiency in primary programming languages.").build(),
                EvaluationCriteria.builder().name("Framework & Library Mastery").category("technical").questionType("technical").promptInstruction("Evaluate experience with core frameworks.").build(),
                EvaluationCriteria.builder().name("Database Design & Optimization").category("technical").questionType("technical").promptInstruction("Evaluate knowledge of SQL/NoSQL databases.").build(),
                EvaluationCriteria.builder().name("System Design & Architecture").category("system_design").questionType("system_design").promptInstruction("Evaluate ability to design scalable systems.").build(),
                EvaluationCriteria.builder().name("Problem Solving & Algorithmic Thinking").category("coding").questionType("coding").promptInstruction("Evaluate problem solving and coding proficiency.").build(),
                EvaluationCriteria.builder().name("Teamwork & Collaboration").category("behavioral").questionType("behavioural").promptInstruction("Evaluate soft skills, teamwork, and communication.").build()
        );
        criteriaRepository.saveAll(criteriaList);

        JobCategoryEntity seCategory = jobCategoryRepository.findByCode("SOFTWARE_ENGINEERING").orElse(null);
        if (seCategory != null) {
            for (EvaluationCriteria c : criteriaList) {
                CategoryCriteriaMapping mapping = CategoryCriteriaMapping.builder()
                        .jobCategory(seCategory)
                        .evaluationCriteria(c)
                        .level("ALL")
                        .weightPercentage(100.0 / criteriaList.size())
                        .build();
                mappingRepository.save(mapping);
            }
        }
        log.info("[DatabaseSeeder] Seeded evaluation criteria and initial category mappings.");
    }
}
