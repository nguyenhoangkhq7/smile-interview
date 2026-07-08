package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Specifies the number of questions to generate for each interview question type.
 * Each value must be between 0 (skip that type) and 10.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuestionConfigDto {

    @Min(1) @Max(50)
    private int totalQuestions;

    /** Returns the total number of questions requested across all types. */
    public int total() {
        return totalQuestions;
    }
}
