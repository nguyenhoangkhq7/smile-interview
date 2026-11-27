package fit.iuh.modules.admin.interviews.dto;

import fit.iuh.modules.admin.interviews.model.InterviewStatus;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class AdminInterviewDtos {
    private AdminInterviewDtos() {}

    public record Summary(String id, String candidateName, String roleTitle, InterviewStatus status,
                          String mode, Instant createdAt, Instant startedAt, Instant endedAt, Integer userRating) {}
    public record Page(List<Summary> sessions, long total, int page, int size, Map<InterviewStatus, Long> counts) {}
    public record Inputs(String cvName, String jdTitle, String company) {}
    public record Matching(Double score, boolean available) {}
    public enum DocumentKind { CV, JD }
    public record DocumentView(String name, String text, boolean originalAvailable) {}
    public record MatchingDetail(Double score, boolean degraded, boolean available, List<MatchingSkill> skills) {}
    public record MatchingSkill(String id, String name, String alignment, String cvSkill, Double requiredLevel,
                                Double priority, Double importance, String context, List<String> cvEvidence,
                                List<String> jdEvidence, List<MatchingTask> tasks) {}
    public record MatchingTask(String description, String requirement, Double requiredLevel, List<String> evidence) {}
    public record Blueprint(Integer maxQuestions, Integer durationSeconds, Integer maxQuestionsPerObjective,
                            String questionMode, Integer objectiveCount, Policy policy) {}
    public record Policy(Double coreImportance, Double reserveFollowupFraction, Integer fallbackDepth,
                         Integer minFailureContexts, Boolean allowExtensionProbes) {}
    public record Evidence(String criterionId, String excerpt, String rationale, String performance) {}
    public record Turn(String id, String skill, String mode, String question, String answer, String feedback,
                       Integer score, String strengths, String improvements, String suggestedAnswer,
                       List<Evidence> evidence) {}
    public record Objective(String skill, String claim, String assessment, List<String> strengths,
                            List<String> weaknesses) {}
    public record Transcript(String opening, String introduction, String closing, List<Turn> turns) {}
    public record Report(String terminationReason, List<Objective> objectives, Integer overallScore, String feedback) {}
    public record Detail(Summary session, Inputs inputs, Matching matching, Blueprint blueprint,
                         boolean finalized, Transcript transcript, Report report) {}
    public record QualityInput(String cv, String jd, String skillsJson, String reportJson,
                               String mode, List<QualityQuestion> questions) {
        @Override public String toString() { return "QualityInput[redacted]"; }
    }
    public record QualityQuestion(String text, String skill) {}
    public record QualityFinding(String status, String code, String detail, String skill, Integer turn, String excerpt) {}
    public record QualitySection(int total, List<QualityFinding> findings) {}
    public record QualityReview(QualitySection matching, QualitySection questions) {}
}
