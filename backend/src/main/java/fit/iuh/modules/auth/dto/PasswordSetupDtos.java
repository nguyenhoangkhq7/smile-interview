package fit.iuh.modules.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.time.Instant;

public final class PasswordSetupDtos {
    private PasswordSetupDtos() {}

    public record Link(String token, Instant expiresAt) {}

    public record Redeem(@NotBlank @Size(min = 43, max = 43) String token,
                         @NotBlank @Size(min = 8, max = 72) String password) {}
}
