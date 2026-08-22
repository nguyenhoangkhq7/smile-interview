package fit.iuh.modules.assessment.util;

import lombok.experimental.UtilityClass;
import lombok.extern.slf4j.Slf4j;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Utility containing regex and heuristic algorithms for extracting resume dates,
 * calculating Years of Experience (YoE), detecting degree mentions, and parsing experience sections.
 */
@Slf4j
@UtilityClass
public class ResumeHeuristicsUtil {

    public record DateRange(LocalDate start, LocalDate end) {}

    private static final Pattern FULL_NUMERIC_DATE_PATTERN = Pattern.compile(
            "(?i)\\b(?:0?[1-9]|[12][0-9]|3[01])[./-](0?[1-9]|1[0-2])[./-](\\d{4})\\s*(?:-|to|until|—|–|->|đến|~)\\s*(Present|Now|Current|Nay|Hiện tại|(?:0?[1-9]|[12][0-9]|3[01])[./-](0?[1-9]|1[0-2])[./-](\\d{4}))\\b"
    );

    private static final Pattern NUMERIC_DATE_PATTERN = Pattern.compile(
            "(?i)\\b(0?[1-9]|1[0-2])[./-](\\d{4})\\s*(?:-|to|until|—|–|->|đến|~)\\s*(Present|Now|Current|Nay|Hiện tại|(?:0?[1-9]|1[0-2])[./-](\\d{4}))\\b"
    );

    private static final Pattern YEAR_FIRST_DATE_PATTERN = Pattern.compile(
            "(?i)\\b(20\\d{2}|19\\d{2})[./-](0?[1-9]|1[0-2])\\s*(?:-|to|until|—|–|->|đến|~)\\s*(Present|Now|Current|Nay|Hiện tại|(?:20\\d{2}|19\\d{2})[./-](0?[1-9]|1[0-2]))\\b"
    );

    private static final Pattern WORD_MONTH_DATE_PATTERN = Pattern.compile(
            "(?i)\\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Tháng\\s*(?:0?[1-9]|1[0-2]))[.,\\s/-]+(\\d{4})\\s*(?:-|to|until|—|–|->|đến|~)\\s*(Present|Now|Current|Nay|Hiện tại|(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Tháng\\s*(?:0?[1-9]|1[0-2]))[.,\\s/-]+(?:\\d{4})))\\b"
    );

    private static final Pattern YEAR_ONLY_DATE_PATTERN = Pattern.compile(
            "(?i)\\b(20\\d{2}|19\\d{2})\\s*(?:-|to|until|—|–|->|đến|~)\\s*(Present|Now|Current|Nay|Hiện tại|(?:20\\d{2}|19\\d{2}))\\b"
    );

    private static final Pattern EXP_HEADER_PATTERN = Pattern.compile(
            "(?i)^[#*\\s-]{0,6}(?!.*(?:academic|coursework|personal|side\\s+project|pet\\s+project|đồ\\s*án|cá\\s*nhân)).*?(?:work\\s+experience|professional\\s+experience|experience|work\\s+history|employment|kinh\\s+nghi[eệ]m|quá\\s+trình\\s+làm\\s+việc|d[uự]\\s*[aá]n|project).*"
    );

    private static final Pattern OTHER_HEADER_PATTERN = Pattern.compile(
            "(?i)^[#*\\s-]{0,6}.*?(?:education|h[oọ]c\\s*v[aấ]n|trình\\s*độ|skill|k[yỹ]\\s*n[aă]ng|certificat|ch[uứ]ng\\s*ch[iỉ]|award|gi[aả]i\\s*th[uư][oở]ng|reference|ng[uư][oờ]i\\s*tham\\s*chi[eế]u|academic|personal\\s+project|coursework|side\\s+project|pet\\s+project|đồ\\s*án|cá\\s*nhân).*"
    );

