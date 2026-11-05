package fit.iuh.modules.questionbank.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonSetter;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonIgnoreProperties(ignoreUnknown = true)
public class QuestionDto {

    @JsonProperty("id")
    @JsonAlias({"question_id", "item_id"})
    private String id;

    @JsonProperty("type")
    @JsonAlias({"question_type", "category"})
    private String type;

    @JsonProperty("difficulty")
    private String difficulty;

    @JsonProperty("topic")
    private String topic;

    @JsonProperty("question")
    @JsonAlias({"question_text"})
    private String question;

    @JsonProperty("follow_up_questions")
    @JsonAlias({"follow_ups", "followUpQuestions", "followups"})
    private List<String> followUpQuestions;

    @JsonProperty("evaluation_criteria")
    @JsonAlias({"good_answer_signals", "goodAnswerSignals", "expected_answer", "evaluationCriteria"})
    private String evaluationCriteria;

    @JsonProperty("expected_competency")
    @JsonAlias({"expectedCompetency", "competency"})
    private String expectedCompetency;

    @JsonProperty("rationale")
    private String rationale;

    @JsonProperty("star_prompt")
    @JsonAlias({"star_format_prompt", "starPrompt", "starFormatPrompt"})
    private String starPrompt;

    @JsonProperty("hints")
    private List<String> hints;

    @JsonProperty("components_to_cover")
    @JsonAlias({"componentsToCover", "components"})
    private List<String> componentsToCover;

    @JsonSetter("evaluation_criteria")
    public void setEvaluationCriteria(JsonNode node) {
        this.evaluationCriteria = parseJsonNodeToString(node);
    }

    @JsonSetter("good_answer_signals")
    public void setGoodAnswerSignals(JsonNode node) {
        if (this.evaluationCriteria == null || this.evaluationCriteria.isBlank()) {
            this.evaluationCriteria = parseJsonNodeToString(node);
        }
    }

    @JsonSetter("expected_answer")
    public void setExpectedAnswer(JsonNode node) {
        if (this.evaluationCriteria == null || this.evaluationCriteria.isBlank()) {
            this.evaluationCriteria = parseJsonNodeToString(node);
        }
    }

    public void setEvaluationCriteria(String criteria) {
        this.evaluationCriteria = criteria;
    }

    private String parseJsonNodeToString(JsonNode node) {
        if (node == null || node.isNull()) {
            return null;
        }
        if (node.isArray()) {
            List<String> items = new ArrayList<>();
            for (JsonNode elem : node) {
                items.add(elem.asText());
            }
            return items.isEmpty() ? "" : "- " + String.join("\n- ", items);
        }
        return node.asText();
    }
}

