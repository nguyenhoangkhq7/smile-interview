package fit.iuh.modules.questionbank.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
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
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonIgnoreProperties(ignoreUnknown = true)
public class QuestionDto {

    private String id;
    private String type;
    private String difficulty;
    private String topic;
    private String question;

    @JsonProperty("follow_up_questions")
    private List<String> followUpQuestions;

    @JsonProperty("evaluation_criteria")
    private String evaluationCriteria;

    @JsonProperty("expected_competency")
    private String expectedCompetency;

    private String rationale;

    @JsonProperty("star_prompt")
    private String starPrompt;

    private List<String> hints;

    @JsonProperty("components_to_cover")
    private List<String> componentsToCover;
}
