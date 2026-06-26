package fit.iuh.controller;

import fit.iuh.service.AssessmentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

/**
 * REST Controller that exposes the holistic Resume Assessment API using
 * Server-Sent Events (SSE) for progressive streaming.
 *
 * <p>Base path: {@code /api/v2/assess-resume}
 *
 * <h2>Why SSE?</h2>
 * The LLM assessment report can exceed 2 000 tokens (~10-15 seconds of generation).
 * A synchronous HTTP response would cause client-side timeouts and poor UX.
 * SSE allows the server to push each token to the client in real-time, producing
 * a ChatGPT-like streaming effect.
 *
 * <h2>Endpoint Summary</h2>
 * <pre>
 *   GET /api/v2/assess-resume/stream?sessionId={sessionId}
 * </pre>
 *
 * <h2>Example — cURL</h2>
 * <pre>
 *   curl -N -H "Accept: text/event-stream" \
 *     "http://localhost:8081/api/v2/assess-resume/stream?sessionId=session-123"
 * </pre>
 *
 * <h2>Example — JavaScript EventSource</h2>
 * <pre>{@code
 *   const source = new EventSource(
 *     '/api/v2/assess-resume/stream?sessionId=session-123'
 *   );
 *   source.onmessage = (e) => process.stdout.write(e.data);
 *   source.addEventListener('error', (e) => { console.error(e.data); source.close(); });
 * }</pre>
 *
 * <p>The stream sends {@code event: error} with a descriptive message if the
 * session has not been ingested or the LLM API call fails.
 */
@Slf4j
@RestController
@RequestMapping("/api/v2/assess-resume")
@RequiredArgsConstructor
public class AssessmentController {

    private final AssessmentService assessmentService;

    /**
     * Performs a standard synchronous (blocking) resume assessment and returns
     * the complete Markdown report in a JSON response body.
     *
     * @param sessionId the unique interview session identifier
     * @return HTTP 200 with the full markdown report inside a JSON object
     */
    @GetMapping(
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    public org.springframework.http.ResponseEntity<java.util.Map<String, String>> assessResumeBlocking(
            @RequestParam("sessionId") String sessionId) {

        log.info("Blocking assessment request received: sessionId={}", sessionId);
        String report = assessmentService.assessResumeBlocking(sessionId);
        return org.springframework.http.ResponseEntity.ok(java.util.Map.of("report", report));
    }

    /**
     * Streams a holistic resume assessment report as Server-Sent Events.
     *
     * <p>The session identified by {@code sessionId} must have been previously
     * processed by {@code POST /api/v1/ingest/{sessionId}} so that CV and JD
     * chunks are available in the database.
     *
     * @param sessionId the unique interview session identifier (required)
     * @return a reactive {@link Flux} of {@link ServerSentEvent} where each event
     *         carries a plain-text token fragment of the assessment report
     */
    @GetMapping(
            value = "/stream",
            produces = MediaType.TEXT_EVENT_STREAM_VALUE
    )
    public Flux<ServerSentEvent<String>> streamAssessment(
            @RequestParam("sessionId") String sessionId) {

        log.info("SSE assessment request received: sessionId={}", sessionId);
        return assessmentService.streamAssessment(sessionId);
    }
}
