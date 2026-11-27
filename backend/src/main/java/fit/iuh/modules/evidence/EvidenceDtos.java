package fit.iuh.modules.evidence;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.*;
import java.util.UUID;

public final class EvidenceDtos {
    private EvidenceDtos() {}

    public record ChecklistRef(@Positive long taskId, @Positive long checklistItemId) {}

    public record Config(
            @JsonProperty(access = JsonProperty.Access.WRITE_ONLY) String mode,
            @JsonProperty("focused_question_mode") String focusedMode,
            @JsonProperty("max_questions") @Min(1) @Max(40) int maxQuestions,
            @JsonProperty("duration_seconds") @Min(60) @Max(7200) int durationSeconds,
            @JsonProperty("max_questions_per_objective") @Min(1) @Max(40) Integer maxPerObjective,
            @JsonProperty("interaction_mode") @Pattern(regexp = "TEXT|VOICE") String interactionMode,
            @jakarta.validation.Valid @com.fasterxml.jackson.annotation.JsonInclude(com.fasterxml.jackson.annotation.JsonInclude.Include.NON_NULL)
            ChecklistRef recheck,
            @JsonProperty("session_purpose") @Pattern(regexp = "ASSESSMENT|PRACTICE") String sessionPurpose,
            @JsonProperty("include_mastered_skills") Boolean includeMasteredSkills) {
        static final int DEFAULT_MAX_PER_OBJECTIVE = 8;

        public Config {
            interactionMode = interactionMode == null ? "TEXT" : interactionMode;
            maxPerObjective = maxPerObjective == null ? DEFAULT_MAX_PER_OBJECTIVE : maxPerObjective;
            sessionPurpose = sessionPurpose == null ? "ASSESSMENT" : sessionPurpose;
            includeMasteredSkills = includeMasteredSkills != null && includeMasteredSkills;
        }
        public Config(String mode, String focusedMode, int maxQuestions, int durationSeconds, int maxPerObjective) {
            this(mode, focusedMode, maxQuestions, durationSeconds, maxPerObjective, "TEXT", null, "ASSESSMENT", false);
        }
        public Config(String mode, String focusedMode, int maxQuestions, int durationSeconds, Integer maxPerObjective,
                      String interactionMode, ChecklistRef recheck) {
            this(mode, focusedMode, maxQuestions, durationSeconds, maxPerObjective, interactionMode, recheck, "ASSESSMENT", false);
        }
        public static Config defaults() { return new Config(null, null, 10, 900, null, "TEXT", null, "ASSESSMENT", false); }

        @JsonIgnore
        @AssertTrue(message = "mode must agree with focused_question_mode")
        public boolean isModeConsistent() {
            return mode == null || mode.equals(modeFor(focusedMode));
        }

        static String modeFor(String focusedMode) {
            return focusedMode == null ? "MIXED" : "FOCUSED";
        }
    }

    public record Answer(
            @JsonProperty("request_id") @NotNull UUID requestId,
            @JsonProperty("turn_id") @NotBlank String turnId,
            @JsonProperty("expected_state_version") @Min(1) long expectedVersion,
            @JsonProperty("candidate_response") @NotNull @Size(max = 50000) String response,
            @JsonProperty("submitted_code") @Size(max = 50000)
            @com.fasterxml.jackson.annotation.JsonInclude(com.fasterxml.jackson.annotation.JsonInclude.Include.NON_NULL) String code) {
        public Answer(UUID requestId, String turnId, long expectedVersion, String response) {
            this(requestId, turnId, expectedVersion, response, null);
        }
        @AssertTrue @JsonIgnore
        public boolean isAnswered() {
            return response != null && (!response.isBlank() || code != null && !code.isBlank());
        }
    }

    public record Stop(
            @JsonProperty("request_id") @NotNull UUID requestId,
            @JsonProperty("expected_state_version") @Min(1) long expectedVersion) {}

    public record NextQuestion(
            @JsonProperty("request_id") @NotNull UUID requestId,
            @JsonProperty("expected_state_version") @Min(1) long expectedVersion) {}

    public record Conversation(
            @JsonProperty("request_id") @NotNull UUID requestId,
            @JsonProperty("message_id") @NotBlank String messageId,
            @JsonProperty("expected_state_version") @Min(1) long expectedVersion,
            @NotBlank @Pattern(regexp = "NEXT|SUBMIT_INTRODUCTION|SKIP_INTRODUCTION") String action,
            @Size(max = 10000) String introduction) {}

    public record RunCode(
            @JsonProperty("turn_id") @NotBlank String turnId,
            @NotBlank @Size(max = 16000) String code,
            @Pattern(regexp = "python|javascript|sql") String language) {}

    public record Clarify(
            @JsonProperty("request_id") @NotNull UUID requestId,
            @JsonProperty("turn_id") @NotBlank String turnId,
            @JsonProperty("expected_state_version") @Min(1) long expectedVersion,
            @Pattern(regexp = "CLARIFY_PROMPT|HINT") String kind,
            @JsonProperty("candidate_question") @Size(max = 1500) String candidateQuestion) {
        public Clarify {
            kind = kind == null ? "CLARIFY_PROMPT" : kind;
            candidateQuestion = candidateQuestion == null ? "" : candidateQuestion;
        }
    }
}
