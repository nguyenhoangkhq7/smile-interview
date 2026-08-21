package fit.iuh.modules.assessment.mapper;

import fit.iuh.modules.assessment.dto.AssessmentResponse;
import fit.iuh.modules.assessment.dto.AssessmentResponseDto;
import fit.iuh.modules.assessment.dto.ImprovementResponseDto;
import fit.iuh.modules.assessment.entity.EvidenceItem;
import fit.iuh.modules.assessment.entity.Improvement;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import lombok.experimental.UtilityClass;

import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

@UtilityClass
public class AssessmentMapper {

    public static AssessmentResponse toResponse(ResumeAssessment entity, boolean cached) {
        if (entity == null) return null;

        List<EvidenceItem> allEvidence = entity.getEvidenceItems() != null ? entity.getEvidenceItems() : List.of();
        List<EvidenceItem> mustHave = allEvidence.stream()
                .filter(i -> !"PREFERRED".equalsIgnoreCase(i.getImportance()) && !"GATE".equalsIgnoreCase(i.getImportance()))
                .collect(Collectors.toList());
        List<EvidenceItem> gate = allEvidence.stream()
                .filter(i -> "GATE".equalsIgnoreCase(i.getImportance()))
                .collect(Collectors.toList());
        List<EvidenceItem> prefer = allEvidence.stream()
                .filter(i -> "PREFERRED".equalsIgnoreCase(i.getImportance()))
                .collect(Collectors.toList());

        List<Improvement> allImprovements = entity.getImprovements() != null ? entity.getImprovements() : List.of();

        return AssessmentResponse.builder()
                .id(entity.getId())
                .sessionId(entity.getSessionId())
                .jobCategory(entity.getJobCategory())
                .seniorityLevel(entity.getSeniorityLevel())
                .overallMatchScore(entity.getOverallMatchScore())
                .mustHaveEvidenceItems(mapToMustHaveDto(mustHave))
                .preferToHaveEvidenceItems(mapToPreferDto(prefer))
                .gateEvidenceItems(mapToGateDto(gate))
                .quickWins(mapToImprovementDto(allImprovements, "[QW]"))
                .skillGaps(mapToImprovementDto(allImprovements, "[SG]"))
                .eligibility(entity.getEligibility())
                .cached(cached)
                .createdAt(entity.getCreatedAt())
                .build();
    }

    public static List<AssessmentResponseDto.EvidenceItem> mapToMustHaveDto(List<EvidenceItem> items) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> !"PREFERRED".equalsIgnoreCase(i.getImportance()) && !"GATE".equalsIgnoreCase(i.getImportance()))
                .map(i -> new AssessmentResponseDto.EvidenceItem(
                        i.getCriteriaId() != null ? i.getCriteriaId().longValue() : null,
                        i.getCriteriaName(), i.getImportance(), i.getJdRequirement(), i.getCvEvidence(),
                        null, i.getStatus(), i.getReasoning(), null, null, null, null, null, null, null
                )).collect(Collectors.toList());
    }

    public static List<AssessmentResponseDto.EvidenceItem> mapToGateDto(List<EvidenceItem> items) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> "GATE".equalsIgnoreCase(i.getImportance()))
                .map(i -> new AssessmentResponseDto.EvidenceItem(
                        i.getCriteriaId() != null ? i.getCriteriaId().longValue() : null,
                        i.getCriteriaName(), i.getImportance(), i.getJdRequirement(), i.getCvEvidence(),
                        null, i.getStatus(), i.getReasoning(), null, null, null, null, null, null, null
                )).collect(Collectors.toList());
    }

    public static List<AssessmentResponseDto.AdHocEvidenceItem> mapToPreferDto(List<EvidenceItem> items) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> "PREFERRED".equalsIgnoreCase(i.getImportance()))
                .map(i -> new AssessmentResponseDto.AdHocEvidenceItem(
                        i.getCriteriaId() != null ? i.getCriteriaId().longValue() : null,
                        i.getCriteriaName(), i.getImportance(), i.getJdRequirement(),
                        i.getCvEvidence(), null, i.getStatus(), i.getReasoning(), null
                )).collect(Collectors.toList());
    }

    public static List<ImprovementResponseDto.ImprovementItem> mapToImprovementDto(List<Improvement> items, String prefix) {
        if (items == null) return List.of();
        return items.stream()
                .filter(i -> i.getTopic() != null && i.getTopic().startsWith(prefix))
                .sorted(Comparator.comparing(Improvement::getPriorityRank))
                .map(i -> new ImprovementResponseDto.ImprovementItem(
                        i.getTopic().length() > 5 ? i.getTopic().substring(5).trim() : i.getTopic(),
                        i.getSuggestionDetails(),
                        String.valueOf(i.getPriorityRank())
                ))
                .collect(Collectors.toList());
    }
}
