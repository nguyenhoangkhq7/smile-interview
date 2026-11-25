package fit.iuh.modules.admin.audit;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.WebApplicationContext;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@Transactional
class AdminAuditHttpTest {
    private static final String PATH = "/api/v1/admin/audit-logs";
    @Autowired WebApplicationContext context;
    @Autowired JdbcTemplate db;
    @Autowired UserRepository users;
    @Autowired JwtService tokens;
    @Autowired ObjectMapper json;

    @Test
    void recordsSuccessfulMutationsAndSupportsAuthorizedFilteredRead() throws Exception {
        var mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", jakarta.servlet.Filter.class)).build();
        UUID actor = account("ADMIN", "=audit fixture");
        UUID candidate = account("USER", "candidate");
        String admin = authorization(actor);
        String change = "/api/v1/admin/users/" + candidate + "/status";
        var lock = "{\"status\":\"LOCKED\",\"reason\":\"Smoke test 100%\"}";

        mvc.perform(get(PATH)).andExpect(status().isUnauthorized());
        mvc.perform(get(PATH + "/export").header("Authorization", authorization(candidate)))
                .andExpect(status().isForbidden());
        mvc.perform(get(PATH).header("Authorization", authorization(candidate))).andExpect(status().isForbidden());
        mvc.perform(patch(change).header("Authorization", admin).contentType("application/json").content(lock))
                .andExpect(status().isNoContent());
        mvc.perform(patch(change).header("Authorization", admin).contentType("application/json").content(lock))
                .andExpect(status().isNoContent());
        mvc.perform(patch(change).header("Authorization", admin).contentType("application/json")
                        .content("{\"status\":\"ACTIVE\"}")).andExpect(status().isNoContent());

        var listed = mvc.perform(get(PATH).header("Authorization", admin)
                        .param("actorId", actor.toString()).param("size", "1").param("page", "9"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(2))
                .andExpect(jsonPath("$.page").value(2)).andExpect(jsonPath("$.rows[0].action").value("LOCK_USER"))
                .andReturn();
        String id = json.readTree(listed.getResponse().getContentAsString()).path("rows").get(0).path("id").asText();
        mvc.perform(get(PATH + "/" + id).header("Authorization", admin)).andExpect(status().isOk())
                .andExpect(jsonPath("$.event.targetCode").value("#USR-" + candidate))
                .andExpect(jsonPath("$.changes[0].newValue").value("LOCKED"))
                .andExpect(jsonPath("$.details.reason").value("Smoke test 100%"));
        mvc.perform(get(PATH).header("Authorization", admin)
                        .param("actorId", actor.toString()).param("action", "LOCK_USER").param("search", "100%"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(1));
        mvc.perform(get(PATH).header("Authorization", admin).param("action", "INVALID"))
                .andExpect(status().isBadRequest());
        mvc.perform(get(PATH + "/9223372036854775807").header("Authorization", admin))
                .andExpect(status().isNotFound());

        var download = mvc.perform(get(PATH + "/export").header("Authorization", admin)
                        .param("actorId", actor.toString()).param("action", "LOCK_USER"))
                .andExpect(status().isOk()).andExpect(content().contentTypeCompatibleWith("text/csv"))
                .andExpect(header().string("Content-Disposition", "attachment; filename=\"admin-audit-logs.csv\""))
                .andReturn();
        assertThat(download.getResponse().getContentAsString(StandardCharsets.UTF_8)).startsWith("\uFEFF")
                .contains("'=audit fixture", "LOCK_USER").doesNotContain("UNLOCK_USER", "Smoke test 100%");
    }

    private UUID account(String role, String name) {
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO users(id,username,email,password_hash,role) VALUES (?,?,?,?,?)",
                id, name, id + "@example.test", "unused", role);
        return id;
    }

    private String authorization(UUID id) {
        return "Bearer " + tokens.generateToken(users.findById(id).orElseThrow());
    }
}
