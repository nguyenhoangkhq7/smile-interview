package fit.iuh.modules.evidence;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.*;
import java.util.UUID;

public final class EvidenceDtos {
    private EvidenceDtos() {}

    public record Config(
            @NotBlank String mode,
            @JsonProperty("focused_question_mode") String focusedMode,
            @JsonProperty("max_questions") @Min(1) @Max(40) int maxQuestions,
            @JsonProperty("duration_seconds") @Min(60) @Max(7200) int durationSeconds,
            @JsonProperty("max_questions_per_objective") @Min(1) @Max(40) int maxPerObjective,
            @JsonProperty("interaction_mode") @Pattern(regexp = "TEXT|VOICE") String interactionMode) {
        public Config {
            interactionMode = interactionMode == null ? "TEXT" : interactionMode;
        }
        public Config(String mode, String focusedMode, int maxQuestions, int durationSeconds, int maxPerObjective) {
            this(mode, focusedMode, maxQuestions, durationSeconds, maxPerObjective, "TEXT");
        }
        public static Config defaults() { return new Config("MIXED", null, 10, 900, 8); }
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