    private static final Pattern YOE_WITH_KEYWORD_PATTERN = Pattern.compile(
            "(?i)(?:tối\\s*thiểu|ít\\s*nhất|at\\s*least|minimum|min|yêu\\s*cầu|require(?:s|d)?)\\s*(\\d+(?:\\.\\d+)?)\\s*(?:\\+|plus)?\\s*(?:years?|yoe|năm|yrs?)?"
    );

    private static final Pattern YOE_NUMBER_UNIT_PATTERN = Pattern.compile(
            "(?i)(?<!(?:java|c#|python|php|node|react|angular|vue|\\bv|v\\.|version|phiên bản|tháng|thang)\\s*)(\\d+(?:\\.\\d+)?)\\s*(?:\\+|plus)?\\s*(?:years?|yoe|năm|yrs?)\\b"
    );

    private static final Pattern GENERIC_NUMBER_FALLBACK_PATTERN = Pattern.compile(
            "(?<!\\d)(?:(19\\d{2}|20\\d{2})|(\\d+(?:\\.\\d+)?))"
    );

    /**
     * Calculate total quantified years of professional experience from CV text.
     */
    public static double calculateCandidateYoe(String cvContent) {
        if (cvContent == null || cvContent.isBlank()) return 0.0;
        String targetText = extractExperienceSection(cvContent);
        if (targetText == null || targetText.isBlank()) return 0.0;
        List<DateRange> ranges = extractDateRanges(targetText);
        if (ranges.isEmpty()) return 0.0;

        ranges.sort(Comparator.comparing(DateRange::start));
        List<DateRange> merged = new ArrayList<>();
        DateRange current = null;

        for (DateRange r : ranges) {
            if (current == null) {
                current = new DateRange(r.start(), r.end());
            } else if (!r.start().isAfter(current.end())) {
                if (r.end().isAfter(current.end())) {
                    current = new DateRange(current.start(), r.end());
                }
            } else {
                merged.add(current);
                current = new DateRange(r.start(), r.end());
            }
        }
        if (current != null) merged.add(current);

        long totalDays = merged.stream().mapToLong(r -> ChronoUnit.DAYS.between(r.start(), r.end())).sum();
        return Math.round((totalDays / 365.25) * 10.0) / 10.0;
    }

    /**
     * Isolates work experience / project section to avoid counting university education duration.
     */
    public static String extractExperienceSection(String cvContent) {
        if (cvContent == null || cvContent.isBlank()) return "";
        String[] lines = cvContent.split("\\r?\\n");
        StringBuilder sb = new StringBuilder();
        boolean inExp = false;
        boolean hasAnyHeader = false;

        for (String line : lines) {
            String trimmed = line.trim();
            if (EXP_HEADER_PATTERN.matcher(trimmed).matches()) {
                inExp = true;
                hasAnyHeader = true;
                sb.append(line).append("\n");
            } else if (OTHER_HEADER_PATTERN.matcher(trimmed).matches()) {
                inExp = false;
                hasAnyHeader = true;
            } else if (inExp) {
                sb.append(line).append("\n");
            }
        }
        String result = sb.toString().trim();
        if (!result.isEmpty()) return result;
        // If CV has other structured headers (Education, Academic Projects, etc.) but no experience header -> 0 YOE
        if (hasAnyHeader) return "";
        // If CV has no structured headers at all (e.g. short text snippet), return raw text
        return cvContent;
    }

