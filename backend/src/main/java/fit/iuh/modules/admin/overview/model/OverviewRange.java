package fit.iuh.modules.admin.overview.model;

import java.time.LocalDate;
import java.util.Arrays;
import java.util.Optional;

public enum OverviewRange {
    WEEK("7d", 7), MONTH("30d", 30), QUARTER("90d", 90), ALL("all", 0);

    private final String key;
    private final int days;

    OverviewRange(String key, int days) {
        this.key = key;
        this.days = days;
    }

    public static Optional<OverviewRange> fromKey(String key) {
        return Arrays.stream(values()).filter(range -> range.key.equals(key)).findFirst();
    }

    public Window window(LocalDate today) {
        LocalDate end = today.plusDays(1);
        if (this == ALL) {
            LocalDate earliest = LocalDate.of(1, 1, 1);
            return new Window(earliest, earliest, end, false);
        }
        return new Window(end.minusDays(days * 2L), end.minusDays(days), end, true);
    }

    public record Window(LocalDate previousStart, LocalDate start, LocalDate end, boolean comparable) {}
}
