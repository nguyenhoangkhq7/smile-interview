package fit.iuh.modules.session.dto;

import fit.iuh.modules.session.dto.SessionResponse.SessionTurnDto;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CreateSessionRequest {

    private String id;
    private String roleTitle;
    private String interviewType;
    private String status;
    private UUID resumeId;
    private UUID jdId;
    private String cvFilename;
    private String jdFilename;
    private Integer overallScore;
    private String overallFeedback;
    private Integer userRating;
    private String userFeedbackText;
    private List<SessionTurnDto> questions;
    private Boolean replaceQuestions;
}
