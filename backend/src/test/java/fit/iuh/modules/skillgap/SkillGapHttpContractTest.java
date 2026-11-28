package fit.iuh.modules.skillgap;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import fit.iuh.config.AppProperties;
import fit.iuh.modules.evidence.EvidenceAiClient;
import fit.iuh.modules.evidence.EvidenceInputs;
import fit.iuh.modules.evidence.EvidenceJson;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.skillgap.client.SkillGapClient;
import org.junit.jupiter.api.Test;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import static org.assertj.core.api.Assertions.assertThat;

class SkillGapHttpContractTest {
    @Test void taskObjectsSurviveRealAnalysisAndInterviewHttpConverters() throws Exception {
        var mapper = new ObjectMapper();
        var analysisRequest = new AtomicReference<String>();
        var interviewRequest = new AtomicReference<String>();
        String response = """
                {"analysis_id":"test","skills":[{
                  "jd_skill_id":"postgresql","semantic_alignment":"PARTIAL",
                  "jd_skill_name":"Tối ưu PostgreSQL","matched_cv_skill_name":"Quản trị PostgreSQL",
                  "priority":0,
                  "required_proficiency":4,"cv_evidence_spans":["SQL"],
                  "importance_weight":0.9,
                  "job_tasks":[{"task_id":"sql-1","description":"Tối ưu truy vấn SQL",
                    "required_level":4,"evidence_spans":["Tối ưu truy vấn"],
                    "metadata":{"optional":false,"tags":["SQL","EXPLAIN"],"note":null}}]
                }],"report":{"matching_score":0.85,"degraded":false,
                  "eligibility":{"state":"complete","results":[{"condition_id":"C1","type":"gpa",
                    "priority":"required","jd_quote":"GPA > 3.0/4.0","cv_quotes":["GPA 2.9/4.0"],
                    "status":"not_met","reason":"GPA dưới ngưỡng yêu cầu."}]},"cv_skills":[
                  {"skill_id":"helm","skill_name":"Helm","type":"explicit","confidence":0.95,
                   "evidence_spans":["Deployed with Helm"]}]}}
                """;
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/v1/pipeline/analyze", exchange -> {
            analysisRequest.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] body = response.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body); exchange.close();
        });
        server.createContext("/api/v2/interview/start", exchange -> {
            interviewRequest.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] body = "{\"snapshot\":{},\"public\":{}}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body); exchange.close();
        });
        server.start();
        try {
            AppProperties properties = new AppProperties();
            properties.getAi().getFastapi().setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            var gaps = new SkillGapClient(properties);
            var result = gaps.analyzeGap("test", "CV tiếng Việt", "JD tiếng Việt");
            var original = mapper.readTree(response);
            var roundtrip = mapper.valueToTree(result);
            assertThat(roundtrip.path("skills").get(0).path("jd_skill_name").asText()).isEqualTo("Tối ưu PostgreSQL");
            assertThat(roundtrip.path("skills").get(0).path("matched_cv_skill_name").asText()).isEqualTo("Quản trị PostgreSQL");
            assertThat(roundtrip.path("skills").get(0).path("required_proficiency").asDouble()).isEqualTo(4.0);
        assertThat(roundtrip.path("skills").get(0).has("is_substituted")).isFalse();
        assertThat(roundtrip.path("skills").get(0).has("gap_magnitude")).isFalse();
        assertThat(roundtrip.path("skills").get(0).has("candidate_proficiency")).isFalse();
            assertThat(roundtrip.path("skills").get(0).has("jd_evidence_spans")).isFalse();
            assertThat(roundtrip.path("report")).isEqualTo(original.path("report"));
            assertThat(roundtrip.path("skills").get(0).path("job_tasks"))
                    .isEqualTo(original.path("skills").get(0).path("job_tasks"));
            assertThat(mapper.readTree(analysisRequest.get()).path("analysis_id").asText()).isEqualTo("test");
            var json = new EvidenceJson(mapper);
            var session = Session.builder().skillGapJson(roundtrip.path("skills").toString()).build();
            var interviewSkills = new EvidenceInputs(gaps, json).skills(session);
            new EvidenceAiClient(properties, json)
                    .compute("start", java.util.Map.of("session_id", "test", "skills", interviewSkills));
            var interviewSkill = mapper.readTree(interviewRequest.get()).path("skills").get(0);
            assertThat(interviewSkill.path("job_tasks")).isEqualTo(original.path("skills").get(0).path("job_tasks"));
            assertThat(interviewSkill.propertyStream().map(java.util.Map.Entry::getKey)).containsExactlyInAnyOrder(
                    "jd_skill_id", "required_proficiency", "importance_weight", "priority", "job_tasks", "cv_evidence_spans");
            // Spring Boot 4's MVC and RestClient use Jackson 3 by default.
            var webMapper = tools.jackson.databind.json.JsonMapper.builder().build();
            assertThat(mapper.readTree(webMapper.writeValueAsString(result)).path("report").path("eligibility"))
                    .isEqualTo(original.path("report").path("eligibility"));
            assertThat(mapper.readTree(webMapper.writeValueAsString(result)).path("skills").get(0).path("jd_skill_name").asText())
                    .isEqualTo("Tối ưu PostgreSQL");
            assertThat(mapper.readTree(webMapper.writeValueAsString(result)).path("skills").get(0).path("job_tasks"))
                    .isEqualTo(original.path("skills").get(0).path("job_tasks"));
        } finally { server.stop(0); }
    }
}
