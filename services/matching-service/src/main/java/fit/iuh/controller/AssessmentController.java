package fit.iuh.controller;

import fit.iuh.dto.AssessmentResponse;
import fit.iuh.service.AssessmentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

/**
 * REST Controller exposing the holistic Resume Assessment API.
 *
 * <p>Base path: {@code /api/v2/assess-resume}
 *
 * <h2>Endpoint Summary</h2>
 * <pre>
 *   GET /api/v2/assess-resume?sessionId={id}[&forceRefresh=true]  — Blocking JSON response (Cache-Aside)
 *   GET /api/v2/assess-resume/stream?sessionId={id}               — SSE streaming response
 * </pre>
 *
 * <h2>Cache-Aside Behavior</h2>
 * The blocking endpoint checks the database for a cached result before calling
 * the LLM API. Pass {@code forceRefresh=true} to delete the cache and regenerate.
 * The response includes a {@code "cached": true/false} field to indicate the source.
 */
@Slf4j
@RestController
@RequestMapping("/api/v2/assess-resume")
@RequiredArgsConstructor
public class AssessmentController {

    private final AssessmentService assessmentService;

    /**
     * Performs a synchronous resume assessment and returns the complete report as JSON.
     *
     * <p>Implements Cache-Aside: returns the cached DB result if available.
     * Use {@code forceRefresh=true} to bypass the cache and regenerate from LLM.
     *
     * @param sessionId    the unique interview session identifier (required)
     * @param forceRefresh if {@code true}, bypasses the cache and re-generates (default: false)
     * @return HTTP 200 with an {@link AssessmentResponse} containing the report and metadata
     */
    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AssessmentResponse> assessResumeBlocking(
            @RequestParam("sessionId") String sessionId,
            @RequestParam(value = "forceRefresh", defaultValue = "false") boolean forceRefresh) {

        log.info("Blocking assessment request: sessionId={}, forceRefresh={}", sessionId, forceRefresh);
        AssessmentResponse response = assessmentService.assessResumeBlocking(sessionId, forceRefresh);
        return ResponseEntity.ok(response);
    }

    /**
     * Streams a holistic resume assessment report as Server-Sent Events.
     *
     * <p>Each SSE event carries a plain-text token fragment of the Markdown report.
     * The complete report is persisted to the database after the stream completes.
     *
     * <p>Example cURL:
     * <pre>
     *   curl -N -H "Accept: text/event-stream" \
     *     "http://localhost:8081/api/v2/assess-resume/stream?sessionId=session-123"
     * </pre>
     *
     * @param sessionId the unique interview session identifier (required)
     * @return a reactive {@link Flux} of {@link ServerSentEvent} tokens
     */
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> streamAssessment(
            @RequestParam("sessionId") String sessionId) {

        log.info("SSE assessment request: sessionId={}", sessionId);
        return assessmentService.streamAssessment(sessionId);
    }
}
