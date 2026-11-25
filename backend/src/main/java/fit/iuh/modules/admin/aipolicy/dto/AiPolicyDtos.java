package fit.iuh.modules.admin.aipolicy.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class AiPolicyDtos {
    private AiPolicyDtos() {}
    private static final String ID = "[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}";
    private static final String OPTIONAL = "(?:" + ID + ")?";
    private static final String HF_ID = "[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}";

    public record Models(@NotBlank @Pattern(regexp = ID) String interviewModel,
            @NotNull @Pattern(regexp = OPTIONAL) String fastModel,
            @NotBlank @Pattern(regexp = ID) String matchingModel,
            @NotNull @Pattern(regexp = OPTIONAL) String verifierModel,
            @NotBlank @Pattern(regexp = ID) String skillGapModel,
            @NotBlank @Pattern(regexp = HF_ID) String embeddingModel,
            @NotNull @Pattern(regexp = "[A-Za-z0-9._/-]{0,120}") String embeddingRevision,
            @NotBlank @Pattern(regexp = ID) String sttModel,
            @NotBlank @Pattern(regexp = ID) String ttsModel,
            @NotBlank @Size(max = 120) String ttsVoice,
            @NotBlank @Pattern(regexp = "pcm|mp3") String ttsFormat,
            @NotNull @Min(8000) @Max(96000) Integer ttsSampleRate,
            @NotNull @Pattern(regexp = OPTIONAL) String simliFaceId) {}

    public record Policy(@NotNull @DecimalMin("0") @DecimalMax("1") Double coreImportance,
            @NotNull @Min(1) @Max(4) Integer fallbackDepth,
            @NotNull @DecimalMin("0") @DecimalMax("0.8") Double reserveFollowupFraction,
            @NotNull @Min(2) @Max(5) Integer minFailureContexts,
            @NotNull Boolean allowExtensionProbes,
            @NotNull @Min(1) @Max(40) Integer maxQuestions,
            @NotNull @Min(60) @Max(7200) Integer durationSeconds,
            @NotNull @Min(1) @Max(40) Integer maxQuestionsPerObjective,
            @NotNull Boolean voiceEnabled, @NotNull Boolean simliAvatarEnabled,
            @NotNull @Min(0) @Max(1000) Integer dailyQuota) {
        public static Policy defaults() {
            return new Policy(0.7, 2, 0.3, 2, true, 40, 7200, 40, true, true, 0);
        }
    }

    public record Settings(@NotNull @Valid Models models, @NotNull @Valid Policy policy) {}
    public record Credentials(String openRouterKey, String simliKey, boolean resetOpenRouterKey, boolean resetSimliKey) {
        @Override public String toString() { return "Credentials[redacted]"; }
    }
    public record Save(@NotNull @Min(0) Long revision, @NotNull @Valid Settings settings, Credentials credentials) {}
    public record Reset(@NotNull @Min(0) Long revision) {}
    public record Parameter(String key, double value) {}
    public record Defaults(Settings settings, boolean openRouterConfigured, boolean simliConfigured,
                           List<Parameter> skillGapParameters, int embeddingDimension,
                           boolean embeddingLoaded, boolean evidenceReady) {}
    public record View(long revision, Instant updatedAt, Settings settings, boolean overridden,
                       boolean openRouterOverridden, boolean simliOverridden, boolean openRouterConfigured,
                       boolean simliConfigured, List<Parameter> skillGapParameters, Integer embeddingDimension) {}
    public record Check(String id, String status, Long latencyMs, String detail) {}
    public record Runtime(long revision, Settings settings, Map<String, String> credentials) {
        @Override public String toString() { return "Runtime[revision=" + revision + "]"; }
    }
    public record SealedRuntime(String payload) {}
}
