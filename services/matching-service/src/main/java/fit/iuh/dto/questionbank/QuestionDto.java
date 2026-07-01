package fit.iuh.dto.questionbank;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Represents a single generated interview question with its metadata,
 * follow-up questions, evaluation criteria, and type-specific fields.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonIgnoreProperties(ignoreUnknown = true)
public class QuestionDto {

    /** Sequential ID within the question bank, e.g. "Q001". */
    private String id;

    /** Question type: behavioural | technical | coding | system_design */
    private String type;

    /** Difficulty level: easy | medium | hard */
    private String difficulty;

    /** Topic/category of the question, e.g. "Conflict Resolution", "Database Indexing". */
    private String topic;

    /** The main question text (may include code snippets for coding type). */
    private String question;

    /** 2 follow-up questions to probe deeper. */
    @JsonProperty("follow_up_questions")
    private List<String> followUpQuestions;

    /** Criteria for evaluating strong vs. weak answers. */
    @JsonProperty("evaluation_criteria")
    private String evaluationCriteria;

    /** The competency being assessed. */
    @JsonProperty("expected_competency")
    private String expectedCompetency;

    /** Why this question is appropriate for this specific candidate. */
    private String rationale;

    // ── Type-specific optional fields ──

    /** STAR framework prompt (behavioural questions only). */
    @JsonProperty("star_prompt")
    private String starPrompt;

    /** Hints or scaffolding for the candidate (coding questions only). */
    private String hints;

    /** System components the candidate should discuss (system_design questions only). */
    @JsonProperty("components_to_cover")
    private List<String> componentsToCover;
}
