package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.BetaDiversity;
import io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics;
import io.github.richeyworks.csrbt.experimental.ecology.EcologyRecorder;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;
import io.github.richeyworks.csrbt.experimental.ecology.FieldData;
import io.github.richeyworks.csrbt.experimental.ecology.LifeTable;
import io.github.richeyworks.csrbt.experimental.ecology.MarkRecapture;
import io.github.richeyworks.csrbt.experimental.ecology.PhyloTree;
import io.github.richeyworks.csrbt.experimental.ecology.PopulationGenetics;
import io.github.richeyworks.csrbt.experimental.ecology.TheoreticalModels;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Edge-case hardening pass, 2026-08-17 — the ecology layer's degenerate ends.
 *
 * <p>Biology students type into {@code .eco} files, so the house rule here is stricter than
 * anywhere else in the repo: malformed input is <em>reported</em>, in plain English, never guessed
 * at, and never silently propagated into an export. This class walks the degenerate ends of that
 * promise: an empty file, a file that is only comments, every directive with no argument at all, a
 * zero-op phase, a one-species community, a one-taxon Newick tree, and the division-by-zero shape
 * of every metric.</p>
 *
 * <p>Fixes guarded here:</p>
 * <ul>
 *   <li><b>EC-E1</b> {@code PhyloTree} accepted a non-finite branch length — {@code A:1e400}
 *       overflows to {@code Infinity} and {@code json()} then emitted the bare token
 *       {@code Infinity}, which is not valid JSON, so one over-large number in a
 *       {@code tree:} line made the whole {@code session.json} unreadable to the lab page. A
 *       literal {@code NaN} was silently dropped instead, because NaN is the class's own
 *       "no branch length" marker.</li>
 *   <li><b>EC-E2</b> a carrying capacity of zero ({@code model: logistic r 0 n0 steps},
 *       {@code model: competition …}) wrote {@code NaN} into {@code session.json},
 *       {@code model-series.csv} and {@code report.html} — invalid JSON again. It is now a
 *       reported {@code ⚠ spec:} problem, like every other out-of-domain model line.</li>
 *   <li><b>EC-E3</b> {@code keys:} / {@code seed:} / {@code window:} with a missing or
 *       non-numeric value reported {@code (For input string: "")} — the one place in this layer
 *       that leaked a JDK exception message at a student.</li>
 * </ul>
 */
@DisplayName("Ecology edge cases — degenerate specs, communities and models (2026-08-17)")
class EcologyEdgeCaseTest {

    private static ExperimentSpec parse(String... lines) {
        return ExperimentSpec.parse(Arrays.asList(lines));
    }

    /** The single problem a one-bad-line spec reports. */
    private static String onlyProblem(ExperimentSpec spec) {
        assertEquals(1, spec.problems().size(), "expected exactly one problem, got " + spec.problems());
        return spec.problems().get(0);
    }

    // ── .eco files at their degenerate ends ─────────────────────────────────────────

    @Nested
    @DisplayName("degenerate .eco files")
    class SpecFiles {

        @Test
        @DisplayName("an empty file, a blank file and an all-comments file each parse to nothing, quietly")
        void emptyAndCommentOnlyFiles() {
            for (ExperimentSpec spec : List.of(parse(), parse("", "   ", "\t"),
                    parse("# hello", "  # world", "#"))) {
                assertEquals(List.of(), spec.problems(), "nothing there is not a problem");
                assertEquals(0, spec.phases().size());
                assertEquals(0, spec.models().size());
                assertEquals(0, spec.expectations().size());
                assertEquals(0, spec.datasets().size());
                assertEquals(0, spec.trees().size());
                assertEquals("unnamed experiment", spec.name());
                assertEquals(TheoreticalModels.Environment.NEUTRAL, spec.environment());
            }
        }

        @Test
        @DisplayName("a line with no colon is reported, not guessed at")
        void lineWithNoDirective() {
            assertTrue(onlyProblem(parse("just some words")).contains("no directive"));
            assertTrue(onlyProblem(parse(":")).contains("unknown directive"));
            assertTrue(onlyProblem(parse("nosuchthing: 3")).contains("unknown directive 'nosuchthing'"));
        }

