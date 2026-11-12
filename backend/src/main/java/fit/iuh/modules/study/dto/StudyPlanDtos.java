package fit.iuh.modules.study.dto;

import fit.iuh.modules.application.CompetencyProjection;
import fit.iuh.modules.study.entity.StudyPlan;
import fit.iuh.modules.study.entity.StudyTask;
import fit.iuh.modules.study.entity.StudyTaskChecklistItem;
import fit.iuh.modules.study.entity.StudyTaskResource;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

public final class StudyPlanDtos {
    private StudyPlanDtos() {}

    public record PlanInput(@NotBlank @Size(max = 255) String title, @Size(max = 10000) String description,
                            @NotNull @DecimalMin("0") @DecimalMax("100") @Digits(integer = 3, fraction = 2)
                            BigDecimal targetCompletionPercent, LocalDate targetDate,
                            @Size(max = 128) String sourceSessionId) {}

    public record Progress(long done, int total, BigDecimal percent, Boolean meetsTarget) {}

    public record PlanView(StudyPlan plan, Progress progress, List<TaskView> tasks) {}

    public record PlanTotals(UUID applicationProfileId, long done, int total, BigDecimal targetCompletionPercent) {}
    public record PlanProgress(UUID applicationProfileId, Progress progress) {}

    public record KnowledgeGaps(int completedAttempts, List<CompetencyProjection.Skill> weak,
                                List<CompetencyProjection.Skill> needsVerification,
                                List<String> notAssessedSkillIds, List<ReportWeakness> reportWeaknesses,
                                List<ObjectiveSuggestion> objectiveSuggestions) {}

    public record ObjectiveSuggestion(String skillId, String objectiveId, String claim, String assessment,
                                      CompetencyProjection.Source source, List<CriterionSuggestion> criteria) {}

    public record CriterionSuggestion(String criterionId, String description, boolean essential, String assessment,
                                      String kind, boolean selectedByDefault, String reason, String goal,
                                      CompetencyProjection.Source source, CompetencyProjection.Source lastAssessment) {}

    public record ReportWeakness(String skillId, String sessionId, int attemptNumber, List<String> weaknesses) {}

    public record TaskView(StudyTask task, List<StudyTaskChecklistItem> checklist, List<StudyTaskResource> resources) {}

    public record TaskInput(@NotBlank @Size(max = 255) String title, String skillId,
                            @Size(max = 10000) String notes, @NotNull @Pattern(regexp = "TODO|IN_PROGRESS|DONE")
                            String status, @PositiveOrZero Integer sortOrder) {}

    public record GapOriginInput(@NotBlank @Size(max = 128) String skillId,
                                 @Size(max = 128) String sessionId,
                                 @Positive Integer attemptNumber, @Size(max = 128) String objectiveId) {}

    public record TaskPositionInput(@NotNull @Pattern(regexp = "TODO|IN_PROGRESS|DONE") String status,
                                    @Positive Long beforeTaskId) {}

    public record TaskParentInput(@Positive Long parentTaskId,
                                  @Pattern(regexp = "TODO|IN_PROGRESS|DONE") String status) {}

    public record CreateTaskInput(@NotBlank @Size(max = 255) String title, String skillId,
                                  @Size(max = 10000) String notes, @NotNull @Pattern(regexp = "TODO|IN_PROGRESS|DONE")
                                  String status, @PositiveOrZero Integer sortOrder,
                                  @Size(max = 50) List<@NotNull @Valid ChecklistInput> checklist,
                                  @Valid ResourceInput resource, @Positive Long parentTaskId,
                                  @Valid GapOriginInput gapOrigin) {
        public TaskInput task() {
            return new TaskInput(title, skillId, notes, status, sortOrder);
        }
    }

    public record ChecklistInput(@NotBlank @Size(max = 500) String content, Boolean isCompleted,
                                 @PositiveOrZero Integer sortOrder,
                                 @Size(max = 128) String sourceCriterionId,
                                 @Size(max = 128) String sourceSessionId, @Positive Integer sourceAttemptNumber) {}

    public record ResourceInput(@NotBlank @Size(max = 255) String title, @NotBlank @Size(max = 2048) String url) {}

    public record Attachment(String fileName, byte[] fileData) {}
}
