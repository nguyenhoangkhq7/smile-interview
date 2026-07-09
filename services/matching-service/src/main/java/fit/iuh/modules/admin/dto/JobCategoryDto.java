package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * DTO for {@link fit.iuh.modules.rulengine.JobCategoryEntity}.
 * Used by {@link fit.iuh.modules.admin.RuleAdminController} for GET, POST and PUT operations.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class JobCategoryDto {

    @JsonProperty("id")
    private Long id;

    @NotBlank(message = "name is required")
    @Size(max = 100, message = "name must be ≤ 100 characters")
    @JsonProperty("name")
    private String name;

    /** ID of the parent category node; {@code null} for root nodes. */
    @JsonProperty("parent_id")
    private Long parentId;

    /** Human-readable parent name (read-only; included in GET responses). */
    @JsonProperty("parent_name")
    private String parentName;
}