        @Test
        @DisplayName("every directive with no argument reports what the directive needs")
        void directivesWithNoArgument() {
            // The message must name the shape the student should have written, not echo a JDK
            // exception. Each assertion below is the wording the report prints verbatim.
            assertTrue(onlyProblem(parse("phase:")).contains("phase needs: <name> <kind> <ops>"));
            assertTrue(onlyProblem(parse("model:")).contains("unknown model"));
            assertTrue(onlyProblem(parse("cross:")).contains("cross needs:"));
            assertTrue(onlyProblem(parse("expect:")).contains("expect needs metric"));
            assertTrue(onlyProblem(parse("data:")).contains("data needs:"));
            assertTrue(onlyProblem(parse("tree:")).contains("tree needs: <label> <newick>"));
            assertTrue(onlyProblem(parse("factor:")).contains("factor needs: <name> <value>"));
            assertTrue(onlyProblem(parse("note:")).contains("empty note"));
            // `name:` with no argument is legal — an experiment may be unnamed.
            assertEquals(List.of(), parse("name:").problems());
            assertEquals("", parse("name:").name());
        }

        @Test
        @DisplayName("FIX EC-E3: a missing or non-numeric count reports in English, not JDK-speak")
        void numericDirectivesReportInEnglish() {
            for (String directive : List.of("keys", "seed", "window")) {
                String empty = onlyProblem(parse(directive + ":"));
                assertTrue(empty.contains(directive + " needs a whole number"),
                        directive + " with no value: " + empty);
                assertFalse(empty.contains("For input string"),
                        directive + " must not leak the JDK message: " + empty);

                String words = onlyProblem(parse(directive + ": banana"));
                assertTrue(words.contains(directive + " must be a whole number, not 'banana'"),
                        directive + " with a word: " + words);
                assertFalse(words.contains("For input string"), words);
            }
            // The bounded ones still report their range when the number itself is out of it.
            assertTrue(onlyProblem(parse("keys: 0")).contains("keys out of range"));
            assertTrue(onlyProblem(parse("window: 0")).contains("window out of range"));
        }

        @Test
        @DisplayName("a phase with zero ops is refused; one op is accepted")
        void zeroOpPhase() {
            assertTrue(onlyProblem(parse("phase: p uniform 0")).contains("phase ops out of range"));
            ExperimentSpec one = parse("phase: p uniform 1");
            assertEquals(List.of(), one.problems());
            assertEquals(1, one.phases().get(0).ops());
        }

        @Test
        @DisplayName("a spec with zero phases still runs and still produces a report")
        void zeroPhaseExperimentStillRuns() {
            Map<String, String> files = ExperimentLab.runWithExports(parse("name: nothing"));
            assertTrue(files.get("report.txt").contains("nothing"));
            assertTrue(files.get("report.txt").contains("0 phase(s)"));
            assertNotNull(files.get("session.json"));
            assertFalse(files.get("session.json").contains("NaN"));
            assertFalse(files.get("session.json").contains("Infinity"));
        }

        @Test
        @DisplayName("a one-species dataset grades without dividing by ln(1)")
        void oneSpeciesDataset() {
            ExperimentSpec spec = parse("data: pond oak=1", "expect: evenness(pond) > 0.5");
            assertEquals(List.of(), spec.problems());
            Map<String, String> files = ExperimentLab.runWithExports(spec);
            assertFalse(files.get("report.txt").contains("NaN"), files.get("report.txt"));
            assertFalse(files.get("session.json").contains("NaN"));
        }

        @Test
        @DisplayName("a dataset with no positive count is refused, naming both the line and the dataset")
        void datasetWithNoValidCounts() {
            List<String> problems = parse("data: pond oak=0").problems();
            assertEquals(2, problems.size(), problems.toString());
            assertTrue(problems.get(0).contains("count must be positive"), problems.toString());
            assertTrue(problems.get(1).contains("has no valid counts"), problems.toString());
        }
    }

    // ── Newick at its degenerate ends ───────────────────────────────────────────────

    @Nested
    @DisplayName("Newick trees")
    class Newick {

        @Test
        @DisplayName("a bare leaf is a valid one-taxon tree, with and without the terminating ';'")
        void bareLeaf() {
            for (String nw : List.of("A;", "A", " A ;", " A ")) {
                PhyloTree t = PhyloTree.parse(nw);
                assertEquals(List.of("A"), t.leaves(), nw);
                assertEquals(1, t.depth(), nw);
                assertEquals("A;", t.newick(), nw);
                assertEquals("{ \"name\": \"A\" }", t.json(), nw);
            }
            ExperimentSpec spec = parse("tree: t A;");
            assertEquals(List.of(), spec.problems());
            assertEquals(List.of("A"), spec.trees().get(0).tree().leaves());
        }

