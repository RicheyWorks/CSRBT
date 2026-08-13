package io.github.richeyworks.csrbt.experimental.ecology;

import io.github.richeyworks.csrbt.BPlusTreeEngine;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.experimental.cache.CacheGenome;
import io.github.richeyworks.csrbt.experimental.cache.SegmentedLruCache;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * A field day across the whole ecosystem — one seeded, deterministic scenario that
 * walks every ecology instrument over every engine and narrates what it finds in plain
 * language ({@link FieldReport}), then writes the session as JSON for the interactive
 * lab page ({@code docs/ecology-lab.html}).
 *
 * <p>Run from the repo root: {@code ./gradlew ecologyFieldDay} — prints the narrated
 * report and writes {@code docs/ecology-lab-session.json}. Same seed, same bytes,
 * every run (the V5 standard applied to the demo).</p>
 *
 * <p>The five stations: the <b>meadow</b> (one tree, two grazing regimes — diversity
 * and niche overlap), its <b>census</b> (life table and logistic growth from churn),
 * the <b>archipelago</b> (ensemble members as patches — occupancy and Levins), the
 * <b>fossil record</b> (persistent snapshots — descent and turnover), the <b>survey
 * grid</b> (B+tree key layout — dispersion), and the <b>island</b> (cache —
 * immigration/extinction turnover at carrying capacity).</p>
 */
public final class EcologyFieldDay {

    /** The whole session: the narrated report and the JSON artifact, both deterministic. */
    public record Session(String report, String json) {}

    private EcologyFieldDay() {}

    public static void main(String[] args) throws IOException {
        Session session = run();
        System.out.println(session.report());
        Path out = Path.of(args.length > 0 ? args[0] : "docs/ecology-lab-session.json");
        Files.writeString(out, session.json());
        System.out.println("session written → " + out);
    }

    public static Session run() {
        StringBuilder report = new StringBuilder("🌿 ECOLOGY FIELD DAY — full-ecosystem survey\n\n");
        Json json = new Json();

        meadow(report, json);
        census(report, json);
        archipelago(report, json);
        fossils(report, json);
        surveyGrid(report, json);
        island(report, json);

        return new Session(report.toString(), json.close());
    }

    // ── Station 1: the meadow (diversity under two grazing regimes) ───────────

    private static void meadow(StringBuilder report, Json json) {
        TreeContext meadow = new TreeContext(new RedBlackStrategy<>());
        EcologyRecorder uniform = new EcologyRecorder(500, 16);
        EcologyRecorder hotPatch = new EcologyRecorder(500, 16);
        for (int k = 0; k < 100; k++) {
            meadow.add(k);
            uniform.recordAdd(k);
            hotPatch.recordAdd(k);
        }
        Random rng = new Random(7);
        for (int i = 0; i < 2000; i++) {
            int u = i % 100;                                   // even grazing
            meadow.contains(u);
            uniform.recordSearch(u, 1);
            int h = rng.nextInt(10) < 9 ? rng.nextInt(5) : rng.nextInt(100); // hot patch
            meadow.contains(h);
            hotPatch.recordSearch(h, 1);
        }
        Map<Integer, Long> a = uniform.cumulativeAbundance();
        Map<Integer, Long> b = hotPatch.cumulativeAbundance();
        double overlap = BetaDiversity.pianka(a, b);
        double turnover = BetaDiversity.brayCurtis(a, b);

        report.append(FieldReport.communitySection("STATION 1 · THE MEADOW — even grazing", a));
        report.append(FieldReport.communitySection("STATION 1 · THE MEADOW — hot-patch grazing", b));
        report.append(String.format(
                "  Between regimes: Pianka O = %.2f (%s); Bray–Curtis = %.2f (%s).%n%n",
                overlap, FieldReport.overlapReading(overlap),
                turnover, FieldReport.turnoverReading(turnover)));

        json.obj("meadow")
            .phases(new String[]{ "Even grazing", "Hot-patch grazing" }, List.of(a, b))
            .num("pianka", overlap).num("brayCurtis", turnover)
            .end();
    }

