package fit.iuh.modules.hrevaluation.service.impl;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.hrevaluation.dto.HrEvaluationRequestDto;
import fit.iuh.modules.hrevaluation.dto.HrEvaluationResponseDto;
import fit.iuh.modules.hrevaluation.entity.HrEvaluation;
import fit.iuh.modules.hrevaluation.repository.HrEvaluationRepository;
import fit.iuh.modules.hrevaluation.service.HrEvaluationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Default implementation of {@link HrEvaluationService}.
 *
 * <p>Maps the incoming DTO to a {@link HrEvaluation} entity, persists it via
 * {@link HrEvaluationRepository}, and returns a confirmation DTO.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class HrEvaluationServiceImpl implements HrEvaluationService {

    private final HrEvaluationRepository hrEvaluationRepository;

    @Override
    @Transactional
    public HrEvaluationResponseDto saveEvaluation(HrEvaluationRequestDto dto) {
        UUID currentUserId = null;
        String evaluatorName = dto.getEvaluatorName();

        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof User currentUser) {
            currentUserId = currentUser.getId();
            if (evaluatorName == null || evaluatorName.isBlank()) {
                evaluatorName = currentUser.getDisplayUsername();
            }
        }

        log.info("[HrEvaluation] Saving evaluation for sessionId={}, evaluator={}, userId={}",
                dto.getSessionId(), evaluatorName, currentUserId);

        HrEvaluation entity = HrEvaluation.builder()
                .sessionId(dto.getSessionId())
                .userId(currentUserId)
                .evaluatorName(evaluatorName)
                .ratingMatchingAccuracy(dto.getRatingMatchingAccuracy())
                .ratingAiRationale(dto.getRatingAiRationale())
                .ratingQuestionQuality(dto.getRatingQuestionQuality())
                .feedbackNotes(dto.getFeedbackNotes())
                .build();

        HrEvaluation saved = hrEvaluationRepository.save(entity);

        log.info("[HrEvaluation] Saved evaluation id={} for sessionId={}",
                saved.getId(), saved.getSessionId());

        HrEvaluationResponseDto response = toResponseDto(saved);
        response.setMessage("HR evaluation submitted successfully.");
        return response;
    }

    @Override
    @Transactional(readOnly = true)
    public List<HrEvaluationResponseDto> getAllEvaluations() {
        log.info("[HrEvaluation] Retrieving all evaluations for admin");
        return hrEvaluationRepository.findAllByOrderByCreatedAtDesc()
                .stream()
                .map(this::toResponseDto)
                .collect(Collectors.toList());
    }

    private HrEvaluationResponseDto toResponseDto(HrEvaluation entity) {
        return HrEvaluationResponseDto.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .userId(entity.getUserId())
                .evaluatorName(entity.getEvaluatorName())
                .ratingMatchingAccuracy(entity.getRatingMatchingAccuracy())
                .ratingAiRationale(entity.getRatingAiRationale())
                .ratingQuestionQuality(entity.getRatingQuestionQuality())
                .feedbackNotes(entity.getFeedbackNotes())
                .createdAt(entity.getCreatedAt())
                .build();
    }
}
