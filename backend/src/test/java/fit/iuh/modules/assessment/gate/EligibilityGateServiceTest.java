package fit.iuh.modules.assessment.gate;

import fit.iuh.modules.assessment.entity.EligibilityStatus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class EligibilityGateServiceTest {

    private EligibilityGateService gateService;

    @BeforeEach
    void setUp() {
        gateService = new EligibilityGateService(
                List.of(new YoeGateEvaluator(), new DegreeGateEvaluator()),
                null, null, null
        );
    }

    @Test
    @DisplayName("Evaluate YOE Gate - Candidate meets 2+ years requirement")
    void testYoeGatePass() {
        var gate = new EligibilityGateService.GateCheckDto();
        gate.setCriteriaName("Years of Experience");
        gate.setImportance("REQUIRED");
        gate.setRequiredValue("2.0 years");

        String cvContent = "Backend Developer (Jan 2021 - Present)\nBuilt Spring Boot microservices.";
        var result = gateService.evaluateEligibilityWithRawGates(List.of(gate), "Sample JD", cvContent);

        assertNotNull(result);
        assertEquals(EligibilityStatus.ELIGIBILITY, result.status());
        assertFalse(result.gateItems().isEmpty());
        assertEquals("PASSED", result.gateItems().get(0).status());
    }

    @Test
    @DisplayName("Evaluate Degree Gate - Candidate has Bachelor Degree")
    void testDegreeGatePass() {
        var gate = new EligibilityGateService.GateCheckDto();
        gate.setCriteriaName("Degree Qualification");
        gate.setImportance("REQUIRED");
        gate.setRequiredValue("Bachelor in Computer Science");

        String cvContent = "Education: Bachelor of Science in Information Technology, 2022.";
        var result = gateService.evaluateEligibilityWithRawGates(List.of(gate), "Sample JD", cvContent);

        assertNotNull(result);
        assertEquals(EligibilityStatus.ELIGIBILITY, result.status());
        assertEquals("PASSED", result.gateItems().get(0).status());
    }
}