    /**
     * Extracts date intervals from text using multiple date format patterns.
     */
    public static List<DateRange> extractDateRanges(String text) {
        List<DateRange> ranges = new ArrayList<>();
        if (text == null || text.isBlank()) return ranges;

        // Pattern 0: Full Numeric Day/Month/Year: 15/05/2021 - 20/08/2023 or 01.01.2020 - Present
        Matcher m0 = FULL_NUMERIC_DATE_PATTERN.matcher(text);
        while (m0.find()) {
            try {
                int startMonth = Integer.parseInt(m0.group(1));
                int startYear = Integer.parseInt(m0.group(2));
                LocalDate start = LocalDate.of(startYear, startMonth, 1);

                String endStr = m0.group(3);
                LocalDate end;
                if (endStr.matches("(?i)Present|Now|Current|Nay|Hiện tại")) {
                    end = LocalDate.now();
                } else {
                    String[] parts = endStr.split("[./-]");
                    int endMonth = parts.length >= 3 ? Integer.parseInt(parts[1]) : Integer.parseInt(parts[0]);
                    int endYear = parts.length >= 3 ? Integer.parseInt(parts[2]) : Integer.parseInt(parts[1]);
                    end = LocalDate.of(endYear, endMonth, 1).plusMonths(1).minusDays(1);
                }
                if (!end.isBefore(start)) ranges.add(new DateRange(start, end));
            } catch (Exception ignored) {}
        }

        // Pattern 1: Numeric Month/Year: 01/2021 - 05/2023 or 1.2021 - 5.2023 or 1/2021 - Present
        Matcher m1 = NUMERIC_DATE_PATTERN.matcher(text);
        while (m1.find()) {
            try {
                int startMonth = Integer.parseInt(m1.group(1));
                int startYear = Integer.parseInt(m1.group(2));
                LocalDate start = LocalDate.of(startYear, startMonth, 1);

                String endStr = m1.group(3);
                LocalDate end;
                if (endStr.matches("(?i)Present|Now|Current|Nay|Hiện tại")) {
                    end = LocalDate.now();
                } else {
                    String[] parts = endStr.split("[./-]");
                    int endMonth = Integer.parseInt(parts[0]);
                    int endYear = Integer.parseInt(parts[1]);
                    end = LocalDate.of(endYear, endMonth, 1).plusMonths(1).minusDays(1);
                }
                if (!end.isBefore(start)) ranges.add(new DateRange(start, end));
            } catch (Exception ignored) {}
        }

        // Pattern 1b: Year-first Month/Year: 2021.05 - 2023.08 or 2021/01 - 2023/12 or 2022-01 - Present
        Matcher m1b = YEAR_FIRST_DATE_PATTERN.matcher(text);
        while (m1b.find()) {
            try {
                int startYear = Integer.parseInt(m1b.group(1));
                int startMonth = Integer.parseInt(m1b.group(2));
                LocalDate start = LocalDate.of(startYear, startMonth, 1);

                String endStr = m1b.group(3);
                LocalDate end;
                if (endStr.matches("(?i)Present|Now|Current|Nay|Hiện tại")) {
                    end = LocalDate.now();
                } else {
                    String[] parts = endStr.split("[./-]");
                    int endYear = Integer.parseInt(parts[0]);
                    int endMonth = Integer.parseInt(parts[1]);
                    end = LocalDate.of(endYear, endMonth, 1).plusMonths(1).minusDays(1);
                }
                if (!end.isBefore(start)) ranges.add(new DateRange(start, end));
            } catch (Exception ignored) {}
        }

        // Pattern 2: Word Month/Year: Jan 2021 - Mar 2023 or Tháng 1/2021 - Nay
        Matcher m2 = WORD_MONTH_DATE_PATTERN.matcher(text);
        while (m2.find()) {
            try {
                int startMonth = parseMonthWordToNumber(m2.group(1));
                int startYear = Integer.parseInt(m2.group(2));
                LocalDate start = LocalDate.of(startYear, startMonth, 1);

                String endStr = m2.group(3);
                LocalDate end;
                if (endStr.matches("(?i)Present|Now|Current|Nay|Hiện tại")) {
                    end = LocalDate.now();
                } else {
                    Matcher endMatcher = Pattern.compile("(?i)(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Tháng\\s*(?:0?[1-9]|1[0-2]))[.,\\s/-]+(\\d{4})").matcher(endStr);
                    if (endMatcher.find()) {
                        int endMonth = parseMonthWordToNumber(endMatcher.group(1));
                        int endYear = Integer.parseInt(endMatcher.group(2));
                        end = LocalDate.of(endYear, endMonth, 1).plusMonths(1).minusDays(1);
                    } else {
                        end = LocalDate.now();
                    }
                }
                if (!end.isBefore(start)) ranges.add(new DateRange(start, end));
            } catch (Exception ignored) {}
        }

        // Pattern 3: Year-only: 2020 - 2023 or 2021 - Present
        Matcher m3 = YEAR_ONLY_DATE_PATTERN.matcher(text);
        while (m3.find()) {
            try {
                int startYear = Integer.parseInt(m3.group(1));
                LocalDate start = LocalDate.of(startYear, 1, 1);

                String endStr = m3.group(2);
                LocalDate end;
                if (endStr.matches("(?i)Present|Now|Current|Nay|Hiện tại")) {
                    end = LocalDate.now();
                } else {
                    int endYear = Integer.parseInt(endStr);
                    end = LocalDate.of(endYear, 12, 31);
                }
                if (!end.isBefore(start)) ranges.add(new DateRange(start, end));
            } catch (Exception ignored) {}
        }

        return ranges;
    }

