package fit.iuh.modules.assessment.entity;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Eligibility {
    @JsonProperty("status")
    private EligibilityStatus status;

    @JsonProperty("gate_checks")
    private List<GateCheck> gateChecks;
}
