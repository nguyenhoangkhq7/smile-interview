package fit.iuh.modules.assessment;

/**
 * Captures the expected seniority level of the candidate as stated in the JD.
 *
 * <p>Extracted via {@code MetadataExtractionService} from the JD Markdown.
 * Stored as a {@code VARCHAR} column via {@code @Enumerated(EnumType.STRING)}.
 *
 * <p>The {@code category_criteria_mapping} table uses this ENUM's {@code name()} to
 * select the appropriate weight set from the rule engine — e.g., a BACKEND/FRESHER
 * role gets a different criteria weighting than a BACKEND/SENIOR role.
 *
 * <p>Ordinal order (INTERN < FRESHER < JUNIOR < MID < SENIOR < LEAD) can be used
 * for difficulty distribution logic in {@code DifficultyDistributor}.
 */
public enum SeniorityLevel {

    /** University student / traineeship — 0 experience required */
    INTERN,

    /** 0–1 year — entry-level, no prior professional experience required */
    FRESHER,

    /** 1–2 years — some hands-on production experience */
    JUNIOR,

    /** 2–5 years — independent contributor, owns features end-to-end */
    MID,

    /** 5–8 years — system design, mentoring, cross-team leadership */
    SENIOR,

    /** 8+ years — architectural decisions, team management, principal engineering */
    LEAD
}
