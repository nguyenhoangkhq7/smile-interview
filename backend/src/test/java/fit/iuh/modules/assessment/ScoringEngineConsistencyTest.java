package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.service.AssessmentScoringEngine;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class ScoringEngineConsistencyTest {

    private AssessmentScoringEngine scoringEngine;

    private static class DummyWeightProjection implements CriteriaWeightProjection {
        private final Long id;
        private final String name;
        private final Double weight;

        DummyWeightProjection(Long id, String name, Double weight) {
            this.id = id;
            this.name = name;
            this.weight = weight;
        }

        @Override public Long getCriteriaId() { return id; }
        @Override public String getCriteriaName() { return name; }
        @Override public String getPromptInstruction() { return name; }
        @Override public String getLevelPromptInstruction() { return null; }
        @Override public Double getWeightPercentage() { return weight; }
        @Override public String getEmbedding() { return null; }
        @Override public Integer getSourceDepth() { return null; }
    }

    @BeforeEach
    void setUp() {
        scoringEngine = new AssessmentScoringEngine(null);
    }

    @Test
    @DisplayName("ScoringEngine: Ad-Hoc criteria weights remain stable and consistent")
    void testAdHocCriteriaWeightStability() {
        List<AssessmentResponseDto.EvidenceItem> mustHave = List.of(
                new AssessmentResponseDto.EvidenceItem(1L, "Java Core", "REQUIRED", "Java", "Java 21", "Java 21", "matched", "ok", 20.0, 20.0, 1.0, null, false, false, null),
                new AssessmentResponseDto.EvidenceItem(2L, "Spring Boot", "REQUIRED", "Spring", "Spring 3", "Spring 3", "matched", "ok", 20.0, 20.0, 1.0, null, false, false, null)
        );

        List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems = List.of(
                new AssessmentResponseDto.AdHocEvidenceItem(null, "Redis Caching", "PREFERRED", "Redis", "Redis pub/sub", "Redis", "matched", "ok", null),
                new AssessmentResponseDto.AdHocEvidenceItem(null, "Docker Containers", "PREFERRED", "Docker", "Docker compose", "Docker", "matched", "ok", null),
                new AssessmentResponseDto.AdHocEvidenceItem(null, "Kafka Streaming", "PREFERRED", "Kafka", "Kafka streams", "Kafka", "matched", "ok", null)
        );

        List<CriteriaWeightProjection> weights = List.of(
                new DummyWeightProjection(1L, "Java Core", 20.0),
                new DummyWeightProjection(2L, "Spring Boot", 20.0)
        );

        AssessmentScoringEngine.ScoringResult result = scoringEngine.calculateWithBreakdown(
                mustHave, adHocItems, weights, SeniorityLevel.MID
        );

        assertNotNull(result);
        assertEquals(100, result.overallScore(), "Overall score should be 100% when all items are matched");
        assertNotNull(result.breakdown());
        assertEquals(100, result.breakdown().rawMustHaveScore());
        assertEquals(100, result.breakdown().rawPreferToHaveScore());
    }

    @Test
    @DisplayName("ScoringEngine: Preferred-only criteria without Must-Have should calculate fair score")
    void testPreferredOnlyCriteriaScoring() {
        List<AssessmentResponseDto.AdHocEvidenceItem> adHocItems = List.of(
                new AssessmentResponseDto.AdHocEvidenceItem(null, "Redis Caching", "PREFERRED", "Redis", "Redis pub/sub", "Redis", "matched", "ok", null),
                new AssessmentResponseDto.AdHocEvidenceItem(null, "Docker Containers", "PREFERRED", "Docker", "Docker compose", "Docker", "matched", "ok", null)
        );

        AssessmentScoringEngine.ScoringResult result = scoringEngine.calculateWithBreakdown(
                List.of(), adHocItems, List.of(), SeniorityLevel.MID
        );

        assertNotNull(result);
        assertEquals(100, result.overallScore(), "Overall score should be 100% when all preferred items are matched");
    }

    @Test
    @DisplayName("ScoringEngine: Partial status contributes default 65% of criteria weight")
    void testPartialStatusScoring() {
        List<AssessmentResponseDto.EvidenceItem> mustHave = List.of(
                new AssessmentResponseDto.EvidenceItem(1L, "Java Core", "REQUIRED", "Java", "Java 21", "Java 21", "matched", "ok", 20.0, 20.0, 1.0, null, false, false, null),
                new AssessmentResponseDto.EvidenceItem(2L, "Spring Boot", "REQUIRED", "Spring", "Spring 3", "Spring 3", "partial", "ok", 20.0, 13.0, 1.0, null, false, false, null)
        );

        List<CriteriaWeightProjection> weights = List.of(
                new DummyWeightProjection(1L, "Java Core", 20.0),
                new DummyWeightProjection(2L, "Spring Boot", 20.0)
        );

        AssessmentScoringEngine.ScoringResult result = scoringEngine.calculateWithBreakdown(
                mustHave, List.of(), weights, SeniorityLevel.MID
        );

        assertNotNull(result);
        // (100% * 20 + 65% * 20) / 40 = 82.5% -> rounds to 83%
        assertEquals(83, result.overallScore(), "Overall score should reflect 65% contribution for partial status");
    }
}
