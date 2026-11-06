package fit.iuh.modules.matching.client;

import fit.iuh.config.AppProperties;
import fit.iuh.exception.AiServiceException;
import fit.iuh.modules.matching.dto.MatchingDtos.Module1OutputDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

/**
 * REST Client for Contribution 1: Semantic Similarity Metric (Sentence-BERT + GNN).
 */
@Slf4j
@Component
public class SemanticMatchingClient {

    private final RestClient restClient;

    public SemanticMatchingClient(AppProperties appProperties) {
        String baseUrl = appProperties.getAi() != null && appProperties.getAi().getFastapi() != null
                ? appProperties.getAi().getFastapi().getBaseUrl()
                : "http://localhost:8000";
        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .build();
    }

    public Module1OutputDto match(String cvText, String jdText) {
        log.info("[SemanticMatchingClient] Executing SBERT+GNN matching: CV len={}, JD len={}",
                cvText != null ? cvText.length() : 0, jdText != null ? jdText.length() : 0);
        try {
            Map<String, Object> payload = Map.of(
                    "cv_text", cvText != null ? cvText : "",
                    "jd_text", jdText != null ? jdText : ""
            );
            return restClient.post()
                    .uri("/api/v1/match")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(Module1OutputDto.class);
        } catch (Exception e) {
            log.error("[SemanticMatchingClient] Error executing match: {}", e.getMessage());
            throw new AiServiceException("Failed to execute SBERT+GNN Semantic Matching: " + e.getMessage(), e);
        }
    }
}
