package io.github.richeyworks.csrbt.experimental.ecology;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;

/**
 * The classroom runner (ADR-019): execute an {@link ExperimentSpec} — a plain-text
 * experiment a student wrote — against a live tree, grade its pre-registered
 * hypotheses, run its theory models, and emit the same narrated report + lab-page
 * session every other station produces.
 *
 * <p>Run from the repo root:
 * {@code ./gradlew ecologyExperiment -Pspec=path/to/experiment.eco}
 * (default {@code docs/sample-experiment.eco}) — prints the report, writes
 * {@code docs/ecology-experiment-session.json}, drop it onto
 * {@code docs/ecology-lab.html}. Deterministic: same spec, same bytes.</p>
 *
 * <p>The grading is the pedagogy: hypotheses were written before the run, and each is
 * printed with its observed value and a CONFIRMED / REFUTED verdict — or UNGRADEABLE
 * when it names a phase that doesn't exist, because a hypothesis that can't be tested
 * is a spec bug, not a result. Malformed spec lines are likewise reported, never
 * guessed at.</p>
 */
public final class ExperimentLab {

    private ExperimentLab() {}

    public static void main(String[] args) throws IOException {
        Path in = Path.of(args.length > 0 ? args[0] : "docs/sample-experiment.eco");
        Path out = Path.of(args.length > 1 ? args[1] : "docs/ecology-experiment-session.json");
        Path exportDir = Path.of(args.length > 2 ? args[2] : "docs/experiment-out");
        ExperimentSpec spec = ExperimentSpec.parse(Files.readAllLines(in));
        Map<String, String> files = runWithExports(spec);
        System.out.println(files.get("report.txt"));
        Files.writeString(out, files.get("session.json"));
        Files.createDirectories(exportDir);
        for (Map.Entry<String, String> f : files.entrySet()) {
            Files.writeString(exportDir.resolve(f.getKey()), f.getValue());
        }
        System.out.println("session written → " + out + "  (drop it onto docs/ecology-lab.html)");
        System.out.println("export bundle  → " + exportDir
                + "  (CSVs open in Excel/Sheets; report.html prints to PDF)");
    }

    /**
     * Run a spec and produce the full export bundle: {@code report.txt} (the narrated
     * report), {@code session.json} (the lab page's food), one CSV per result family
     * (phases, hypotheses, models, model series in long format, crosses, punnett
     * squares, drift windows — each opens directly in Excel, Sheets, or R), and
     * {@code report.html}, a self-contained printable report for handing in or
     * printing to PDF/slides. Deterministic: same spec, same bytes, every file.
     */
    public static Map<String, String> runWithExports(ExperimentSpec spec) {
        Map<String, StringBuilder> exports = new LinkedHashMap<>();
        EcologyFieldDay.Session session = run(spec, exports);
        Map<String, String> out = new LinkedHashMap<>();
        out.put("report.txt", session.report());
        out.put("session.json", session.json());
        for (Map.Entry<String, StringBuilder> e : exports.entrySet()) {
            out.put(e.getKey(), e.getValue().toString());
        }
        out.put("report.html", ExperimentExport.html(spec, session, out));
        return out;
    }

    /** Execute a spec; returns the narrated report and the lab-page session JSON. */
    public static EcologyFieldDay.Session run(ExperimentSpec spec) {
        return run(spec, null);
    }

