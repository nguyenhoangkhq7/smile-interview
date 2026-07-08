package fit.iuh.modules.assessment;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * REST Controller exposing the SimInterview Resume Assessment API.
 *
 * <p>Base path: {@code /api/v2/assess-resume}
 *
 * <h2>Endpoint</h2>
 * <pre>
 *   GET /api/v2/assess-resume?sessionId={id}[&amp;forceRefresh=true]
 * </pre>
 *
 * <h2>Response Structure (3-Part SimInterview Output)</h2>
 * <pre>{@code
 * {
 *   "id": "...",
 *   "session_id": "session-123",
 *   "competency_fit_score": 78,
 *   "section_wise_feedback": {
 *     "skills_evaluation": {
 *       "analysis": "...",
 *       "critical_missing_skills": ["Docker", "Kubernetes"]
 *     },
 *     "experience_evaluation": "...",
 *     "project_evaluation": "..."
 *   },
 *   "actionable_improvement_suggestions": ["...", "..."],
 *   "cached": false,
 *   "created_at": "2026-06-26T10:00:00"
 * }
 * }</pre>
 *
 * <h2>Cache-Aside Behavior</h2>
 * The endpoint checks the {@code resume_assessments} table for an existing record
 * before invoking the LLM. Use {@code forceRefresh=true} to delete the cache and
 * regenerate. The response includes {@code "cached": true/false} to indicate the source.
 *
 * <h2>Note on Loading Time</h2>
 * The LLM call (Groq JSON mode, {@code temperature: 0.0}) typically takes 10–15 seconds
 * on a cache miss. Clients should render a loading skeleton during this time.
 * On a cache hit, the response is returned immediately from the database.
 */
@Slf4j
@RestController
@RequestMapping("/api/v2/assess-resume")
@RequiredArgsConstructor
public class AssessmentController {

    private final AssessmentService assessmentService;

    /**
     * Performs a synchronous SimInterview resume assessment and returns the
     * complete 3-part structured result as JSON.
     *
     * <p>Implements Cache-Aside: returns the cached DB result if available.
     * Use {@code forceRefresh=true} to bypass the cache and regenerate from the LLM.
     *
     * @param sessionId    the unique interview session identifier (required)
     * @param forceRefresh if {@code true}, bypasses cache and re-invokes the LLM (default: false)
     * @return HTTP 200 with an {@link AssessmentResponse} containing the 3 SimInterview outputs
     */
    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AssessmentResponse> assessResume(
            @RequestParam("sessionId") String sessionId,
            @RequestParam(value = "forceRefresh", defaultValue = "false") boolean forceRefresh) {

        log.info("Assessment request: sessionId={}, forceRefresh={}", sessionId, forceRefresh);
        AssessmentResponse response = assessmentService.assessResumeBlocking(sessionId, forceRefresh);
        return ResponseEntity.ok(response);
    }

    @PostMapping(value = "/evaluate-session", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> evaluateSession(@RequestBody InterviewEvaluationRequest request) {
        log.info("Received interview evaluation request for sessionId={}", request.sessionId());
        String response = assessmentService.evaluateSession(request);
        return ResponseEntity.ok(response);
    }
}
