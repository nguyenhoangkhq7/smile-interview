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

    public int getTotalQuestions() {
        return total != null ? total : 10;
    }
}