    private static EcologyFieldDay.Session run(ExperimentSpec spec,
                                               Map<String, StringBuilder> exports) {
        StringBuilder report = new StringBuilder();
        report.append("🧪 ECOLOGY EXPERIMENT — ").append(spec.name()).append('\n');
        report.append(String.format(Locale.ROOT,
                "   %d keys, seed %d, window %d ops, %d phase(s), %d model(s), %d hypothesis(es)%n",
                spec.keys(), spec.seed(), spec.window(), spec.phases().size(),
                spec.models().size(), spec.expectations().size()));
        if (!spec.datasets().isEmpty() || !spec.notes().isEmpty() || !spec.trees().isEmpty()) {
            report.append(String.format(Locale.ROOT,
                    "   entered: %d dataset(s), %d note(s), %d tree(s)%n",
                    spec.datasets().size(), spec.notes().size(), spec.trees().size()));
        }
        TheoreticalModels.Environment env = spec.environment();
        if (!env.equals(TheoreticalModels.Environment.NEUTRAL)) {
            report.append(String.format(Locale.ROOT,
                    "   environment: area=%.2f temperature=%.2f wind=%.2f distance=%.2f%n",
                    env.area(), env.temperature(), env.wind(), env.distance()));
        }
        for (String problem : spec.problems()) {
            report.append("   ⚠ spec: ").append(problem).append('\n');
        }
        report.append('\n');

        // ── Simulation: one seeded stream through a live tree ─────────────────
        TreeContext tree = new TreeContext(new RedBlackStrategy<>());
        EcologyRecorder global = new EcologyRecorder(spec.window(), 64);
        Map<String, Map<Integer, Long>> phaseAbundance = new LinkedHashMap<>();
        Random rng = new Random(spec.seed());
        List<Integer> alive = new ArrayList<>();
        int nextKey = spec.keys();
        for (int k = 0; k < spec.keys(); k++) {
            tree.add(k);
            global.recordAdd(k);
            alive.add(k);
        }

        for (ExperimentSpec.Phase phase : spec.phases()) {
            EcologyRecorder local = new EcologyRecorder(spec.window(), 64);
            for (int i = 0; i < phase.ops(); i++) {
                switch (phase.kind()) {
                    case UNIFORM -> {
                        int k = rng.nextInt(spec.keys());
                        tree.contains(k);
                        global.recordSearch(k, 1);
                        local.recordSearch(k, 1);
                    }
                    case HOT -> {
                        int hotSet = Math.min(phase.hotSetSize(), spec.keys());
                        int k = rng.nextInt(100) < phase.hotSharePct()
                                ? rng.nextInt(hotSet) : rng.nextInt(spec.keys());
                        tree.contains(k);
                        global.recordSearch(k, 1);
                        local.recordSearch(k, 1);
                    }
                    case CHURN -> {
                        boolean doAdd = alive.isEmpty() || rng.nextInt(100) < phase.addPct();
                        if (doAdd) {
                            int k = nextKey++;
                            tree.add(k);
                            global.recordAdd(k);
                            local.recordAdd(k);
                            alive.add(k);
                        } else {
                            int k = alive.remove(rng.nextInt(alive.size()));
                            tree.remove(k);
                            global.recordRemove(k, 0);
                            local.recordRemove(k, 0);
                        }
                    }
                }
            }
            phaseAbundance.put(phase.name(), local.cumulativeAbundance());
            if (exports != null) {
                Map<Integer, Long> a = local.cumulativeAbundance();
                ExperimentExport.row(exports, "phases.csv",
                        "phase,kind,ops,richness,touches,shannon,evenness,hill1,chao1,bestFit",
                        phase.name(), phase.kind().name().toLowerCase(Locale.ROOT),
                        String.valueOf(phase.ops()),
                        String.valueOf(CommunityMetrics.richness(a)),
                        String.valueOf(CommunityMetrics.total(a)),
                        String.format(Locale.ROOT, "%.6f", CommunityMetrics.shannon(a)),
                        String.format(Locale.ROOT, "%.6f", CommunityMetrics.pielouEvenness(a)),
                        String.format(Locale.ROOT, "%.6f", CommunityMetrics.hillNumber(a, 1)),
                        String.format(Locale.ROOT, "%.6f", CommunityMetrics.chao1(a)),
                        CommunityMetrics.bestFit(a).best().name());
            }
            report.append(FieldReport.communitySection(
                    "PHASE · " + phase.name() + " (" + phase.kind().name().toLowerCase(Locale.ROOT)
                            + ", " + phase.ops() + " ops)", local.cumulativeAbundance()));
        }
        // Cross-phase readings, consecutive pairs.
        List<String> phaseNames = new ArrayList<>(phaseAbundance.keySet());
        for (int i = 0; i + 1 < phaseNames.size(); i++) {
            Map<Integer, Long> a = phaseAbundance.get(phaseNames.get(i));
            Map<Integer, Long> b = phaseAbundance.get(phaseNames.get(i + 1));
            double bc = BetaDiversity.brayCurtis(a, b);
            double ov = BetaDiversity.pianka(a, b);
            report.append(String.format(Locale.ROOT,
                    "  %s → %s: Bray–Curtis %.2f (%s); Pianka %.2f (%s).%n",
                    phaseNames.get(i), phaseNames.get(i + 1),
                    bc, FieldReport.turnoverReading(bc), ov, FieldReport.overlapReading(ov)));
        }
        report.append('\n');

        // ── Entered field data (ADR-020): same instruments, the student's numbers ─
        for (ExperimentSpec.Dataset d : spec.datasets()) {
            report.append(FieldReport.communitySection(
                    "ENTERED DATA · " + d.name() + " (" + d.counts().size() + " kinds, "
                            + CommunityMetrics.total(d.counts()) + " records)", d.counts()));
            if (exports != null) {
                for (Map.Entry<String, Long> e : d.counts().entrySet()) {
                    ExperimentExport.row(exports, "data.csv", "dataset,name,count",
                            d.name(), e.getKey(), String.valueOf(e.getValue()));
                }
            }
        }
        for (int i = 0; i + 1 < spec.datasets().size(); i++) {
            ExperimentSpec.Dataset a = spec.datasets().get(i), b = spec.datasets().get(i + 1);
            var pa = BetaDiversity.presence(a.counts());
            var pb = BetaDiversity.presence(b.counts());
            var shared = new java.util.HashSet<>(pa);
            shared.retainAll(pb);
            report.append(String.format(Locale.ROOT,
                    "  %s ↔ %s: Jaccard %.2f, Sørensen %.2f — share %d of %d kinds; Bray–Curtis %.2f (%s).%n",
                    a.name(), b.name(), BetaDiversity.jaccard(pa, pb),
                    BetaDiversity.sorensen(pa, pb), shared.size(),
                    pa.size() + pb.size() - shared.size(),
                    BetaDiversity.brayCurtis(a.counts(), b.counts()),
                    FieldReport.turnoverReading(BetaDiversity.brayCurtis(a.counts(), b.counts()))));
        }
        if (!spec.datasets().isEmpty()) report.append('\n');

        // ── JSON assembly (lab-page schema) ───────────────────────────────────
        StringBuilder json = new StringBuilder("{\n");
        boolean[] first = { true };
        appendMeadowPhases(json, first, phaseAbundance);

        List<Map<Integer, Long>> windows = global.closedWindows();
        if (windows.size() >= 3) {
            double[] bray = new double[windows.size() - 1];
            for (int i = 1; i < windows.size(); i++) {
                bray[i - 1] = BetaDiversity.brayCurtis(windows.get(i - 1), windows.get(i));
            }
            // The recorder retains only its most recent windows and evicts the rest, so a
            // position in that list is NOT its window number in the run. Labelling the
            // retained list from 1 made end-of-run drift read as opening drift (audit
            // 2026-08-17 finding 28): with window 50 and a 5000-op phase, 100 windows
            // close, 36 are dropped, and row "1->2" was really windows 37→38.
            long dropped = global.evictedWindowCount();
            if (dropped > 0) {
                report.append(String.format(Locale.ROOT,
                        "  Drift: %d windows of %d ops closed, the most recent %d kept — "
                        + "windows 1–%d were dropped, so this series starts at window %d.%n%n",
                        global.closedWindowCount(), spec.window(), windows.size(),
                        dropped, dropped + 1));
            }
            if (exports != null) {
                for (int i = 0; i < bray.length; i++) {
                    long from = dropped + i + 1;        // absolute window number, 1-based
                    ExperimentExport.row(exports, "drift.csv", "transition,brayCurtis",
                            from + "->" + (from + 1),
                            String.format(Locale.ROOT, "%.6f", bray[i]));
                }
            }
            sep(json, first);
            json.append("  \"drift\": { \"windowOps\": ").append(spec.window()).append(", \"bray\": [");
            for (int i = 0; i < bray.length; i++) {
                if (i > 0) json.append(',');
                json.append(String.format(Locale.ROOT, "%.4f", bray[i]));
            }
            json.append("] }");
        }

        LifeTable census = null;
        if (global.lifespans().size() >= 2) {
            census = LifeTable.fromLifespans(global.lifespans(),
                    Math.min(6, Math.max(3, global.lifespans().size() / 4)));
            report.append(FieldReport.demographySection("THE CENSUS — lifespans in this experiment", census));
            report.append('\n');
            sep(json, first);
            json.append("  \"demography\": {");
            WorkloadTrace.appendLifeTable(json, census);
            json.append(" }");
        }

        // ── Entered data: lab-page card ───────────────────────────────────────
        if (!spec.datasets().isEmpty()) {
            sep(json, first);
            json.append("  \"entered\": [");
            for (int d = 0; d < spec.datasets().size(); d++) {
                if (d > 0) json.append(',');
                ExperimentSpec.Dataset ds = spec.datasets().get(d);
                Map<String, Long> a = ds.counts();
                json.append("{ \"name\": \"").append(WorkloadTrace.escapeJson(ds.name())).append('"');
                json.append(", \"richness\": ").append(CommunityMetrics.richness(a));
                json.append(", \"total\": ").append(CommunityMetrics.total(a));
                json.append(String.format(Locale.ROOT, ", \"shannon\": %.6f", CommunityMetrics.shannon(a)));
                json.append(String.format(Locale.ROOT, ", \"evenness\": %.6f", CommunityMetrics.pielouEvenness(a)));
                json.append(String.format(Locale.ROOT, ", \"chao1\": %.6f", CommunityMetrics.chao1(a)));
                List<Map.Entry<String, Long>> sorted = new ArrayList<>(a.entrySet());
                sorted.sort(Map.Entry.<String, Long>comparingByValue().reversed()
                        .thenComparing(Map.Entry.comparingByKey()));
                json.append(", \"labels\": [");
                for (int i = 0; i < Math.min(30, sorted.size()); i++) {
                    if (i > 0) json.append(',');
                    json.append('"').append(WorkloadTrace.escapeJson(sorted.get(i).getKey())).append('"');
                }
                json.append("], \"counts\": [");
                for (int i = 0; i < Math.min(30, sorted.size()); i++) {
                    if (i > 0) json.append(',');
                    json.append(sorted.get(i).getValue());
                }
                json.append("] }");
            }
            json.append("]");
        }

        // ── Field notebook ────────────────────────────────────────────────────
        if (!spec.notes().isEmpty()) {
            report.append("── FIELD NOTEBOOK ──\n");
            sep(json, first);
            json.append("  \"notes\": [");
            for (int i = 0; i < spec.notes().size(); i++) {
                ExperimentSpec.Note n = spec.notes().get(i);
                report.append("  ").append(n.about() == null ? "•" : "[" + n.about() + "]")
                      .append(' ').append(n.text()).append('\n');
                if (exports != null) {
                    ExperimentExport.row(exports, "notes.csv", "about,note",
                            n.about() == null ? "" : n.about(), n.text());
                }
                if (i > 0) json.append(',');
                json.append("{ \"about\": ").append(n.about() == null
                        ? "null" : '"' + WorkloadTrace.escapeJson(n.about()) + '"');
                json.append(", \"text\": \"").append(WorkloadTrace.escapeJson(n.text())).append("\" }");
            }
            json.append("]");
            report.append('\n');
        }

        // ── Phylogenies ───────────────────────────────────────────────────────
        if (!spec.trees().isEmpty()) {
            report.append("── TREE THINKING — phylogenies in this experiment ──\n");
            sep(json, first);
            json.append("  \"trees\": [");
            for (int i = 0; i < spec.trees().size(); i++) {
                ExperimentSpec.Tree t = spec.trees().get(i);
                report.append(String.format(Locale.ROOT, "  %s — %d taxa, depth %d:%n",
                        t.label(), t.tree().leaves().size(), t.tree().depth()));
                for (String line : t.tree().ascii().split("\n")) {
                    report.append("    ").append(line).append('\n');
                }
                if (exports != null) {
                    ExperimentExport.row(exports, "trees.csv", "label,taxa,depth,newick",
                            t.label(), String.valueOf(t.tree().leaves().size()),
                            String.valueOf(t.tree().depth()), t.tree().newick());
                }
                if (i > 0) json.append(',');
                json.append("{ \"label\": \"").append(WorkloadTrace.escapeJson(t.label()))
                    .append("\", \"root\": ").append(t.tree().json()).append(" }");
            }
            json.append("]");
            report.append('\n');
        }

        // ── Theory bench ──────────────────────────────────────────────────────
        if (!spec.models().isEmpty()) {
            report.append("── THEORY BENCH ──\n");
            sep(json, first);
            json.append("  \"models\": [");
            for (int m = 0; m < spec.models().size(); m++) {
                if (m > 0) json.append(',');
                appendModel(report, json, spec.models().get(m), env, exports);
            }
            json.append("]");
            report.append('\n');
        }

        // ── Punnett squares ───────────────────────────────────────────────────
        if (!spec.crosses().isEmpty()) {
            report.append("── PUNNETT SQUARES ──\n");
            sep(json, first);
            json.append("  \"crosses\": [");
            for (int c = 0; c < spec.crosses().size(); c++) {
                if (c > 0) json.append(',');
                appendCross(report, json, spec.crosses().get(c), exports);
            }
            json.append("]");
            report.append('\n');
        }

        // ── Hypotheses, graded ────────────────────────────────────────────────
        if (!spec.expectations().isEmpty()) {
            // One community table for grading: simulated phases (keys stringified) and
            // entered datasets, addressable by the same names the student wrote.
            Map<String, Map<String, Long>> communities = new LinkedHashMap<>();
            for (Map.Entry<String, Map<Integer, Long>> e : phaseAbundance.entrySet()) {
                Map<String, Long> s = new LinkedHashMap<>();
                for (Map.Entry<Integer, Long> k : e.getValue().entrySet()) {
                    s.put(String.valueOf(k.getKey()), k.getValue());
                }
                communities.put(e.getKey(), s);
            }
            java.util.Set<String> datasetNames = new java.util.HashSet<>();
            for (ExperimentSpec.Dataset d : spec.datasets()) {
                if (!communities.containsKey(d.name())) {   // name collisions already flagged
                    communities.put(d.name(), d.counts());
                    datasetNames.add(d.name());
                }
            }
            Ctx ctx = new Ctx(communities, phaseAbundance.keySet(), datasetNames, census);
            report.append("── HYPOTHESES (pre-registered, graded by the run) ──\n");
            sep(json, first);
            json.append("  \"hypotheses\": [");
            for (int i = 0; i < spec.expectations().size(); i++) {
                if (i > 0) json.append(',');
                gradeExpectation(report, json, spec.expectations().get(i), ctx, exports);
            }
            json.append("]");
        }

        json.append("\n}\n");
        return new EcologyFieldDay.Session(report.toString(), json.toString());
    }

