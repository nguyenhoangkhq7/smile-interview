package fit.iuh.modules.auth.config;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.auth.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * Ensures the V1 seeded development admin account never runs with its public
 * default password when hardened security mode is enabled.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DefaultAdminGuard implements ApplicationRunner {

    static final String DEFAULT_ADMIN_EMAIL = "admin@smile.com";
    static final String DEV_DEFAULT_PASSWORD = "password";
    private static final String V1_SEEDED_ADMIN_PASSWORD_HASH =
            "$2a$10$8.UnVuG9HHgffUDAlk8qfOUVGkqRzgVymGe07xd00DMxs.AQubh4a";
    static final int MIN_BOOTSTRAP_PASSWORD_LENGTH = 12;

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Value("${app.security.require-hardened-admin:false}")
    private boolean requireHardenedAdmin;

    @Value("${app.security.admin-bootstrap-password:}")
    private String adminBootstrapPassword;

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (requireHardenedAdmin) {
            userRepository.findByEmail(DEFAULT_ADMIN_EMAIL).ifPresent(this::rotateSeededAdmin);
        }
    }

    private void rotateSeededAdmin(User admin) {
        String passwordHash = admin.getPassword();
        if (!V1_SEEDED_ADMIN_PASSWORD_HASH.equals(passwordHash)
                && !passwordEncoder.matches(DEV_DEFAULT_PASSWORD, passwordHash)) {
            return;
        }
        if (adminBootstrapPassword == null || adminBootstrapPassword.length() < MIN_BOOTSTRAP_PASSWORD_LENGTH) {
            throw new IllegalStateException("Seeded admin@smile.com still has its development credentials. "
                    + "Set ADMIN_BOOTSTRAP_PASSWORD (>= 12 characters) or rotate it in the database before starting.");
        }
        if (DEV_DEFAULT_PASSWORD.equals(adminBootstrapPassword)
                || passwordEncoder.matches(adminBootstrapPassword, passwordHash)) {
            throw new IllegalStateException("ADMIN_BOOTSTRAP_PASSWORD must not reuse the development default password");
        }
        admin.setPassword(passwordEncoder.encode(adminBootstrapPassword));
        userRepository.save(admin);
        log.info("Rotated seeded admin account password from ADMIN_BOOTSTRAP_PASSWORD.");
    }
}
