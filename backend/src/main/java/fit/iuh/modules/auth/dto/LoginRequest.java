package fit.iuh.modules.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

/**
 * Request body for {@code POST /api/auth/login}.
 *
 * @param email    the user's registered email address
 * @param password the plain-text password to authenticate
 */
public record LoginRequest(

        @NotBlank(message = "Email must not be blank")
        @Email(message = "Email must be a valid email address")
        String email,

        @NotBlank(message = "Password must not be blank")
        String password
) {}