    public static int parseMonthWordToNumber(String monthWord) {
        if (monthWord == null) return 1;
        String clean = monthWord.toLowerCase(Locale.ROOT).trim();
        if (clean.startsWith("tháng") || clean.startsWith("thang")) {
            Matcher m = Pattern.compile("(\\d+)").matcher(clean);
            if (m.find()) {
                return Integer.parseInt(m.group(1));
            }
        }
        return switch (clean.substring(0, Math.min(3, clean.length()))) {
            case "jan" -> 1;
            case "feb" -> 2;
            case "mar" -> 3;
            case "apr" -> 4;
            case "may" -> 5;
            case "jun" -> 6;
            case "jul" -> 7;
            case "aug" -> 8;
            case "sep" -> 9;
            case "oct" -> 10;
            case "nov" -> 11;
            case "dec" -> 12;
            default -> 1;
        };
    }

    /**
     * Parses numeric requirement for YoE from gate string with context-aware pattern matching.
     * Prioritizes explicit time unit matches (e.g. "3 years", "2+ năm") to avoid capturing framework
     * versions like "Java 11" or calendar years like "2022".
     */
    public static double parseRequiredYoe(String reqVal) {
        if (reqVal == null || reqVal.isBlank()) return 0.0;

        // Pass 1: Look for explicit keyword patterns like "tối thiểu 3 năm", "at least 2 years"
        Matcher mKw = YOE_WITH_KEYWORD_PATTERN.matcher(reqVal);
        if (mKw.find()) {
            try {
                return Double.parseDouble(mKw.group(1));
            } catch (Exception ignored) {}
        }

        // Pass 2: Look for number + unit like "3+ years", "2 năm", "1.5 yoe"
        Matcher mUnit = YOE_NUMBER_UNIT_PATTERN.matcher(reqVal);
        if (mUnit.find()) {
            try {
                return Double.parseDouble(mUnit.group(1));
            } catch (Exception ignored) {}
        }

        // Pass 3: Fallback for generic number if the string contains experience keywords or is a short numeric string
        String lower = reqVal.toLowerCase(Locale.ROOT).trim();
        boolean hasExpContext = lower.contains("exp") || lower.contains("kinh nghiệm") || lower.contains("yoe")
                || lower.contains("year") || lower.contains("năm") || lower.matches("^\\s*\\d+(?:\\.\\d+)?\\s*\\+?\\s*$");

        if (hasExpContext) {
            Matcher mGeneric = GENERIC_NUMBER_FALLBACK_PATTERN.matcher(reqVal);
            while (mGeneric.find()) {
                if (mGeneric.group(2) != null) {
                    try {
                        double val = Double.parseDouble(mGeneric.group(2));
                        if (val > 0 && val <= 30) { // Reasonable YoE boundary check
                            return val;
                        }
                    } catch (Exception ignored) {}
                }
            }
        }
        return 0.0;
    }

