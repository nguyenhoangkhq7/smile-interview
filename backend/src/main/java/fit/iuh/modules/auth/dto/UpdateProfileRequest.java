package fit.iuh.modules.auth.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * Request body for updating user profile information.
 */
public record UpdateProfileRequest(
        String username,
        String phoneNumber,
        String avatarUrl,
        String defaultResumeId
) {}
