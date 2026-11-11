package fit.iuh.modules.study.entity;

import java.time.LocalDateTime;

public record StudyTaskResource(long id, long taskId, String title, String url, String fileName, LocalDateTime createdAt) {}
