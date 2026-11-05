package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;

public record JobCategoryDto(
        @JsonProperty("id") Long id,
        @NotBlank(message = "code is required") @JsonProperty("code") String code,
        @NotBlank(message = "name is required") @JsonProperty("name") String name,
        @JsonProperty("parent_id") Long parentId
) {}
