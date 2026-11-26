package fit.iuh.modules.admin.overview.dto;

import java.time.LocalDate;
import java.util.List;

public record AdminOverviewResponse(
        Kpis kpis,
        List<TelemetryPoint> telemetry,
        List<Distribution> termination,
        List<Distribution> assessments,
        List<KnowledgeGap> knowledgeGaps,
        List<PopularRole> popularRoles
) {
    public record Kpis(
            long users, Double usersGrowth,
            long applicationProfiles, Double applicationProfilesGrowth,
            long interviews, long completedInterviews, Double interviewsGrowth,
            Double completionRate, Double completionRateChange,
            long skillGapJobs, long successfulSkillGapJobs, Double skillGapSuccessRate,
            long textInterviews, long voiceInterviews
    ) {}

    public record TelemetryPoint(LocalDate from, LocalDate through, long analyses, long completedInterviews) {}

    public record Distribution(String code, long count, double percentage) {}

    public record KnowledgeGap(String title, long candidates, double percentage) {}

    public record PopularRole(String title, long interviews, Double growth) {}
}
