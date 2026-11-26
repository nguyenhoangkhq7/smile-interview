package fit.iuh.modules.auth.dto;

import java.util.UUID;

/**
 * Response returned after successful registration or login,
 * and also used by {@code GET /api/auth/me}.
 *
 * @param token           the signed JWT bearer token (null for /me responses)
 * @param id              the user's UUID
 * @param username        the user's display name
 * @param email           the user's email address
 * @param role            the user's assigned role (e.g. {@code "USER"}, {@code "ADMIN"})
 * @param phoneNumber     optional phone number
 * @param avatarUrl       optional avatar URL (Cloudinary etc.)
 * @param defaultResumeId optional ID of the user's default resume
 */
public record AuthResponse(
        String token,
        UUID id,
        String username,
        String email,
        String role,
        String phoneNumber,
        String avatarUrl,
        String defaultResumeId
) {}
