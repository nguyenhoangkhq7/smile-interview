package fit.iuh.modules.assessment.gate;

import fit.iuh.modules.assessment.util.TextSanitizationUtil;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Locale;

@Component
public class CertificationGateEvaluator implements GateEvaluator {

    private static final List<String> COMMON_CERTS = List.of(
            "aws", "gcp", "azure", "pmp", "ckad", "cka", "istqb", "cisco", "ccna", "ccnp",
            "oracle", "scrum", "psm", "csm", "toeic", "ielts", "jlpt", "hsk", "ceh", "cissp", "comptia"
    );

    @Override
    public boolean supports(String criteriaName) {
        if (criteriaName == null) return false;
        String lower = criteriaName.toLowerCase(Locale.ROOT);
        return lower.contains("certificat")
                || lower.contains("certified")
                || lower.contains("chứng chỉ")
                || lower.contains("chứng nhận")
                || lower.contains("certificate")
                || lower.contains("certification");
    }

    @Override
    public GateEvaluationResult evaluate(String criteriaName, String requiredValue, String cvContent) {
        if (cvContent == null || cvContent.isBlank()) {
            return new GateEvaluationResult(true, false, "No CV content provided", "Candidate CV is empty.");
        }

        String effectiveReq = (requiredValue != null && !requiredValue.isBlank()) ? requiredValue : criteriaName;
        String reqLower = effectiveReq.toLowerCase(Locale.ROOT);
        String cvLower = cvContent.toLowerCase(Locale.ROOT);

        // 1. Check known specific certification tokens
        for (String certToken : COMMON_CERTS) {
            if (reqLower.contains(certToken)) {
                boolean hasCert = TextSanitizationUtil.containsSkillTerm(cvLower, certToken);
                if (hasCert) {
                    return new GateEvaluationResult(
                            true,
                            true,
                            "Candidate holds the specified certification (" + certToken.toUpperCase(Locale.ROOT) + ") in CV",
                            "Candidate meets the certification requirement (" + effectiveReq + ")."
                    );
                } else {
                    return new GateEvaluationResult(
                            true,
                            false,
                            "No " + certToken.toUpperCase(Locale.ROOT) + " certificate found in CV",
                            "Candidate CV does not mention the required certification: " + effectiveReq
                    );
                }
            }
        }

        // 2. Generic phrase match
        String cleanReq = reqLower.replaceAll("[^a-z0-9\\s]", " ").replaceAll("\\s+", " ").trim();
        boolean hasGenericCert = !cleanReq.isBlank() && (cvLower.contains(cleanReq) || TextSanitizationUtil.containsSkillTerm(cvLower, cleanReq));

        if (hasGenericCert) {
            return new GateEvaluationResult(
                    true,
                    true,
                    "Certification requirement mentioned in CV",
                    "Candidate meets the certification requirement (" + effectiveReq + ")."
            );
        }

        return new GateEvaluationResult(
                true,
                false,
                "No matching certificate found in CV for: " + effectiveReq,
                "Candidate CV does not mention the required qualification (" + effectiveReq + ")."
        );
    }
}
