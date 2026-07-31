package fit.iuh.modules.session.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "job_descriptions")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class JobDescription {

    @Id
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "user_id")
    private UUID userId;

    @Column(name = "title", nullable = false)
    private String title;

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

    @Column(name = "accepted_levels")
    private String acceptedLevels;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;
}
