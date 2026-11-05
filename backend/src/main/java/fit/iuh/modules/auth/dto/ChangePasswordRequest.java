package fit.iuh.modules.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * Request body for {@code POST /api/auth/change-password}.
 *
 * @param currentPassword the user's existing password to verify identity
 * @param newPassword     the desired new password (min 6 characters)
 * @param confirmPassword must match {@code newPassword} exactly
 */
public record ChangePasswordRequest(

        @NotBlank(message = "Current password must not be blank")
        String currentPassword,

        @NotBlank(message = "New password must not be blank")
        @Size(min = 6, message = "New password must be at least 6 characters")
        String newPassword,

        @NotBlank(message = "Confirm password must not be blank")
        String confirmPassword
) {}