    /**
     * Checks whether candidate CV mentions a higher education degree (Bachelor, Master, Engineer, University, etc.).
     * Handles negative statements (e.g. "không có bằng đại học", "no university degree").
     */
    public static boolean checkDegreeInCv(String cvContent) {
        return checkDegreeInCv(cvContent, null);
    }

    /**
     * Checks whether candidate CV meets degree requirement, supporting degree level checking.
     */
    public static boolean checkDegreeInCv(String cvContent, String requiredDegree) {
        if (cvContent == null || cvContent.isBlank()) return false;
        String lower = cvContent.toLowerCase(Locale.ROOT);

        // Check for explicit negation phrases
        if (lower.contains("không có bằng đại học")
                || lower.contains("chưa có bằng đại học")
                || lower.contains("no degree")
                || lower.contains("no university degree")
                || lower.contains("without a degree")
                || lower.contains("without degree")) {
            return false;
        }

        boolean onlyHighSchool = lower.contains("high school")
                && !lower.contains("bachelor") && !lower.contains("university")
                && !lower.contains("college") && !lower.contains("đại học");
        if (onlyHighSchool) return false;

        // If required level is Master / PhD specifically:
        if (requiredDegree != null && !requiredDegree.isBlank()) {
            String reqLower = requiredDegree.toLowerCase(Locale.ROOT);
            if (reqLower.contains("master") || reqLower.contains("thạc sĩ") || reqLower.contains("m.s.") || reqLower.contains("m.sc")) {
                return lower.contains("master") || lower.contains("thạc sĩ") || lower.contains("m.s.") || lower.contains("m.sc")
                        || lower.contains("tiến sĩ") || lower.contains("ph.d") || lower.contains("phd");
            }
            if (reqLower.contains("phd") || reqLower.contains("ph.d") || reqLower.contains("tiến sĩ") || reqLower.contains("doctorate")) {
                return lower.contains("tiến sĩ") || lower.contains("ph.d") || lower.contains("phd") || lower.contains("doctorate");
            }
            if (reqLower.contains("bachelor") || reqLower.contains("đại học") || reqLower.contains("cử nhân")
                    || reqLower.contains("kỹ sư") || reqLower.contains("b.s") || reqLower.contains("b.sc")
                    || reqLower.contains("university")) {
                return lower.contains("bachelor")
                        || lower.contains("master")
                        || lower.contains("cử nhân")
                        || lower.contains("kỹ sư")
                        || lower.contains("thạc sĩ")
                        || lower.contains("tiến sĩ")
                        || lower.contains("ph.d")
                        || lower.contains("phd")
                        || lower.contains("b.s.")
                        || lower.contains("b.sc")
                        || lower.contains("b.e.")
                        || lower.contains("b.tech")
                        || lower.contains("đại học")
                        || lower.contains("university")
                        || lower.contains("học viện")
                        || lower.contains("bách khoa")
                        || lower.contains("fpt university")
                        || lower.contains("institute of technology");
            }
        }

        return lower.contains("bachelor")
                || lower.contains("master")
                || lower.contains("degree")
                || lower.contains("cử nhân")
                || lower.contains("kỹ sư")
                || lower.contains("thạc sĩ")
                || lower.contains("tiến sĩ")
                || lower.contains("ph.d")
                || lower.contains("phd")
                || lower.contains("b.s.")
                || lower.contains("b.sc")
                || lower.contains("b.e.")
                || lower.contains("b.tech")
                || lower.contains("m.s.")
                || lower.contains("m.sc")
                || lower.contains("đại học")
                || lower.contains("cao đẳng")
                || lower.contains("university")
                || lower.contains("college")
                || lower.contains("học viện")
                || lower.contains("bách khoa")
                || lower.contains("fpt university")
                || lower.contains("institute of technology");
    }
}
