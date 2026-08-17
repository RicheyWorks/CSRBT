package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * The classroom experiment spec (ADR-019) — a plain-text format a student can write in
 * five minutes that defines a workload experiment, the theory models to run beside it,
 * and the <b>hypotheses</b> the run will grade. The point is the discipline, not the
 * syntax: predictions are written down before the run, and the runner prints
 * CONFIRMED or REFUTED next to each one — pre-registration as a built-in habit.
 *
 * <p>Format, one directive per line ({@code #} comments and blank lines ignored;
 * malformed lines are counted and reported, never guessed at):</p>
 *
 * <pre>
 * name: my first field experiment
 * keys: 100                          # key population (default 100)
 * seed: 42                           # RNG seed (default 42)
 * window: 250                        # recorder window in ops (default 250)
 *
 * phase: graze  uniform 2000         # &lt;name&gt; uniform &lt;ops&gt;
 * phase: bloom  hot 2000 5 90        # &lt;name&gt; hot &lt;ops&gt; &lt;hotSetSize&gt; &lt;hotShare%&gt;
 * phase: seasons churn 1500 60       # &lt;name&gt; churn &lt;ops&gt; &lt;addPercent&gt;
 *
 * factor: area 0.5                   # small pond: halves K, doubles extinction pressure
 * factor: wind 1.4                   # dispersal aid: scales colonization/immigration
 * factor: temperature 0.9            # rate multiplier on r and colonization
 * factor: distance 1.2               # isolation: immigration decays as e^(-distance)
 *
 * model: levins 0.4 0.1 0.05 40      # c e p0 steps
 * model: logistic 0.15 120 5 60      # r K n0 steps
 * model: island 0.3 0.1 100 0 40     # c e pool s0 steps
 * model: exponential 0.1 5 40        # r n0 steps
 * model: competition 0.4 100 0.4 80 0.7 1.1 5 5 80    # r1 K1 r2 K2 a12 a21 n1 n2 steps
 * model: predation 0.5 0.02 0.3 0.4 40 9 200          # r a b m n0 p0 steps
 * model: hardyweinberg 298 489 213   # observed genotype counts AA Aa aa
 * model: eulerlotka 1.0:0 0.8:1.5 0.5:2.0 0.2:1.0     # lx:mx per age
 *
 * model: markrecapture 120 90 30     # marked, caught, recaptured (the bean lab)
 *
 * cross: Rr x Rr observed 5474 1850  # Mendel's seed shape, graded vs 3:1
 * cross: Bb x Bb incomplete          # blue Andalusian chickens, 1:2:1
 * cross: RrPp x RrPp                 # chicken combs: walnut/rose/pea/single 9:3:3:1
 *
 * data: pondA cattail=18 duckweed=44 frogbit=3     # entered field counts (ADR-020)
 * data: coop  peck peck flap peck strut            # bare names tally, like clipboard marks
 * note: sampled both ponds after two dry weeks     # field-notebook entry
 * note(bloom): five keys took nearly all the traffic   # a note attached to a phase
 * tree: pondlife (Porifera,(Cnidaria,(Mollusca,Chordata)));   # Newick, drawn + counted
 *
 * expect: evenness(graze) &gt; 0.9
 * expect: hill1(bloom) &lt; 20
 * expect: brayCurtis(graze, bloom) &gt; 0.5
 * expect: jaccard(pondA, pondB) &lt; 0.5        # entered datasets grade like phases
 * expect: evenness(bloom) is uneven           # qualitative — graded against the bands
 * expect: survivorship is type3               # the census's Deevey type
 * </pre>
 *
 * <p><b>Numeric hypotheses</b> — {@code metric(args) op value}, operators
 * {@code < > <= >=}. Metrics: {@code richness}, {@code shannon}, {@code evenness},
 * {@code hill1}, {@code chao1} on one community; {@code brayCurtis}, {@code pianka},
 * {@code jaccard}, {@code sorensen} between two. A community is a phase or an entered
 * {@code data:} set — but not one of each: comparing a simulated phase to a field
 * dataset is graded UNGRADEABLE, because the numbers share no species.</p>
 *
 * <p><b>Qualitative hypotheses</b> — {@code metric(args) is word}, graded against the
 * same fixed {@link FieldReport} bands the narrated report uses:
 * {@code evenness(p) is very-even|moderate|uneven|dominated};
 * {@code turnover(p, q) is low|moderate|major} (Bray–Curtis bands);
 * {@code overlap(p, q) is high|partial|little} (Pianka bands);
 * {@code fit(p) is geometric|brokenstick|uniform} (rank-abundance best fit);
 * {@code survivorship is type1|type2|type3} (no parentheses — it reads the run's
 * census). Everything else belongs in Java against the instruments directly — this
 * format stays small on purpose.</p>
 */
public final class ExperimentSpec {

    public enum PhaseKind { UNIFORM, HOT, CHURN }

    /** One workload phase: a named stretch of ops with one access pattern. */
    public record Phase(String name, PhaseKind kind, int ops, int hotSetSize,
                        int hotSharePct, int addPct) {}

    /** One theory model to run beside the simulation. */
    public record Model(String kind, double[] params) {}

    /**
     * One pre-registered hypothesis. Numeric: {@code metric(args) op value} with
     * {@code word == null}. Qualitative: {@code metric(args) is word} with
     * {@code op == "is"} and {@code value == NaN}.
     */
    public record Expectation(String raw, String metric, String[] phaseArgs,
                              String op, double value, String word) {}

    /** One entered dataset ({@code data:} line): field counts, tallies, or a survey. */
    public record Dataset(String name, LinkedHashMap<String, Long> counts) {}

    /** One field-notebook entry; {@code about} is a phase/dataset name or null (general). */
    public record Note(String about, String text) {}

    /** One phylogeny ({@code tree:} line): label + parsed Newick. */
    public record Tree(String label, PhyloTree tree) {}

    /** One Mendelian cross: parents, dominance mode, optional observed offspring counts. */
    public record CrossSpec(String parent1, String parent2,
                            MendelianGenetics.Dominance dominance, long[] observed) {}

    private final String name;
    private final int keys;
    private final long seed;
    private final int window;
    private final List<Phase> phases;
    private final List<Model> models;
    private final List<CrossSpec> crosses;
    private final List<Expectation> expectations;
    private final List<Dataset> datasets;
    private final List<Note> notes;
    private final List<Tree> trees;
    private final List<String> problems;
    private final TheoreticalModels.Environment environment;

    private ExperimentSpec(String name, int keys, long seed, int window,
                           List<Phase> phases, List<Model> models, List<CrossSpec> crosses,
                           List<Expectation> expectations, List<Dataset> datasets,
                           List<Note> notes, List<Tree> trees, List<String> problems,
                           TheoreticalModels.Environment environment) {
        this.name = name;
        this.keys = keys;
        this.seed = seed;
        this.window = window;
        this.phases = phases;
        this.models = models;
        this.crosses = crosses;
        this.expectations = expectations;
        this.datasets = datasets;
        this.notes = notes;
        this.trees = trees;
        this.problems = problems;
        this.environment = environment;
    }

    public String name() { return name; }
    public int keys() { return keys; }
    public long seed() { return seed; }
    public int window() { return window; }
    public List<Phase> phases() { return phases; }
    public List<Model> models() { return models; }
    public List<CrossSpec> crosses() { return crosses; }
    public List<Expectation> expectations() { return expectations; }
    /** Entered field datasets, in file order. */
    public List<Dataset> datasets() { return datasets; }
    /** Field-notebook entries, in file order. */
    public List<Note> notes() { return notes; }
    /** Phylogenies, in file order. */
    public List<Tree> trees() { return trees; }
    /** Lines that could not be parsed, verbatim with their reason — reported, never guessed. */
    public List<String> problems() { return problems; }
    /** The abiotic environment built from {@code factor:} lines; NEUTRAL when none. */
    public TheoreticalModels.Environment environment() { return environment; }

    // ── Parsing ───────────────────────────────────────────────────────────────

    public static ExperimentSpec parse(List<String> lines) {
        String name = "unnamed experiment";
        int keys = 100, window = 250;
        long seed = 42;
        List<Phase> phases = new ArrayList<>();
        List<Model> models = new ArrayList<>();
        List<CrossSpec> crosses = new ArrayList<>();
        List<Expectation> expectations = new ArrayList<>();
        List<Dataset> datasets = new ArrayList<>();
        List<Note> notes = new ArrayList<>();
        List<Tree> trees = new ArrayList<>();
        List<String> problems = new ArrayList<>();
        double area = 1, temperature = 1, wind = 1, distance = 0;

        for (String raw : lines) {
            String line = stripComment(raw).trim();
            if (line.isEmpty()) continue;
            int colon = line.indexOf(':');
            if (colon < 0) { problems.add(raw.trim() + "  (no directive)"); continue; }
            String key = line.substring(0, colon).trim().toLowerCase(Locale.ROOT);
            String val = line.substring(colon + 1).trim();
            if (key.startsWith("note")) {                 // note: text  |  note(target): text
                String about = null;
                if (key.startsWith("note(") && key.endsWith(")")) {
                    // Extract the target from the ORIGINAL line, not the lowercased key:
                    // phase/dataset names are stored case-sensitively, so a lowercased
                    // target ("note(Bloom):" → "bloom") could never attach to phase
                    // "Bloom" — it drew a problem AND rendered detached as "[bloom]".
                    String origKey = line.substring(0, colon).trim();
                    about = origKey.substring(5, origKey.length() - 1).trim();
                } else if (!key.equals("note")) {
                    problems.add(raw.trim() + "  (unknown directive '" + key + "')");
                    continue;
                }
                if (val.isEmpty()) { problems.add(raw.trim() + "  (empty note)"); continue; }
                notes.add(new Note(about, val));
                continue;
            }
            try {
                switch (key) {
                    case "name" -> name = val;
                    case "keys" -> keys = parseBounded(val, 2, 1_000_000, "keys");
                    case "seed" -> seed = parseWholeNumber(val, "seed");
                    case "window" -> window = parseBounded(val, 16, 1_000_000, "window");
                    case "phase" -> phases.add(parsePhase(val));
                    case "model" -> models.add(parseModel(val));
                    case "cross" -> crosses.add(parseCross(val));
                    case "expect" -> expectations.add(parseExpect(val));
                    case "data" -> datasets.add(parseData(val, problems));
                    case "tree" -> trees.add(parseTree(val));
                    case "factor" -> {
                        String[] f = val.split("\\s+");
                        if (f.length != 2) throw new IllegalArgumentException("factor needs: <name> <value>");
                        double fv = Double.parseDouble(f[1]);
                        switch (f[0].toLowerCase(Locale.ROOT)) {
                            case "area" -> area = fv;
                            case "temperature" -> temperature = fv;
                            case "wind" -> wind = fv;
                            case "distance" -> distance = fv;
                            default -> throw new IllegalArgumentException(
                                    "unknown factor '" + f[0] + "' (area, temperature, wind, distance)");
                        }
                    }
                    default -> problems.add(raw.trim() + "  (unknown directive '" + key + "')");
                }
            } catch (RuntimeException bad) {
                problems.add(raw.trim() + "  (" + bad.getMessage() + ")");
            }
        }
        // Community names must be unique — expectations address them by name.
        for (int i = 0; i < phases.size(); i++) {
            for (int j = i + 1; j < phases.size(); j++) {
                if (phases.get(i).name().equals(phases.get(j).name())) {
                    problems.add("duplicate phase name '" + phases.get(i).name() + "'");
                }
            }
        }
        Set<String> phaseNames = new java.util.HashSet<>();
        for (Phase p : phases) phaseNames.add(p.name());
        Set<String> datasetNames = new java.util.HashSet<>();
        for (Dataset d : datasets) {
            if (phaseNames.contains(d.name())) {
                problems.add("dataset '" + d.name() + "' collides with a phase name");
            } else if (!datasetNames.add(d.name())) {
                problems.add("duplicate dataset name '" + d.name() + "'");
            }
        }
        // A note may target a phase or dataset; an unknown target is a spec bug.
        for (Note n : notes) {
            if (n.about() != null && !phaseNames.contains(n.about())
                    && !datasetNames.contains(n.about())) {
                problems.add("note targets unknown phase/dataset '" + n.about() + "'");
            }
        }
        TheoreticalModels.Environment env;
        try {
            env = new TheoreticalModels.Environment(area, temperature, wind, distance);
        } catch (IllegalArgumentException bad) {
            problems.add("factors: " + bad.getMessage() + " — using neutral environment");
            env = TheoreticalModels.Environment.NEUTRAL;
        }
        return new ExperimentSpec(name, keys, seed, window, phases, models, crosses,
                expectations, datasets, notes, trees, problems, env);
    }

    /** data: &lt;label&gt; &lt;name[=count]&gt; ... — entered counts, tallies, or surveys. */
    private static Dataset parseData(String val, List<String> problems) {
        String[] parts = val.split("\\s+", 2);
        if (parts.length < 2) {
            throw new IllegalArgumentException("data needs: <label> <name[=count]> ...");
        }
        if (parts[0].indexOf('=') >= 0) {
            throw new IllegalArgumentException("first token is the dataset label, not a count");
        }
        FieldData.Parsed parsed = FieldData.parseTokens(parts[1]);
        for (String p : parsed.problems()) problems.add("data " + parts[0] + ": " + p);
        if (parsed.counts().isEmpty()) {
            throw new IllegalArgumentException("dataset '" + parts[0] + "' has no valid counts");
        }
        return new Dataset(parts[0], parsed.counts());
    }

    /** tree: &lt;label&gt; &lt;newick&gt; — a phylogeny to draw, count, and export. */
    private static Tree parseTree(String val) {
        String[] parts = val.split("\\s+", 2);
        if (parts.length < 2) throw new IllegalArgumentException("tree needs: <label> <newick>");
        return new Tree(parts[0], PhyloTree.parse(parts[1]));
    }

    private static String stripComment(String line) {
        int hash = line.indexOf('#');
        return hash < 0 ? line : line.substring(0, hash);
    }

    private static int parseBounded(String v, int lo, int hi, String what) {
        long x = parseWholeNumber(v, what);
        if (x < lo || x > hi) throw new IllegalArgumentException(what + " out of range [" + lo + ", " + hi + "]");
        return (int) x;
    }

    /**
     * A whole number written by a student, with a message a student can act on (edge-case pass
     * 2026-08-17). {@code Long.parseLong}'s own text is {@code For input string: ""}, which is
     * what {@code keys:}, {@code seed:} and {@code window:} used to print into the report's
     * {@code ⚠ spec:} list — the one place in this layer that leaked a JDK exception message
     * instead of saying what was wrong with the line. Everything else here already reports in
     * plain English; this closes the exception.
     */
    private static long parseWholeNumber(String v, String what) {
        String t = v.trim();
        if (t.isEmpty()) throw new IllegalArgumentException(what + " needs a whole number");
        try {
            return Long.parseLong(t);
        } catch (NumberFormatException bad) {
            throw new IllegalArgumentException(
                    what + " must be a whole number, not '" + t + "'");
        }
    }

    private static Phase parsePhase(String val) {
        String[] p = val.split("\\s+");
        if (p.length < 3) throw new IllegalArgumentException("phase needs: <name> <kind> <ops> ...");
        String pname = p[0];
        int ops = parseBounded(p[2], 1, 10_000_000, "phase ops");
        return switch (p[1].toLowerCase(Locale.ROOT)) {
            case "uniform" -> new Phase(pname, PhaseKind.UNIFORM, ops, 0, 0, 0);
            case "hot" -> {
                if (p.length < 5) throw new IllegalArgumentException("hot needs: <ops> <hotSetSize> <hotShare%>");
                yield new Phase(pname, PhaseKind.HOT, ops,
                        parseBounded(p[3], 1, 1_000_000, "hotSetSize"),
                        parseBounded(p[4], 0, 100, "hotShare%"), 0);
            }
            case "churn" -> {
                if (p.length < 4) throw new IllegalArgumentException("churn needs: <ops> <addPercent>");
                yield new Phase(pname, PhaseKind.CHURN, ops, 0, 0,
                        parseBounded(p[3], 0, 100, "addPercent"));
            }
            default -> throw new IllegalArgumentException("unknown phase kind '" + p[1] + "'");
        };
    }

    private static Model parseModel(String val) {
        String[] p = val.split("\\s+");
        String kind = p[0].toLowerCase(Locale.ROOT);
        if (kind.equals("eulerlotka")) {          // variable-length lx:mx pairs, age = index
            if (p.length < 3) throw new IllegalArgumentException("eulerlotka needs >= 2 lx:mx pairs");
            double[] params = new double[(p.length - 1) * 2];
            for (int i = 1; i < p.length; i++) {
                String[] pair = p[i].split(":");
                if (pair.length != 2) throw new IllegalArgumentException("pairs are lx:mx, got '" + p[i] + "'");
                params[(i - 1) * 2] = Double.parseDouble(pair[0]);
                params[(i - 1) * 2 + 1] = Double.parseDouble(pair[1]);
            }
            // Validate the domain now so a bad schedule (e.g. R0 = 0) is a reported spec
            // problem, not a runtime crash that sinks the whole report — the same discipline
            // cross:/tree:/data: already follow (see parseCross).
            int ages = params.length / 2;
            double[] lx = new double[ages], mx = new double[ages];
            for (int i = 0; i < ages; i++) { lx[i] = params[i * 2]; mx[i] = params[i * 2 + 1]; }
            PopulationGenetics.eulerLotka(lx, mx);
            return new Model(kind, params);
        }
        int want = switch (kind) {
            case "levins" -> 4;          // c e p0 steps
            case "logistic" -> 4;        // r K n0 steps
            case "island" -> 5;          // c e pool s0 steps
            case "exponential" -> 3;     // r n0 steps
            case "competition" -> 9;     // r1 K1 r2 K2 a12 a21 n1 n2 steps
            case "predation" -> 7;       // r a b m n0 p0 steps
            case "hardyweinberg" -> 3;   // observed AA Aa aa
            case "markrecapture" -> 3;   // marked caught recaptured
            default -> throw new IllegalArgumentException("unknown model '" + p[0] + "'");
        };
        if (p.length != want + 1) {
            throw new IllegalArgumentException("model " + p[0] + " needs " + want + " parameters");
        }
        double[] params = new double[want];
        for (int i = 0; i < want; i++) params[i] = Double.parseDouble(p[i + 1]);
        boolean hasSteps = !kind.equals("hardyweinberg") && !kind.equals("markrecapture");
        if (hasSteps && (params[want - 1] < 0 || params[want - 1] > 100_000)) {
            throw new IllegalArgumentException("steps out of range [0, 100000]");
        }
        // Validate the domain of the value-sensitive models now — a parseable line whose
        // numbers are out of range (markrecapture R > min(M,C), hardyweinberg negative
        // counts, a carrying capacity of zero) is a spec problem, reported like any other,
        // not a crash inside run() and not a NaN in the export (edge-case pass 2026-08-17:
        // `model: logistic 0.15 0 5 60` wrote the bare token NaN into session.json, which
        // is invalid JSON, so the lab page could not load the session at all).
        //
        // The trajectory models are probed over their REAL step count, not over a single point.
        // Whether a run leaves the range of a double is a property of how long it runs — `model:
        // exponential 0.7 1 1200` is finite for a thousand steps and Infinity after step 1014 —
        // so a one-point probe cannot see it, and an Infinity in a series is exactly as fatal to
        // session.json as the NaN this probe was built for (frontend verification 2026-08-17, J1).
        // The probe runs on the RAW parameters; `factor:` lines are applied later, in
        // ExperimentLab, so a factor-amplified overflow is caught there instead — same message,
        // reported into the report rather than the spec list.
        int steps = hasSteps ? (int) params[want - 1] : 0;
        switch (kind) {
            case "markrecapture" ->
                    MarkRecapture.estimate((long) params[0], (long) params[1], (long) params[2]);
            case "hardyweinberg" ->
                    PopulationGenetics.hardyWeinberg((long) params[0], (long) params[1], (long) params[2]);
            case "levins" ->
                    TheoreticalModels.levinsTrajectory(params[0], params[1], params[2], steps);
            case "logistic" ->
                    TheoreticalModels.logisticTrajectory(params[0], params[1], params[2], steps);
            case "island" ->
                    TheoreticalModels.islandTrajectory(params[0], params[1], params[2], params[3], steps);
            case "exponential" ->
                    TheoreticalModels.exponentialTrajectory(params[0], params[1], steps);
            case "competition" ->
                    TheoreticalModels.competitionTrajectories(params[0], params[1], params[2],
                            params[3], params[4], params[5], params[6], params[7], steps);
            case "predation" ->
                    TheoreticalModels.predationTrajectories(params[0], params[1], params[2],
                            params[3], params[4], params[5], steps);
            default -> { }
        }
        return new Model(kind, params);
    }

    /** cross: &lt;p1&gt; x &lt;p2&gt; [incomplete] [observed n1 n2 ...] */
    private static CrossSpec parseCross(String val) {
        String[] p = val.split("\\s+");
        if (p.length < 3 || !p[1].equalsIgnoreCase("x")) {
            throw new IllegalArgumentException("cross needs: <parent1> x <parent2> [incomplete] [observed n...]");
        }
        MendelianGenetics.Dominance dom = MendelianGenetics.Dominance.COMPLETE;
        long[] observed = null;
        int i = 3;
        if (i < p.length && p[i].equalsIgnoreCase("incomplete")) {
            dom = MendelianGenetics.Dominance.INCOMPLETE;
            i++;
        }
        if (i < p.length) {
            if (!p[i].equalsIgnoreCase("observed")) {
                throw new IllegalArgumentException("unexpected token '" + p[i] + "'");
            }
            observed = new long[p.length - i - 1];
            if (observed.length < 2) throw new IllegalArgumentException("observed needs >= 2 counts");
            for (int j = 0; j < observed.length; j++) {
                observed[j] = Long.parseLong(p[i + 1 + j]);
            }
        }
        // Validate parents now so a bad cross is a spec problem, not a runtime crash.
        MendelianGenetics.cross(p[0], p[2], dom);
        return new CrossSpec(p[0], p[2], dom, observed);
    }

    private static Expectation parseExpect(String val) {
        // Qualitative form: <metric>[(args)] is <word> — graded against the report's bands.
        int isAt = indexOfWord(val, " is ");
        if (isAt >= 0) return parseQualitative(val, isAt);

        // Numeric form: <metric>(<p>[, <q>]) <op> <number>
        int open = val.indexOf('('), close = val.indexOf(')');
        if (open < 0 || close < open) throw new IllegalArgumentException("expect needs metric(phase...)");
        String metric = val.substring(0, open).trim().toLowerCase(Locale.ROOT);
        String[] args = val.substring(open + 1, close).split(",");
        for (int i = 0; i < args.length; i++) {
            args[i] = args[i].trim();
            // "richness() > 1" used to slip through: "".split(",") yields one empty
            // arg, satisfying wantArgs == 1, and only degraded to UNGRADEABLE at run
            // time. Malformed hypotheses are parse-time spec problems (ADR-020).
            if (args[i].isEmpty()) {
                throw new IllegalArgumentException("expect has a blank phase/dataset name");
            }
        }
        String rest = val.substring(close + 1).trim();
        String[] tail = rest.split("\\s+");
        if (tail.length != 2) throw new IllegalArgumentException("expect needs: metric(...) <op> <value>");
        String op = tail[0];
        if (!op.equals("<") && !op.equals(">") && !op.equals("<=") && !op.equals(">=")) {
            throw new IllegalArgumentException("operator must be < > <= >= (or 'is <word>')");
        }
        int wantArgs = switch (metric) {
            case "richness", "shannon", "evenness", "hill1", "chao1" -> 1;
            case "braycurtis", "pianka", "jaccard", "sorensen" -> 2;
            default -> throw new IllegalArgumentException("unknown metric '" + metric + "'");
        };
        if (args.length != wantArgs) {
            throw new IllegalArgumentException(metric + " takes " + wantArgs + " community name(s)");
        }
        return new Expectation(val, metric, args, op, Double.parseDouble(tail[1]), null);
    }

    /** The words each qualitative metric accepts — exactly the report's bands. */
    static List<String> wordsFor(String metric) {
        return switch (metric) {
            case "evenness" -> List.of("very-even", "moderate", "uneven", "dominated");
            case "turnover" -> List.of("low", "moderate", "major");
            case "overlap" -> List.of("high", "partial", "little");
            case "fit" -> List.of("geometric", "brokenstick", "uniform");
            case "survivorship" -> List.of("type1", "type2", "type3");
            default -> List.of();
        };
    }

    private static Expectation parseQualitative(String val, int isAt) {
        String left = val.substring(0, isAt).trim();
        String word = val.substring(isAt + 4).trim().toLowerCase(Locale.ROOT);
        String metric;
        String[] args;
        int open = left.indexOf('(');
        if (open >= 0) {
            int close = left.indexOf(')');
            if (close < open) throw new IllegalArgumentException("unbalanced parentheses");
            metric = left.substring(0, open).trim().toLowerCase(Locale.ROOT);
            args = left.substring(open + 1, close).split(",");
            for (int i = 0; i < args.length; i++) args[i] = args[i].trim();
        } else {
            metric = left.toLowerCase(Locale.ROOT);
            args = new String[0];
        }
        int wantArgs = switch (metric) {
            case "evenness", "fit" -> 1;
            case "turnover", "overlap" -> 2;
            case "survivorship" -> 0;
            default -> throw new IllegalArgumentException(
                    "unknown qualitative metric '" + metric
                    + "' (evenness, turnover, overlap, fit, survivorship)");
        };
        if (args.length != wantArgs) {
            throw new IllegalArgumentException(metric + " takes " + wantArgs + " community name(s)");
        }
        List<String> words = wordsFor(metric);
        if (!words.contains(word)) {
            throw new IllegalArgumentException(
                    "'" + word + "' is not a " + metric + " band — one of " + words);
        }
        return new Expectation(val, metric, args, "is", Double.NaN, word);
    }

    private static int indexOfWord(String s, String word) {
        int i = s.indexOf(word);
        // " is " inside parentheses would be part of a community name — reject that case.
        if (i < 0) return -1;
        int open = s.indexOf('('), close = s.indexOf(')');
        return (open >= 0 && close > open && i > open && i < close) ? -1 : i;
    }
}
