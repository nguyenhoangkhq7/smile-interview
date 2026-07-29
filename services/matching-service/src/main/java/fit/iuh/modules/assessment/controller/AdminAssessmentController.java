package fit.iuh.modules.assessment.controller;

import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.SuggestedCriteria;
import fit.iuh.modules.assessment.repository.SuggestedCriteriaRepository;
import fit.iuh.modules.rulengine.entity.CategoryCriteriaMapping;
import fit.iuh.modules.rulengine.entity.EvaluationCriteria;
import fit.iuh.modules.rulengine.entity.JobCategoryEntity;
import fit.iuh.modules.rulengine.repository.CategoryCriteriaMappingRepository;
import fit.iuh.modules.rulengine.repository.EvaluationCriteriaRepository;
import fit.iuh.modules.rulengine.repository.JobCategoryEntityRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Sort;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Admin API để quản lý suggested criteria (tiêu chí được LLM phát hiện trong JD nhưng chưa có trong DB).
 *
 * Flow "tạo thêm criteria":
 *   1. LLM tìm thấy kỹ năng mới trong JD → ghi vào suggested_criteria (promoted=false).
 *   2. Admin xem danh sách qua GET /api/v1/admin/suggested-criteria.
 *   3. Admin approve qua POST /api/v1/admin/suggested-criteria/{id}/promote
 *      → criteria được insert vào evaluation_criteria + category_criteria_mapping.
 *   4. Từ lần sau, criteria này sẽ được load đúng từ DB theo đúng category + level.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/admin/suggested-criteria")
@RequiredArgsConstructor
public class AdminAssessmentController {

    private final SuggestedCriteriaRepository suggestedCriteriaRepository;
    private final EvaluationCriteriaRepository evaluationCriteriaRepository;
    private final CategoryCriteriaMappingRepository categoryCriteriaMappingRepository;
    private final JobCategoryEntityRepository jobCategoryEntityRepository;

    /**
     * Lấy danh sách tất cả suggested criteria, sắp xếp theo occurrenceCount giảm dần.
     * Criteria xuất hiện nhiều lần → ưu tiên promote trước.
     */
    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<List<SuggestedCriteria>> getSuggestedCriteria() {
        List<SuggestedCriteria> criteria = suggestedCriteriaRepository.findAll(
                Sort.by(Sort.Direction.DESC, "occurrenceCount")
        );
        return ResponseEntity.ok(criteria);
    }

    /**
     * Promote một suggested criteria vào DB thật (evaluation_criteria + category_criteria_mapping).
     *
     * Request body (JSON):
     * {
     *   "categoryCode": "FULLSTACK",        // code trong job_categories (e.g. FULLSTACK, BACKEND, REACT)
     *   "level": "ALL",                     // ALL | INTERN | FRESHER | JUNIOR | MID | SENIOR | LEAD
     *   "weightPercentage": 10.0,           // trọng số (%)
     *   "questionType": "technical",        // technical | behavioral | coding | system_design
     *   "category": "technical"             // nhóm criteria (technical | behavioral | soft_skill)
     * }
     *
     * Response: 200 nếu thành công, 404 nếu suggested criteria không tồn tại,
     *           409 nếu đã được promote trước đó, 400 nếu categoryCode không tồn tại trong DB.
     */
    @PostMapping(value = "/{id}/promote", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    @Transactional
    public ResponseEntity<Map<String, Object>> promoteCriteria(
            @PathVariable Long id,
            @RequestBody PromoteRequest body) {

        // 1. Load suggested criteria
        SuggestedCriteria suggested = suggestedCriteriaRepository.findById(id).orElse(null);
        if (suggested == null) {
            return ResponseEntity.notFound().build();
        }
        if (Boolean.TRUE.equals(suggested.getPromoted())) {
            return ResponseEntity.status(409)
                    .body(Map.of("error", "Already promoted", "criteriaName", suggested.getCriteriaName()));
        }

        // 2. Tìm job category trong DB theo code
        String categoryCode = body.categoryCode() != null ? body.categoryCode().toUpperCase().strip() : null;
        if (categoryCode == null || categoryCode.isBlank()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "categoryCode is required"));
        }
        JobCategoryEntity jobCategory = jobCategoryEntityRepository.findByCode(categoryCode).orElse(null);
        if (jobCategory == null) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "Job category not found: " + categoryCode));
        }

        // 3. Insert vào evaluation_criteria
        String level = body.level() != null ? body.level().toUpperCase().strip() : "ALL";
        double weight = body.weightPercentage() != null ? body.weightPercentage() : 10.0;
        String questionType = body.questionType() != null ? body.questionType() : "technical";
        String criteriaCategory = body.category() != null ? body.category() : "technical";

        EvaluationCriteria newCriteria = EvaluationCriteria.builder()
                .name(suggested.getCriteriaName())
                .category(criteriaCategory)
                .questionType(questionType)
                .promptInstruction(suggested.getSampleJdText() != null
                        ? "Evaluate candidate's proficiency in " + suggested.getCriteriaName()
                          + ". Specifically: " + suggested.getSampleJdText()
                        : "Evaluate candidate's proficiency in " + suggested.getCriteriaName() + " based on CV evidence.")
                .build();
        newCriteria = evaluationCriteriaRepository.save(newCriteria);

        // 4. Insert vào category_criteria_mapping
        CategoryCriteriaMapping mapping = CategoryCriteriaMapping.builder()
                .jobCategory(jobCategory)
                .evaluationCriteria(newCriteria)
                .level(level)
                .weightPercentage(weight)
                .build();
        categoryCriteriaMappingRepository.save(mapping);

        // 5. Đánh dấu đã promote
        suggested.setPromoted(true);
        suggestedCriteriaRepository.save(suggested);

        log.info("[AdminAssessment] Promoted suggested criteria '{}' → evaluation_criteria id={}, category={}, level={}, weight={}%",
                suggested.getCriteriaName(), newCriteria.getId(), categoryCode, level, weight);

        return ResponseEntity.ok(Map.of(
                "message", "Criteria promoted successfully",
                "criteriaId", newCriteria.getId(),
                "criteriaName", newCriteria.getName(),
                "mappedCategory", categoryCode,
                "mappedLevel", level,
                "weightPercentage", weight
        ));
    }

    /**
     * Xóa một suggested criteria khỏi danh sách (nếu admin quyết định không promote).
     */
    @DeleteMapping("/{id}")
    @Transactional
    public ResponseEntity<Void> deleteSuggestedCriteria(@PathVariable Long id) {
        if (!suggestedCriteriaRepository.existsById(id)) {
            return ResponseEntity.notFound().build();
        }
        suggestedCriteriaRepository.deleteById(id);
        log.info("[AdminAssessment] Deleted suggested criteria id={}", id);
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
