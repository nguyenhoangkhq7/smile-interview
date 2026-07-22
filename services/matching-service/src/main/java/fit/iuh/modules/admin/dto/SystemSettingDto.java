package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDateTime;

public record SystemSettingDto(
        @JsonProperty("id") Long id,
        @NotBlank(message = "setting_key is required") @JsonProperty("setting_key") String settingKey,
        @NotBlank(message = "setting_value is required") @JsonProperty("setting_value") String settingValue,
        @JsonProperty("description") String description,
        @JsonProperty("updated_at") LocalDateTime updatedAt
) {}
