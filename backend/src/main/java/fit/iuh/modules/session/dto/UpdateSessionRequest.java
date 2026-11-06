package fit.iuh.modules.session.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UpdateSessionRequest {

    private String roleTitle;
    private String interviewType;
    private String status;
    private Integer overallScore;
    private String overallFeedback;
    private Integer userRating;
    private String userFeedbackText;
    private LocalDateTime endedAt;
}
