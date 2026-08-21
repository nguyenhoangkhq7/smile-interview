package fit.iuh.modules.session.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "sessions")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Session {

    @Id
    @Column(name = "id", updatable = false, nullable = false, length = 128)
    private String id;

    @Column(name = "user_id")
    private UUID userId;

    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "resume_id")
    private Resume resume;

    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "jd_id")
    private JobDescription jobDescription;

    @Column(name = "assessment_id")
    private UUID assessmentId;

    @Column(name = "status", length = 50)
    private String status;

    @Column(name = "interview_type", length = 50)
    private String interviewType;

    @Column(name = "role_title")
    private String roleTitle;

    @Column(name = "overall_score")
    private Integer overallScore;

    @Column(name = "overall_feedback", columnDefinition = "text")
    private String overallFeedback;

    @Column(name = "user_rating")
    private Integer userRating;

    @Column(name = "user_feedback_text", columnDefinition = "text")
    private String userFeedbackText;

    @Column(name = "started_at", updatable = false)
    private LocalDateTime startedAt;

    @Column(name = "ended_at")
    private LocalDateTime endedAt;
}