    // ── Grading ───────────────────────────────────────────────────────────────

    /** Everything grading can see: communities by name, which are which, the census. */
    private record Ctx(Map<String, Map<String, Long>> communities,
                       java.util.Set<String> phaseNames,
                       java.util.Set<String> datasetNames,
                       LifeTable census) {}

    private static void gradeExpectation(StringBuilder report, StringBuilder json,
                                         ExperimentSpec.Expectation e, Ctx ctx,
                                         Map<String, StringBuilder> exports) {
        for (String arg : e.phaseArgs()) {
            if (!ctx.communities().containsKey(arg)) {
                ungradeable(report, json, exports, e, "unknown phase or dataset '" + arg + "'");
                return;
            }
        }
        if (e.phaseArgs().length == 2) {
            boolean p0 = ctx.phaseNames().contains(e.phaseArgs()[0]);
            boolean p1 = ctx.phaseNames().contains(e.phaseArgs()[1]);
            if (p0 != p1) {
                ungradeable(report, json, exports, e,
                        "cannot compare a simulated phase to an entered dataset — they share no species");
                return;
            }
        }
        if (e.metric().equals("survivorship") && ctx.census() == null) {
            ungradeable(report, json, exports, e,
                    "no census — the run had too few completed lifespans (add a churn phase)");
            return;
        }

        if (e.word() != null) {                            // qualitative: metric is word
            double value = qualitativeValue(e, ctx);
            String word = qualitativeWord(e, ctx, value);
            boolean pass = word.equals(e.word());
            String shown = Double.isNaN(value)
                    ? String.format(Locale.ROOT, "(observed \"%s\")", word)
                    : String.format(Locale.ROOT, "(observed %.4f → \"%s\")", value, word);
            report.append(String.format(Locale.ROOT, "  %s  %-40s %s%n",
                    pass ? "✅ CONFIRMED" : "❌ REFUTED  ", e.raw(), shown));
            if (exports != null) {
                ExperimentExport.row(exports, "hypotheses.csv", "hypothesis,observed,verdict",
                        e.raw(), word, pass ? "CONFIRMED" : "REFUTED");
            }
            json.append("{ \"expr\": \"").append(WorkloadTrace.escapeJson(e.raw()))
                .append("\", \"observed\": \"").append(word).append('"');
            if (!Double.isNaN(value)) {
                json.append(String.format(Locale.ROOT, ", \"value\": %.6f", value));
            }
            json.append(", \"verdict\": \"").append(pass ? "CONFIRMED" : "REFUTED").append("\" }");
            return;
        }

        double observed = metric(e, ctx.communities());
        boolean pass = switch (e.op()) {
            case "<" -> observed < e.value();
            case ">" -> observed > e.value();
            case "<=" -> observed <= e.value();
            default -> observed >= e.value();
        };
        report.append(String.format(Locale.ROOT, "  %s  %-40s (observed %.4f)%n",
                pass ? "✅ CONFIRMED" : "❌ REFUTED  ", e.raw(), observed));
        if (exports != null) {
            ExperimentExport.row(exports, "hypotheses.csv", "hypothesis,observed,verdict",
                    e.raw(), String.format(Locale.ROOT, "%.6f", observed),
                    pass ? "CONFIRMED" : "REFUTED");
        }
        json.append(String.format(Locale.ROOT,
                "{ \"expr\": \"%s\", \"observed\": %.6f, \"verdict\": \"%s\" }",
                WorkloadTrace.escapeJson(e.raw()), observed, pass ? "CONFIRMED" : "REFUTED"));
    }

