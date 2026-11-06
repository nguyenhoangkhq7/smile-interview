package fit.iuh.modules.auth.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import fit.iuh.modules.auth.entity.Role;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Response payload returned after creating an HR user account.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CreateHrUserResponse {

    @JsonProperty("id")
    private UUID id;

    @JsonProperty("username")
    private String username;

    @JsonProperty("email")
    private String email;

    @JsonProperty("evaluator_name")
    private String evaluatorName;

    @JsonProperty("role")
    private Role role;

    @JsonProperty("created_at")
    private LocalDateTime createdAt;

    @JsonProperty("message")
    private String message;
}
