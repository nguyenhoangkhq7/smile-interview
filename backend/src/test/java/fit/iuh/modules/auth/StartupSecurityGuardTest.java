package fit.iuh.modules.auth;

import fit.iuh.exception.GlobalExceptionHandler;
import fit.iuh.modules.auth.config.DefaultAdminGuard;
import fit.iuh.modules.auth.entity.Role;
import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import fit.iuh.modules.auth.security.JwtService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.Optional;
import java.util.UUID;

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
    void jwtServiceRejectsDefaultOrShortSecretWhenHardened() {
        JwtService defaultService = new JwtService();
        ReflectionTestUtils.setField(defaultService, "jwtSecret", JwtService.DEV_DEFAULT_SECRET);
        ReflectionTestUtils.setField(defaultService, "allowDefaultSecret", false);
        assertThatThrownBy(() -> ReflectionTestUtils.invokeMethod(defaultService, "validateSecret"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("development JWT_SECRET");

        JwtService shortService = new JwtService();
        ReflectionTestUtils.setField(shortService, "jwtSecret", Base64.getEncoder().encodeToString("short".getBytes(StandardCharsets.UTF_8)));
        ReflectionTestUtils.setField(shortService, "allowDefaultSecret", false);
        assertThatThrownBy(() -> ReflectionTestUtils.invokeMethod(shortService, "validateSecret"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("256 bits");

        JwtService strongService = new JwtService();
        String strongSecret = Base64.getEncoder().encodeToString("0123456789abcdef0123456789abcdef_strong".getBytes(StandardCharsets.UTF_8));
        ReflectionTestUtils.setField(strongService, "jwtSecret", strongSecret);
        ReflectionTestUtils.setField(strongService, "allowDefaultSecret", false);
        ReflectionTestUtils.invokeMethod(strongService, "validateSecret");
    }

    @Test
    void defaultAdminGuardFailsFastOrRotatesWhenHardened() {
        PasswordEncoder encoder = new BCryptPasswordEncoder();
        UserRepository repo = mock(UserRepository.class);
        User admin = User.builder()
                .id(UUID.randomUUID())
                .username("System Admin")
                .email("admin@smile.com")
                .password(encoder.encode("password"))
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

        verify(repo).save(admin);
        assertThat(encoder.matches("VeryStrongAdminPass#2026", admin.getPassword())).isTrue();
        assertThat(encoder.matches("password", admin.getPassword())).isFalse();
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