    private static void ungradeable(StringBuilder report, StringBuilder json,
                                    Map<String, StringBuilder> exports,
                                    ExperimentSpec.Expectation e, String why) {
        report.append("  ⚠ UNGRADEABLE  ").append(e.raw())
              .append("   (").append(why).append(")\n");
        if (exports != null) {
            ExperimentExport.row(exports, "hypotheses.csv", "hypothesis,observed,verdict",
                    e.raw(), why, "UNGRADEABLE");
        }
        json.append(String.format(Locale.ROOT,
                "{ \"expr\": \"%s\", \"verdict\": \"UNGRADEABLE\" }",
                WorkloadTrace.escapeJson(e.raw())));
    }

    private static double metric(ExperimentSpec.Expectation e,
                                 Map<String, Map<String, Long>> communities) {
        Map<String, Long> a = communities.get(e.phaseArgs()[0]);
        return switch (e.metric()) {
            case "richness" -> CommunityMetrics.richness(a);
            case "shannon" -> CommunityMetrics.shannon(a);
            case "evenness" -> CommunityMetrics.pielouEvenness(a);
            case "hill1" -> CommunityMetrics.hillNumber(a, 1);
            case "chao1" -> CommunityMetrics.chao1(a);
            case "braycurtis" -> BetaDiversity.brayCurtis(a, communities.get(e.phaseArgs()[1]));
            case "jaccard" -> BetaDiversity.jaccard(BetaDiversity.presence(a),
                    BetaDiversity.presence(communities.get(e.phaseArgs()[1])));
            case "sorensen" -> BetaDiversity.sorensen(BetaDiversity.presence(a),
                    BetaDiversity.presence(communities.get(e.phaseArgs()[1])));
            default -> BetaDiversity.pianka(a, communities.get(e.phaseArgs()[1]));
        };
    }

