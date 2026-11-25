package fit.iuh.common;

public final class CsvCell {
    private CsvCell() {}

    public static String text(String value) {
        if (value == null) return "\"\"";
        String start = value.stripLeading();
        if ((!start.isEmpty() && "=+-@＝＋－＠".indexOf(start.charAt(0)) >= 0)
                || value.startsWith("\t") || value.startsWith("\r") || value.startsWith("\n")) {
            value = "'" + value;
        }
        return "\"" + value.replace("\"", "\"\"") + "\"";
    }
}
