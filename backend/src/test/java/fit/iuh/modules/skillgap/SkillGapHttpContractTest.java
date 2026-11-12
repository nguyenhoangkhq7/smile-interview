package fit.iuh.modules.skillgap;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import fit.iuh.config.AppProperties;
import fit.iuh.modules.evidence.EvidenceAiClient;
import fit.iuh.modules.evidence.EvidenceJson;
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
                  "jd_skill_id":"postgresql","semantic_alignment":"MATCH",
                  "jd_skill_name":"Tối ưu PostgreSQL","matched_cv_skill_name":"Quản trị PostgreSQL",
                  "is_substituted":false,"gap_magnitude":0,"severity":0,"priority":0,
                  "required_proficiency":4,"candidate_proficiency":4,"cv_evidence_spans":["SQL"],
                  "suggested_strategy":"PROBE_DEPTH","degraded":false,"flags":[],
                  "c_evidence":0.8,"recency_flag":false,
                  "importance_weight":0.9,"jd_evidence_spans":["Tối ưu truy vấn"],
                  "job_tasks":[{"task_id":"sql-1","description":"Tối ưu truy vấn SQL",
                    "required_level":4,"evidence_spans":["Tối ưu truy vấn"],
                    "metadata":{"optional":false,"tags":["SQL","EXPLAIN"],"note":null}}]
                }],"report":{"markdown_summary":"Phân tích hoàn tất"}}
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
            var result = new SkillGapClient(properties).analyzeGap("test", "CV tiếng Việt", "JD tiếng Việt");
            var original = mapper.readTree(response);
            var roundtrip = mapper.valueToTree(result);
            assertThat(roundtrip.path("skills").get(0).path("jd_skill_name").asText()).isEqualTo("Tối ưu PostgreSQL");
            assertThat(roundtrip.path("skills").get(0).path("matched_cv_skill_name").asText()).isEqualTo("Quản trị PostgreSQL");
            assertThat(roundtrip.path("skills").get(0).path("job_tasks"))
                    .isEqualTo(original.path("skills").get(0).path("job_tasks"));
            assertThat(mapper.readTree(analysisRequest.get()).path("analysis_id").asText()).isEqualTo("test");
            new EvidenceAiClient(properties, new EvidenceJson(mapper))
                    .compute("start", java.util.Map.of("session_id", "test", "skills", result.skills()));
            assertThat(mapper.readTree(interviewRequest.get()).path("skills").get(0).path("job_tasks"))
                    .isEqualTo(original.path("skills").get(0).path("job_tasks"));
            // Spring Boot 4's MVC and RestClient use Jackson 3 by default.
            var webMapper = tools.jackson.databind.json.JsonMapper.builder().build();
            assertThat(mapper.readTree(webMapper.writeValueAsString(result)).path("skills").get(0).path("jd_skill_name").asText())
                    .isEqualTo("Tối ưu PostgreSQL");
            assertThat(mapper.readTree(webMapper.writeValueAsString(result)).path("skills").get(0).path("job_tasks"))
                    .isEqualTo(original.path("skills").get(0).path("job_tasks"));
        } finally { server.stop(0); }
    }
}
