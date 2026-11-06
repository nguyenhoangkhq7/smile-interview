package fit.iuh.modules.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * Request body for {@code POST /api/auth/register}.
 *
 * @param username display name chosen by the user
 * @param email    unique email address (used as login principal)
 * @param password plain-text password (will be BCrypt-hashed before storage)
 */
public record RegisterRequest(

        @NotBlank(message = "Username must not be blank")
        @Size(min = 2, max = 50, message = "Username must be between 2 and 50 characters")
        String username,

        @NotBlank(message = "Email must not be blank")
        @Email(message = "Email must be a valid email address")
        String email,

        @NotBlank(message = "Password must not be blank")
        @Size(min = 6, message = "Password must be at least 6 characters")
        String password
) {}
