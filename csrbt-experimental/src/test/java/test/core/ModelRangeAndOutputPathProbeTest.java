package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;
import io.github.richeyworks.csrbt.experimental.ecology.TheoreticalModels;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Frontend verification 2026-08-17 (J1, J4, J5) — the Java-side pins.
 *
 * <p>J1 and J5 are the same family: a model that answers a question the parameters did not ask.
 * A trajectory point that is not a real number renders as the bare token {@code Infinity} or
 * {@code NaN}, and neither is JSON — so one out-of-range model made the <em>whole</em>
 * {@code session.json} unparseable and {@code docs/ecology-lab.html} could not open the session at
 * all. J4 is the other half of "a student's run must not surprise them": running your own spec
 * silently overwrote the shipped sample artifacts.</p>
 */
@DisplayName("Frontend verification 2026-08-17 — model range and output paths")
class ModelRangeAndOutputPathProbeTest {

    /** No point of a series may be non-finite; %.4f would render it as a non-JSON token. */
    private static void allFinite(String what, double[][] series) {
        for (double[] p : series) {
            assertTrue(Double.isFinite(p[1]), what + ": step " + (int) p[0] + " is " + p[1]);
        }
    }

    // ── J1 ──────────────────────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("J1 — a trajectory that leaves the number line is reported, never written")
    class UnrepresentableTrajectories {

        @Test
        @DisplayName("the reproduction: model: exponential 0.7 1 1200 is refused with the step it breaks at")
        void exponentialOverflowIsReported() {
            // Finite for a thousand steps, Infinity from step 1014 — which is exactly why the
            // spec's old one-point probe could not see it.
            allFinite("exponential 0.7 1 1000", TheoreticalModels.exponentialTrajectory(0.7, 1, 1000));

            IllegalArgumentException bad = assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.exponentialTrajectory(0.7, 1, 1200));
            assertTrue(bad.getMessage().contains("step 1014"), bad.getMessage());
            assertTrue(bad.getMessage().contains("shorten the run"), bad.getMessage());
        }

