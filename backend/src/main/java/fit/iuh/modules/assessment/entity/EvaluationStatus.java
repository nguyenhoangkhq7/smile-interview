package fit.iuh.modules.assessment.entity;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

import java.util.Locale;

/**
 * Standardized status representing candidate alignment on an evaluation criterion.
 */
@Getter
public enum EvaluationStatus {
    MATCHED("matched", 1.0),
    PARTIAL("partial", 0.65),
    WEAK("weak", 0.30),
    MISSING("missing", 0.0),
    NOT_APPLICABLE("not_applicable", 0.0);

    private final String code;
    private final double defaultPoint;

    EvaluationStatus(String code, double defaultPoint) {
        this.code = code;
        this.defaultPoint = defaultPoint;
    }

    @JsonValue
    public String getCode() {
        return code;
    }

    @JsonCreator
    public static EvaluationStatus fromCode(String code) {
        if (code == null || code.isBlank()) {
            return MISSING;
        }
        String clean = code.trim().toLowerCase(Locale.ROOT);
        return switch (clean) {
            case "matched", "pass", "passed" -> MATCHED;
            case "partial" -> PARTIAL;
            case "weak" -> WEAK;
            case "missing", "fail", "failed" -> MISSING;
            case "not_applicable", "not_in_jd" -> NOT_APPLICABLE;
            default -> MISSING;
        };
    }
}
