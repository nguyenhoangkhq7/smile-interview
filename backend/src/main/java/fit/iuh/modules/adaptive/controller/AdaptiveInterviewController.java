package fit.iuh.modules.adaptive.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.adaptive.client.AdaptiveInterviewClient;
import fit.iuh.modules.adaptive.dto.AdaptiveDtos.RespondInterviewRequestDto;
import fit.iuh.modules.adaptive.dto.AdaptiveDtos.RespondInterviewResponseDto;
import fit.iuh.modules.adaptive.dto.AdaptiveDtos.StartInterviewResponseDto;
import fit.iuh.modules.session.entity.Session;
import fit.iuh.modules.session.entity.SessionTurn;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.modules.session.repository.SessionTurnRepository;
import fit.iuh.modules.skillgap.client.SkillGapClient;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.AnalyzeWithReportResponseDto;
import fit.iuh.modules.skillgap.dto.SkillGapDtos.SkillGapResultDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * REST Controller for Contribution 3: Prompt-Chaining & Bayesian Adaptive Questioning Framework.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/sessions/{sessionId}/interview")
@RequiredArgsConstructor
public class AdaptiveInterviewController {

    private final SessionRepository sessionRepository;
    private final SessionTurnRepository sessionTurnRepository;
    private final AdaptiveInterviewClient adaptiveClient;
    private final SkillGapClient skillGapClient;
    private final ObjectMapper objectMapper;

