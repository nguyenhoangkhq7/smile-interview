package fit.iuh.modules.adaptive.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.exception.ResourceNotFoundException;
import fit.iuh.modules.evidence.InterviewRunRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

/** Read-only access to archived reports; all interview execution uses V2. */
@RestController
@RequestMapping("/api/v1/sessions/{sessionId}/interview")
@RequiredArgsConstructor
public class AdaptiveInterviewController {
    private final SessionRepository sessions;
    private final ObjectMapper mapper;
    private final InterviewRunRepository evidenceRuns;

    @PostMapping(value = {"/start", "/respond"}, produces = MediaType.APPLICATION_JSON_VALUE)
    public void retired(@PathVariable String sessionId) {
        throw new ResponseStatusException(HttpStatus.GONE,
                "Luồng phỏng vấn cũ đã ngừng hỗ trợ. Hãy tạo lượt phỏng vấn mới bằng V2.");
    }

    @GetMapping(value = "/report", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> archivedReport(@PathVariable String sessionId) {
        var session = sessions.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        if (evidenceRuns.existsById(sessionId) || session.getApplicationProfile() != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Use the V2 endpoint for this interview");
        }
        if (session.getInterviewReportJson() == null || session.getInterviewReportJson().isBlank()) {
            throw new ResourceNotFoundException("No archived interview report for session " + sessionId);
        }
        try {
            return ResponseEntity.ok(mapper.readValue(session.getInterviewReportJson(), new TypeReference<>() {}));
        } catch (com.fasterxml.jackson.core.JsonProcessingException ex) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Invalid archived report", ex);
        }
    }
}
