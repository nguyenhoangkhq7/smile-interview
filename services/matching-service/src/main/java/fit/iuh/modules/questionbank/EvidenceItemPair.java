package fit.iuh.modules.questionbank;

/**
 * Represents a single assessment evidence item used as input for question generation.
 *
 * <p>Replaces {@code ExperienceRequirementPair} (which was derived from cosine similarity
 * between raw document chunks). This record is populated directly from
 * {@link fit.iuh.modules.assessment.ResumeAssessment#getEvidenceItems()} and
 * {@link fit.iuh.modules.assessment.ResumeAssessment#getAdditionalEvidenceItems()},
 * which are richer, LLM-evaluated, and already consistent with the assessment result
 * shown to the candidate.
 *
 * <h3>Ad-hoc items</h3>
 * Items sourced from {@code additional_evidence_items} (ad-hoc, JD-specific requirements
 * not covered by the standard criteria list) will have {@code criteriaId = null} and
 * {@code weightUsed = null}.
 */
public record EvidenceItemPair(

        /**
         * Foreign key to {@code evaluation_criteria.id}.
         * {@code null} for ad-hoc items from {@code additional_evidence_items}.
         */
        Long criteriaId,

        /** Human-readable criterion name (e.g., "Tech Stack Alignment"). */
        String criteriaName,

        /** The specific JD requirement text for this criterion. */
        String jdRequirement,

        /**
         * Concrete evidence extracted from the CV, or {@code null} if the requirement
         * is missing from the CV entirely.
         */
        String cvEvidence,

        /**
         * LLM-assigned status for this criterion:
         * {@code "matched"} | {@code "weak"} | {@code "missing"} | {@code "not_applicable"}
         */
        String status,

        /** LLM reasoning explaining why this status was chosen. */
        String reasoning,

        /**
         * DB weight of this criterion, used for sorting by importance.
         * {@code null} for ad-hoc items.
         */
        Double weightUsed

) {}
