package fit.iuh.modules.session.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

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
    private UUID assessmentId;
    private String cvFilename;
    private String jdFilename;
}
