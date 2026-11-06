package fit.iuh.modules.skillgap.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.skillgap.client.SkillGapClient;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.AnalyzeWithReportResponseDto;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.SkillGapResultDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * REST Controller for Contribution 2: Skill-Gap Detection Algorithm.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/sessions/{sessionId}/analyze-gap")
@RequiredArgsConstructor
public class SkillGapController {

    private final SessionRepository sessionRepository;
    private final SkillGapClient skillGapClient;
    private final ObjectMapper objectMapper;

    @PostMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    @Transactional
    public ResponseEntity<AnalyzeWithReportResponseDto> analyzeSkillGap(
            @PathVariable String sessionId,
            @RequestParam(value = "forceRefresh", required = false, defaultValue = "false") boolean forceRefresh) {

        log.info("[SkillGapController] Analyze gap requested for sessionId={}, forceRefresh={}", sessionId, forceRefresh);

        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));

        if (!forceRefresh && session.getSkillGapJson() != null && session.getGapReportJson() != null) {
            try {
                List<SkillGapResultDto> cachedSkills = objectMapper.readValue(
                        session.getSkillGapJson(), new TypeReference<List<SkillGapResultDto>>() {});
                Map<String, Object> cachedReport = objectMapper.readValue(
                        session.getGapReportJson(), new TypeReference<Map<String, Object>>() {});
                return ResponseEntity.ok(new AnalyzeWithReportResponseDto(sessionId, cachedSkills, cachedReport));
            } catch (Exception e) {
                log.warn("[SkillGapController] Failed to parse cached skill gap JSON, re-running pipeline: {}", e.getMessage());
            }
        }

        String cvText = session.getResume() != null
                ? session.getResume().getRawText()
                : "";
        String jdText = session.getJobDescription() != null
                ? session.getJobDescription().getRawText()
                : "";

        AnalyzeWithReportResponseDto response = skillGapClient.analyzeGap(sessionId, cvText, jdText);

        try {
            session.setSkillGapJson(objectMapper.writeValueAsString(response.skills()));
            session.setGapReportJson(objectMapper.writeValueAsString(response.report()));

            if (response.skills() != null && !response.skills().isEmpty()) {
                double avgGap = response.skills().stream()
                        .mapToDouble(SkillGapResultDto::gapMagnitude)
                        .average()
                        .orElse(0.0);
                int matchScore = (int) Math.round(Math.max(0.0, Math.min(100.0, (1.0 - avgGap) * 100.0)));
                session.setOverallScore(matchScore);
            }
            sessionRepository.save(session);
        } catch (Exception e) {
            log.error("[SkillGapController] Error saving skill gap JSON to session {}: {}", sessionId, e.getMessage());
        }

        return ResponseEntity.ok(response);
    }
}
