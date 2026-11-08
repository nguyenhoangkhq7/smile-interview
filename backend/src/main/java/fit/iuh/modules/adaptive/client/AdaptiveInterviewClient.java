package fit.iuh.modules.adaptive.client;

import fit.iuh.config.AiClientConfig;
import fit.iuh.config.AppProperties;
import fit.iuh.exception.AiServiceException;
import fit.iuh.modules.adaptive.dto.AdaptiveDtos.RespondInterviewResponseDto;
import fit.iuh.modules.adaptive.dto.AdaptiveDtos.StartInterviewResponseDto;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.SkillGapResultDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;

/**
 * REST Client for Contribution 3: Prompt-Chaining & Bayesian Adaptive Questioning Framework.
 */
@Slf4j
@Component
public class AdaptiveInterviewClient {

    private final RestClient restClient;

    public AdaptiveInterviewClient(AppProperties appProperties) {
        this.restClient = AiClientConfig.createAiRestClient(appProperties);
    }

    public StartInterviewResponseDto startInterview(List<SkillGapResultDto> skills) {
        log.info("[AdaptiveInterviewClient] Calling POST /api/v1/interview/start with {} skills",
                skills != null ? skills.size() : 0);
        try {
            Map<String, Object> payload = Map.of("skills", skills != null ? skills : List.of());
            return restClient.post()
                    .uri("/api/v1/interview/start")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(StartInterviewResponseDto.class);
        } catch (Exception e) {
            log.error("[AdaptiveInterviewClient] Failed to start interview: {}", e.getMessage());
            throw new AiServiceException("Failed to start adaptive interview: " + e.getMessage(), e);
        }
    }

    public RespondInterviewResponseDto respondInterview(String sessionId, String candidateResponse) {
        log.info("[AdaptiveInterviewClient] Calling POST /api/v1/interview/respond for sessionId={}", sessionId);
        try {
            Map<String, Object> payload = Map.of(
                    "session_id", sessionId,
                    "candidate_response", candidateResponse != null ? candidateResponse : ""
            );
            return restClient.post()
                    .uri("/api/v1/interview/respond")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(RespondInterviewResponseDto.class);
        } catch (Exception e) {
            log.error("[AdaptiveInterviewClient] Failed to process candidate response: {}", e.getMessage());
            throw new AiServiceException("Failed to process candidate response: " + e.getMessage(), e);
        }
    }

    public Map<String, Object> getInterviewReport(String sessionId) {
        log.info("[AdaptiveInterviewClient] Calling GET /api/v1/interview/report/{}", sessionId);
        try {
            return restClient.get()
                    .uri("/api/v1/interview/report/{session_id}", sessionId)
                    .accept(MediaType.APPLICATION_JSON)
                    .retrieve()
                    .body(new ParameterizedTypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            log.error("[AdaptiveInterviewClient] Failed to fetch HITL interview report: {}", e.getMessage());
            throw new AiServiceException("Failed to fetch HITL interview report: " + e.getMessage(), e);
        }
    }
}
