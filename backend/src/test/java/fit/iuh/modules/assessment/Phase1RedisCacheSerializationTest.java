package fit.iuh.modules.assessment;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle;
import fit.iuh.modules.assessment.dto.PreparedJdContext;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.gate.EligibilityGateService.GateCheckDto;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class Phase1RedisCacheSerializationTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    @DisplayName("Serialize and deserialize PreparedJdContext to and from JSON without Jackson error")
    void testPreparedJdContextSerializationAndDeserialization() throws Exception {
        var classifiedDbCriteria = List.of(
                new ClassifiedCriteriaBundle.ClassifiedCriteria(1L, "Java Core", "Prompt 1", 10.0, "required"),
                new ClassifiedCriteriaBundle.ClassifiedCriteria(2L, "Spring Boot", "Prompt 2", 15.0, "required")
        );

        var jdExtras = List.of(
                new ClassifiedCriteriaBundle.JdExtraCriteria("Kafka", "preferred", "Evaluate Kafka experience")
        );

        var bundle = new ClassifiedCriteriaBundle(classifiedDbCriteria, jdExtras);

        var criteriaList = List.of(
                new PreparedJdContext.CriteriaWeightDto(
                        1L, "Java Core", "Instruction 1", "Level Inst 1", 10.0, null
                ),
                new PreparedJdContext.CriteriaWeightDto(
                        2L, "Spring Boot", "Instruction 2", "Level Inst 2", 15.0, null
                )
        );

        GateCheckDto gate1 = new GateCheckDto();
        gate1.setCriteriaName("YOE");
        gate1.setImportance("REQUIRED");
        gate1.setRequiredValue("2 years");

        var rawGates = List.of(gate1);

        var context = new PreparedJdContext(
                JobCategory.SOFTWARE_ENGINEERING,
                SeniorityLevel.MID,
                List.of(SeniorityLevel.FRESHER, SeniorityLevel.MID),
                bundle,
                criteriaList,
                rawGates
        );

        // 1. Serialize to JSON
        String json = objectMapper.writeValueAsString(context);
        assertNotNull(json);
        assertFalse(json.isBlank());

        // 2. Deserialize back from JSON
        PreparedJdContext deserialized = objectMapper.readValue(json, PreparedJdContext.class);

        assertNotNull(deserialized);
        assertEquals(JobCategory.SOFTWARE_ENGINEERING, deserialized.category());
        assertEquals(SeniorityLevel.MID, deserialized.targetLevel());
        assertEquals(2, deserialized.acceptedLevels().size());
        assertEquals(2, deserialized.bundle().dbCriteria().size());
        assertEquals(1, deserialized.bundle().jdExtras().size());
        assertEquals(2, deserialized.criteriaList().size());
        assertEquals("Java Core", deserialized.criteriaList().get(0).criteriaName());
        assertEquals(1, deserialized.gateRequirements().size());
        assertEquals("YOE", deserialized.gateRequirements().get(0).getCriteriaName());
    }
}