package fit.iuh.modules.session.dto;

import fit.iuh.modules.session.entity.Session;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SessionResponse {

    private String id;
    private UUID userId;
    private UUID resumeId;
    private String resumeFileName;
    private UUID jdId;
    private String jdTitle;
    private UUID assessmentId;
    private String status;
    private String interviewType;
    private String roleTitle;
    private Integer overallScore;
    private String overallFeedback;
    private Integer userRating;
    private String userFeedbackText;
    private LocalDateTime startedAt;
    private LocalDateTime endedAt;

    public static SessionResponse from(Session session) {
        if (session == null) return null;
        return SessionResponse.builder()
                .id(session.getId())
                .userId(session.getUserId())
                .resumeId(session.getResume() != null ? session.getResume().getId() : null)
                .resumeFileName(session.getResume() != null ? session.getResume().getFileName() : null)
                .jdId(session.getJobDescription() != null ? session.getJobDescription().getId() : null)
                .jdTitle(session.getJobDescription() != null ? session.getJobDescription().getTitle() : null)
                .assessmentId(session.getAssessmentId())
                .status(session.getStatus())
                .interviewType(session.getInterviewType())
                .roleTitle(session.getRoleTitle())
                .overallScore(session.getOverallScore())
                .overallFeedback(session.getOverallFeedback())
                .userRating(session.getUserRating())
                .userFeedbackText(session.getUserFeedbackText())
                .startedAt(session.getStartedAt())
                .endedAt(session.getEndedAt())
                .build();
    }
}
