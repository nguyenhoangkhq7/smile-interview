package fit.iuh.modules.assessment.controller;

import fit.iuh.modules.assessment.dto.ClassifiedCriteriaBundle;
import fit.iuh.modules.assessment.entity.EligibilityStatus;
import fit.iuh.modules.assessment.service.AssessmentCriteriaPreparer;
import fit.iuh.modules.assessment.service.AssessmentCriteriaPreparer.MetadataResult;
import fit.iuh.modules.rulengine.repository.JobCriteriaRepository.CriteriaWeightProjection;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Controller dành riêng cho việc Debug/Test từng bước (Step-by-step) 
 * trong quy trình đánh giá CV/JD mà không cần chạy toàn bộ pipeline.
 */
@RestController
@RequestMapping("/api/v1/debug/assessment")
@RequiredArgsConstructor
public class DebugAssessmentController {

    private final AssessmentCriteriaPreparer criteriaPreparer;
    private final fit.iuh.modules.assessment.service.CriteriaEmbeddingInitializer criteriaEmbeddingInitializer;

    // =========================================================================
    // STEP 1: Metadata Extraction
    // =========================================================================
    @PostMapping("/extract-metadata")
    public ResponseEntity<MetadataResult> debugExtractMetadata(
            @RequestParam(value = "jd_content", defaultValue = "") String jdContent) {
        MetadataResult result = criteriaPreparer.extractMetadata(jdContent);
        return ResponseEntity.ok(result);
    }

    // =========================================================================
    // STEP 2: Gate Extraction & Eligibility (Hard Requirements)
    // =========================================================================
    @PostMapping("/evaluate-eligibility")
    public ResponseEntity<?> debugEvaluateEligibility(
            @RequestParam("jdContent") String jdContent,
            @RequestParam("cvContent") String cvContent) {
        var result = criteriaPreparer.evaluateEligibility(jdContent, cvContent);
        return ResponseEntity.ok(result);
    }

    // =========================================================================
    // STEP 3A: Pre-Filter Criteria (LLM Full JD Markdown & Criteria Matching)
    // =========================================================================
    @PostMapping("/pre-filter-criteria")
    public ResponseEntity<Map<String, Object>> debugPreFilterCriteria(
            @RequestParam(value = "jd_content", defaultValue = "") String jdContent,
            @RequestParam(value = "category", defaultValue = "SOFTWARE_ENGINEERING") String category,
            @RequestParam(value = "level", defaultValue = "MID") String level,
            @RequestParam(value = "threshold", defaultValue = "0.75") double threshold) {

        List<AssessmentCriteriaPreparer.CriteriaFilterDebugDetail> details =
                criteriaPreparer.debugFilterCriteriaDetails(category, level, jdContent, threshold);

        long matchedCount = details.stream().filter(AssessmentCriteriaPreparer.CriteriaFilterDebugDetail::isMatched).count();

        Map<String, Object> response = new java.util.LinkedHashMap<>();
        response.put("threshold_used", threshold);
        response.put("total_db_criteria", details.size());
        response.put("total_matched_criteria", matchedCount);
        response.put("criteria_details", details);

        return ResponseEntity.ok(response);
    }

    // =========================================================================
    // STEP 3C: Recompute & Persist Missing Embeddings in DB
    // =========================================================================
    @PostMapping("/recompute-embeddings")
    public ResponseEntity<Map<String, String>> debugRecomputeEmbeddings() {
        if (criteriaEmbeddingInitializer != null) {
            criteriaEmbeddingInitializer.preComputeMissingEmbeddings();
            return ResponseEntity.ok(Map.of("message", "Đã kích hoạt tính toán và lưu Vector Embedding cho tất cả tiêu chí DB thành công!"));
        } else {
            return ResponseEntity.badRequest().body(Map.of("error", "CriteriaEmbeddingInitializer chưa được khởi tạo."));
        }
    }

    // =========================================================================
    // STEP 3B: LLM Classification (Required / Preferred / Ad-hoc)
    // =========================================================================
    @PostMapping("/classify-criteria")
    public ResponseEntity<ClassifiedCriteriaBundle> debugClassifyCriteria(
            @RequestParam(value = "jd_content", defaultValue = "") String jdContent,
            @RequestParam(value = "category", defaultValue = "SOFTWARE_ENGINEERING") String category,
            @RequestParam(value = "level", defaultValue = "MID") String level) {

        // Đầu tiên lọc criteria từ DB bằng Vector
        List<CriteriaWeightProjection> filteredCriteria = criteriaPreparer.loadAndFilterCriteria(
                category, level, "debug-session", jdContent, false
        );

        // Sau đó truyền danh sách đã lọc cho LLM phân loại
        ClassifiedCriteriaBundle result = criteriaPreparer.classifyCriteria(
                jdContent, filteredCriteria, level
        );
        
        return ResponseEntity.ok(result);
    }
}
