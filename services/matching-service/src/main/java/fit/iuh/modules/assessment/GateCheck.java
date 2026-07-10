package fit.iuh.modules.assessment;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GateCheck {
    
    @JsonProperty("criteria_name")
    private String criteriaName;

    @JsonProperty("importance")
    private Importance importance;

    @JsonProperty("required_value")
    private String requiredValue;

    @JsonProperty("actual_value")
    private String actualValue;

    @JsonProperty("status")
    private String status; // "met", "not_met"
}
