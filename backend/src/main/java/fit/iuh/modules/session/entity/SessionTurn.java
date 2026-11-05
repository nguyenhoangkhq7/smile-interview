package fit.iuh.modules.session.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "session_turns")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SessionTurn {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "session_id", nullable = false, length = 128)
    private String sessionId;

    @Column(columnDefinition = "TEXT")
    private String question;

    @Column(columnDefinition = "TEXT")
    private String answer;

    private Integer score;

    @Column(columnDefinition = "TEXT")
    private String strengths;

    @Column(columnDefinition = "TEXT")
    private String improvements;

    @Column(name = "suggested_answer", columnDefinition = "TEXT")
    private String suggestedAnswer;

    @Column(name = "topic_tag")
    private String topicTag;

    @Column(name = "is_deep_dive")
    private Boolean isDeepDive;

    @Column(name = "hr_rating")
    private Integer hrRating;

    @Column(name = "hr_feedback", columnDefinition = "TEXT")
    private String hrFeedback;
}
