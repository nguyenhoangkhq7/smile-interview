package fit.iuh.modules.questionbank.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Min;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class QuestionConfigDto {

    @Min(1)
    @JsonProperty("total")
    private Integer total;

    @JsonProperty("distribution")
    private Map<String, Integer> distribution;

    @JsonProperty("mode")
    private String mode; // "SCREENING" | "DEEP_DIVE"

    @JsonProperty("interview_channel")
    private String interviewChannel; // "VOICE" | "TEXT_IDE"

    public int getTotalQuestions() {
        return total != null ? total : 10;
    }

    public String getMode() {
        return (mode != null && !mode.isBlank()) ? mode.toUpperCase() : "SCREENING";
    }

    public String getInterviewChannel() {
        return (interviewChannel != null && !interviewChannel.isBlank()) ? interviewChannel.toUpperCase() : "VOICE";
    }
}
