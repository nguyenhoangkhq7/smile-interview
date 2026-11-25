package fit.iuh.modules.admin.overview.service;

import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse;
import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse.Distribution;
import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse.KnowledgeGap;
import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse.Kpis;
import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse.PopularRole;
import fit.iuh.modules.admin.overview.model.OverviewRange;
import fit.iuh.modules.admin.overview.repository.AdminOverviewRepository;
import fit.iuh.modules.admin.overview.repository.AdminOverviewRepository.Counts;
import fit.iuh.modules.admin.overview.repository.AdminOverviewRepository.InterviewCount;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Comparator;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AdminOverviewService {
    private static final List<String> TERMINATION_CODES = List.of(
            "PLAN_COMPLETE", "USER_STOP", "QUESTION_BUDGET", "TIME_BUDGET", "OTHER");
    private static final List<String> ASSESSMENT_CODES = List.of(
            "DEMONSTRATED_ABOVE_TARGET", "DEMONSTRATED_AT_TARGET", "DEMONSTRATED_BELOW_TARGET",
            "NOT_DEMONSTRATED", "INSUFFICIENT_EVIDENCE", "NOT_ASSESSED");

    private final AdminOverviewRepository repository;

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public AdminOverviewResponse load(OverviewRange range) {
        ZoneId zone = ZoneId.systemDefault();
        var window = range.window(LocalDate.now(zone));
        var breakdown = repository.interviewBreakdown(window, zone);
        return new AdminOverviewResponse(
                kpis(repository.counts(window, zone), window.comparable()),
                OverviewTelemetry.bucket(repository.telemetry(window, zone), window),
                distribution(breakdown, "termination", TERMINATION_CODES),
                distribution(breakdown, "assessment", ASSESSMENT_CODES),
                repository.knowledgeGaps(window, zone).stream().map(gap -> new KnowledgeGap(
                        gap.title(), gap.candidates(), percentage(gap.candidates(), gap.totalCandidates()))).toList(),
                roles(breakdown, window.comparable()));
    }

    private static Kpis kpis(Counts counts, boolean comparable) {
        Double currentRate = rate(counts.completed(), counts.interviews());
        Double previousRate = rate(counts.previousCompleted(), counts.previousInterviews());
        Double rateChange = comparable && currentRate != null && previousRate != null
                ? round(currentRate - previousRate) : null;
        return new Kpis(counts.users(), growth(counts.users(), counts.previousUsers(), comparable),
                counts.profiles(), growth(counts.profiles(), counts.previousProfiles(), comparable),
                counts.interviews(), counts.completed(),
                growth(counts.interviews(), counts.previousInterviews(), comparable),
                currentRate, rateChange, counts.jobs(), counts.successfulJobs(),
                rate(counts.successfulJobs(), counts.jobs()), counts.text(), counts.voice());
    }

    private static List<Distribution> distribution(List<InterviewCount> rows, String category, List<String> codes) {
        var counts = rows.stream().filter(row -> row.category().equals(category))
                .collect(Collectors.toMap(InterviewCount::code, Function.identity()));
        long total = counts.values().stream().mapToLong(InterviewCount::current).sum();
        return codes.stream().map(code -> {
            var row = counts.get(code);
            long count = row == null ? 0 : row.current();
            return new Distribution(code, count, percentage(count, total));
        }).toList();
    }

    private static List<PopularRole> roles(List<InterviewCount> rows, boolean comparable) {
        return rows.stream().filter(row -> row.category().equals("role"))
                .sorted(Comparator.comparingLong(InterviewCount::current).reversed().thenComparing(InterviewCount::code))
                .map(row -> new PopularRole(row.code(), row.current(), growth(row.current(), row.previous(), comparable)))
                .toList();
    }

    private static Double growth(long current, long previous, boolean comparable) {
        return comparable ? rate(current - previous, previous) : null;
    }

    private static Double rate(long count, long total) {
        return total == 0 ? null : percentage(count, total);
    }

    private static double percentage(long count, long total) {
        return total == 0 ? 0 : round(count * 100.0 / total);
    }

    private static double round(double value) {
        return Math.round(value * 10) / 10.0;
    }
}