    // ── Station 2: the census (life table + logistic growth from churn) ───────

    private static void census(StringBuilder report, Json json) {
        TreeContext plot = new TreeContext(new RedBlackStrategy<>());
        EcologyRecorder census = new EcologyRecorder(64, 64);
        Random rng = new Random(11);
        List<Integer> alive = new ArrayList<>();
        int nextKey = 0;
        for (int op = 0; op < 2400; op++) {
            // Density-dependent colonization — the logistic assumption made literal:
            // birth probability falls from 95% (empty plot) to 50% (at capacity 140),
            // where births and deaths balance and the population plateaus.
            int pAdd = alive.isEmpty() ? 100 : (int) (95 - 45.0 * alive.size() / 140);
            boolean doAdd = rng.nextInt(100) < pAdd;
            if (doAdd && alive.size() < 140) {
                int k = nextKey++;
                plot.add(k);
                census.recordAdd(k);
                alive.add(k);
            } else if (!alive.isEmpty()) {
                int k = alive.remove(rng.nextInt(alive.size()));
                plot.remove(k);
                census.recordRemove(k);
            }
        }
        LifeTable table = LifeTable.fromLifespans(census.lifespans(), 6);
        // Fit the colonization phase (t ≤ 1200) — the standard practice: the logistic
        // model describes growth toward K; plateau-noise logits would swamp the ramp.
        List<long[]> ramp = new ArrayList<>();
        for (long[] s : census.populationSeries()) {
            if (s[0] <= 1200) ramp.add(s);
        }
        LogisticGrowth.Fit fit = LogisticGrowth.fit(ramp);

        report.append(FieldReport.demographySection("STATION 2 · THE CENSUS — who lives how long", table));
        report.append("  Growth: ").append(FieldReport.growthReading(fit)).append(".\n\n");

        json.obj("demography").lifeTable(table).end();
        json.obj("growth").series("series", census.populationSeries())
            .num("r", fit.r()).num("K", fit.carryingCapacity())
            .num("n0", fit.n0()).num("r2", fit.rSquared()).end();
    }

    // ── Station 3: the archipelago (ensemble members as patches) ──────────────

    private static void archipelago(StringBuilder report, Json json) {
        EnsembleOrderedSet<Integer> arch = EnsembleOrderedSet.<Integer>builder(Comparator.naturalOrder())
                .member(RedBlackStrategy::new)
                .member(AVLStrategy::new)
                .member(SplayStrategy::new)
                .build();
        for (int k = 0; k < 100; k++) arch.add(k);
        EnsembleCommunity<Integer> eco = new EnsembleCommunity<>(arch);

        EnsembleMember<Integer> patch = null;
        for (EnsembleMember<Integer> m : arch.members()) {
            if (m != arch.primary()) { patch = m; break; }
        }
        List<double[]> timeline = new ArrayList<>();
        for (int storm = 0; storm < 3; storm++) {
            arch.quarantine(patch);                            // a storm hits the patch
            eco.sample();
            timeline.add(new double[]{ eco.samples(), eco.occupancy() });
            arch.healFromPrimary(patch);                       // recolonized from the mainland
            eco.sample();
            timeline.add(new double[]{ eco.samples(), eco.occupancy() });
        }
        report.append(FieldReport.metapopulationSection(
                "STATION 3 · THE ARCHIPELAGO — patches, storms, recolonization", eco));
        report.append('\n');

        json.obj("archipelago").timeline("timeline", timeline, "survey", "occupancy")
            .num("extinctions", eco.extinctions()).num("recolonizations", eco.recolonizations())
            .num("levins", eco.levinsEquilibrium()).num("observed", eco.occupancy())
            .num("diversity", eco.strategyDiversity()).end();
        arch.close();
    }

    // ── Station 4: the fossil record (persistent snapshots as strata) ─────────

