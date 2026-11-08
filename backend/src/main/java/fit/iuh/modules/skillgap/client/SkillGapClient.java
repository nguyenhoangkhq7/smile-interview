package fit.iuh.modules.skillgap.client;

import fit.iuh.config.AiClientConfig;
import fit.iuh.config.AppProperties;
import fit.iuh.exception.AiServiceException;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.AnalyzeWithReportResponseDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

/**
 * REST Client for Contribution 2: Skill-Gap Detection Algorithm.
 */
@Slf4j
@Component
public class SkillGapClient {

    private final RestClient restClient;

    public SkillGapClient(AppProperties appProperties) {
        this.restClient = AiClientConfig.createAiRestClient(appProperties);
    }

    public AnalyzeWithReportResponseDto analyzeGap(String sessionId, String cvText, String jdText) {
        log.info("[SkillGapClient] Calling POST /api/v1/pipeline/analyze for sessionId={}", sessionId);
        try {
            Map<String, Object> payload = Map.of(
                    "analysis_id", sessionId,
                    "cv_text", cvText != null ? cvText : "",
                    "jd_text", jdText != null ? jdText : ""
            );
            return restClient.post()
                    .uri("/api/v1/pipeline/analyze")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(AnalyzeWithReportResponseDto.class);
        } catch (Exception e) {
            log.error("[SkillGapClient] Pipeline analysis failed for sessionId={}: {}", sessionId, e.getMessage());
            throw new AiServiceException("Failed to execute Skill-Gap Detection pipeline: " + e.getMessage(), e);
        }
    }
}
