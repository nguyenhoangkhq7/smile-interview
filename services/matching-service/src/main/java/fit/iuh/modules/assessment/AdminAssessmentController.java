package fit.iuh.modules.assessment;

import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Sort;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/admin/suggested-criteria")
@RequiredArgsConstructor
public class AdminAssessmentController {

    private final SuggestedCriteriaRepository suggestedCriteriaRepository;

    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<List<SuggestedCriteria>> getSuggestedCriteria() {
        List<SuggestedCriteria> criteria = suggestedCriteriaRepository.findAll(
                Sort.by(Sort.Direction.DESC, "occurrenceCount")
        );
        return ResponseEntity.ok(criteria);
    }
}