    /** The underlying number for a qualitative metric (NaN when there isn't one). */
    private static double qualitativeValue(ExperimentSpec.Expectation e, Ctx ctx) {
        return switch (e.metric()) {
            case "evenness" -> CommunityMetrics.pielouEvenness(
                    ctx.communities().get(e.phaseArgs()[0]));
            case "turnover" -> BetaDiversity.brayCurtis(
                    ctx.communities().get(e.phaseArgs()[0]),
                    ctx.communities().get(e.phaseArgs()[1]));
            case "overlap" -> BetaDiversity.pianka(
                    ctx.communities().get(e.phaseArgs()[0]),
                    ctx.communities().get(e.phaseArgs()[1]));
            default -> Double.NaN;                         // fit, survivorship
        };
    }

    /** The observed band word — derived from the SAME thresholds the report narrates with. */
    private static String qualitativeWord(ExperimentSpec.Expectation e, Ctx ctx, double value) {
        return switch (e.metric()) {
            case "evenness" -> value >= FieldReport.EVEN_VERY ? "very-even"
                    : value >= FieldReport.EVEN_MODERATE ? "moderate"
                    : value >= FieldReport.EVEN_UNEVEN ? "uneven" : "dominated";
            case "turnover" -> value <= FieldReport.TURNOVER_LOW ? "low"
                    : value <= FieldReport.TURNOVER_MODERATE ? "moderate" : "major";
            case "overlap" -> value >= FieldReport.OVERLAP_HIGH ? "high"
                    : value >= FieldReport.OVERLAP_PARTIAL ? "partial" : "little";
            case "fit" -> switch (CommunityMetrics.bestFit(
                    ctx.communities().get(e.phaseArgs()[0])).best()) {
                case GEOMETRIC -> "geometric";
                case BROKEN_STICK -> "brokenstick";
                case UNIFORM -> "uniform";
            };
            default -> switch (ctx.census().survivorshipType()) {   // survivorship
                case TYPE_I -> "type1";
                case TYPE_II -> "type2";
                case TYPE_III -> "type3";
            };
        };
    }

