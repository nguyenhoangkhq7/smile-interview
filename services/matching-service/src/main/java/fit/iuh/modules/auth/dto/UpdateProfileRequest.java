package fit.iuh.modules.auth.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * Request body for updating user profile information.
 */
public record UpdateProfileRequest(
        @NotBlank(message = "Họ và tên không được để trống")
        String username,

        String phoneNumber,

        String avatarUrl
) {}
