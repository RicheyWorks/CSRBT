package io.github.richeyworks.csrbt.experimental.ecology;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Your workload as an ecosystem — replay a recorded operation trace through the
 * ecology instruments and get the same narrated field report and lab-page session
 * the demo produces, but about <em>your</em> data.
 *
 * <p>Trace format: one op per line, {@code op,key} (comma or whitespace separated).
 * Accepted op aliases (case-insensitive): {@code add / a / insert / put},
 * {@code remove / r / delete / del}, {@code search / s / get / read / contains /
 * lookup}. Blank lines and {@code #} comments are skipped; malformed lines are
 * counted and reported, never guessed at.</p>
 *
 * <p>Run from the repo root:
 * {@code ./gradlew ecologyTrace -Ptrace=path/to/trace.csv} — prints the narrated
 * report and writes {@code docs/ecology-trace-session.json}, which
 * {@code docs/ecology-lab.html} renders (drag-drop it onto the page). A worked
 * example lives at {@code docs/sample-trace.csv}. Deterministic: same trace,
 * same bytes.</p>
 *
 * <p>Stations are emitted only where the trace carries the signal: the community
 * survey always (any ops at all); <b>drift</b> — consecutive-window Bray–Curtis,
 * workload change made visible — when at least three windows closed; demography
 * when at least two keys completed a lifespan; growth when the population series
 * supports a fit; the survey grid when keys remain at the end.</p>
 */
public final class WorkloadTrace {

    /** One parsed op. */
    public record Op(int kind, int key) {}   // kind: 0 add, 1 remove, 2 search

    /** Parse result: ops plus the count of lines that could not be read. */
    public record Parsed(List<Op> ops, int skipped) {}

    private WorkloadTrace() {}

    public static void main(String[] args) throws IOException {
        Path in = Path.of(args.length > 0 ? args[0] : "docs/sample-trace.csv");
        Path out = Path.of(args.length > 1 ? args[1] : "docs/ecology-trace-session.json");
        EcologyFieldDay.Session session = run(Files.readAllLines(in), in.getFileName().toString());
        System.out.println(session.report());
        Files.writeString(out, session.json());
        System.out.println("session written → " + out + "  (drop it onto docs/ecology-lab.html)");
    }

    /** Replay a trace; returns the narrated report and the lab-page session JSON. */
    public static EcologyFieldDay.Session run(List<String> lines, String label) {
        Parsed parsed = parse(lines);
        List<Op> ops = parsed.ops();
        int windowOps = Math.max(32, ops.size() / 24);
        EcologyRecorder rec = new EcologyRecorder(windowOps, 64);
        for (Op op : ops) {
            switch (op.kind()) {
                case 0 -> rec.recordAdd(op.key());
                case 1 -> rec.recordRemove(op.key(), 0);
                default -> rec.recordSearch(op.key(), 1);
            }
        }

        StringBuilder report = new StringBuilder();
        report.append("🌿 ECOLOGY TRACE SURVEY — ").append(label).append('\n');
        report.append(String.format(Locale.ROOT,
                "   %d ops replayed (%d lines skipped), window = %d ops%n%n",
                ops.size(), parsed.skipped(), windowOps));
        StringBuilder json = new StringBuilder("{\n");
        boolean[] first = { true };

        // ── Community ─────────────────────────────────────────────────────────
        Map<Integer, Long> abundance = rec.cumulativeAbundance();
        report.append(FieldReport.communitySection("THE COMMUNITY — " + label, abundance));
        report.append('\n');
        appendMeadow(json, first, label, abundance);

        // ── Drift (consecutive-window turnover) ───────────────────────────────
        List<Map<Integer, Long>> windows = rec.closedWindows();
        if (windows.size() >= 3) {
            double[] bray = new double[windows.size() - 1];
            int peak = 0;
            for (int i = 1; i < windows.size(); i++) {
                bray[i - 1] = BetaDiversity.brayCurtis(windows.get(i - 1), windows.get(i));
                if (bray[i - 1] > bray[peak]) peak = i - 1;
            }
            report.append("── THE DRIFT — how the workload changed while it ran ──\n");
            report.append(String.format(Locale.ROOT,
                    "  %d windows closed; sharpest change at window %d → %d (Bray–Curtis %.2f: %s).%n%n",
                    windows.size(), peak + 1, peak + 2, bray[peak],
                    FieldReport.turnoverReading(bray[peak])));
            sep(json, first);
            json.append("  \"drift\": { \"windowOps\": ").append(windowOps)
                .append(", \"bray\": [");
            for (int i = 0; i < bray.length; i++) {
                if (i > 0) json.append(',');
                json.append(String.format(Locale.ROOT, "%.4f", bray[i]));
            }
            json.append("] }");
        }

        // ── Demography ────────────────────────────────────────────────────────
        if (rec.lifespans().size() >= 2) {
            LifeTable table = LifeTable.fromLifespans(rec.lifespans(),
                    Math.min(6, Math.max(3, rec.lifespans().size() / 4)));
            report.append(FieldReport.demographySection("THE CENSUS — key lifespans in this trace", table));
            report.append('\n');
            sep(json, first);
            json.append("  \"demography\": {");
            appendLifeTable(json, table);
            json.append(" }");
        }

        // ── Growth ────────────────────────────────────────────────────────────
        List<long[]> series = rec.populationSeries();
        try {
            LogisticGrowth.Fit fit = LogisticGrowth.fit(series);
            report.append("── THE GROWTH CURVE ──\n  ")
                  .append(FieldReport.growthReading(fit)).append(".\n\n");
            sep(json, first);
            json.append("  \"growth\": { \"series\": [");
            for (int i = 0; i < series.size(); i++) {
                if (i > 0) json.append(',');
                json.append('[').append(series.get(i)[0]).append(',').append(series.get(i)[1]).append(']');
            }
            json.append(String.format(Locale.ROOT,
                    "], \"r\": %.6f, \"K\": %.6f, \"n0\": %.6f, \"r2\": %.6f }",
                    fit.r(), fit.carryingCapacity(), fit.n0(), fit.rSquared()));
        } catch (IllegalArgumentException tooFewSamples) {
            // fewer than two usable population samples — station skipped, honestly
        }

        // ── Survey grid ───────────────────────────────────────────────────────
        List<Integer> aliveKeys = new ArrayList<>(rec.aliveBirthOps().keySet());
        aliveKeys.sort(null);
        if (!aliveKeys.isEmpty()) {
            long[] counts = RangeQuadrats.countsOfInts(aliveKeys, Math.min(20, Math.max(4, aliveKeys.size() / 5)));
            report.append(FieldReport.spatialSection("THE SURVEY GRID — keys still present at trace end", counts));
            sep(json, first);
            json.append("  \"grid\": { \"clustered\": { \"counts\": [");
            for (int i = 0; i < counts.length; i++) {
                if (i > 0) json.append(',');
                json.append(counts[i]);
            }
            json.append(String.format(Locale.ROOT, "], \"dispersion\": %.6f, \"morisita\": %.6f } }",
                    RangeQuadrats.indexOfDispersion(counts), RangeQuadrats.morisita(counts)));
        }

        json.append("\n}\n");
        return new EcologyFieldDay.Session(report.toString(), json.toString());
    }

    // ── Parsing ───────────────────────────────────────────────────────────────

    public static Parsed parse(List<String> lines) {
        List<Op> ops = new ArrayList<>();
        int skipped = 0;
        for (String raw : lines) {
            String line = raw.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] parts = line.split("[,\\s]+");
            if (parts.length < 2) { skipped++; continue; }
            int kind = opKind(parts[0]);
            if (kind < 0) { skipped++; continue; }
            try {
                ops.add(new Op(kind, Integer.parseInt(parts[1].trim())));
            } catch (NumberFormatException nf) {
                skipped++;
            }
        }
        return new Parsed(ops, skipped);
    }

    private static int opKind(String op) {
        return switch (op.toLowerCase(Locale.ROOT)) {
            case "add", "a", "insert", "put" -> 0;
            case "remove", "r", "delete", "del" -> 1;
            case "search", "s", "get", "read", "contains", "lookup" -> 2;
            default -> -1;
        };
    }

    // ── JSON helpers (same conventions as EcologyFieldDay.Json) ───────────────

    /** Minimal JSON string escaping — the label is the only free-text field emitted. */
    public static String escapeJson(String s) {
        StringBuilder out = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            switch (ch) {
                case '"'  -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (ch < 0x20) out.append(String.format(java.util.Locale.ROOT, "\\u%04x", (int) ch));
                    else out.append(ch);
                }
            }
        }
        return out.toString();
    }

    private static void sep(StringBuilder json, boolean[] first) {
        if (!first[0]) json.append(",\n");
        first[0] = false;
    }

    private static void appendMeadow(StringBuilder json, boolean[] first,
                                     String label, Map<Integer, Long> abundance) {
        sep(json, first);
        json.append("  \"meadow\": { \"phases\": [{ \"name\": \"")
            .append(escapeJson(label)).append('"');
        json.append(", \"richness\": ").append(CommunityMetrics.richness(abundance));
        json.append(", \"total\": ").append(CommunityMetrics.total(abundance));
        json.append(String.format(Locale.ROOT, ", \"shannon\": %.6f", CommunityMetrics.shannon(abundance)));
        json.append(String.format(Locale.ROOT, ", \"evenness\": %.6f", CommunityMetrics.pielouEvenness(abundance)));
        json.append(String.format(Locale.ROOT, ", \"hill1\": %.6f", CommunityMetrics.hillNumber(abundance, 1)));
        json.append(String.format(Locale.ROOT, ", \"chao1\": %.6f", CommunityMetrics.chao1(abundance)));
        json.append(", \"bestFit\": \"").append(CommunityMetrics.bestFit(abundance).best()).append('"');
        List<Long> ranks = CommunityMetrics.rankAbundance(abundance);
        json.append(", \"rank\": [");
        for (int i = 0; i < Math.min(40, ranks.size()); i++) {
            if (i > 0) json.append(',');
            json.append(ranks.get(i));
        }
        json.append(']');
        double[][] rc = CommunityMetrics.rarefactionCurve(abundance, 20);
        json.append(", \"rarefaction\": [");
        for (int i = 0; i < rc.length; i++) {
            if (i > 0) json.append(',');
            json.append(String.format(Locale.ROOT, "[%.0f,%.4f]", rc[i][0], rc[i][1]));
        }
        json.append("] }] }");
    }

    static void appendLifeTable(StringBuilder json, LifeTable t) {
        json.append(" \"classWidth\": ").append(t.classWidth());
        json.append(", \"cohort\": ").append(t.cohortSize());
        json.append(String.format(Locale.ROOT, ", \"meanAge\": %.6f", t.lifeExpectancy()));
        json.append(String.format(Locale.ROOT, ", \"medianAge\": %.6f", t.medianAge()));
        json.append(", \"type\": \"").append(t.survivorshipType()).append('"');
        json.append(", \"survivorship\": [");
        for (int x = 0; x < t.ageClasses(); x++) {
            if (x > 0) json.append(',');
            json.append(String.format(Locale.ROOT, "%.6f", t.survivorshipAt(x)));
        }
        json.append("], \"deaths\": [");
        for (int x = 0; x < t.ageClasses(); x++) {
            if (x > 0) json.append(',');
            json.append(t.deathsAt(x));
        }
        json.append(']');
    }
}
