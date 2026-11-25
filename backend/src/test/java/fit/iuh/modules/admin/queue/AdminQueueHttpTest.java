package fit.iuh.modules.admin.queue;

import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.WebApplicationContext;

import java.util.UUID;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@Transactional
class AdminQueueHttpTest {
    @Autowired WebApplicationContext context;
    @Autowired JdbcTemplate db;
    @Autowired UserRepository users;
    @Autowired JwtService tokens;

    @Test
    void exposesCatalogAndStorageOnlyToAdminAndReleasesAndPrioritizesJobs() throws Exception {
        var mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", Filter.class)).build();
        UUID owner = account("USER");
        String admin = authorization(account("ADMIN"));
        String session = UUID.randomUUID().toString();
        UUID old = UUID.randomUUID();
        UUID latest = UUID.randomUUID();
        UUID claim = UUID.randomUUID();
        db.update("INSERT INTO sessions(id,user_id,role_title) VALUES (?,?,'Platform Engineer')", session, owner);
        db.update("""
                INSERT INTO skill_gap_jobs(id,session_id,owner_id,input_key,status,claim_token,created_at)
                VALUES (?,?,?,'same','FAILED',NULL,now()-interval '1 day'), (?,?,?,'same','RUNNING',?,now())
                """, old, session, owner, latest, session, owner, claim);

        String path = "/api/v1/admin/queue/jobs";
        mvc.perform(get(path)).andExpect(status().isUnauthorized());
        mvc.perform(get(path).header("Authorization", authorization(owner))).andExpect(status().isForbidden());
        mvc.perform(post("/api/v1/admin/storage/cleanup").header("Authorization", authorization(owner)))
                .andExpect(status().isForbidden());
        mvc.perform(get(path).param("search", "platform").param("size", "1")
                .header("Authorization", admin)).andExpect(status().isOk()).andExpect(jsonPath("$.total").value(2))
                .andExpect(jsonPath("$.jobs[0].id").value(latest.toString())).andExpect(jsonPath("$.maxAttempts").value(3));
        mvc.perform(get(path + "/" + old).header("Authorization", admin)).andExpect(status().isOk())
                .andExpect(jsonPath("$.job.prioritized").value(false));
        mvc.perform(post(path + "/" + old + "/prioritize").header("Authorization", admin)).andExpect(status().isConflict());
        mvc.perform(post(path + "/" + latest + "/release").header("Authorization", admin)
                .contentType("application/json").content("{\"claimToken\":\"" + UUID.randomUUID() + "\"}"))
                .andExpect(status().isConflict());
        mvc.perform(post(path + "/" + latest + "/release").header("Authorization", admin)
                .contentType("application/json").content("{\"claimToken\":\"" + claim + "\"}"))
                .andExpect(status().isNoContent());
        mvc.perform(post(path + "/" + latest + "/prioritize").header("Authorization", admin)).andExpect(status().isNoContent());
        mvc.perform(get(path + "/" + latest).header("Authorization", admin)).andExpect(status().isOk())
                .andExpect(jsonPath("$.job.prioritized").value(true)).andExpect(jsonPath("$.job.status").value("PENDING"));
        mvc.perform(get("/api/v1/admin/audit-logs").param("search", latest.toString()).header("Authorization", admin))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(2))
                .andExpect(jsonPath("$.rows[0].action").value("PRIORITIZE_JOB"))
                .andExpect(jsonPath("$.rows[1].action").value("RELEASE_JOB_LEASE"));
    }

    private UUID account(String role) {
        UUID id = UUID.randomUUID();
        db.update("INSERT INTO users(id,username,email,password_hash,role) VALUES (?,?,?,?,?)",
                id, "Queue fixture", id + "@example.test", "unused", role);
        return id;
    }

    private String authorization(UUID id) {
        return "Bearer " + tokens.generateToken(users.findById(id).orElseThrow());
    }
}
