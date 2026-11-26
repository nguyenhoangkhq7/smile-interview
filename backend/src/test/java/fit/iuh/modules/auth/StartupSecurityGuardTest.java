package fit.iuh.modules.auth;

import fit.iuh.exception.GlobalExceptionHandler;
import fit.iuh.modules.auth.config.DefaultAdminGuard;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.core.io.ClassPathResource;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.Optional;
import java.util.UUID;
import java.util.regex.Pattern;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class StartupSecurityGuardTest {

    @LocalServerPort int port;
    @Autowired GlobalExceptionHandler exceptionHandler;

    @Test
    void jwtServiceRequiresConfiguredStrongKey() {
        JwtService missingSecretService = new JwtService();
        assertThatThrownBy(() -> ReflectionTestUtils.invokeMethod(missingSecretService, "validateSecret"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("JWT_SECRET must be configured");

        JwtService shortService = new JwtService();
        ReflectionTestUtils.setField(shortService, "jwtSecret", Base64.getEncoder().encodeToString("short".getBytes(StandardCharsets.UTF_8)));
        assertThatThrownBy(() -> ReflectionTestUtils.invokeMethod(shortService, "validateSecret"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("256 bits");

        JwtService strongService = new JwtService();
        String strongSecret = Base64.getEncoder().encodeToString("0123456789abcdef0123456789abcdef_strong".getBytes(StandardCharsets.UTF_8));
        ReflectionTestUtils.setField(strongService, "jwtSecret", strongSecret);
        ReflectionTestUtils.invokeMethod(strongService, "validateSecret");
    }

    @ParameterizedTest
    @ValueSource(booleans = {true, false})
    void defaultAdminGuardFailsFastOrRotatesWhenHardened(boolean useV1Seed) throws IOException {
        PasswordEncoder encoder = new BCryptPasswordEncoder();
        UserRepository repo = mock(UserRepository.class);
        User admin = User.builder()
                .id(UUID.randomUUID())
                .username("System Admin")
                .email("admin@smile.com")
                .password(useV1Seed ? readV1AdminPasswordHash() : encoder.encode("password"))
                .role(Role.ADMIN)
                .build();
        when(repo.findByEmail("admin@smile.com")).thenReturn(Optional.of(admin));

        DefaultAdminGuard failingGuard = new DefaultAdminGuard(repo, encoder);
        ReflectionTestUtils.setField(failingGuard, "requireHardenedAdmin", true);
        ReflectionTestUtils.setField(failingGuard, "adminBootstrapPassword", "");
        assertThatThrownBy(() -> failingGuard.run(new DefaultApplicationArguments()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("ADMIN_BOOTSTRAP_PASSWORD");

        DefaultAdminGuard rotatingGuard = new DefaultAdminGuard(repo, encoder);
        ReflectionTestUtils.setField(rotatingGuard, "requireHardenedAdmin", true);
        ReflectionTestUtils.setField(rotatingGuard, "adminBootstrapPassword", "VeryStrongAdminPass#2026");
        rotatingGuard.run(new DefaultApplicationArguments());
        failingGuard.run(new DefaultApplicationArguments());

        verify(repo).save(admin);
        assertThat(encoder.matches("VeryStrongAdminPass#2026", admin.getPassword())).isTrue();
        assertThat(encoder.matches("password", admin.getPassword())).isFalse();
    }

    private static String readV1AdminPasswordHash() throws IOException {
        String migration = new ClassPathResource("db/migration/V1__init_schema.sql")
                .getContentAsString(StandardCharsets.UTF_8);
        var matcher = Pattern.compile("'admin@smile\\.com',\\s*'([^']+)'").matcher(migration);
        assertThat(matcher.find()).as("V1 admin seed hash").isTrue();
        return matcher.group(1);
    }

    @Test
    void healthEndpointReturns200UpWithoutAuth() throws Exception {
        HttpClient http = HttpClient.newHttpClient();
        HttpRequest req = HttpRequest.newBuilder(URI.create("http://localhost:" + port + "/actuator/health"))
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        HttpResponse<String> response = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"status\":\"UP\"").contains("\"database\":\"UP\"");
    }

    @Test
    void generic500ResponseDoesNotLeakInternalExceptionDetail() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/internal-test");
        var response = exceptionHandler.handleGenericException(
                new RuntimeException("Sensitive SQL statement leaked"), request);
        assertThat(response.getStatusCode().value()).isEqualTo(500);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getDetail()).isNull();
    }
}
