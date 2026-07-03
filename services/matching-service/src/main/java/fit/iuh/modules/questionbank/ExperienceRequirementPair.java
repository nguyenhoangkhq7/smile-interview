package fit.iuh.modules.questionbank;

/**
 * Represents a pair of Job Description requirement and Candidate CV experience
 * matched via semantic vector similarity.
 */
public record ExperienceRequirementPair(
        String jdChunkText,
        String cvChunkText,
        float[] jdEmbedding,
        float[] cvEmbedding,
        double similarityScore
) {}
