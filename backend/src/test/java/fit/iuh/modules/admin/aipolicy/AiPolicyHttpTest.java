package fit.iuh.modules.admin.aipolicy;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.admin.aipolicy.dto.AiPolicyDtos.*;
import fit.iuh.modules.admin.aipolicy.service.AiPolicySources;
import fit.iuh.modules.admin.aipolicy.service.AiRuntimeKey;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.WebApplicationContext;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.containsString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@Transactional
class AiPolicyHttpTest {
    private static final String ADMIN = "/api/v1/admin/ai-policy";
    private static final String INTERNAL = "/api/internal/ai-runtime";
    @Autowired WebApplicationContext context;
    @Autowired JdbcTemplate db;
    @Autowired ObjectMapper json;
    @Autowired UserRepository users;
    @Autowired JwtService tokens;
    @Autowired AiRuntimeKey key;
    @MockitoBean AiPolicySources sources;
    @TempDir(cleanup = org.junit.jupiter.api.io.CleanupMode.NEVER) static Path temp;

    @DynamicPropertySource
    static void runtimeKeyPath(DynamicPropertyRegistry properties) {
        properties.add("AI_RUNTIME_KEY_FILE", () -> temp.resolve("runtime.key").toString());
    }

    @AfterAll
    static void removeRuntimeKey() throws IOException {
        Files.deleteIfExists(temp.resolve("runtime.key"));
        Files.deleteIfExists(temp);
    }

    @Test
    void protectsCredentialsAndAppliesVersionedSettingsUntilReset() throws Exception {
        var mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", Filter.class)).build();
        var models = new Models("provider/interview", "", "provider/matching", "", "provider/gap",
                "test/embedding", "", "provider/stt", "provider/tts", "test", "pcm", 24000, "");
        var defaults = new Settings(models, Policy.defaults());
        var policy = new Policy(0.8, 2, 0.2, 3, true, 12, 1200, 3, false, false, 2);
        var input = new Settings(models, policy);
        when(sources.defaults()).thenReturn(new Defaults(defaults, false, false, List.of(), 768, false, false));

        String admin = authorization("ADMIN");
        String candidate = authorization("USER");
        mvc.perform(get(ADMIN)).andExpect(status().isUnauthorized());
        mvc.perform(get(ADMIN).header("Authorization", candidate)).andExpect(status().isForbidden());
        mvc.perform(get(INTERNAL)).andExpect(status().isUnauthorized());
        mvc.perform(get(ADMIN).header("Authorization", admin)).andExpect(status().isOk())
                .andExpect(jsonPath("$.revision").value(0)).andExpect(jsonPath("$.embeddingDimension").value(768));

        String credential = "example-policy-test-key";
        String body = json.writeValueAsString(new Save(0L, input, new Credentials(credential, null, false, false)));
        mvc.perform(put(ADMIN).header("Authorization", admin).contentType("application/json").content(body))
                .andExpect(status().isNoContent());
        mvc.perform(put(ADMIN).header("Authorization", admin).contentType("application/json").content(body))
                .andExpect(status().isConflict());
        mvc.perform(get(ADMIN).header("Authorization", admin)).andExpect(status().isOk())
                .andExpect(jsonPath("$.openRouterOverridden").value(true))
                .andExpect(jsonPath("$.settings.models.matchingModel").value(models.matchingModel()))
                .andExpect(content().string(not(containsString(credential))));
        assertThat(db.queryForObject("SELECT credentials FROM ai_runtime_configuration", String.class))
                .isNotBlank().doesNotContain(credential);
        var log = mvc.perform(get("/api/v1/admin/audit-logs").param("action", "UPDATE_POLICY")
                        .header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(1)).andReturn();
        var logId = json.readTree(log.getResponse().getContentAsString()).path("rows").get(0).path("id").asText();
        mvc.perform(get("/api/v1/admin/audit-logs/" + logId).header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(content().string(not(containsString(credential))))
                .andExpect(jsonPath("$.details.openRouterKeyChange").value("REPLACED"));

        var result = mvc.perform(get(INTERNAL).header("X-Smile-Runtime-Token", key.token()))
                .andExpect(status().isOk()).andExpect(content().string(not(containsString(credential))))
                .andReturn();
        String payload = json.readTree(result.getResponse().getContentAsString()).path("payload").asText();
        var runtime = json.readTree(key.open(payload, "smile-ai-runtime-response-v1"));
        assertThat(runtime.path("credentials").path("openRouterKey").asText()).isEqualTo(credential);
        assertThat(runtime.path("settings").path("policy").path("dailyQuota").asInt()).isEqualTo(2);

        mvc.perform(get("/api/v2/interview/limits").header("Authorization", candidate))
                .andExpect(status().isOk()).andExpect(jsonPath("$.maxQuestions").value(12))
                .andExpect(jsonPath("$.voiceEnabled").value(false));
        mvc.perform(post(ADMIN + "/reset").header("Authorization", admin)
                .contentType("application/json").content("{\"revision\":1}")).andExpect(status().isNoContent());
        mvc.perform(get(ADMIN).header("Authorization", admin)).andExpect(status().isOk())
                .andExpect(jsonPath("$.revision").value(2)).andExpect(jsonPath("$.overridden").value(false))
                .andExpect(jsonPath("$.openRouterOverridden").value(true));
    }

    private String authorization(String role) {
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO users(id,username,email,password_hash,role) VALUES (?,?,?,?,?)",
                id, "AI policy fixture", id + "@example.test", "unused", role);
        return "Bearer " + tokens.generateToken(users.findById(id).orElseThrow());
    }
}
