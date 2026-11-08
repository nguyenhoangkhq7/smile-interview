package fit.iuh.modules.application;

import fit.iuh.modules.session.entity.JobDescription;
import fit.iuh.modules.session.entity.Resume;
import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity @Table(name = "application_profiles")
@Getter @Setter @NoArgsConstructor
public class ApplicationProfile {
    @Id private UUID id;
    @Column(nullable = false) private UUID userId;
    @Column(nullable = false, length = 200) private String title;
    @Column(length = 200) private String company;
    @Column(nullable = false) private String roleTitle;
    @ManyToOne(optional = false) @JoinColumn(name = "resume_id") private Resume resume;
    @ManyToOne(optional = false) @JoinColumn(name = "jd_id") private JobDescription jobDescription;
    @Column(nullable = false) private String cvFilename;
    @Column(nullable = false) private String jdTitle;
    @Column(nullable = false, columnDefinition = "text") private String cvText;
    @Column(nullable = false, columnDefinition = "text") private String jdText;
    @Column(nullable = false, columnDefinition = "text") private String skillGapJson;
    @Column(nullable = false, columnDefinition = "text") private String gapReportJson;
    @Column(columnDefinition = "text") private String blueprintJson;
    @Column(columnDefinition = "text") private String policyJson;
    @Column(nullable = false) private LocalDateTime createdAt;
}
