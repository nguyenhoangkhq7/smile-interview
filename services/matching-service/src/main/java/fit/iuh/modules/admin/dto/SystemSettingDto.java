package fit.iuh.modules.admin.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * DTO for {@link fit.iuh.modules.admin.SystemSetting}.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SystemSettingDto {

    @NotBlank(message = "setting_key is required")
    @JsonProperty("setting_key")
    private String settingKey;

    @NotBlank(message = "setting_value is required")
    @JsonProperty("setting_value")
    private String settingValue;
}