    private static void fossils(StringBuilder report, Json json) {
        PersistentTreeEngine<Integer> bed = PersistentTreeEngine.withNaturalOrder();
        SnapshotLineage<Integer> lineage = new SnapshotLineage<>();
        for (int k = 0; k < 40; k++) bed.add(k);
        lineage.capture(bed);
        int next = 1000;
        for (int g = 0; g < 5; g++) {                          // 20% replaced per stratum
            for (int i = 0; i < 8; i++) bed.remove(g * 8 + i);
            for (int i = 0; i < 8; i++) bed.add(next++);
            lineage.capture(bed);
        }
        report.append(FieldReport.lineageSection(
                "STATION 4 · THE FOSSIL RECORD — strata of the persistent engine", lineage));
        report.append('\n');

        json.obj("fossils").lineage(lineage).end();
    }

    // ── Station 5: the survey grid (key-space dispersion, engine-generic) ─────

    private static void surveyGrid(StringBuilder report, Json json) {
        BPlusTreeEngine<Integer> patchy = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
        for (int base : new int[]{ 0, 500, 990 }) {
            for (int i = 0; i < 30; i++) patchy.add(base + i);
        }
        BPlusTreeEngine<Integer> sown = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
        for (int i = 0; i < 100; i++) sown.add(i * 10);

        long[] patchyCounts = RangeQuadrats.countsOfInts(patchy.inOrder(), 20);
        long[] sownCounts   = RangeQuadrats.countsOfInts(sown.inOrder(), 20);
        report.append(FieldReport.spatialSection(
                "STATION 5 · THE SURVEY GRID — patchy planting (B+tree)", patchyCounts));
        report.append(pageLine(patchy));
        report.append(FieldReport.spatialSection(
                "STATION 5 · THE SURVEY GRID — evenly sown field (B+tree)", sownCounts));
        report.append(pageLine(sown));
        report.append('\n');

        json.obj("grid")
            .quadrats("clustered", patchyCounts).leaves("clusteredLeaves", patchy)
            .quadrats("spread", sownCounts).leaves("spreadLeaves", sown)
            .end();
    }

    /** The engine's own pages, narrated: leaf count, fill factor, reading (ADR-017). */
    private static String pageLine(BPlusTreeEngine<Integer> tree) {
        List<Integer> leaves = tree.leafKeyCounts();
        double fill = leaves.isEmpty() ? 0.0
                : (double) tree.size() / ((long) leaves.size() * tree.fanout());
        return String.format(java.util.Locale.ROOT,
                "  Pages: %d leaves at fanout %d, fill %.0f%% — %s.%n",
                leaves.size(), tree.fanout(), fill * 100,
                FieldReport.pageOccupancyReading(fill));
    }

    // ── Station 6: the island (cache at carrying capacity) ────────────────────

    private static void island(StringBuilder report, Json json) {
        // All-probation genome: the whole capacity is one open habitat, so the island
        // actually fills — and every arrival after that displaces a resident.
        SegmentedLruCache cache = new SegmentedLruCache(12, CacheGenome.of(0, 2));
        CacheIsland isle = new CacheIsland(cache, 12);
        for (int k = 0; k < 6; k++) isle.admit(k);             // probation habitat fills
        isle.sample();
        List<double[]> timeline = new ArrayList<>();
        int next = 100;
        for (int wave = 0; wave < 8; wave++) {                 // fresh arrivals, every wave
            for (int j = 0; j < 6; j++) isle.admit(next++);
            isle.sample();
            timeline.add(new double[]{ isle.samples(), isle.richness(), isle.lastIntervalTurnover() });
        }
        report.append(FieldReport.islandSection(
                "STATION 6 · THE ISLAND — the cache at carrying capacity", isle));

        List<Long> ages = new ArrayList<>();
        for (LifeTable.Lifespan ls : isle.residencies()) ages.add(ls.age());
        json.obj("island").num("capacity", isle.capacity())
            .timeline3("timeline", timeline, "survey", "richness", "turnover")
            .num("immigrations", isle.immigrations()).num("extinctions", isle.extinctions())
            .longs("residenceAges", ages).end();
    }

