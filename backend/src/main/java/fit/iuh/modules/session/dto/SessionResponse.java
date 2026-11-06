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
    private String status;
    private String interviewType;
    private String roleTitle;
    private Integer overallScore;
    private String overallFeedback;
    private Integer userRating;
    private String userFeedbackText;
    private String skillGapJson;
    private String gapReportJson;
    private String aiInterviewSessionId;
    private String interviewReportJson;
    private LocalDateTime startedAt;
    private LocalDateTime endedAt;
    private java.util.List<SessionTurnDto> turns;

    public record SessionTurnDto(
            Long id,
            String question,
            String answer,
            Integer score,
            String strengths,
            String improvements,
            String suggestedAnswer,
            String topicTag,
            Boolean isDeepDive
    ) {
        public static SessionTurnDto from(fit.iuh.modules.session.entity.SessionTurn t) {
            if (t == null) return null;
            return new SessionTurnDto(
                    t.getId(),
                    t.getQuestion(),
                    t.getAnswer(),
                    t.getScore(),
                    t.getStrengths(),
                    t.getImprovements(),
                    t.getSuggestedAnswer(),
                    t.getTopicTag(),
                    t.getIsDeepDive()
            );
        }
    }

    public static SessionResponse from(Session session) {
        return from(session, null);
    }

    public static SessionResponse from(Session session, java.util.List<fit.iuh.modules.session.entity.SessionTurn> turns) {
        if (session == null) return null;
        return SessionResponse.builder()
                .id(session.getId())
                .userId(session.getUserId())
                .resumeId(session.getResume() != null ? session.getResume().getId() : null)
                .resumeFileName(session.getResume() != null ? session.getResume().getFileName() : null)
                .jdId(session.getJobDescription() != null ? session.getJobDescription().getId() : null)
                .jdTitle(session.getJobDescription() != null ? session.getJobDescription().getTitle() : null)
                .status(session.getStatus())
                .interviewType(session.getInterviewType())
                .roleTitle(session.getRoleTitle())
                .overallScore(session.getOverallScore())
                .overallFeedback(session.getOverallFeedback())
                .userRating(session.getUserRating())
                .userFeedbackText(session.getUserFeedbackText())
                .skillGapJson(session.getSkillGapJson())
                .gapReportJson(session.getGapReportJson())
                .aiInterviewSessionId(session.getAiInterviewSessionId())
                .interviewReportJson(session.getInterviewReportJson())
                .startedAt(session.getStartedAt())
                .endedAt(session.getEndedAt())
                .turns(turns != null ? turns.stream().map(SessionTurnDto::from).toList() : null)
                .build();
    }
}