    // ── Theory bench ──────────────────────────────────────────────────────────

    private static void appendModel(StringBuilder report, StringBuilder json,
                                    ExperimentSpec.Model m, TheoreticalModels.Environment env,
                                    Map<String, StringBuilder> exports) {
        double[] p = m.params();
        switch (m.kind()) {
            case "levins" -> {
                double c = env.colonization(p[0]), e = env.extinction(p[1]);
                double[][] traj = TheoreticalModels.levinsTrajectory(c, e, p[2], (int) p[3]);
                String label = String.format(Locale.ROOT, "Levins occupancy (c=%.3f, e=%.3f)", c, e);
                exportSeries(exports, label, "occupancy", traj);
                trajectoryModel(report, json, m.kind(), label, traj,
                        TheoreticalModels.levinsEquilibrium(c, e), "equilibrium p*");
            }
            case "logistic" -> {
                double r = env.growth(p[0]), k = env.capacity(p[1]);
                double[][] traj = TheoreticalModels.logisticTrajectory(r, k, p[2], (int) p[3]);
                String label = String.format(Locale.ROOT, "Logistic growth (r=%.3f, K=%.0f)", r, k);
                exportSeries(exports, label, "N", traj);
                trajectoryModel(report, json, m.kind(), label, traj, k, "carrying capacity K");
            }
            case "island" -> {
                double c = env.colonization(p[0]), e = env.extinction(p[1]);
                double[][] traj = TheoreticalModels.islandTrajectory(c, e, p[2], p[3], (int) p[4]);
                String label = String.format(Locale.ROOT,
                        "Island richness (c=%.3f, e=%.3f, pool=%.0f)", c, e, p[2]);
                exportSeries(exports, label, "S", traj);
                trajectoryModel(report, json, m.kind(), label, traj,
                        TheoreticalModels.islandEquilibrium(c, e, p[2]), "equilibrium S*");
            }
            case "exponential" -> {
                double r = env.growth(p[0]);
                double[][] traj = TheoreticalModels.exponentialTrajectory(r, p[1], (int) p[2]);
                String label = String.format(Locale.ROOT, "Exponential growth (r=%.3f)", r);
                exportSeries(exports, label, "N", traj);
                trajectoryModel(report, json, m.kind(), label, traj, Double.NaN, null);
            }
            case "competition" -> {
                double r1 = env.growth(p[0]), k1 = env.capacity(p[1]);
                double r2 = env.growth(p[2]), k2 = env.capacity(p[3]);
                double[][][] t = TheoreticalModels.competitionTrajectories(
                        r1, k1, r2, k2, p[4], p[5], p[6], p[7], (int) p[8]);
                String label = String.format(Locale.ROOT,
                        "Lotka–Volterra competition (K1=%.0f, K2=%.0f, α12=%.2f, α21=%.2f)",
                        k1, k2, p[4], p[5]);
                report.append("  ").append(label).append('\n');
                exportSeries(exports, label, "species 1", t[0]);
                exportSeries(exports, label, "species 2", t[1]);
                twoSeriesModel(json, m.kind(), label, "species 1", t[0], "species 2", t[1]);
            }
            case "predation" -> {
                double r = env.growth(p[0]);
                double[][][] t = TheoreticalModels.predationTrajectories(
                        r, p[1], p[2], p[3], p[4], p[5], (int) p[6]);
                String label = String.format(Locale.ROOT,
                        "Lotka–Volterra predation (r=%.2f, a=%.3f, m=%.2f)", r, p[1], p[3]);
                report.append("  ").append(label).append('\n');
                exportSeries(exports, label, "prey", t[0]);
                exportSeries(exports, label, "predator", t[1]);
                twoSeriesModel(json, m.kind(), label, "prey", t[0], "predator", t[1]);
            }
            case "markrecapture" -> {
                MarkRecapture.Estimate est = MarkRecapture.estimate(
                        (long) p[0], (long) p[1], (long) p[2]);
                String lp = Double.isInfinite(est.lincolnPetersen()) ? null
                        : String.format(Locale.ROOT, "%.1f", est.lincolnPetersen());
                report.append(String.format(Locale.ROOT,
                        "  Mark–recapture (M=%d, C=%d, R=%d): Lincoln–Petersen N̂=%s, "
                        + "Chapman N̂=%.1f (95%% CI %.1f–%.1f).%n",
                        est.marked(), est.caught(), est.recaptured(),
                        lp == null ? "undefined (R=0)" : lp,
                        est.chapman(), est.low95(), est.high95()));
                json.append(String.format(Locale.ROOT,
                        "{ \"kind\": \"markrecapture\", \"label\": \"Mark–recapture estimate\", "
                        + "\"stats\": { \"marked\": %d, \"caught\": %d, \"recaptured\": %d, "
                        + "\"lincolnPetersen\": %s, \"chapman\": %.4f, "
                        + "\"low95\": %.4f, \"high95\": %.4f } }",
                        est.marked(), est.caught(), est.recaptured(),
                        lp == null ? "null" : lp,
                        est.chapman(), est.low95(), est.high95()));
            }
            case "hardyweinberg" -> {
                PopulationGenetics.HardyWeinberg hw =
                        PopulationGenetics.hardyWeinberg((long) p[0], (long) p[1], (long) p[2]);
                report.append(String.format(Locale.ROOT,
                        "  Hardy–Weinberg: p=%.3f q=%.3f, χ²=%.3f (df 1, critical %.3f) → %s.%n",
                        hw.p(), hw.q(), hw.chiSquare(), PopulationGenetics.CHI_SQUARE_CRITICAL_DF1,
                        hw.inEquilibrium() ? "consistent with equilibrium"
                                           : "significantly out of equilibrium"));
                json.append(String.format(Locale.ROOT,
                        "{ \"kind\": \"hardyweinberg\", \"label\": \"Hardy–Weinberg test\", "
                        + "\"stats\": { \"p\": %.6f, \"q\": %.6f, \"chi2\": %.6f, "
                        + "\"inEquilibrium\": %b, \"observed\": [%d,%d,%d], "
                        + "\"expected\": [%.2f,%.2f,%.2f] } }",
                        hw.p(), hw.q(), hw.chiSquare(), hw.inEquilibrium(),
                        hw.aaHom(), hw.het(), hw.aHom(),
                        hw.expectedAA(), hw.expectedAa(), hw.expectedaa()));
            }
            default -> {   // eulerlotka: params are lx:mx pairs flattened
                int ages = p.length / 2;
                double[] lx = new double[ages], mx = new double[ages];
                for (int i = 0; i < ages; i++) { lx[i] = p[i * 2]; mx[i] = p[i * 2 + 1]; }
                PopulationGenetics.LifeTableRates rates = PopulationGenetics.eulerLotka(lx, mx);
                report.append(String.format(Locale.ROOT,
                        "  Euler–Lotka: R0=%.3f, T=%.2f, r≈%.4f (ln R0/T), r=%.4f (exact).%n",
                        rates.r0(), rates.generationTime(), rates.rApprox(), rates.rExact()));
                json.append(String.format(Locale.ROOT,
                        "{ \"kind\": \"eulerlotka\", \"label\": \"Euler–Lotka rates\", "
                        + "\"stats\": { \"R0\": %.6f, \"T\": %.6f, \"rApprox\": %.6f, "
                        + "\"rExact\": %.6f }, \"series\": [",
                        rates.r0(), rates.generationTime(), rates.rApprox(), rates.rExact()));
                for (int i = 0; i < ages; i++) {
                    if (i > 0) json.append(',');
                    json.append(String.format(Locale.ROOT, "[%d,%.4f]", i, lx[i] * mx[i]));
                }
                json.append("] }");
            }
        }
    }