    // ── Minimal deterministic JSON writer (no dependencies) ───────────────────

    private static final class Json {
        private final StringBuilder sb = new StringBuilder("{\n");
        private boolean firstTop = true;
        private boolean firstField = true;

        Json obj(String name) {
            if (!firstTop) sb.append(",\n");
            firstTop = false;
            sb.append("  \"").append(name).append("\": {");
            firstField = true;
            return this;
        }

        private void sep() {
            if (!firstField) sb.append(',');
            firstField = false;
            sb.append(' ');
        }

        Json num(String key, double v) {
            if (!Double.isFinite(v)) {              // hardening pass 2: never emit NaN/Infinity
                throw new IllegalStateException("non-finite value for JSON key '" + key + "'");
            }
            sep();
            sb.append('"').append(key).append("\": ");
            if (v == Math.floor(v)) sb.append((long) v);
            else sb.append(String.format(java.util.Locale.ROOT, "%.6f", v));
            return this;
        }

        Json longs(String key, List<Long> values) {
            sep();
            sb.append('"').append(key).append("\": [");
            for (int i = 0; i < values.size(); i++) {
                if (i > 0) sb.append(',');
                sb.append(values.get(i));
            }
            sb.append(']');
            return this;
        }

        Json phases(String[] names, List<Map<Integer, Long>> maps) {
            sep();
            sb.append("\"phases\": [");
            for (int p = 0; p < maps.size(); p++) {
                if (p > 0) sb.append(',');
                Map<Integer, Long> abundance = maps.get(p);
                sb.append("{ \"name\": \"").append(names[p]).append('"');
                sb.append(", \"richness\": ").append(CommunityMetrics.richness(abundance));
                sb.append(", \"total\": ").append(CommunityMetrics.total(abundance));
                sb.append(String.format(java.util.Locale.ROOT, ", \"shannon\": %.6f", CommunityMetrics.shannon(abundance)));
                sb.append(String.format(java.util.Locale.ROOT, ", \"evenness\": %.6f", CommunityMetrics.pielouEvenness(abundance)));
                sb.append(String.format(java.util.Locale.ROOT, ", \"hill1\": %.6f", CommunityMetrics.hillNumber(abundance, 1)));
                sb.append(String.format(java.util.Locale.ROOT, ", \"chao1\": %.6f", CommunityMetrics.chao1(abundance)));
                sb.append(", \"bestFit\": \"").append(CommunityMetrics.bestFit(abundance).best()).append('"');
                List<Long> ranks = CommunityMetrics.rankAbundance(abundance);
                sb.append(", \"rank\": [");
                for (int i = 0; i < Math.min(40, ranks.size()); i++) {
                    if (i > 0) sb.append(',');
                    sb.append(ranks.get(i));
                }
                sb.append(']');
                double[][] rc = CommunityMetrics.rarefactionCurve(abundance, 20);
                sb.append(", \"rarefaction\": [");
                for (int i = 0; i < rc.length; i++) {
                    if (i > 0) sb.append(',');
                    sb.append(String.format(java.util.Locale.ROOT, "[%.0f,%.4f]", rc[i][0], rc[i][1]));
                }
                sb.append("] }");
            }
            sb.append(']');
            return this;
        }

        Json lifeTable(LifeTable t) {
            num("classWidth", t.classWidth());
            num("cohort", t.cohortSize());
            num("meanAge", t.lifeExpectancy());
            num("medianAge", t.medianAge());
            sep();
            sb.append("\"type\": \"").append(t.survivorshipType()).append('"');
            sep();
            sb.append("\"survivorship\": [");
            for (int x = 0; x < t.ageClasses(); x++) {
                if (x > 0) sb.append(',');
                sb.append(String.format(java.util.Locale.ROOT, "%.6f", t.survivorshipAt(x)));
            }
            sb.append(']');
            sep();
            sb.append("\"deaths\": [");
            for (int x = 0; x < t.ageClasses(); x++) {
                if (x > 0) sb.append(',');
                sb.append(t.deathsAt(x));
            }
            sb.append(']');
            return this;
        }

