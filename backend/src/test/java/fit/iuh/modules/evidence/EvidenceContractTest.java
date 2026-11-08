package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.SkillGapResultDto;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class EvidenceContractTest {
    @Test void adaptiveDefaultsAllowMoreThanThreeQuestionsAndKeepExplicitLegacyCaps() throws Exception {
        assertThat(EvidenceDtos.Config.defaults().maxPerObjective()).isEqualTo(8);
        var mapper = new ObjectMapper();
        var explicit = mapper.readValue("""
                {"mode":"MIXED","max_questions":20,"duration_seconds":1800,"max_questions_per_objective":12}
                """, EvidenceDtos.Config.class);
        assertThat(explicit.maxPerObjective()).isEqualTo(12);
        try (var factory = jakarta.validation.Validation.buildDefaultValidatorFactory()) {
            assertThat(factory.getValidator().validate(explicit)).isEmpty();
            var invalid = new EvidenceDtos.Config("MIXED", null, 20, 1800, 41);
            assertThat(factory.getValidator().validate(invalid)).isNotEmpty();
        }
    }
    @Test void interactionModeSurvivesJsonAndOldConfigsDefaultToText() throws Exception {
        var mapper = new ObjectMapper();
        String legacy = "{\"mode\":\"MIXED\",\"max_questions\":10,\"duration_seconds\":900,\"max_questions_per_objective\":3}";
        assertThat(mapper.readValue(legacy, EvidenceDtos.Config.class).interactionMode()).isEqualTo("TEXT");
        var voice = mapper.readValue(legacy.replace("\"MIXED\"", "\"MIXED\",\"interaction_mode\":\"VOICE\""), EvidenceDtos.Config.class);
        assertThat(mapper.valueToTree(voice).path("interaction_mode").asText()).isEqualTo("VOICE");
    }
    @Test
    void c2ContextSurvivesJavaRoundtrip() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        String input = """
                {"jd_skill_id":"postgresql", "importance_weight":0.8,
                 "required_proficiency":4, "candidate_proficiency":3,
                 "jd_reasoning":"diagnose performance", "jd_evidence_spans":["Optimize SQL"],
                 "job_tasks":[{"description":"Optimize SQL", "required_level":4}],
                 "c_evidence":0.6, "recency_flag":true, "degraded":true, "flags":["fallback"]}
                """;
        var dto = mapper.readValue(input, SkillGapResultDto.class);
        var output = mapper.valueToTree(dto);
        assertThat(output.path("importance_weight").asDouble()).isEqualTo(0.8);
        assertThat(output.path("job_tasks").get(0).path("required_level").asInt()).isEqualTo(4);
        assertThat(output.path("jd_evidence_spans").get(0).asText()).isEqualTo("Optimize SQL");
        assertThat(output.path("recency_flag").asBoolean()).isTrue();
    }
}
