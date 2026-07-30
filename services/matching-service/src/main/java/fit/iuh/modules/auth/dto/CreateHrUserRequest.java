package fit.iuh.modules.auth.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Request payload for creating a new HR account by an Admin.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CreateHrUserRequest {

    /** Username or login identifier for the HR user. */
    @NotBlank(message = "username must not be blank")
    @JsonProperty("username")
    private String username;

    /** Password for the new HR account. */
    @NotBlank(message = "password must not be blank")
    @Size(min = 6, message = "password must be at least 6 characters")
    @JsonProperty("password")
    private String password;

    /** Optional evaluator name / display name for the HR user. */
    @JsonProperty("evaluator_name")
    private String evaluatorName;

    /** Optional email address for the HR user. */
    @JsonProperty("email")
    private String email;
}
