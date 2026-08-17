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
 *       {@code name count}, just {@code name} (one sighting), or a
 *       {@code dataset,name,count} row straight out of {@link #toCsv}. Comma/tab fields
 *       are RFC-4180 quoted, so {@code "oak, white",12} is one species. {@code #}
 *       comments and blank lines are ignored.</li>
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
     * {@code name count}, a bare {@code name} (counts 1), or a {@code dataset,name,count}
     * row exactly as {@link #toCsv} writes one. Repeated names add. {@code #} starts a
     * comment; blank lines are skipped.
     *
     * <p><b>Quoting.</b> Comma/tab fields are split RFC-4180-style by {@link #splitFields},
     * so a name that contains a comma round-trips as long as it is quoted the way
     * {@code toCsv} quotes it: {@code "oak, white",12} is one name and one count, not a
     * malformed three-field line. Without this the tool could not read its own export
     * (audit 2026-08-17, item 4); an <em>unquoted</em> comma is still a field separator,
     * because that is what CSV means — {@code oak, white,12} is three fields and is read
     * as an export row.</p>
     *
     * <p><b>The dataset column.</b> Only the three-field shape carries one, which is the
     * only shape {@code toCsv} emits; a two-field row is always {@code name,count} and is
     * never re-read as {@code dataset,name}, so nothing here has to guess which of the two
     * a caller meant. The label itself is dropped — {@link Parsed} is a single name → count
     * table — so pasting rows from two different datasets merges them, exactly as repeating
     * a name already adds.</p>
     *
     * <p><b>A bare name may carry its count.</b> A single-token line goes through the same
     * {@code name=count} reader the token form uses, so {@code oak=5} on a line means five oaks —
     * which matters because {@code name=count} is exactly what {@link #toEcoLine} and the lab
     * page's "build .eco lines" button emit, and a student who copies that output back into the
     * table would otherwise get a species literally named {@code oak=5}.</p>
     *
     * <p><b>A bare number is reported, not guessed.</b> A line that is nothing but a number is
     * the one shape whose meaning cannot be recovered — a count with the name missing, or a
     * species named by a number — so it is reported with both fixes rather than silently read
     * one way (audit 2026-08-17, seventh pass, item B; see {@link #bareNumberProblem}). Write
     * {@code sp1,12} for a count of twelve, or {@code 12,1} for one sighting of a species called
     * {@code 12}.</p>
     *
     * <p>Everything else keeps the house rule: a line that does not fit one of those shapes
     * is <b>reported</b> in {@link Parsed#problems()} with its reason, never guessed at.</p>
     *
     * <p><b>Mirrored by the lab page.</b> {@code docs/ecology-lab.html}'s {@code parseCounts} is
     * a transliteration of this method — same shapes, same problems, same wording — and the two
     * are held to it by a differential test over a random corpus
     * ({@code FieldDataJsMirrorTest}), because the page is where most students meet this
     * format.</p>
     */
    public static Parsed parseLines(List<String> lines) {
        LinkedHashMap<String, Long> counts = new LinkedHashMap<>();
        List<String> problems = new java.util.ArrayList<>();
        for (String raw : lines) {
            int hash = raw.indexOf('#');
            String line = (hash < 0 ? raw : raw.substring(0, hash)).trim();
            if (line.isEmpty()) continue;
            // Normalize the three separators to one: comma/tab fields (quote-aware, so an
            // empty trailing field survives — "oak," is a comma line with an empty count,
            // a reportable problem, not a bare name literally spelled "oak,"), else the
            // last space in a "name count" line.
            String[] parts = splitFields(line);
            boolean commaOrTab = parts.length > 1;
            if (parts.length == 1) parts = line.split("\\s+(?=\\S+$)");   // "name count"
            if (parts.length == 1) {
                String token = parts[0].trim();
                if (BARE_NUMBER.matcher(token).matches()) { problems.add(bareNumberProblem(token)); continue; }
                addToken(token, counts, problems);
                continue;
            }
            if (parts.length == 3) {
                // dataset,name,count — toCsv's own row shape. Drop the label and judge the
                // remaining pair by the normal rules, so a bad count in an export row is
                // still reported as a bad count rather than as an unrecognizable line.
                parts = new String[]{ parts[1], parts[2] };
            }
            if (parts.length != 2) {
                problems.add(raw.trim()
                        + "  (want: name,count or dataset,name,count or name count or a bare name)");
                continue;
            }
            String name = parts[0].trim();
            String num = parts[1].trim();
            if (name.isEmpty()) { problems.add(raw.trim() + "  (empty name)"); continue; }
            try {
                long n = Long.parseLong(num);
                // Same condition as addToken's, so the same sentence: a student who writes
                // "robin,0" on one line and "robin=0" on another is told the same thing twice.
                if (n <= 0) { problems.add(raw.trim() + "  " + NON_POSITIVE); continue; }
                counts.merge(name, n, Long::sum);
            } catch (NumberFormatException bad) {
                if (commaOrTab) {
                    // An explicit comma/tab separator means the second field IS the
                    // count — a bad one is reported, never guessed.
                    problems.add(raw.trim() + "  (count '" + num + "' is not an integer)");
                } else {
                    // Whole line might itself be a multi-word bare name ("great blue heron").
                    addToken(line.replaceAll("\\s+", "-"), counts, problems);
                }
            }
        }
        return new Parsed(counts, problems);
    }

    /**
     * Split one table line into fields with {@link ExperimentExport#splitCsv}'s RFC-4180
     * semantics — {@code "} opens/closes a quoted field, {@code ""} inside one is a literal
     * quote — plus TAB as a second separator, which the table form has always accepted.
     * Empty trailing fields survive (the old {@code split("[,\t]", -1)} kept them too), so
     * {@code "oak,"} still reaches the empty-count problem instead of being tallied as a
     * species literally named {@code oak,}.
     *
     * <p>Kept here rather than folded into {@code ExperimentExport.splitCsv} because that
     * method is the exact inverse of {@code ExperimentExport.csv} and must stay
     * comma-only; this one is the table form's reader, and the two are pinned to each
     * other by {@code FieldDataTest} rather than by sharing code.</p>
     */
    static String[] splitFields(String line) {
        List<String> out = new java.util.ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (quoted) {
                if (c == '"' && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    cur.append('"');
                    i++;
                } else if (c == '"') {
                    quoted = false;
                } else {
                    cur.append(c);
                }
            } else if (c == '"') {
                quoted = true;
            } else if (c == ',' || c == '\t') {
                out.add(cur.toString());
                cur.setLength(0);
            } else {
                cur.append(c);
            }
        }
        out.add(cur.toString());
        return out.toArray(new String[0]);
    }

    /**
     * A table line that is nothing but a number, sign optional. {@code \p{Nd}} rather than
     * {@code [0-9]} because that is the digit set {@link Long#parseLong} itself accepts
     * ({@code Character.digit}), so the "is this a number?" question is answered the same way
     * here as where the count is actually parsed.
     */
    private static final java.util.regex.Pattern BARE_NUMBER =
            java.util.regex.Pattern.compile("[+-]?\\p{Nd}+");

    /**
     * One sentence for one condition, used by both entry forms. The table form used to say only
     * "count must be positive" while the token form explained the fix, so the same mistake was
     * reported two different ways depending on which separator the student typed.
     */
    private static final String NON_POSITIVE =
            "(count must be positive — omit a name to record absence)";

    /**
     * The report for a table line that is nothing but a number.
     *
     * <p>Such a line is genuinely ambiguous and this parser will not guess which way it goes.
     * Read as a name it makes a species literally called {@code 12} with abundance 1, so a pasted
     * count column becomes N species of abundance 1 — a community whose evenness J′ is exactly
     * 1.0000 by construction, which is a silently perfect and completely wrong answer. Read as a
     * count it needs a name, and inventing one ({@code sp1}, {@code sp2}, …) puts a fabricated
     * identifier into the student's own data: it flows out through {@link #toEcoLine} into the
     * {@code .eco} protocol and the exports, it renumbers when lines are reordered, and it
     * collides silently with a real species that happens to be called {@code sp1}. Neither
     * reading can be recovered downstream, so the line is reported with the two one-character
     * fixes — the house rule, applied to an ambiguity rather than to a malformation
     * (audit 2026-08-17, seventh pass, item B).</p>
     */
    private static String bareNumberProblem(String token) {
        return token + "  (a bare number is ambiguous — write \"name," + token
                + "\" for a count, or \"" + token + ",1\" for a species named " + token + ")";
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
            if (n <= 0) { problems.add(token + "  " + NON_POSITIVE); return; }
            counts.merge(name, n, Long::sum);
        } catch (NumberFormatException bad) {
            problems.add(token + "  (count '" + num + "' is not an integer)");
        }
    }

    /**
     * The inverse of token form: a ready-to-paste {@code data:} directive line.
     * Names containing whitespace or {@code =} (legal in table form: "great heron,5")
     * are hyphen-normalized the same way multi-word bare names already are — emitting
     * them verbatim into the whitespace-tokenized token form re-parsed as different
     * species with different counts, silently ("great heron=5" → {great=1, heron=5}).
     */
    public static String toEcoLine(String label, Map<String, Long> counts) {
        StringBuilder sb = new StringBuilder("data: ").append(label);
        for (Map.Entry<String, Long> e : counts.entrySet()) {
            sb.append(' ').append(e.getKey().replaceAll("[\\s=]+", "-"));
            if (e.getValue() != 1) sb.append('=').append(e.getValue());
        }
        return sb.toString();
    }

    /**
     * CSV rows ({@code dataset,name,count}, no header) — Excel/Sheets/R ready, and readable
     * back by {@link #parseLines}, quoted names included (the dataset label is dropped on
     * the way in). The row shape is unchanged; only the reader learned to accept it.
     */
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
