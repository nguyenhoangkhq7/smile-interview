package fit.iuh.modules.questionbank;

import fit.iuh.modules.admin.entity.LevelDistributionRule;
import fit.iuh.modules.admin.entity.SystemSetting;
import fit.iuh.modules.admin.repository.LevelDistributionRuleRepository;
import fit.iuh.modules.admin.repository.SystemSettingRepository;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.questionbank.dto.EvidenceItemPair;
import fit.iuh.modules.questionbank.dto.QuestionAssignment;
import fit.iuh.modules.questionbank.dto.QuestionConfigDto;
import fit.iuh.modules.questionbank.service.DifficultyDistributor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DifficultyDistributorTest {

    @Mock
    private LevelDistributionRuleRepository levelRuleRepository;

    @Mock
    private SystemSettingRepository settingRepository;

    private DifficultyDistributor distributor;

    @BeforeEach
    void setUp() {
        distributor = new DifficultyDistributor(levelRuleRepository, settingRepository);
    }

    @Test
    @DisplayName("Distribute uses Admin Level Distribution Rules from database")
    void testDistributeWithAdminRules() {
        LevelDistributionRule adminRule = LevelDistributionRule.builder()
                .level("SENIOR")
                .behavioralPct(20.0)
                .technicalPct(40.0)
                .codingPct(10.0)
                .systemDesignPct(30.0)
                .build();

        when(levelRuleRepository.findByLevel(eq("SENIOR"))).thenReturn(Optional.of(adminRule));
        when(settingRepository.findBySettingKey(eq("MATCHED_QUESTIONS_RATIO")))
                .thenReturn(Optional.of(SystemSetting.builder().settingValue("0.6").build()));

        QuestionConfigDto config = QuestionConfigDto.builder().total(10).build();

        EvidenceItemPair item1 = new EvidenceItemPair(1L, "Architecture", "Microservices", "Spring Cloud", "matched", "Good", 10.0, "technical");
        EvidenceItemPair item2 = new EvidenceItemPair(2L, "Leadership", "Team lead", "Lead 5 devs", "matched", "Good", 10.0, "behavioural");

        List<QuestionAssignment> result = distributor.distribute(
                config,
                SeniorityLevel.SENIOR,
                85,
                List.of(item1, item2)
        );

        assertEquals(10, result.size());

        long techCount = result.stream().filter(a -> "technical".equals(a.category())).count();
        long behavCount = result.stream().filter(a -> "behavioural".equals(a.category())).count();
        long codeCount = result.stream().filter(a -> "coding".equals(a.category())).count();
        long sysCount = result.stream().filter(a -> "system_design".equals(a.category())).count();

        assertEquals(4, techCount);
        assertEquals(2, behavCount);
        assertEquals(1, codeCount);
        assertEquals(3, sysCount);
        assertNotNull(config.getDistribution());
        assertEquals(4, config.getDistribution().get("technical"));
    }

    @Test
    @DisplayName("Distribute honors custom distribution when specified in request")
    void testDistributeWithCustomDistributionOverride() {
        QuestionConfigDto customConfig = QuestionConfigDto.builder()
                .total(5)
                .distribution(Map.of(
                        "coding", 3,
                        "technical", 2,
                        "behavioral", 0
                ))
                .build();

        EvidenceItemPair item1 = new EvidenceItemPair(1L, "Algorithms", "DS & Algo", "LeetCode 300", "matched", "Good", 10.0, "coding");

        List<QuestionAssignment> result = distributor.distribute(
                customConfig,
                SeniorityLevel.JUNIOR,
                75,
                List.of(item1)
        );

        assertEquals(5, result.size());

        long codeCount = result.stream().filter(a -> "coding".equals(a.category())).count();
        long techCount = result.stream().filter(a -> "technical".equals(a.category())).count();
        long behavCount = result.stream().filter(a -> "behavioural".equals(a.category())).count();

        assertEquals(3, codeCount);
        assertEquals(2, techCount);
        assertEquals(0, behavCount);
    }
}