    private static void exportSeries(Map<String, StringBuilder> exports, String label,
                                     String seriesName, double[][] series) {
        if (exports == null) return;
        for (double[] pt : series) {
            ExperimentExport.row(exports, "model-series.csv", "model,series,t,value",
                    label, seriesName,
                    String.format(Locale.ROOT, "%.0f", pt[0]),
                    String.format(Locale.ROOT, "%.6f", pt[1]));
        }
    }

    private static void trajectoryModel(StringBuilder report, StringBuilder json,
                                        String kind, String label, double[][] series,
                                        double equilibrium, String equilibriumName) {
        if (equilibriumName != null) {
            report.append(String.format(Locale.ROOT, "  %s: %s = %.3f, %d steps.%n",
                    label, equilibriumName, equilibrium, series.length - 1));
        } else {
            report.append(String.format(Locale.ROOT, "  %s: %d steps.%n", label, series.length - 1));
        }
        json.append("{ \"kind\": \"").append(kind).append("\", \"label\": \"")
            .append(WorkloadTrace.escapeJson(label)).append('"');
        if (equilibriumName != null) {
            json.append(String.format(Locale.ROOT, ", \"equilibrium\": %.6f", equilibrium));
        }
        appendSeries(json, ", \"series\": [", series);
        json.append(" }");
    }

    private static void twoSeriesModel(StringBuilder json, String kind, String label,
                                       String name1, double[][] s1, String name2, double[][] s2) {
        json.append("{ \"kind\": \"").append(kind).append("\", \"label\": \"")
            .append(WorkloadTrace.escapeJson(label)).append('"');
        json.append(", \"seriesLabel\": \"").append(name1).append('"');
        appendSeries(json, ", \"series\": [", s1);
        json.append(", \"series2Label\": \"").append(name2).append('"');
        appendSeries(json, ", \"series2\": [", s2);
        json.append(" }");
    }

    private static void appendSeries(StringBuilder json, String prefix, double[][] series) {
        json.append(prefix);
        for (int i = 0; i < series.length; i++) {
            if (i > 0) json.append(',');
            json.append(String.format(Locale.ROOT, "[%.0f,%.4f]", series[i][0], series[i][1]));
        }
        json.append(']');
    }