        @Test
        @DisplayName("a single-child clade and a nested single chain are valid and round-trip")
        void singleChildClades() {
            assertEquals("(A);", PhyloTree.parse("(A);").newick());
            assertEquals(2, PhyloTree.parse("(A);").depth());
            assertEquals("((A));", PhyloTree.parse("((A));").newick());
            assertEquals(3, PhyloTree.parse("((A));").depth());
            assertEquals(List.of("A"), PhyloTree.parse("((A));").leaves());
        }

        @Test
        @DisplayName("empty, unbalanced and nameless trees are each refused with a reason")
        void malformedNewickIsReported() {
            assertTrue(reason("").contains("empty tree"));
            assertTrue(reason(";").contains("empty tree"));
            assertTrue(reason("()").contains("empty node"));
            assertTrue(reason("(,)").contains("empty node"));
            assertTrue(reason("(A,);").contains("empty node"));
            assertTrue(reason("(A").contains("unbalanced"));
            assertTrue(reason("A)").contains("trailing characters"));
            assertTrue(reason("(A:x);").contains("bad branch length 'x'"));
        }

        @Test
        @DisplayName("FIX EC-E1: a non-finite branch length is reported, so json() stays valid JSON")
        void nonFiniteBranchLengthIsReported() {
            // Double.parseDouble accepts "Infinity" and overflows "1e400" to it; json() then wrote
            // the bare token Infinity, which JSON.parse rejects — one bad number made the whole
            // session unreadable. NaN is this class's marker for "no length", so a literal NaN was
            // being silently dropped instead of reported.
            for (String bad : List.of("A:1e400;", "A:-1e400;", "A:Infinity;", "A:-Infinity;", "A:NaN;",
                                      "(A:1e400,B);")) {
                assertTrue(reason(bad).contains("not a finite number"),
                        bad + " -> " + reason(bad));
            }
            // Through a .eco file it becomes a reported spec problem, not a corrupt export.
            ExperimentSpec spec = parse("tree: t (A:1e400,B);");
            assertEquals(0, spec.trees().size());
            assertTrue(onlyProblem(spec).contains("not a finite number"), spec.problems().toString());

            // Ordinary finite lengths, including very small ones, are untouched (F-6 / S6-37).
            assertEquals("A:1.0E-7;", PhyloTree.parse("A:1e-7;").newick());
            assertTrue(PhyloTree.parse("A:1e-7;").json().contains("\"length\": 1.0E-7"));
            assertEquals("A:0.5;", PhyloTree.parse("A:0.5;").newick());
            assertEquals("A:0;", PhyloTree.parse("A:0;").newick());
        }

        private String reason(String newick) {
            return assertThrows(IllegalArgumentException.class,
                    () -> PhyloTree.parse(newick)).getMessage();
        }
    }

    // ── Metrics at their division-by-zero shapes ────────────────────────────────────

    @Nested
    @DisplayName("metrics at zero and one")
    class Metrics {

