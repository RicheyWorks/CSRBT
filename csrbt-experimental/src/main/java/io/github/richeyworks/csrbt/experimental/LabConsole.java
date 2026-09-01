package io.github.richeyworks.csrbt.experimental;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.evolution.GenomeDrivenTreeController;
import io.github.richeyworks.csrbt.evolution.StrategyBattleRunner;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;

/**
 * The science engine as a harness target (ADR-116, 2026-09-01): the classroom runner, the
 * strategy arena, the adaptive controller and the field day, driven over stdin/stdout by a
 * line protocol so the CSRBT automation contract — the gateway that already fronts every kit
 * page and the WholeHog organism — can front them through the same four operations.
 *
 * <p>Like WholeHog's {@code HarnessConsole}, this is a seam, not the contract: no token, no
 * policy, no risk ladder. Those live in {@code tools/harness_contract.py}; the
 * {@code csrbt-lab} plugin is this process's only client.</p>
 *
 * <h2>Protocol</h2>
 * One request per line, whitespace-separated tokens; one JSON object per reply line. A
 * protocol (an {@code .eco} text) is the one thing here that is not a number, and it crosses
 * the seam as a single base64 token so the line protocol stays one line. {@code dwc:} lines
 * are refused before parsing: a protocol that names a file on disk would make the harness
 * read the operator's disk, and no target in this kit does that.
 *
 * <pre>
 *   lint B64        → phases/models/expectations/datasets counted, problems named; runs nothing
 *   run B64         → the graded run: report text, session JSON, and the export names+sizes
 *   export B64 DIR  → the full bundle (CSVs, HTML, xlsx, pptx) written under DIR
 *   battle WORKLOAD OPS SEED   → StrategyBattleRunner: four strategies ranked
 *   adapt KEYS OPS SEED        → GenomeDrivenTreeController over a three-regime workload;
 *                                the morph log and where it ended
 *   fieldday        → EcologyFieldDay.run(): the full-ecosystem survey
 *   observe         → counters only
 *   quit
 * </pre>
 */
public final class LabConsole {

    static final String PROTOCOL = "1.0";
    static final int OPS_MAX = 50_000;
    static final int REPORT_CAP = 20_000;

    private final PrintStream out;
    private int runs, lints, battles, adapts, fieldDays, exportsWritten;
    private String lastName = "";

