package fit.iuh.modules.auth.security;

import fit.iuh.modules.auth.entity.User;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.security.Key;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Date;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;

/**
 * Centralized JWT service for token generation, claim extraction and validation.
 *
 * <p>Set {@code JWT_SECRET} to a signing key of at least 256 bits.
 */
@Slf4j
@Service
public class JwtService {

    private static final String PUBLIC_DEVELOPMENT_KEY_SHA256 =
            "0e170e0d88b06b1128197f6344b9f560928711d0f86d02db19f6aae9fa2de91e";

    @Value("${app.jwt.secret}")
    private String jwtSecret;

    @Value("${app.jwt.expiration-ms:86400000}")
    private long jwtExpirationMs;

    @PostConstruct
    void validateSecret() {
        if (jwtSecret == null || jwtSecret.isBlank()) {
            throw new IllegalStateException("JWT_SECRET must be configured");
        }
        byte[] keyBytes = decodeKeyBytes();
        if (keyBytes.length < 32) {
            throw new IllegalStateException("JWT_SECRET must be at least 256 bits (32 bytes)");
        }
        if (isPublicDevelopmentKey(keyBytes)) {
            throw new IllegalStateException("Refusing to start with the public development JWT_SECRET");
        }
    }

    private static boolean isPublicDevelopmentKey(byte[] keyBytes) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(keyBytes);
            return PUBLIC_DEVELOPMENT_KEY_SHA256.equals(HexFormat.of().formatHex(digest));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    // ----------------------------------------------------------------
    // Token generation
    // ----------------------------------------------------------------

    /**
     * Generates a signed JWT for the given {@link User}.
     * <p>Claims included: {@code id}, {@code email}, {@code username}, {@code role}.
     */
    public String generateToken(User user) {
        Map<String, Object> extraClaims = new HashMap<>();
        extraClaims.put("id",       user.getId().toString());
        extraClaims.put("email",    user.getEmail());
        extraClaims.put("username", user.getDisplayUsername());
        extraClaims.put("role",     user.getRole() != null ? user.getRole().name() : "USER");

        return buildToken(extraClaims, user.getEmail());
    }

    private String buildToken(Map<String, Object> extraClaims, String subject) {
        long now = System.currentTimeMillis();
        return Jwts.builder()
                .setClaims(extraClaims)
                .setSubject(subject)
                .setIssuedAt(new Date(now))
                .setExpiration(new Date(now + jwtExpirationMs))
                .signWith(getSigningKey(), SignatureAlgorithm.HS256)
                .compact();
    }

    // ----------------------------------------------------------------
    // Claim extraction
    // ----------------------------------------------------------------

    /** Extracts the {@code sub} (email / username principal) from the token. */
    public String extractSubject(String token) {
        return extractClaim(token, Claims::getSubject);
    }

    public UUID extractUserId(String token) {
        String id = extractClaim(token, claims -> claims.get("id", String.class));
        return UUID.fromString(id);
    }

    public String extractEmail(String token) {
        return extractClaim(token, claims -> claims.get("email", String.class));
    }

    public String extractUsername(String token) {
        return extractClaim(token, claims -> claims.get("username", String.class));
    }

    public String extractRole(String token) {
        return extractClaim(token, claims -> claims.get("role", String.class));
    }

    public Date extractExpiration(String token) {
        return extractClaim(token, Claims::getExpiration);
    }

    public <T> T extractClaim(String token, Function<Claims, T> claimsResolver) {
        final Claims claims = extractAllClaims(token);
        return claimsResolver.apply(claims);
    }

    private Claims extractAllClaims(String token) {
        return Jwts.parserBuilder()
                .setSigningKey(getSigningKey())
                .build()
                .parseClaimsJws(token)
                .getBody();
    }

    // ----------------------------------------------------------------
    // Validation
    // ----------------------------------------------------------------

    /**
     * Returns {@code true} if the token is well-formed, properly signed, and not expired.
     *
     * @param token         the raw JWT string
     * @param userDetails   the loaded {@link User} to check subject against
     */
    public boolean isTokenValid(String token, org.springframework.security.core.userdetails.UserDetails userDetails) {
        try {
            final String subject = extractSubject(token);
            return subject.equals(userDetails.getUsername()) && !isTokenExpired(token);
        } catch (JwtException | IllegalArgumentException ex) {
            log.warn("JWT validation failed: {}", ex.getMessage());
            return false;
        }
    }

    private boolean isTokenExpired(String token) {
        return extractExpiration(token).before(new Date());
    }

    // ----------------------------------------------------------------
    // Key
    // ----------------------------------------------------------------

    private Key getSigningKey() {
        return Keys.hmacShaKeyFor(decodeKeyBytes());
    }

    private byte[] decodeKeyBytes() {
        try {
            return Decoders.BASE64.decode(jwtSecret);
        } catch (Exception e1) {
            try {
                return Decoders.BASE64URL.decode(jwtSecret);
            } catch (Exception e2) {
                return jwtSecret.getBytes(java.nio.charset.StandardCharsets.UTF_8);
            }
        }
    }
}
