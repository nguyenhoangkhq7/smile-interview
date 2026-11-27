package fit.iuh.modules.admin.interviews.service;

import fit.iuh.modules.admin.aipolicy.service.AiPolicySources;
import fit.iuh.modules.admin.interviews.dto.AdminInterviewDtos.QualityReview;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AdminAiQualityService {
    private final AdminInterviewService interviews;
    private final AiPolicySources runtime;

    public QualityReview review(String id) {
        return runtime.quality(interviews.qualityInput(id));
    }
}
