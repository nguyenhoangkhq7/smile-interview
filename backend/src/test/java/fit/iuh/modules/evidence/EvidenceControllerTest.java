package fit.iuh.modules.evidence;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class EvidenceControllerTest {
    @Test void sessionAndReportHideLegacyCoachingUntilCompletion() throws Exception {
        var mapper = new ObjectMapper();
        var service = mock(EvidenceService.class);
        var mvc = MockMvcBuilders.standaloneSetup(new EvidenceController(service)).build();
        var session = mapper.createObjectNode().put("is_finished", false);
        session.set("report", mapper.readTree("""
            {"objectives":[{"strengths":[],"weaknesses":["missing index"],"study_recommendations":["use an index"],
            "evidence":[{"response_excerpt":"scan","rationale":"use an index"}]}]}
            """));
        when(service.read(eq("saved"), any())).thenReturn(session);
        String path = "/api/v2/sessions/saved/interview";
        for (String route : new String[]{path, path + "/report"}) {
            String root = route.equals(path) ? "$.report" : "$";
            mvc.perform(get(route)).andExpect(status().isOk())
                    .andExpect(jsonPath(root + ".turn_reviews").isEmpty())
                    .andExpect(jsonPath(root + ".objectives[0].weaknesses").isEmpty())
                    .andExpect(jsonPath(root + ".objectives[0].study_recommendations").isEmpty())
                    .andExpect(jsonPath(root + ".objectives[0].evidence[0].rationale").value(""))
                    .andExpect(jsonPath(root + ".objectives[0].evidence[0].response_excerpt").value("scan"));
        }
        session.put("is_finished", true);
        mvc.perform(get(path + "/report")).andExpect(status().isOk())
                .andExpect(jsonPath("$.objectives[0].study_recommendations[0]").value("use an index"));
    }
}