        @Test
        @DisplayName("island and predation reach it too — the guard is on the model layer, not on one model")
        void theOtherTwoDivergentModelsAreCaught() {
            // c + e < 0 flips e^(-(c+e)t) from decay to growth. A negative rate is now refused as a
            // rate (J5) before it can even get there, so the overflow route is via predation.
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.islandTrajectory(-1, 0, 100, 0, 300));
            // Predation's Euler walk diverges on a negative mortality...
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.predationTrajectories(0.5, 0.01, 0.02, -1, 40, 9, 1200));
            // ...and, the reason this is a model-layer gate rather than a sign check, on entirely
            // positive parameters given a long enough run (steps = 100000 is spec-legal).
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.predationTrajectories(0.5, 0.01, 0.02, 100, 40, 9, 100_000));

            // ...and the classroom regime is untouched: every model stays finite at ordinary rates.
            allFinite("levins", TheoreticalModels.levinsTrajectory(0.4, 0.1, 0.1, 200));
            allFinite("logistic", TheoreticalModels.logisticTrajectory(0.3, 500, 5, 200));
            allFinite("island", TheoreticalModels.islandTrajectory(0.3, 0.1, 100, 0, 200));
            allFinite("exponential", TheoreticalModels.exponentialTrajectory(0.05, 5, 200));
            double[][][] pred = TheoreticalModels.predationTrajectories(0.5, 0.01, 0.02, 0.3, 40, 9, 200);
            allFinite("predation prey", pred[0]);
            allFinite("predation predator", pred[1]);
            double[][][] comp = TheoreticalModels.competitionTrajectories(
                    0.5, 400, 0.4, 300, 0.6, 0.7, 10, 10, 200);
            allFinite("competition 1", comp[0]);
            allFinite("competition 2", comp[1]);
        }

        @Test
        @DisplayName("the spec reports it at parse time, over the real step count")
        void theSpecProbeUsesTheRealStepCount() {
            ExperimentSpec spec = ExperimentSpec.parse(List.of(
                    "name: bacteria doubling",
                    "keys: 50", "seed: 7", "window: 100",
                    "model: exponential 0.7 1 1200",
                    "model: logistic 0.3 500 5 60"));
            assertEquals(1, spec.models().size(), "the good model survives: " + spec.models());
            assertEquals("logistic", spec.models().get(0).kind());
            assertEquals(1, spec.problems().size(), spec.problems().toString());
            assertTrue(spec.problems().get(0).contains("leaves the range of a double"),
                    spec.problems().get(0));
            // A run of the same shape that DOES fit is not reported — the probe is not a step cap.
            ExperimentSpec ok = ExperimentSpec.parse(List.of(
                    "name: fine", "keys: 50", "seed: 7", "window: 100",
                    "model: exponential 0.7 1 1000"));
            assertEquals(List.of(), ok.problems());
            assertEquals(1, ok.models().size());
        }

        @Test
        @DisplayName("a factor-amplified overflow is caught at run time and the session stays valid JSON")
        void aFactorAmplifiedOverflowIsReportedAndOmitted() {
            // The spec probes the RAW parameters; `factor:` is applied later, so r = 0.01 passes
            // parse and becomes r = 2 under temperature 200. The model is dropped from the export
            // rather than written as Infinity, and the surviving model must still be well-formed.
            ExperimentSpec spec = ExperimentSpec.parse(List.of(
                    "name: factor amplified", "keys: 50", "seed: 7", "window: 100",
                    "factor: temperature 200",
                    "model: exponential 0.01 1 400",
                    "model: logistic 0.3 500 5 60"));
            assertEquals(List.of(), spec.problems(), "parse time cannot see this one");
            assertEquals(2, spec.models().size());

            Map<String, String> files = ExperimentLab.runWithExports(spec);
            String json = files.get("session.json");
            assertFalse(json.contains("Infinity"), "'Infinity' is not a JSON token:\n" + json);
            assertFalse(json.contains("NaN"), "'NaN' is not a JSON token:\n" + json);
            assertTrue(files.get("report.txt").contains("⚠ exponential:"),
                    "the reader must be told which model was dropped and why:\n" + files.get("report.txt"));
            assertTrue(files.get("report.txt").contains("leaves the range of a double"),
                    files.get("report.txt"));

            // The models array must not be left with a dangling comma by the omission, and the
            // model that IS representable must still be there.
            String models = json.substring(json.indexOf("\"models\""));
            models = models.substring(models.indexOf('['), models.indexOf(']') + 1);
            assertFalse(models.contains("[,") || models.contains(",]") || models.contains(",,"),
                    "a skipped model must not leave a hole in the array: " + models);
            assertTrue(models.contains("\"kind\": \"logistic\""), models);
            assertFalse(models.contains("\"kind\": \"exponential\""), models);
            assertBalanced(json);
        }

        /** Cheap structural stand-in for a parser: the export must at least stay bracket-balanced. */
        private void assertBalanced(String json) {
            int braces = 0, brackets = 0;
            boolean inString = false, escaped = false;
            for (char c : json.toCharArray()) {
                if (escaped) { escaped = false; continue; }
                if (c == '\\') { escaped = true; continue; }
                if (c == '"') { inString = !inString; continue; }
                if (inString) continue;
                if (c == '{') braces++;
                if (c == '}') braces--;
                if (c == '[') brackets++;
                if (c == ']') brackets--;
            }
            assertEquals(0, braces, "unbalanced braces");
            assertEquals(0, brackets, "unbalanced brackets");
        }
    }

    // ── J5 ──────────────────────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("J5 — colonization and extinction are rates, so they cannot be negative")
    class NegativeRatesAreRefused {

        @Test
        @DisplayName("the reproduction: e = -1 used to make p* = 3.5, clamped to a confident 1.0")
        void negativeExtinctionIsRefusedRatherThanClamped() {
            // 1 - e/c with c = 0.4, e = -1 is 3.5; the [0,1] clamp turned that into "every patch
            // occupied", printed with no hint the input was meaningless.
            assertEquals(3.5, 1.0 - (-1.0) / 0.4, 1e-9, "the arithmetic the clamp was hiding");
            IllegalArgumentException bad = assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.levinsEquilibrium(0.4, -1));
            assertTrue(bad.getMessage().contains("extinction rate e must be >= 0"), bad.getMessage());
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.levinsTrajectory(0.4, -1, 0.5, 20));
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.levinsTrajectory(-0.4, 0.1, 0.5, 20));
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.islandEquilibrium(-0.3, 0.1, 100));
            assertThrows(IllegalArgumentException.class,
                    () -> TheoreticalModels.islandTrajectory(0.3, -0.1, 100, 0, 20));
        }

        @Test
        @DisplayName("zero is still a rate, and the documented degenerate answers are unchanged")
        void zeroRatesStillWork() {
            assertEquals(0.0, TheoreticalModels.levinsEquilibrium(0.0, 0.1), 1e-12);
            assertEquals(0.75, TheoreticalModels.levinsEquilibrium(0.4, 0.1), 1e-12);
            assertEquals(0.0, TheoreticalModels.islandEquilibrium(0, 0, 100), 1e-12);
            assertEquals(75.0, TheoreticalModels.islandEquilibrium(0.3, 0.1, 100), 1e-12);
            allFinite("levins c=e=0", TheoreticalModels.levinsTrajectory(0, 0, 0.5, 10));
        }

        @Test
        @DisplayName("a negative rate in a .eco file is a reported spec problem, not a crash")
        void theSpecReportsANegativeRate() {
            ExperimentSpec spec = ExperimentSpec.parse(List.of(
                    "name: bad rates", "keys: 50", "seed: 7", "window: 100",
                    "model: levins 0.4 -1 0.1 40"));
            assertEquals(0, spec.models().size());
            assertEquals(1, spec.problems().size(), spec.problems().toString());
            assertTrue(spec.problems().get(0).contains("must be >= 0"), spec.problems().get(0));
        }
    }

    // ── J4 ──────────────────────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("J4 — a student's run lands beside their own spec")
    class OutputPathsFollowTheSpec {

        private static final List<String> SPEC = List.of(
                "name: mine", "keys: 60", "seed: 3", "window: 50",
                "phase: settle churn 200 70",
                "model: logistic 0.3 500 5 40");

        @Test
        @DisplayName("with no output paths the results are named after the spec, not after the sample")
        void defaultsAreDerivedFromTheSpec(@TempDir Path dir) throws Exception {
            Path spec = dir.resolve("mine.eco");
            Files.write(spec, SPEC);
            ExperimentLab.main(new String[]{ spec.toString() });

            assertTrue(Files.isRegularFile(dir.resolve("mine-session.json")),
                    "the session belongs beside the spec that produced it");
            assertTrue(Files.isDirectory(dir.resolve("mine-out")));
            assertTrue(Files.isRegularFile(dir.resolve("mine-out/report.txt")));
            assertFalse(Files.exists(dir.resolve("ecology-experiment-session.json")),
                    "the shipped sample's NAME must not appear for someone else's spec");
            assertFalse(Files.exists(dir.resolve("experiment-out")));
        }

        @Test
        @DisplayName("explicit output paths still win — that is how the shipped bundle is regenerated")
        void explicitPathsAreHonoured(@TempDir Path dir) throws Exception {
            Path spec = mkSpec(dir);
            Path session = dir.resolve("named.json");
            Path bundle = dir.resolve("bundle");
            ExperimentLab.main(new String[]{ spec.toString(), session.toString(), bundle.toString() });

            assertTrue(Files.isRegularFile(session));
            assertTrue(Files.isRegularFile(bundle.resolve("session.json")));
            assertFalse(Files.exists(dir.resolve("mine-session.json")),
                    "the derived default must not also be written");
        }

        @Test
        @DisplayName("a spec with no directory part resolves in the working directory, never a fixed one")
        void aBareSpecNameStaysLocal(@TempDir Path dir) throws Exception {
            // The derivation is textual, so this is the case that could have escaped: verify the
            // names it produces are relative and carry the spec's own stem.
            Path spec = mkSpec(dir);
            String derived = spec.getFileName().toString().replace(".eco", "-session.json");
            assertEquals("mine-session.json", derived);
            ExperimentLab.main(new String[]{ spec.toString() });
            assertTrue(Files.isRegularFile(dir.resolve(derived)));
        }

        private Path mkSpec(Path dir) throws Exception {
            Path spec = dir.resolve("mine.eco");
            Files.write(spec, SPEC);
            return spec;
        }
    }
}
