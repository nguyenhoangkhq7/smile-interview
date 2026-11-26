package fit.iuh.modules.evidence;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "interview_runs")
@Getter @Setter @NoArgsConstructor
public class InterviewRun {
    @Id @Column(name = "session_id", length = 128)
    private String sessionId;
    private long stateVersion;
    @Column(columnDefinition = "text", nullable = false)
    private String configJson;
    @Column(columnDefinition = "text", nullable = false)
    private String snapshotJson;
    @Column(columnDefinition = "text", nullable = false)
    private String publicJson;
}
