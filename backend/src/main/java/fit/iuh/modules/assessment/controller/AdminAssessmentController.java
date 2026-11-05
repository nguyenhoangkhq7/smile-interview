package fit.iuh.modules.assessment.controller;

import fit.iuh.modules.assessment.dto.SuggestedCriteriaDto;
import fit.iuh.modules.assessment.service.SuggestedCriteriaService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Admin API để quản lý suggested criteria (tiêu chí được LLM phát hiện trong JD nhưng chưa có trong DB).
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/admin/suggested-criteria")
@RequiredArgsConstructor
public class AdminAssessmentController {

    private final SuggestedCriteriaService suggestedCriteriaService;

    /**
     * Lấy danh sách tất cả suggested criteria, sắp xếp theo occurrenceCount giảm dần.
     */
    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<List<SuggestedCriteriaDto>> getSuggestedCriteria() {
        return ResponseEntity.ok(suggestedCriteriaService.getSuggestedCriteria());
    }

    /**
     * Promote một suggested criteria vào DB thật (evaluation_criteria + category_criteria_mapping).
     */
    @PostMapping(value = "/{id}/promote", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> promoteCriteria(
            @PathVariable Long id,
            @RequestBody PromoteRequest body) {
        return ResponseEntity.ok(suggestedCriteriaService.promoteCriteria(
                id,
                body.categoryCode(),
                body.level(),
                body.weightPercentage(),
                body.questionType(),
                body.category()
        ));
    }

    /**
     * Xóa một suggested criteria khỏi danh sách (nếu admin quyết định không promote).
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteSuggestedCriteria(@PathVariable Long id) {
        suggestedCriteriaService.deleteSuggestedCriteria(id);
        return ResponseEntity.noContent().build();
    }

    public record PromoteRequest(
            String categoryCode,
            String level,
            Double weightPercentage,
            String questionType,
            String category
    ) {}
}
