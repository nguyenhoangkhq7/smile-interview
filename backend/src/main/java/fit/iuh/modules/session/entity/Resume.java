package fit.iuh.modules.session.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "resumes")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Resume {

    @Id
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "user_id")
    private UUID userId;

    @Column(name = "file_name", nullable = false)
    private String fileName;

    @Column(name = "parsed_content", columnDefinition = "text")
    private String parsedContent;

    @Column(name = "raw_text", columnDefinition = "text")
    private String rawText;

    @Column(name = "file_url")
    private String fileUrl;

    @Column(name = "cloudinary_id")
    private String cloudinaryId;

    @Column(name = "job_category")
    private String jobCategory;

    @Column(name = "seniority_level")
    private String seniorityLevel;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;
}