    @PostMapping(value = "/start", produces = MediaType.APPLICATION_JSON_VALUE)
    @Transactional
    public ResponseEntity<StartInterviewResponseDto> startAdaptiveInterview(@PathVariable String sessionId) {
        log.info("[AdaptiveInterviewController] Starting adaptive interview for sessionId={}", sessionId);

        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));

        if (session.getSkillGapJson() == null || session.getSkillGapJson().isBlank()) {
            String cvText = session.getResume() != null ? session.getResume().getRawText() : "";
            String jdText = session.getJobDescription() != null ? session.getJobDescription().getRawText() : "";
            AnalyzeWithReportResponseDto gapRes = skillGapClient.analyzeGap(sessionId, cvText, jdText);
            try {
                session.setSkillGapJson(objectMapper.writeValueAsString(gapRes.skills()));
                session.setGapReportJson(objectMapper.writeValueAsString(gapRes.report()));
                session = sessionRepository.save(session);
            } catch (Exception e) {
                log.warn("[AdaptiveInterviewController] Could not serialize skill gap: {}", e.getMessage());
            }
        }

        List<SkillGapResultDto> skills;
        try {
            skills = objectMapper.readValue(session.getSkillGapJson(), new TypeReference<List<SkillGapResultDto>>() {});
        } catch (Exception e) {
            throw new IllegalStateException("Invalid skill_gap_json in session " + sessionId, e);
        }

        StartInterviewResponseDto startRes = adaptiveClient.startInterview(skills);

        session.setAiInterviewSessionId(startRes.sessionId());
        session.setStatus(startRes.isFinished() ? "Completed" : "In progress");
        sessionRepository.save(session);

        // Clear previous turns and save Turn 1
        sessionTurnRepository.deleteBySessionId(sessionId);
        if (!startRes.isFinished() && startRes.question() != null) {
            String abducStr = startRes.abductiveReasoning() != null
                    ? String.format("[C0] %s | [A0] %s",
                            startRes.abductiveReasoning().surprisingFactC(),
                            startRes.abductiveReasoning().hypothesisA())
                    : "";
            SessionTurn turn1 = SessionTurn.builder()
                    .sessionId(sessionId)
                    .question(startRes.question())
                    .answer("")
                    .topicTag(startRes.activeSkillId())
                    .suggestedAnswer(abducStr)
                    .isDeepDive(false)
                    .build();
            sessionTurnRepository.save(turn1);
        }

        return ResponseEntity.ok(startRes);
    }

    @PostMapping(
            value = "/respond",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    @Transactional
    public ResponseEntity<RespondInterviewResponseDto> respondAdaptiveInterview(
            @PathVariable String sessionId,
            @RequestBody RespondInterviewRequestDto request) {

        log.info("[AdaptiveInterviewController] Received response for sessionId={}", sessionId);

        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));

        if (session.getAiInterviewSessionId() == null || session.getAiInterviewSessionId().isBlank()) {
            throw new IllegalStateException("Adaptive interview has not been started for session " + sessionId);
        }

        String evaluatedSkillBefore = null;
        var existingTurns = sessionTurnRepository.findBySessionIdOrderByIdAsc(sessionId);
        SessionTurn currentTurn = existingTurns.isEmpty() ? null : existingTurns.get(existingTurns.size() - 1);
        if (currentTurn != null) {
            evaluatedSkillBefore = currentTurn.getTopicTag();
        }

        RespondInterviewResponseDto resp = adaptiveClient.respondInterview(
                session.getAiInterviewSessionId(),
                request.candidateResponse()
        );

        if (currentTurn != null) {
            currentTurn.setAnswer(request.candidateResponse());
            currentTurn.setStrengths(resp.reflectiveInsight());
            currentTurn.setImprovements(String.format(
                    "Metamorphic Tag: %s | TV Delta: %.3f | Belief: %s -> %s",
                    resp.metamorphicTag(),
                    resp.tvDelta(),
                    resp.previousBelief(),
                    resp.updatedBelief()
            ));
            if (resp.updatedBelief() != null && resp.updatedBelief().size() == 3) {
                double sHat = 1.5 * resp.updatedBelief().get(0)
                        + 3.0 * resp.updatedBelief().get(1)
                        + 4.5 * resp.updatedBelief().get(2);
                currentTurn.setScore((int) Math.round((sHat / 5.0) * 100.0));
            }
            sessionTurnRepository.save(currentTurn);
        }

        if (!resp.isFinished() && resp.nextQuestion() != null && !resp.nextQuestion().isBlank()) {
            boolean isFollowUpOnSameSkill = evaluatedSkillBefore != null
                    && evaluatedSkillBefore.equalsIgnoreCase(resp.activeSkillId());
            SessionTurn nextTurn = SessionTurn.builder()
                    .sessionId(sessionId)
                    .question(resp.nextQuestion())
                    .answer("")
                    .topicTag(resp.activeSkillId())
                    .isDeepDive(isFollowUpOnSameSkill)
                    .build();
            sessionTurnRepository.save(nextTurn);
        }

        if (resp.isFinished()) {
            session.setStatus("Completed");
            session.setEndedAt(LocalDateTime.now());
            try {
                Map<String, Object> report = adaptiveClient.getInterviewReport(session.getAiInterviewSessionId());
                session.setInterviewReportJson(objectMapper.writeValueAsString(report));
                if (report.get("markdown_summary") instanceof String md) {
                    session.setOverallFeedback(md);
                }
            } catch (Exception e) {
                log.warn("[AdaptiveInterviewController] Could not auto-fetch final HITL report: {}", e.getMessage());
            }
            sessionRepository.save(session);
        }

        return ResponseEntity.ok(resp);
    }

    @GetMapping(value = "/report", produces = MediaType.APPLICATION_JSON_VALUE)
    @Transactional
    public ResponseEntity<Map<String, Object>> getInterviewReport(@PathVariable String sessionId) {
        log.info("[AdaptiveInterviewController] Fetching report for sessionId={}", sessionId);

        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));

        if (session.getInterviewReportJson() != null && !session.getInterviewReportJson().isBlank()) {
            try {
                Map<String, Object> cached = objectMapper.readValue(
                        session.getInterviewReportJson(), new TypeReference<Map<String, Object>>() {});
                return ResponseEntity.ok(cached);
            } catch (Exception e) {
                log.warn("[AdaptiveInterviewController] Failed to parse cached interviewReportJson: {}", e.getMessage());
            }
        }

        if (session.getAiInterviewSessionId() != null && !session.getAiInterviewSessionId().isBlank()) {
            Map<String, Object> liveReport = adaptiveClient.getInterviewReport(session.getAiInterviewSessionId());
            try {
                session.setInterviewReportJson(objectMapper.writeValueAsString(liveReport));
                sessionRepository.save(session);
            } catch (Exception ignored) {}
            return ResponseEntity.ok(liveReport);
        }

        throw new ResourceNotFoundException("No interview report available for session " + sessionId);
    }
}
