package fit.iuh.modules.admin.overview.service;

import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse.TelemetryPoint;
import fit.iuh.modules.admin.overview.repository.AdminOverviewRepository.DailyCount;
import fit.iuh.modules.admin.overview.model.OverviewRange.Window;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.stream.IntStream;

final class OverviewTelemetry {
    private static final int MAX_BUCKETS = 6;

    private OverviewTelemetry() {}

    static List<TelemetryPoint> bucket(List<DailyCount> daily, Window window) {
        LocalDate start = window.comparable() ? window.start()
                : daily.isEmpty() ? window.end().minusDays(1) : daily.getFirst().day();
        long days = ChronoUnit.DAYS.between(start, window.end());
        int buckets = (int) Math.min(MAX_BUCKETS, days);
        long[] analyses = new long[buckets];
        long[] completed = new long[buckets];
        for (DailyCount day : daily) {
            long offset = ChronoUnit.DAYS.between(start, day.day());
            int index = (int) (offset * buckets / days);
            analyses[index] += day.analyses();
            completed[index] += day.completed();
        }
        return IntStream.range(0, buckets)
                .mapToObj(index -> new TelemetryPoint(start.plusDays(Math.ceilDiv(index * days, buckets)),
                        start.plusDays(Math.ceilDiv((index + 1) * days, buckets) - 1),
                        analyses[index], completed[index]))
                .toList();
    }
}
