package fit.iuh.modules.study.entity;

import java.time.LocalDateTime;

public record StudyTaskChecklistItem(long id, long taskId, String content, boolean isCompleted, int sortOrder,
                                     LocalDateTime completedAt, LocalDateTime createdAt, LocalDateTime updatedAt) {}
