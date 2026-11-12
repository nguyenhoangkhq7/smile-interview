package fit.iuh.modules.study.entity;

import java.time.LocalDateTime;

public record StudyTask(long id, long planId, String skillId, String title, String notes, String status, int sortOrder,
                        LocalDateTime completedAt, LocalDateTime createdAt, LocalDateTime updatedAt, Long parentTaskId,
                        String gapSourceSkillId, String gapSourceSessionId, Integer gapSourceAttemptNumber,
                        String gapSourceObjectiveId) {}