    LabConsole(PrintStream out) {
        this.out = out;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        LabConsole c = new LabConsole(out);
        out.println("{\"ok\":true,\"ready\":true,\"protocol\":\"" + PROTOCOL + "\"}");
        c.serve(new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8)));
    }

    void serve(BufferedReader in) throws IOException {
        String line;
        while ((line = in.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) {
                continue;
            }
            if ("quit".equals(line)) {
                out.println("{\"ok\":true,\"bye\":true}");
                return;
            }
            out.println(answer(line));
        }
    }

    String answer(String line) {
        try {
            return handle(line.split("\\s+"));
        } catch (NumberFormatException e) {
            return refuse("invalid_argument", "not a number: " + e.getMessage());
        } catch (IllegalArgumentException e) {
            return refuse("invalid_argument", e.getMessage());
        } catch (Exception e) {
            return refuse("failed", e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }

    String handle(String[] t) throws IOException {
        switch (t[0]) {
            case "observe":  return observe();
            case "lint":     return lint(spec(t, 1));
            case "run":      return run(spec(t, 1));
            case "export":   return export(spec(t, 1), t.length > 2 ? t[2] : null);
            case "battle":   return battle(t);
            case "adapt":    return adapt(intArg(t, 1, 1, 100_000), intArg(t, 2, 1, OPS_MAX), longArg(t, 3));
            case "fieldday": return fieldDay();
            default:
                return refuse("not_found", "unknown verb " + t[0]);
        }
    }

    String observe() {
        return "{\"ok\":true,\"ready\":true,\"runs\":" + runs + ",\"lints\":" + lints
                + ",\"battles\":" + battles + ",\"adapts\":" + adapts + ",\"fieldDays\":" + fieldDays
                + ",\"exportsWritten\":" + exportsWritten + ",\"lastName\":" + str(lastName)
                + ",\"workloads\":" + workloads() + "}";
    }

    // ── the classroom runner ────────────────────────────────────────────────

    /** Decode the protocol, refusing the one directive that would read the operator's disk. */
    static List<String> spec(String[] t, int i) {
        if (i >= t.length) {
            throw new IllegalArgumentException(t[0] + " needs a base64 protocol");
        }
        String text;
        try {
            text = new String(Base64.getDecoder().decode(t[i]), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("protocol is not base64");
        }
        List<String> lines = Arrays.asList(text.split("\r?\n", -1));
        for (String l : lines) {
            if (l.trim().toLowerCase(Locale.ROOT).startsWith("dwc:")) {
                throw new IllegalArgumentException("dwc: lines are refused through the harness: "
                        + "a protocol that names a file would read the operator's disk");
            }
        }
        return lines;
    }

    String lint(List<String> lines) {
        ExperimentSpec s = ExperimentSpec.parse(lines);
        lints++;
        lastName = s.name();
        return "{\"ok\":true,\"name\":" + str(s.name()) + ",\"keys\":" + s.keys() + ",\"seed\":" + s.seed()
                + ",\"phases\":" + s.phases().size() + ",\"models\":" + s.models().size()
                + ",\"expectations\":" + s.expectations().size() + ",\"datasets\":" + s.datasets().size()
                + ",\"crosses\":" + s.crosses().size() + ",\"notes\":" + s.notes().size()
                + ",\"trees\":" + s.trees().size() + ",\"problems\":" + strs(s.problems()) + "}";
    }

    String run(List<String> lines) {
        ExperimentSpec s = ExperimentSpec.parse(lines);
        Map<String, String> files = ExperimentLab.runWithExports(s);
        runs++;
        lastName = s.name();
        String report = files.get("report.txt");
        List<String> names = new ArrayList<>();
        for (Map.Entry<String, String> e : files.entrySet()) {
            names.add("{\"name\":" + str(e.getKey()) + ",\"bytes\":"
                    + e.getValue().getBytes(StandardCharsets.UTF_8).length + "}");
        }
        return "{\"ok\":true,\"name\":" + str(s.name()) + ",\"problems\":" + strs(s.problems())
                + ",\"report\":" + str(report.length() > REPORT_CAP ? report.substring(0, REPORT_CAP) : report)
                + ",\"reportTruncated\":" + (report.length() > REPORT_CAP)
                + ",\"session\":" + str(files.get("session.json"))
                + ",\"files\":[" + String.join(",", names) + "]}";
    }

    String export(List<String> lines, String dir) throws IOException {
        if (dir == null) {
            throw new IllegalArgumentException("export needs a directory");
        }
        ExperimentSpec s = ExperimentSpec.parse(lines);
        Map<String, byte[]> all = ExperimentLab.runWithAllExports(s);
        Path d = Path.of(dir);
        Files.createDirectories(d);
        List<String> names = new ArrayList<>();
        for (Map.Entry<String, byte[]> e : all.entrySet()) {
            Files.write(d.resolve(e.getKey()), e.getValue());
            names.add("{\"name\":" + str(e.getKey()) + ",\"bytes\":" + e.getValue().length + "}");
        }
        runs++;
        exportsWritten += all.size();
        lastName = s.name();
        return "{\"ok\":true,\"name\":" + str(s.name()) + ",\"dir\":" + str(d.toString())
                + ",\"files\":[" + String.join(",", names) + "]}";
    }

    // ── the arena ───────────────────────────────────────────────────────────

    String battle(String[] t) {
        if (t.length < 4) {
            throw new IllegalArgumentException("battle needs WORKLOAD OPS SEED");
        }
        StrategyBattleRunner.WorkloadType w;
        try {
            w = StrategyBattleRunner.WorkloadType.valueOf(t[1]);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("workload must be one of " + workloads() + ", not " + t[1]);
        }
        int ops = intArg(t, 2, 100, OPS_MAX);
        long seed = longArg(t, 3);
        List<StrategyBattleRunner.BattleResult> rs = StrategyBattleRunner.run(w, ops, seed);
        battles++;
        List<String> rows = new ArrayList<>();
        for (StrategyBattleRunner.BattleResult r : rs) {
            rows.add("{\"rank\":" + r.rank + ",\"strategy\":" + str(r.strategyName)
                    + ",\"timeMs\":" + String.format(Locale.ROOT, "%.3f", r.totalTimeNs / 1_000_000.0)
                    + ",\"avgDepth\":" + String.format(Locale.ROOT, "%.4f", r.avgSearchDepth)
                    + ",\"rotations\":" + r.rotations + ",\"finalSize\":" + r.finalSize
                    + ",\"searchHits\":" + r.searchHits + ",\"totalOps\":" + r.totalOps + "}");
        }
        return "{\"ok\":true,\"workload\":\"" + w + "\",\"ops\":" + ops + ",\"seed\":" + seed
                + ",\"results\":[" + String.join(",", rows) + "]}";
    }

    /**
     * The adaptive controller over a three-regime workload shaped like the arena session:
     * a mixed build-up, a hot-key read burst, then a heavy write flush — under the eager
     * policy the session recorder captured (no cooldown, 10% margin, one stability win), so
     * a morph can happen inside a bounded run. Deterministic per seed.
     */
    String adapt(int keys, int ops, long seed) {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        GenomeDrivenTreeController c = new GenomeDrivenTreeController(
                ctx, TreeGenome.redBlackGenome(),
                new MorphPolicy(0, 0.10, 1));
        Random rnd = new Random(seed);
        int third = Math.max(1, ops / 3);
        for (int i = 0; i < third; i++) {
            c.add(rnd.nextInt(keys));
        }
        int hot = rnd.nextInt(keys);
        for (int i = 0; i < third; i++) {
            c.contains(hot);
        }
        for (int i = 0; i < ops - 2 * third; i++) {
            c.add(keys + rnd.nextInt(keys));
        }
        adapts++;
        List<String> log = new ArrayList<>();
        for (GenomeDrivenTreeController.MorphEvent e : c.getMorphLog()) {
            log.add("{\"op\":" + e.opCountAtMorph + ",\"from\":\"" + e.from + "\",\"to\":\"" + e.to
                    + "\",\"pressure\":" + String.format(Locale.ROOT, "%.4f", e.morphPressure) + "}");
        }
        return "{\"ok\":true,\"keys\":" + keys + ",\"ops\":" + ops + ",\"seed\":" + seed
                + ",\"morphs\":" + c.getMorphCount() + ",\"lastStress\":"
                + String.format(Locale.ROOT, "%.4f", c.getLastStress())
                + ",\"strategy\":" + str(ctx.getStrategy().getClass().getSimpleName())
                + ",\"size\":" + ctx.getOrderedSet().size()
                + ",\"log\":[" + String.join(",", log) + "]}";
    }

    String fieldDay() {
        EcologyFieldDay.Session s = EcologyFieldDay.run();
        fieldDays++;
        String report = s.report();
        return "{\"ok\":true,\"report\":" + str(report.length() > REPORT_CAP ? report.substring(0, REPORT_CAP) : report)
                + ",\"reportTruncated\":" + (report.length() > REPORT_CAP) + ",\"session\":" + str(s.json()) + "}";
    }

    // ── emission ────────────────────────────────────────────────────────────

    static String workloads() {
        List<String> ws = new ArrayList<>();
        for (StrategyBattleRunner.WorkloadType w : StrategyBattleRunner.WorkloadType.values()) {
            ws.add(str(w.name()));
        }
        return "[" + String.join(",", ws) + "]";
    }

    static String strs(List<String> xs) {
        List<String> out = new ArrayList<>();
        for (String x : xs) {
            out.add(str(x));
        }
        return "[" + String.join(",", out) + "]";
    }

    static String refuse(String code, String why) {
        return "{\"ok\":false,\"code\":\"" + code + "\",\"why\":" + str(why) + "}";
    }

    static String str(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : String.valueOf(s).toCharArray()) {
            switch (c) {
                case '"':  b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        b.append(String.format(Locale.ROOT, "\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
            }
        }
        return b.append('"').toString();
    }

    static long longArg(String[] t, int i) {
        if (i >= t.length) {
            throw new IllegalArgumentException(t[0] + " needs an argument at position " + i);
        }
        return Long.parseLong(t[i]);
    }

    static int intArg(String[] t, int i, int lo, int hi) {
        int v = Math.toIntExact(longArg(t, i));
        if (v < lo || v > hi) {
            throw new IllegalArgumentException(t[0] + " argument " + i + " must be " + lo + ".." + hi + ", got " + v);
        }
        return v;
    }
}
