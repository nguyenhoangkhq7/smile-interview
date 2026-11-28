package fit.iuh.modules.matching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record EligibilityReportDto(String state, List<Condition> results) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Condition(
            @JsonProperty("condition_id") String conditionId,
            String type,
            String priority,
            @JsonProperty("jd_quote") String jdQuote,
            @JsonProperty("cv_quotes") List<String> cvQuotes,
            String status,
            String reason
    ) {}
}
