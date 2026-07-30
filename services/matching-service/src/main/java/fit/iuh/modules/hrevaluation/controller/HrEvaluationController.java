package fit.iuh.modules.hrevaluation.controller;

import fit.iuh.modules.hrevaluation.dto.HrEvaluationRequestDto;
import fit.iuh.modules.hrevaluation.dto.HrEvaluationResponseDto;
import fit.iuh.modules.hrevaluation.service.HrEvaluationService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * REST controller for HR evaluation submissions and admin evaluation management.
 *
 * <p>Exposes {@code POST /api/v1/hr-evaluations} for HR evaluations and
 * {@code GET /api/v1/hr-evaluations/all} for Admin evaluation listing.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/hr-evaluations")
@RequiredArgsConstructor
public class HrEvaluationController {

    private final HrEvaluationService hrEvaluationService;

    /**
     * Submits an HR evaluation for an AI-generated question bank.
     *
     * <p>Validates the request payload, persists the evaluation, and returns
     * {@code 201 Created} with the saved record's ID and a confirmation message.
     *
     * @param request the evaluation payload from the HR portal
     * @return {@code 201 Created} with {@link HrEvaluationResponseDto} body
     */
    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<HrEvaluationResponseDto> submitEvaluation(
            @Valid @RequestBody HrEvaluationRequestDto request) {
        log.info("Received HR evaluation submission for sessionId={}", request.getSessionId());
        HrEvaluationResponseDto response = hrEvaluationService.saveEvaluation(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    /**
     * Retrieves all evaluations submitted across all sessions.
     *
     * <p>Requires {@code ROLE_ADMIN}.
     *
     * @return {@code 200 OK} with list of all HR evaluation records
     */
    @GetMapping(value = "/all", produces = MediaType.APPLICATION_JSON_VALUE)
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<HrEvaluationResponseDto>> getAllEvaluations() {
        log.info("Admin request to fetch all HR evaluations");
        List<HrEvaluationResponseDto> list = hrEvaluationService.getAllEvaluations();
        return ResponseEntity.ok(list);
    }
}
