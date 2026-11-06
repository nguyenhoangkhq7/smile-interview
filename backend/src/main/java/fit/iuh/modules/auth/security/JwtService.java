package fit.iuh.modules.auth.security;

import fit.iuh.modules.auth.entity.User;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.security.Key;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;

/**
 * Centralized JWT service for token generation, claim extraction and validation.
 *
 * <p>Configure via {@code application.yaml}:
 * <pre>
 * app:
 *   jwt:
 *     secret: &lt;Base64-encoded 256-bit key&gt;
 *     expiration-ms: 86400000   # 24 h
 * </pre>
 */
@Slf4j
@Service
public class JwtService {

    @Value("${app.jwt.secret}")
    private String jwtSecret;

    @Value("${app.jwt.expiration-ms:86400000}")
    private long jwtExpirationMs;

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
        byte[] keyBytes;
        try {
            keyBytes = Decoders.BASE64.decode(jwtSecret);
        } catch (Exception e1) {
            try {
                keyBytes = Decoders.BASE64URL.decode(jwtSecret);
            } catch (Exception e2) {
                keyBytes = jwtSecret.getBytes(java.nio.charset.StandardCharsets.UTF_8);
            }
        }
        return Keys.hmacShaKeyFor(keyBytes);
    }
}
