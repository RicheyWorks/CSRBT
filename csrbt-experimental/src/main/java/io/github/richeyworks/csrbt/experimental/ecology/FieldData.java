package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * The data bus (ADR-020): one tiny, forgiving format for getting <b>real observations</b>
 * — field counts, ethogram tallies, presence/absence surveys — into the experiment
 * engine, and back out again for storage, reuse, and export.
 *
 * <p>Two entry forms, one result (a name → count table):</p>
 *
 * <ul>
 *   <li><b>Token form</b> (one line, used by the {@code data:} directive in {@code .eco}
 *       files): {@code oak=12 maple=5 birch}. A bare name counts as one sighting, and
 *       repeating a name adds — so {@code peck peck flap peck} is an ethogram tally
 *       exactly as a student would keep it on a clipboard: tally marks.</li>
 *   <li><b>Table form</b> (many lines, used for pasting from a spreadsheet or CSV):
 *       one observation per line as {@code name,count}, {@code name<TAB>count},
 *       {@code name count}, or just {@code name} (one sighting). {@code #} comments
 *       and blank lines are ignored.</li>
 * </ul>
 *
 * <p>Both parsers follow the house rule: a malformed token or line is <b>reported,
 * never guessed at</b>, and everything that did parse still counts. The inverses —
 * {@link #toEcoLine} and {@link #toCsv} — make data round-trip: type it once in the
 * lab page's Workbench, copy the generated {@code data:} line into a protocol file,
 * and the same numbers re-run, re-grade, and re-export forever.</p>
 */
public final class FieldData {

    private FieldData() {}

    /** A parsed table: counts in first-seen order, problems verbatim with reasons. */
    public record Parsed(LinkedHashMap<String, Long> counts, List<String> problems) {}

    /**
     * Token form: {@code name[=count]} tokens separated by whitespace. Bare names
     * count 1; repeats add (tally marks). Counts must be positive integers —
     * {@code name=0} is a problem, because absence is expressed by not listing a name.
     */
    public static Parsed parseTokens(String s) {
        LinkedHashMap<String, Long> counts = new LinkedHashMap<>();
        List<String> problems = new java.util.ArrayList<>();
        for (String token : s.trim().split("\\s+")) {
            if (token.isEmpty()) continue;
            addToken(token, counts, problems);
        }
        return new Parsed(counts, problems);
    }

    /**
     * Table form: one observation per line — {@code name,count}, {@code name<TAB>count},
     * {@code name count}, or a bare {@code name} (counts 1). Repeated names add.
     * {@code #} starts a comment; blank lines are skipped.
     */
    public static Parsed parseLines(List<String> lines) {
        LinkedHashMap<String, Long> counts = new LinkedHashMap<>();
        List<String> problems = new java.util.ArrayList<>();
        for (String raw : lines) {
            int hash = raw.indexOf('#');
            String line = (hash < 0 ? raw : raw.substring(0, hash)).trim();
            if (line.isEmpty()) continue;
            // Normalize the three separators to one: first comma or tab, else last space.
            String[] parts = line.split("[,\\t]");
            if (parts.length == 1) parts = line.split("\\s+(?=\\S+$)");   // "name count"
            if (parts.length == 1) {
                addToken(parts[0].trim(), counts, problems);
                continue;
            }
            if (parts.length != 2) {
                problems.add(raw.trim() + "  (want: name,count or name count or a bare name)");
                continue;
            }
            String name = parts[0].trim();
            String num = parts[1].trim();
            if (name.isEmpty()) { problems.add(raw.trim() + "  (empty name)"); continue; }
            try {
                long n = Long.parseLong(num);
                if (n <= 0) { problems.add(raw.trim() + "  (count must be positive)"); continue; }
                counts.merge(name, n, Long::sum);
            } catch (NumberFormatException bad) {
                // Whole line might itself be a multi-word bare name ("great blue heron").
                addToken(line.replaceAll("\\s+", "-"), counts, problems);
            }
        }
        return new Parsed(counts, problems);
    }

    private static void addToken(String token, Map<String, Long> counts, List<String> problems) {
        int eq = token.indexOf('=');
        if (eq < 0) {
            counts.merge(token, 1L, Long::sum);
            return;
        }
        String name = token.substring(0, eq).trim();
        String num = token.substring(eq + 1).trim();
        if (name.isEmpty()) { problems.add(token + "  (empty name)"); return; }
        try {
            long n = Long.parseLong(num);
            if (n <= 0) { problems.add(token + "  (count must be positive — omit a name to record absence)"); return; }
            counts.merge(name, n, Long::sum);
        } catch (NumberFormatException bad) {
            problems.add(token + "  (count '" + num + "' is not an integer)");
        }
    }

    /** The inverse of token form: a ready-to-paste {@code data:} directive line. */
    public static String toEcoLine(String label, Map<String, Long> counts) {
        StringBuilder sb = new StringBuilder("data: ").append(label);
        for (Map.Entry<String, Long> e : counts.entrySet()) {
            sb.append(' ').append(e.getKey());
            if (e.getValue() != 1) sb.append('=').append(e.getValue());
        }
        return sb.toString();
    }

    /** CSV rows ({@code dataset,name,count}, no header) — Excel/Sheets/R ready. */
    public static String toCsv(String dataset, Map<String, Long> counts) {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, Long> e : counts.entrySet()) {
            sb.append(ExperimentExport.csv(dataset)).append(',')
              .append(ExperimentExport.csv(e.getKey())).append(',')
              .append(String.format(Locale.ROOT, "%d", e.getValue())).append('\n');
        }
        return sb.toString();
    }
}
