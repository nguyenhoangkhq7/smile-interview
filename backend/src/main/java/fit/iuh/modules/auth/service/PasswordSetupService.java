package fit.iuh.modules.auth.service;

import fit.iuh.modules.auth.dto.PasswordSetupDtos.Link;
import fit.iuh.modules.auth.dto.PasswordSetupDtos.Redeem;
import fit.iuh.modules.auth.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.HexFormat;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class PasswordSetupService {
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final Duration LIFETIME = Duration.ofHours(1);

    private final JdbcTemplate jdbc;
    private final UserRepository users;
    private final PasswordEncoder encoder;

    @Transactional(propagation = Propagation.MANDATORY)
    public Link issue(UUID userId) {
        byte[] random = new byte[32];
        RANDOM.nextBytes(random);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(random);
        Instant expires = Instant.now().plus(LIFETIME);
        jdbc.update("""
                INSERT INTO user_password_setup_tokens(user_id, digest, expires_at) VALUES (?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET digest = excluded.digest, expires_at = excluded.expires_at
                """, userId, digest(token), expires.atOffset(ZoneOffset.UTC));
        return new Link(token, expires);
    }

    @Transactional
    public void redeem(Redeem request) {
        if (request.password().getBytes(StandardCharsets.UTF_8).length > 72) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Mật khẩu vượt quá 72 byte.");
        }
        String digest = digest(request.token());
        UUID id = jdbc.query("SELECT user_id FROM user_password_setup_tokens WHERE digest = ? AND expires_at > now()",
                (rs, row) -> rs.getObject("user_id", UUID.class), digest).stream().findFirst().orElseThrow(this::invalid);
        var user = users.findForUpdate(id).orElseThrow(this::invalid);
        int consumed = jdbc.update("""
                DELETE FROM user_password_setup_tokens WHERE user_id = ? AND digest = ? AND expires_at > clock_timestamp()
                """, id, digest);
        if (consumed != 1) throw invalid();
        user.setPassword(encoder.encode(request.password()));
        user.setTokenVersion(user.getTokenVersion() + 1);
    }

    private ResponseStatusException invalid() {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, "Liên kết đã hết hạn hoặc đã được sử dụng.");
    }

    private static String digest(String token) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is required", ex);
        }
    }
}
