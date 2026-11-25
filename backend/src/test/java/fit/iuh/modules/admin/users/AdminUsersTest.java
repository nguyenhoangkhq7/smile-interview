package fit.iuh.modules.admin.users;

import com.jayway.jsonpath.JsonPath;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.WebApplicationContext;

import java.util.UUID;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@Transactional
class AdminUsersTest {
    private static final String PATH = "/api/v1/admin/users";
    private static final String PASSWORD = "fixture-password-123";

    @Autowired JdbcTemplate jdbc;
    @Autowired UserRepository users;
    @Autowired JwtService jwt;
    @Autowired PasswordEncoder encoder;
    @Autowired WebApplicationContext context;

    private MockMvc mvc;
    private UUID administrator;
    private UUID member;
    private String adminToken;
    private String memberToken;

    @BeforeEach
    void prepare() {
        mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", Filter.class)).build();
        administrator = account("ADMIN", "Quản trị kiểm thử", "");
        member = account("CANDIDATE", "=Sample CSV account", "0123459876");
        adminToken = token(administrator);
        memberToken = token(member);
    }

    @Test
    void listsFiltersAndExportsOnlyForAdministrators() throws Exception {
        mvc.perform(get(PATH)).andExpect(status().isUnauthorized());
        var forbidden = mvc.perform(get(PATH).header("Authorization", memberToken))
                .andExpect(status().isForbidden()).andReturn().getResponse();
        assertFalse(forbidden.isCommitted(), "Forbidden should return a status without triggering an error dispatch");
        mvc.perform(get(PATH).param("role", "MODERATOR").header("Authorization", adminToken))
                .andExpect(status().isBadRequest());
        mvc.perform(get(PATH).param("size", "0").header("Authorization", adminToken))
                .andExpect(status().isBadRequest());
        mvc.perform(get(PATH).param("search", "459876").param("role", "CANDIDATE").param("page", "5")
                        .header("Authorization", adminToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.page").value(1)).andExpect(jsonPath("$.users[0].id").value(member.toString()));
        mvc.perform(get(PATH + "/" + administrator).header("Authorization", adminToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$.user.self").value(true));
        mvc.perform(get(PATH + "/export").param("role", "CANDIDATE").param("search", "459876")
                        .header("Authorization", adminToken))
                .andExpect(status().isOk()).andExpect(header().string("Content-Disposition", containsString("users.csv")))
                .andExpect(content().string(containsString("'=Sample CSV account")));
    }

    @Test
    void excludesAdministratorsFromTheCatalogAndCsv() throws Exception {
        long existingUsers = jdbc.queryForObject("SELECT count(*) FROM users WHERE role IN ('USER', 'CANDIDATE')", Long.class);
        String search = UUID.randomUUID().toString();
        UUID regular = account("USER", search + " user", "");
        UUID admin = account("ADMIN", search + " admin", "");

        mvc.perform(get(PATH).param("search", search).header("Authorization", adminToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.users.length()").value(1))
                .andExpect(jsonPath("$.users[0].id").value(regular.toString()))
                .andExpect(jsonPath("$.stats.totalUsers").value(existingUsers + 1));
        mvc.perform(get(PATH).param("search", search).param("role", "ADMIN").header("Authorization", adminToken))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(0));
        mvc.perform(get(PATH + "/export").param("search", search).header("Authorization", adminToken))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString(regular.toString())))
                .andExpect(content().string(not(containsString(admin.toString()))));
    }

    @Test
    void lockingRevokesSessionsAndUnlockingRequiresNewLogin() throws Exception {
        mvc.perform(patch(PATH + "/" + administrator + "/status").header("Authorization", adminToken)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"status\":\"LOCKED\"}"))
                .andExpect(status().isConflict());
        updateStatus("LOCKED");
        mvc.perform(get("/api/auth/me").header("Authorization", memberToken)).andExpect(status().isUnauthorized());
        login(member + "@example.test", PASSWORD, 401);
        updateStatus("ACTIVE");
        mvc.perform(get("/api/auth/me").header("Authorization", memberToken)).andExpect(status().isUnauthorized());
        String newToken = login(member + "@example.test", PASSWORD, 200);
        mvc.perform(get("/api/auth/me").header("Authorization", "Bearer " + newToken)).andExpect(status().isOk());
    }

    @Test
    void rejectsUpdatesToAnExistingUsersRole() throws Exception {
        mvc.perform(patch(PATH + "/" + member + "/role").header("Authorization", adminToken)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"role\":\"ADMIN\"}"))
                .andExpect(status().isNotFound());
        assertEquals("CANDIDATE", jdbc.queryForObject("SELECT role FROM users WHERE id = ?", String.class, member));
        mvc.perform(get("/api/auth/me").header("Authorization", memberToken)).andExpect(status().isOk());
    }

    @Test
    void createsAdminWithSingleUseSetupLinkAndRevokesSessionsAfterReset() throws Exception {
        String email = UUID.randomUUID() + "@example.test";
        String input = "{\"fullName\":\"Admin mới\",\"email\":\"" + email + "\"}";
        String created = mvc.perform(post(PATH).header("Authorization", adminToken).contentType(MediaType.APPLICATION_JSON)
                .content(input)).andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        String setupToken = JsonPath.read(created, "$.token");
        redeem(setupToken, PASSWORD, 204);
        redeem(setupToken, PASSWORD, 400);
        String invitedToken = login(email, PASSWORD, 200);
        UUID target = users.findByEmail(email).orElseThrow().getId();
        String reset = mvc.perform(post(PATH + "/" + target + "/password-setup").header("Authorization", adminToken))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        redeem(JsonPath.read(reset, "$.token"), "new-fixture-password", 204);
        mvc.perform(get(PATH).header("Authorization", "Bearer " + invitedToken)).andExpect(status().isUnauthorized());
        login(email, "new-fixture-password", 200);
    }

    private UUID account(String role, String name, String phone) {
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO users(id,username,email,password_hash,role,phone_number) VALUES (?,?,?,?,?,?)",
                id, name, id + "@example.test", encoder.encode(PASSWORD), role, phone);
        return id;
    }

    private String token(UUID id) {
        return "Bearer " + jwt.generateToken(users.findById(id).orElseThrow());
    }

    private void updateStatus(String desired) throws Exception {
        mvc.perform(patch(PATH + "/" + member + "/status").header("Authorization", adminToken)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"status\":\"" + desired + "\"}"))
                .andExpect(status().isNoContent());
    }

    private void redeem(String token, String password, int expected) throws Exception {
        mvc.perform(post("/api/auth/password-setup").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"token\":\"" + token + "\",\"password\":\"" + password + "\"}"))
                .andExpect(status().is(expected));
    }

    private String login(String email, String password, int expected) throws Exception {
        String body = mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"" + email + "\",\"password\":\"" + password + "\"}"))
                .andExpect(status().is(expected)).andReturn().getResponse().getContentAsString();
        return expected == 200 ? JsonPath.read(body, "$.token") : null;
    }
}
