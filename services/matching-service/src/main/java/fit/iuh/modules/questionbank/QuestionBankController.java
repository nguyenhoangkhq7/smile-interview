package fit.iuh.modules.questionbank;

import fit.iuh.modules.questionbank.GenerateQuestionBankRequest;
import fit.iuh.modules.questionbank.QuestionBankResponseDto;
import fit.iuh.modules.questionbank.QuestionBankService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * REST controller for Question Bank generation and retrieval endpoints.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/question-banks")
@RequiredArgsConstructor
public class QuestionBankController {

    private final QuestionBankService questionBankService;

    /**
     * POST /api/v1/question-banks/generate
     *
     * <p>Generates a personalized question bank based on candidate context
     * and user specified question configuration.
     *
     * @param request generate request containing session ID and config DTO
     * @return HTTP 201 with generated question bank response DTO
     */
    @PostMapping("/generate")
    public ResponseEntity<QuestionBankResponseDto> generate(
            @Valid @RequestBody GenerateQuestionBankRequest request) {
        log.info("[QuestionBankController] Generate request received for session: {}", request.getSessionId());
        QuestionBankResponseDto response = questionBankService.generate(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    /**
     * GET /api/v1/question-banks/{id}
     *
     * <p>Retrieves a generated question bank by its unique UUID.
     *
     * @param id question bank UUID
     * @return HTTP 200 with question bank response DTO
     */
    @GetMapping("/{id}")
    public ResponseEntity<QuestionBankResponseDto> getById(@PathVariable UUID id) {
        log.info("[QuestionBankController] Retrieve request by ID: {}", id);
        return ResponseEntity.ok(questionBankService.getById(id));
    }

    /**
     * GET /api/v1/question-banks?sessionId=xxx
     *
     * <p>Retrieves all question banks associated with a sessionId,
     * ordered by creation time descending.
     *
     * @param sessionId session identifier
     * @return HTTP 200 with list of question bank response DTOs
     */
    @GetMapping
    public ResponseEntity<List<QuestionBankResponseDto>> getBySession(
            @RequestParam("sessionId") String sessionId) {
        log.info("[QuestionBankController] Retrieve request for session: {}", sessionId);
        return ResponseEntity.ok(questionBankService.getBySessionId(sessionId));
    }

    /**
     * PATCH /api/v1/question-banks/{id}/questions/{questionId}/regenerate
     *
     * <p>Regenerates a single question inside a question bank, keeping its ID
     * and metadata but replacing its content.
     *
     * @param id question bank UUID
     * @param questionId sequential ID of the question (e.g. Q003)
     * @return HTTP 200 with updated question bank response DTO
     */
    @PatchMapping("/{id}/questions/{questionId}/regenerate")
    public ResponseEntity<QuestionBankResponseDto> regenerateQuestion(
            @PathVariable UUID id,
            @PathVariable String questionId) {
        log.info("[QuestionBankController] Regenerate request for question {} in bank {}", questionId, id);
        return ResponseEntity.ok(questionBankService.regenerateQuestion(id, questionId));
    }
}