    private static void appendCross(StringBuilder report, StringBuilder json,
                                    ExperimentSpec.CrossSpec cs,
                                    Map<String, StringBuilder> exports) {
        MendelianGenetics.Cross cross = MendelianGenetics.cross(
                cs.parent1(), cs.parent2(), cs.dominance());
        report.append("  ").append(MendelianGenetics.describe(cross)).append('\n');
        report.append("    phenotypes: ").append(cross.phenotypeCounts()).append('\n');
        if (exports != null) {
            String crossLabel = cs.parent1() + " x " + cs.parent2();
            for (int r = 0; r < cross.square().length; r++) {
                for (int c2 = 0; c2 < cross.square()[r].length; c2++) {
                    ExperimentExport.row(exports, "punnett.csv",
                            "cross,rowGamete,colGamete,offspring",
                            crossLabel, cross.gametes1().get(r), cross.gametes2().get(c2),
                            cross.square()[r][c2]);
                }
            }
            for (var e : cross.phenotypeCounts().entrySet()) {
                ExperimentExport.row(exports, "crosses.csv",
                        "cross,phenotype,expectedRatioPart",
                        crossLabel, e.getKey(), String.valueOf(e.getValue()));
            }
        }
        MendelianGenetics.RatioFit fit = null;
        if (cs.observed() != null && cs.observed().length == cross.phenotypeCounts().size()) {
            fit = MendelianGenetics.ratioFit(cs.observed(), cross);
            report.append(String.format(Locale.ROOT,
                    "    observed vs expected: χ²=%.3f (df %d, critical %.3f) → %s.%n",
                    fit.chiSquare(), fit.df(), fit.critical(),
                    fit.consistent() ? "consistent with the Mendelian ratio"
                                     : "significantly off the Mendelian ratio"));
        } else if (cs.observed() != null) {
            report.append("    ⚠ observed counts ignored: expected ")
                  .append(cross.phenotypeCounts().size()).append(" classes, got ")
                  .append(cs.observed().length).append('\n');
        }
        json.append("{ \"label\": \"").append(WorkloadTrace.escapeJson(
                cs.parent1() + " × " + cs.parent2())).append('"');
        json.append(", \"dominance\": \"").append(cross.dominance()).append('"');
        json.append(", \"g1\": [");
        for (int i = 0; i < cross.gametes1().size(); i++) {
            if (i > 0) json.append(',');
            json.append('"').append(cross.gametes1().get(i)).append('"');
        }
        json.append("], \"g2\": [");
        for (int i = 0; i < cross.gametes2().size(); i++) {
            if (i > 0) json.append(',');
            json.append('"').append(cross.gametes2().get(i)).append('"');
        }
        json.append("], \"square\": [");
        for (int r = 0; r < cross.square().length; r++) {
            if (r > 0) json.append(',');
            json.append('[');
            for (int c = 0; c < cross.square()[r].length; c++) {
                if (c > 0) json.append(',');
                json.append('"').append(cross.square()[r][c]).append('"');
            }
            json.append(']');
        }
        json.append("], \"phenotypes\": {");
        boolean firstP = true;
        for (var e : cross.phenotypeCounts().entrySet()) {
            if (!firstP) json.append(',');
            firstP = false;
            json.append(" \"").append(e.getKey()).append("\": ").append(e.getValue());
        }
        json.append(" }");
        if (fit != null) {
            json.append(String.format(Locale.ROOT,
                    ", \"chi2\": %.6f, \"consistent\": %b", fit.chiSquare(), fit.consistent()));
        }
        json.append(" }");
    }

    // ── JSON helpers ──────────────────────────────────────────────────────────

    private static void sep(StringBuilder json, boolean[] first) {
        if (!first[0]) json.append(",\n");
        first[0] = false;
    }

    private static void appendMeadowPhases(StringBuilder json, boolean[] first,
                                           Map<String, Map<Integer, Long>> phases) {
        sep(json, first);
        json.append("  \"meadow\": { \"phases\": [");
        boolean firstPhase = true;
        for (Map.Entry<String, Map<Integer, Long>> e : phases.entrySet()) {
            if (!firstPhase) json.append(',');
            firstPhase = false;
            Map<Integer, Long> a = e.getValue();
            json.append("{ \"name\": \"").append(WorkloadTrace.escapeJson(e.getKey())).append('"');
            json.append(", \"richness\": ").append(CommunityMetrics.richness(a));
            json.append(", \"total\": ").append(CommunityMetrics.total(a));
            json.append(String.format(Locale.ROOT, ", \"shannon\": %.6f", CommunityMetrics.shannon(a)));
            json.append(String.format(Locale.ROOT, ", \"evenness\": %.6f", CommunityMetrics.pielouEvenness(a)));
            json.append(String.format(Locale.ROOT, ", \"hill1\": %.6f", CommunityMetrics.hillNumber(a, 1)));
            json.append(String.format(Locale.ROOT, ", \"chao1\": %.6f", CommunityMetrics.chao1(a)));
            json.append(", \"bestFit\": \"").append(CommunityMetrics.bestFit(a).best()).append('"');
            List<Long> ranks = CommunityMetrics.rankAbundance(a);
            json.append(", \"rank\": [");
            for (int i = 0; i < Math.min(40, ranks.size()); i++) {
                if (i > 0) json.append(',');
                json.append(ranks.get(i));
            }
            json.append(']');
            double[][] rc = CommunityMetrics.rarefactionCurve(a, 20);
            json.append(", \"rarefaction\": [");
            for (int i = 0; i < rc.length; i++) {
                if (i > 0) json.append(',');
                json.append(String.format(Locale.ROOT, "[%.0f,%.4f]", rc[i][0], rc[i][1]));
            }
            json.append("] }");
        }
        json.append("] }");
    }
}
