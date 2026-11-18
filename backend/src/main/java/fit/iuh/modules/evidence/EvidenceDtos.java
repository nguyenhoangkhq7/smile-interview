package fit.iuh.modules.evidence;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.*;
import java.util.UUID;

public final class EvidenceDtos {
    private EvidenceDtos() {}

    public record Config(
            @JsonProperty(access = JsonProperty.Access.WRITE_ONLY) String mode,
            @JsonProperty("focused_question_mode") String focusedMode,
            @JsonProperty("max_questions") @Min(1) @Max(40) int maxQuestions,
            @JsonProperty("duration_seconds") @Min(60) @Max(7200) int durationSeconds,
            @JsonProperty("max_questions_per_objective") @Min(1) @Max(40) Integer maxPerObjective,
            @JsonProperty("interaction_mode") @Pattern(regexp = "TEXT|VOICE") String interactionMode) {
        static final int DEFAULT_MAX_PER_OBJECTIVE = 8;

        public Config {
            interactionMode = interactionMode == null ? "TEXT" : interactionMode;
            maxPerObjective = maxPerObjective == null ? DEFAULT_MAX_PER_OBJECTIVE : maxPerObjective;
        }
        public Config(String mode, String focusedMode, int maxQuestions, int durationSeconds, int maxPerObjective) {
            this(mode, focusedMode, maxQuestions, durationSeconds, maxPerObjective, "TEXT");
        }
        public static Config defaults() { return new Config(null, null, 10, 900, null, "TEXT"); }

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
            @JsonProperty("candidate_response") @NotBlank @Size(max = 50000) String response) {}

    public record Stop(
            @JsonProperty("request_id") @NotNull UUID requestId,
            @JsonProperty("expected_state_version") @Min(1) long expectedVersion) {}

    public record Conversation(
            @JsonProperty("request_id") @NotNull UUID requestId,
            @JsonProperty("message_id") @NotBlank String messageId,
            @JsonProperty("expected_state_version") @Min(1) long expectedVersion,
            @NotBlank @Pattern(regexp = "NEXT|SUBMIT_INTRODUCTION|SKIP_INTRODUCTION") String action,
            @Size(max = 10000) String introduction) {}
}
