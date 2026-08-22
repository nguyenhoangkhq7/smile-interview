package fit.iuh.modules.assessment.controller;

import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.InterviewEvaluationRequest;
import fit.iuh.modules.assessment.service.AssessmentService;
import fit.iuh.modules.assessment.service.InterviewEvaluationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/api/v2/assess-resume")
@RequiredArgsConstructor
public class AssessmentController {

    private final AssessmentService assessmentService;
    private final InterviewEvaluationService interviewEvaluationService;

    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AssessmentResponse> assessResume(
            @RequestParam("sessionId") String sessionId,
            @RequestParam(value = "forceRefresh", required = false, defaultValue = "false") boolean forceRefresh,
            @RequestParam(value = "fromSessionId", required = false) String fromSessionId) {

        log.info("Received assessment request for sessionId={}, forceRefresh={}, fromSessionId={}",
                sessionId, forceRefresh, fromSessionId);

        AssessmentResponse response = assessmentService.assessResumeBlocking(sessionId, forceRefresh, fromSessionId);
        return ResponseEntity.ok(response);
    }

    @PostMapping(value = "/evaluate-session", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> evaluateSession(@RequestBody InterviewEvaluationRequest request) {
        log.info("Received interview evaluation request for roleTitle={}", request.roleTitle());
        String evaluationJson = interviewEvaluationService.evaluateSession(request);
        return ResponseEntity.ok(evaluationJson);
    }
}