        Json lineage(SnapshotLineage<?> lin) {
            num("turnover", lin.turnoverPerGeneration());
            num("meanContent", lin.meanContentInheritance());
            num("meanStructural", lin.meanStructuralInheritance());
            sep();
            sb.append("\"generations\": [");
            List<? extends SnapshotLineage.Generation<?>> gens = lin.retained();
            for (int i = 0; i < gens.size(); i++) {
                if (i > 0) sb.append(',');
                SnapshotLineage.Generation<?> g = gens.get(i);
                sb.append("{ \"g\": ").append(g.index())
                  .append(", \"size\": ").append(g.size());
                if (i + 1 < gens.size()) {
                    sb.append(String.format(java.util.Locale.ROOT, ", \"inherited\": %.6f",
                            lin.inheritedFraction(g.index())))
                      .append(String.format(java.util.Locale.ROOT, ", \"structural\": %.6f",
                            lin.structuralInheritance(g.index())))
                      .append(", \"gains\": ").append(lin.gains(g.index()))
                      .append(", \"losses\": ").append(lin.losses(g.index()));
                }
                sb.append(" }");
            }
            sb.append(']');
            return this;
        }

        Json quadrats(String name, long[] counts) {
            sep();
            sb.append('"').append(name).append("\": { \"counts\": [");
            for (int i = 0; i < counts.length; i++) {
                if (i > 0) sb.append(',');
                sb.append(counts[i]);
            }
            sb.append(String.format(java.util.Locale.ROOT, "], \"dispersion\": %.6f, \"morisita\": %.6f }",
                    RangeQuadrats.indexOfDispersion(counts), RangeQuadrats.morisita(counts)));
            return this;
        }

        Json leaves(String key, BPlusTreeEngine<Integer> tree) {
            java.util.List<Integer> counts = tree.leafKeyCounts();
            double fill = counts.isEmpty() ? 0.0
                    : (double) tree.size() / ((long) counts.size() * tree.fanout());
            sep();
            sb.append('"').append(key).append("\": { \"fanout\": ").append(tree.fanout())
              .append(", \"counts\": [");
            for (int i = 0; i < counts.size(); i++) {
                if (i > 0) sb.append(',');
                sb.append(counts.get(i));
            }
            sb.append(String.format(java.util.Locale.ROOT, "], \"fill\": %.6f }", fill));
            return this;
        }

        Json timeline(String key, List<double[]> points, String f1, String f2) {
            sep();
            sb.append('"').append(key).append("\": [");
            for (int i = 0; i < points.size(); i++) {
                if (i > 0) sb.append(',');
                sb.append(String.format(java.util.Locale.ROOT, "{ \"%s\": %.0f, \"%s\": %.6f }",
                        f1, points.get(i)[0], f2, points.get(i)[1]));
            }
            sb.append(']');
            return this;
        }

        Json timeline3(String key, List<double[]> points, String f1, String f2, String f3) {
            sep();
            sb.append('"').append(key).append("\": [");
            for (int i = 0; i < points.size(); i++) {
                if (i > 0) sb.append(',');
                sb.append(String.format(java.util.Locale.ROOT, "{ \"%s\": %.0f, \"%s\": %.0f, \"%s\": %.6f }",
                        f1, points.get(i)[0], f2, points.get(i)[1], f3, points.get(i)[2]));
            }
            sb.append(']');
            return this;
        }

        Json series(String key, List<long[]> points) {
            sep();
            sb.append('"').append(key).append("\": [");
            for (int i = 0; i < points.size(); i++) {
                if (i > 0) sb.append(',');
                sb.append('[').append(points.get(i)[0]).append(',')
                  .append(points.get(i)[1]).append(']');
            }
            sb.append(']');
            return this;
        }

        Json end() {
            sb.append(" }");
            return this;
        }

        String close() {
            sb.append("\n}\n");
            return sb.toString();
        }
    }
}