        private Map<String, Long> counts(Object... kv) {
            LinkedHashMap<String, Long> m = new LinkedHashMap<>();
            for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], ((Number) kv[i + 1]).longValue());
            return m;
        }

        @Test
        @DisplayName("an empty, an all-zero and a negative-count community are all finite and zero-ish")
        void emptyCommunityHasNoDivisionByZero() {
            for (Map<String, Long> m : List.of(counts(), counts("a", 0, "b", 0), counts("a", -5))) {
                assertEquals(0, CommunityMetrics.richness(m));
                assertEquals(0L, CommunityMetrics.total(m));
                assertFinite(CommunityMetrics.shannon(m), "shannon");
                assertEquals(0.0, CommunityMetrics.shannon(m));
                assertEquals(1.0, CommunityMetrics.pielouEvenness(m), "S <= 1 is trivially even");
                assertEquals(0.0, CommunityMetrics.simpsonIndex(m));
                assertEquals(0.0, CommunityMetrics.inverseSimpson(m), "1/D must not divide by zero");
                for (double q : new double[]{0, 0.5, 1, 2, 3}) {
                    assertFinite(CommunityMetrics.hillNumber(m, q), "hill q=" + q);
                }
                assertEquals(0.0, CommunityMetrics.chao1(m));
                assertEquals(0.0, CommunityMetrics.rarefiedRichness(m, 5));
                assertEquals(0.0, CommunityMetrics.rarefiedRichness(m, 0));
                assertEquals(0, CommunityMetrics.rarefactionCurve(m, 4).length);
                assertEquals(CommunityMetrics.AbundanceModel.UNIFORM, CommunityMetrics.bestFit(m).best());
            }
        }

        @Test
        @DisplayName("a one-species community is finite everywhere, including ln(S) = 0")
        void oneSpeciesCommunity() {
            Map<String, Long> one = counts("a", 7);
            assertEquals(1, CommunityMetrics.richness(one));
            assertEquals(0.0, CommunityMetrics.shannon(one), 1e-12);
            assertEquals(1.0, CommunityMetrics.pielouEvenness(one),
                    "Pielou is H'/ln(S) and ln(1) = 0 — defined as 1, not NaN");
            assertEquals(1.0, CommunityMetrics.simpsonIndex(one), 1e-12);
            assertEquals(1.0, CommunityMetrics.inverseSimpson(one), 1e-12);
            for (double q : new double[]{0, 0.5, 1, 2, 3}) {
                assertFinite(CommunityMetrics.hillNumber(one, q), "hill q=" + q);
            }
            assertEquals(1.0, CommunityMetrics.chao1(one), 1e-12);
            assertFinite(CommunityMetrics.rarefiedRichness(one, 3), "rarefied");
            for (double[] pt : CommunityMetrics.rarefactionCurve(one, 4)) assertFinite(pt[1], "curve");
            // A one-species rank-abundance list has no successive ratio to fit.
            assertEquals(0.999, CommunityMetrics.fitGeometricK(List.of(7L)), 1e-12);
            assertEquals(1, CommunityMetrics.geometricExpected(1, 7, 0.999).length);
            assertFinite(CommunityMetrics.geometricExpected(1, 7, 0.999)[0], "geometric S=1");
            assertFinite(CommunityMetrics.brokenStickExpected(1, 7)[0], "brokenstick S=1");
            assertNotNull(CommunityMetrics.bestFit(one).best());
        }

        @Test
        @DisplayName("beta diversity between empty and one-species communities is finite")
        void betaDiversityAtZeroOverlap() {
            Map<String, Long> empty = counts();
            Map<String, Long> one = counts("a", 1);
            assertEquals(1.0, BetaDiversity.jaccard(empty.keySet(), empty.keySet()),
                    "two empty surveys found the same nothing");
            assertEquals(1.0, BetaDiversity.sorensen(empty.keySet(), empty.keySet()));
            assertFinite(BetaDiversity.brayCurtis(empty, empty), "bray empty/empty");
            assertFinite(BetaDiversity.pianka(empty, empty), "pianka empty/empty");
            assertEquals(0.0, BetaDiversity.jaccard(one.keySet(), empty.keySet()));
            assertEquals(1.0, BetaDiversity.brayCurtis(one, empty), "no shared individuals at all");
            assertFinite(BetaDiversity.pianka(one, empty), "pianka one/empty");
            assertEquals(0.0, BetaDiversity.brayCurtis(one, one), "a community against itself");
            assertEquals(1.0, BetaDiversity.pianka(one, one), 1e-12);
        }

        @Test
        @DisplayName("a life table with no deaths, one lifespan, and one age class stays finite")
        void lifeTableDegenerate() {
            LifeTable empty = LifeTable.fromLifespans(List.of(), 4);
            assertEquals(0, empty.cohortSize());
            assertFinite(empty.lifeExpectancy(), "e0 of an empty cohort");
            assertFinite(empty.survivorshipAt(0), "lx of an empty cohort");
            assertFinite(empty.mortalityAt(0), "qx of an empty cohort");

            LifeTable one = LifeTable.fromLifespans(List.of(new LifeTable.Lifespan(1, 0, 5)), 4);
            assertEquals(1, one.cohortSize());
            assertFinite(one.lifeExpectancy(), "e0 of a one-individual cohort");
            assertEquals(1.0, one.survivorshipAt(0), 1e-12);

            LifeTable single = LifeTable.fromLifespans(
                    List.of(new LifeTable.Lifespan(1, 0, 1), new LifeTable.Lifespan(2, 0, 2)), 1);
            assertEquals(1, single.ageClasses());
            assertFinite(single.mortalityAt(0), "qx with one age class");

            assertThrows(IllegalArgumentException.class, () -> LifeTable.fromLifespans(List.of(), 0));
            assertThrows(IllegalArgumentException.class, () -> LifeTable.fromLifespans(List.of(), -1));
        }

        @Test
        @DisplayName("mark-recapture with zero recaptures reports Chapman, never a bare Infinity in JSON")
        void markRecaptureWithNoRecaptures() {
            // R = 0 is a legitimate field result. Lincoln-Petersen is M·C/R and therefore infinite;
            // Chapman is exactly the estimator that survives it, and the JSON emitter already
            // writes null rather than the bare token Infinity.
            MarkRecapture.Estimate est = MarkRecapture.estimate(100, 50, 0);
            assertTrue(Double.isInfinite(est.lincolnPetersen()), "the naive estimator is undefined");
            assertFinite(est.chapman(), "Chapman");
            Map<String, String> files = ExperimentLab.runWithExports(
                    parse("model: markrecapture 100 50 0"));
            assertFalse(files.get("session.json").contains("Infinity"),
                    "an undefined Lincoln-Petersen must not become invalid JSON");
            assertFalse(files.get("session.json").contains("NaN"));

            assertThrows(IllegalArgumentException.class, () -> MarkRecapture.estimate(0, 0, 0));
            assertThrows(IllegalArgumentException.class, () -> MarkRecapture.estimate(10, 5, 6));
        }

        @Test
        @DisplayName("Hardy-Weinberg and Euler-Lotka refuse their empty and unsolvable inputs")
        void geneticsDegenerate() {
            assertThrows(IllegalArgumentException.class,
                    () -> PopulationGenetics.hardyWeinberg(0, 0, 0));
            assertThrows(IllegalArgumentException.class,
                    () -> PopulationGenetics.hardyWeinberg(-1, 1, 1));
            assertNotNull(PopulationGenetics.hardyWeinberg(1, 0, 0), "a single homozygote is fine");
            assertThrows(IllegalArgumentException.class,
                    () -> PopulationGenetics.eulerLotka(new double[0], new double[0]));
            assertThrows(IllegalArgumentException.class,
                    () -> PopulationGenetics.eulerLotka(new double[]{1, 1}, new double[]{0, 0}));
            PopulationGenetics.LifeTableRates unity =
                    PopulationGenetics.eulerLotka(new double[]{1, 1}, new double[]{0, 1});
            assertEquals(1.0, unity.r0(), 1e-12);
            assertEquals(0.0, unity.rExact(), 1e-12, "R0 = 1 means r = 0, exactly");
        }

        @Test
        @DisplayName("FIX EC-E2: a zero carrying capacity is refused, not exported as NaN")
        void zeroCarryingCapacityIsReported() {
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.logisticTrajectory(0.1, 0, 5, 10));
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.logisticTrajectory(0.1, -3, 5, 10));
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.competitionTrajectories(0.4, 0, 0.4, 80, 0.7, 1.1, 5, 5, 10));
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.competitionTrajectories(0.4, 100, 0.4, 0, 0.7, 1.1, 5, 5, 10));

            // Through a .eco file it is a spec problem, and the export is clean.
            for (String line : List.of("model: logistic 0.15 0 5 20",
                                       "model: competition 0.4 0 0.4 0 0.7 1.1 5 5 20")) {
                ExperimentSpec spec = parse(line);
                assertEquals(0, spec.models().size(), line);
                assertTrue(onlyProblem(spec).contains("must be > 0"), line + " -> " + spec.problems());
                Map<String, String> files = ExperimentLab.runWithExports(spec);
                for (Map.Entry<String, String> f : files.entrySet()) {
                    assertFalse(f.getValue().contains("NaN"), line + " -> NaN in " + f.getKey());
                    assertFalse(f.getValue().contains("Infinity"), line + " -> Infinity in " + f.getKey());
                }
            }

            // Every other degenerate model input stays finite and keeps working.
            assertFinite(TheoreticalModels.levinsEquilibrium(0, 0), "levins c=e=0");
            assertFinite(TheoreticalModels.islandEquilibrium(0, 0, 0), "island all zero");
            for (double[] pt : TheoreticalModels.logisticTrajectory(0.1, 100, 0, 3)) {
                assertEquals(0.0, pt[1], "an extinct population stays extinct");
            }
            assertEquals(1, TheoreticalModels.logisticTrajectory(0.1, 100, 5, 0).length,
                    "zero steps is one point, not zero");
            assertEquals(1, TheoreticalModels.exponentialTrajectory(0.1, 5, 0).length);
            for (double[] pt : TheoreticalModels.islandTrajectory(0.3, 0.1, 0, 0, 3)) {
                assertEquals(0.0, pt[1], "an empty species pool colonizes nothing");
            }
        }

        @Test
        @DisplayName("a spec whose models are all degenerate-but-legal exports finite numbers only")
        void degenerateButLegalModelsExportFiniteNumbers() {
            ExperimentSpec spec = parse(
                    "model: logistic 0.15 120 0 20",       // extinct start
                    "model: exponential 0 5 20",           // no growth
                    "model: levins 0 0 0 20",              // no colonization, no extinction
                    "model: island 0.3 0.1 0 0 20",        // empty pool
                    "model: predation 0 0 0 0 0 0 20");    // everything zero
            assertEquals(List.of(), spec.problems(), spec.problems().toString());
            Map<String, String> files = ExperimentLab.runWithExports(spec);
            for (Map.Entry<String, String> f : files.entrySet()) {
                assertFalse(f.getValue().contains("NaN"), "NaN in " + f.getKey());
                assertFalse(f.getValue().contains("Infinity"), "Infinity in " + f.getKey());
            }
        }

        private void assertFinite(double v, String what) {
            assertTrue(Double.isFinite(v), what + " must be finite, got " + v);
        }
    }

    // ── Field data and the recorder ─────────────────────────────────────────────────

    @Nested
    @DisplayName("field data and the recorder")
    class FieldAndRecorder {

        @Test
        @DisplayName("an empty, blank and comment-only field file parses to nothing, quietly")
        void emptyFieldData() {
            for (List<String> lines : List.of(List.<String>of(), List.of(""), List.of("# a comment"))) {
                FieldData.Parsed p = FieldData.parseLines(lines);
                assertEquals(0, p.counts().size(), lines.toString());
                assertEquals(List.of(), p.problems(), lines.toString());
            }
            FieldData.Parsed tokens = FieldData.parseTokens("");
            assertEquals(0, tokens.counts().size());
            assertEquals(List.of(), tokens.problems());
        }

        @Test
        @DisplayName("every malformed row is reported verbatim with its reason, and contributes no count")
        void malformedRowsAreReported() {
            FieldData.Parsed p = FieldData.parseLines(List.of(
                    "oak,", "oak,0", ",5", "oak,notanumber", "oak,-1", "oak,99999999999999999999"));
            assertEquals(0, p.counts().size(), "no guessed counts: " + p.counts());
            assertEquals(6, p.problems().size(), p.problems().toString());
            assertTrue(p.problems().get(0).contains("is not an integer"), p.problems().get(0));
            assertTrue(p.problems().get(1).contains("must be positive"), p.problems().get(1));
            assertTrue(p.problems().get(2).contains("empty name"), p.problems().get(2));
        }

        @Test
        @DisplayName("a one-row, one-species file is a valid community")
        void oneRowFile() {
            FieldData.Parsed p = FieldData.parseLines(List.of("oak,1"));
            assertEquals(Map.of("oak", 1L), p.counts());
            assertEquals(List.of(), p.problems());
            assertEquals(1.0, CommunityMetrics.pielouEvenness(p.counts()));
        }

        @Test
        @DisplayName("the recorder refuses a window or history of zero, and works at one")
        void recorderBounds() {
            assertThrows(IllegalArgumentException.class, () -> new EcologyRecorder(0, 1));
            assertThrows(IllegalArgumentException.class, () -> new EcologyRecorder(10, 0));
            assertThrows(IllegalArgumentException.class, () -> new EcologyRecorder(-1, -1));
            EcologyRecorder tightest = new EcologyRecorder(1, 1);
            tightest.recordAdd(1, 0);
            tightest.recordAdd(2, 0);
            assertEquals(2, tightest.opCount());
            assertEquals(2, tightest.closedWindowCount(), "every op closes its own window at width 1");
            assertEquals(1, tightest.closedWindows().size(), "but only one is kept");
            assertEquals(1, tightest.evictedWindowCount());
        }
    }
}
