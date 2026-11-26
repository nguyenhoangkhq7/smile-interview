package fit.iuh.modules.auth.dto;

/**
 * Request body for updating user profile information.
 */
public record UpdateProfileRequest(
        String username,
        String phoneNumber,
        String avatarUrl,
        String defaultResumeId
) {}
