package fit.iuh.modules.study.entity;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.UUID;

public record StudyPlan(Long id, UUID applicationProfileId, String sourceSessionId, String title, String description,
                        BigDecimal targetCompletionPercent, LocalDate targetDate, String status,
                        LocalDateTime createdAt, LocalDateTime updatedAt) {}
