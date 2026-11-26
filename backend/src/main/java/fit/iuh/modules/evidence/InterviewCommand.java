package fit.iuh.modules.evidence;

import jakarta.persistence.*;
import lombok.*;
import java.util.UUID;

@Entity
@Table(name = "interview_commands")
@Getter @Setter @NoArgsConstructor
public class InterviewCommand {
    @Id private UUID id;
    @Column(length = 128, nullable = false) private String sessionId;
    @Column(nullable = false) private UUID requestId;
    @Column(length = 64, nullable = false) private String requestHash;
    @Column(columnDefinition = "text", nullable = false) private String responseJson;
}
