package fit.iuh.modules.auth;

import fit.iuh.modules.auth.config.SecurityConfig;
import fit.iuh.modules.auth.security.JwtAuthenticationFilter;
import fit.iuh.modules.auth.security.JwtService;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.MapPropertySource;
import org.springframework.mock.web.MockServletContext;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Date;
import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class SecurityStatusTest {
    private static final byte[] SECRET = "test-signing-key-with-at-least-32-bytes".getBytes(StandardCharsets.UTF_8);
    private AnnotationConfigWebApplicationContext context;
    private MockMvc mvc;

    @BeforeEach
    void setup() {
        context = new AnnotationConfigWebApplicationContext();
        context.setServletContext(new MockServletContext());
        context.getEnvironment().getPropertySources().addFirst(new MapPropertySource("test-jwt",
                Map.of("app.jwt.secret", Base64.getEncoder().encodeToString(SECRET))));
        context.register(SecurityConfig.class, TestConfig.class);
        context.refresh();
        mvc = MockMvcBuilders.webAppContextSetup(context)
                .addFilters(context.getBean("springSecurityFilterChain", Filter.class)).build();
    }

    @AfterEach
    void cleanup() {
        context.close();
    }

    private String token(long expiresAt) {
        return Jwts.builder().setSubject("user@example.com").setExpiration(new Date(expiresAt))
                .signWith(Keys.hmacShaKeyFor(SECRET)).compact();
    }

    @Test
    void expiredOrMissingCredentialsReturn401() throws Exception {
        mvc.perform(get("/api/v1/test")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/test").header("Authorization", "Bearer " + token(System.currentTimeMillis() - 60000)))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/test").header("Authorization", "Bearer malformed"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void validCredentialsAllowAccessButInsufficientRoleReturns403() throws Exception {
        String authorization = "Bearer " + token(System.currentTimeMillis() + 60000);
        mvc.perform(get("/api/v1/test").header("Authorization", authorization)).andExpect(status().isOk());
        mvc.perform(get("/api/admin/test").header("Authorization", authorization)).andExpect(status().isForbidden());
    }

    @Test
    void publicAuthenticationEndpointRemainsAccessible() throws Exception {
        mvc.perform(get("/api/auth/test")).andExpect(status().isOk());
    }

    @Configuration
    @EnableWebMvc
    static class TestConfig {
        @Bean
        UserDetailsService userDetailsService() {
            return username -> User.withUsername(username).password("unused").roles("USER").build();
        }

        @Bean
        JwtService jwtService() {
            return new JwtService();
        }

        @Bean
        JwtAuthenticationFilter jwtAuthenticationFilter(JwtService jwtService, UserDetailsService users) {
            return new JwtAuthenticationFilter(jwtService, users);
        }

        @Bean
        TestController testController() {
            return new TestController();
        }
    }

    @RestController
    static class TestController {
        @GetMapping({"/api/v1/test", "/api/admin/test", "/api/auth/test"})
        String test() {
            return "ok";
        }
    }
}
