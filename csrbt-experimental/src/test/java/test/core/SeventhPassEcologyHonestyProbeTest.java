package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.experimental.TreeEcology;
import io.github.richeyworks.csrbt.experimental.cache.CacheEvolutionLoop;
import io.github.richeyworks.csrbt.experimental.cache.CacheGenome;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Wiring audit 2026-08-17 (seventh pass), findings 3, 4 and 7.
 *
 * <p><b>Findings 3 and 4</b> are the EC-1 residue the sixth pass left in {@code TreeEcology}.
 * {@code EcologyRecorder}'s class javadoc has said since ADR-015 that the class's distribution
 * indices are constants on a duplicate-free BST — "Shannon H&#x2032; &#x2261; ln(S), evenness &#x2261; 1,
 * empirical z &#x2261; 1, and Pianka overlap between disjoint-by-construction subtrees &#x2261; 0".
 * Only evenness was ever settled (audit 2026-08-09 EC-3 / sixth-pass S6-27): its accessor was
 * deprecated onto the instruments that measure, and {@code ecologyReport()} stopped printing the
 * constant. {@link TreeEcology#empiricalZValue()} and {@link TreeEcology#nicheOverlap()} were left
 * undeprecated, undocumented, and — the part that matters — still printed to four decimal places
 * with an interpretation band beside each, in a report written for a classroom.
 * {@link TreeEcology#colonizationEquilibrium(int)} is the third of the set: superseded by
 * {@code LogisticGrowth} at audit EC-2 for deriving its rates from wall-clock latencies, named as
 * superseded in {@code LogisticGrowth}'s javadoc and nowhere in its own.</p>
 *
 * <p>These tests pin the same three halves the evenness settlement pinned: the constants are still
 * the constants (so the documentation cannot silently rot), the API carries the warning, and the
 * report no longer formats either of them as a measurement.</p>
 *
 * <p><b>Finding 7</b> is the coverage gap: {@link CacheEvolutionLoop#resident(int)} is a published
 * seam "named by the first external consumer (Brine)" with no in-repo caller and no test at all.</p>
 */
@DisplayName("Seventh pass — the last two constant indices, and an untested published seam")
class SeventhPassEcologyHonestyProbeTest {

    /** A 15-node left spine: the worst shape a BST can take. */
    private static TreeContext spine() {
        TreeContext ctx = new TreeContext(new SplayStrategy<>());
        for (int k = 1; k <= 15; k++) ctx.add(k);
        return ctx;
    }

    /** A perfect 15-node tree: Red-Black builds this shape without a single rotation. */
    private static TreeContext perfect() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int k : new int[]{ 8, 4, 12, 2, 6, 10, 14, 1, 3, 5, 7, 9, 11, 13, 15 }) ctx.add(k);
        return ctx;
    }

    // ── Finding 3: the premise ──────────────────────────────────────────────────────────

    @Test
    @DisplayName("empiricalZValue() is 1.0 for every tree that has one — the defect itself")
    @SuppressWarnings("deprecation")
    void empiricalZIsStructurallyConstant() {
        // Not a fix under test — the premise. S = A in every subtree of a SET, so
        // log(S2/S1)/log(A2/A1) collapses to log(A2/A1)/log(A2/A1) = 1. The formula is
        // undefined (NaN) only when a subtree is empty or the two are the same size —
        // which is exactly what a spine and a perfect tree respectively produce, so both
        // fixtures are NaN and the sweep below carries the non-vacuity.
        assertTrue(Double.isNaN(new TreeEcology(spine()).empiricalZValue()),
                "a spine has one empty subtree — undefined, not a measurement");
        assertTrue(Double.isNaN(new TreeEcology(perfect()).empiricalZValue()),
                "a perfect tree has two equal subtrees — undefined, not a measurement");

        Set<Double> seen = new LinkedHashSet<>();
        Random rnd = new Random(20260817L);
        for (int trial = 0; trial < 40; trial++) {
            TreeContext ctx = new TreeContext(trial % 2 == 0
                    ? new RedBlackStrategy<>() : new AVLStrategy<>());
            int n = 3 + rnd.nextInt(300);
            for (int i = 0; i < n; i++) ctx.add(rnd.nextInt(10_000));
            seen.add(new TreeEcology(ctx).empiricalZValue());
        }
        for (double z : seen) {
            assertTrue(z == 1.0 || Double.isNaN(z),
                    "the only values a set-backed species-area ratio can take are 1.0 and NaN, saw " + z);
        }
        assertTrue(seen.contains(1.0),
                "non-vacuity: at least one of the 40 trees must actually reach the defined branch, "
                        + "or this test would pass on a method that only ever returned NaN — saw " + seen);
    }

    @Test
    @DisplayName("nicheOverlap() is 0.0 for every tree — the subtrees are disjoint by the BST invariant")
    @SuppressWarnings("deprecation")
    void nicheOverlapIsStructurallyConstant() {
        assertEquals(0.0, new TreeEcology(spine()).nicheOverlap(), 1e-12);
        assertEquals(0.0, new TreeEcology(perfect()).nicheOverlap(), 1e-12);

        Random rnd = new Random(4242L);
        for (int trial = 0; trial < 40; trial++) {
            TreeContext ctx = new TreeContext(trial % 2 == 0
                    ? new SplayStrategy<>() : new RedBlackStrategy<>());
            int n = 3 + rnd.nextInt(300);
            for (int i = 0; i < n; i++) ctx.add(rnd.nextInt(10_000));
            assertEquals(0.0, new TreeEcology(ctx).nicheOverlap(), 1e-12,
                    "every Pianka term is pL*pR with one factor zero");
        }
    }

    // ── Findings 3 and 4: the API carries the warning ───────────────────────────────────

    @Test
    @DisplayName("the three superseded accessors are deprecated; their replacements are not")
    void constantAndNondeterministicAccessorsAreDeprecated() throws NoSuchMethodException {
        for (String name : List.of("empiricalZValue", "nicheOverlap")) {
            assertTrue(TreeEcology.class.getMethod(name).isAnnotationPresent(Deprecated.class),
                    name + ": a public accessor that can only return one value must carry the "
                            + "warning in the API, not only in an audit document");
        }
        assertTrue(TreeEcology.class.getMethod("colonizationEquilibrium", int.class)
                        .isAnnotationPresent(Deprecated.class),
                "colonizationEquilibrium derives its rates from wall-clock latencies (EC-2); "
                        + "LogisticGrowth's javadoc has named it superseded, its own did not");

        // The instruments callers are being sent to must not themselves be flagged.
        assertFalse(TreeEcology.class.getMethod("subtreeEvenness").isAnnotationPresent(Deprecated.class));
        assertFalse(TreeEcology.class.getMethod("speciesRichness").isAnnotationPresent(Deprecated.class));
    }

    // ── Finding 3: the report stops formatting constants as measurements ────────────────

    @Test
    @DisplayName("ecologyReport() prints neither an empirical-z nor an overlap number")
    void reportQuotesNeitherConstant() {
        // "Empirical z = 1.0000" and "O_LR = 0.0000" appeared identically on both trees below.
        Pattern quotedZ  = Pattern.compile("Empirical z\\s*=\\s*[0-9]");
        Pattern quotedO  = Pattern.compile("O_LR\\s*=\\s*[0-9]");
        for (TreeContext ctx : new TreeContext[]{ spine(), perfect() }) {
            String report = new TreeEcology(ctx).ecologyReport();
            assertFalse(quotedZ.matcher(report).find(),
                    "a constant must not be formatted as a measurement:\n" + report);
            assertFalse(quotedO.matcher(report).find(),
                    "a constant must not be formatted as a measurement:\n" + report);

            // The omissions are explained, not silent — the evenness settlement's rule.
            assertTrue(report.contains("Empirical z") && report.contains("O_LR"),
                    "the omission must be explained, not silent:\n" + report);
            assertTrue(report.contains("rarefiedRichness"),
                    "the report must name the instrument that does measure richness-vs-effort:\n" + report);
            assertTrue(report.contains("BetaDiversity.pianka"),
                    "the report must name the instrument that does measure overlap:\n" + report);

            // The interpretation bands went with the numbers they interpreted.
            assertFalse(report.contains("z≈0.30=islands"),
                    "an interpretation band for a constant is worse than the constant:\n" + report);
            assertFalse(report.contains("O=1→identical niches"),
                    "an interpretation band for a constant is worse than the constant:\n" + report);
        }
    }

    @Test
    @DisplayName("the rest of the report is untouched, and still varies with the tree")
    void reportStillMeasuresWhatItCan() {
        String spineReport   = new TreeEcology(spine()).ecologyReport();
        String perfectReport = new TreeEcology(perfect()).ecologyReport();

        // The species-area PREDICTION is a function of n and is kept, labelled as a prediction.
        assertTrue(spineReport.contains("Predicted S"), spineReport);
        assertTrue(spineReport.contains("not a measurement"), spineReport);

        // And the numbers the sixth pass made real are still real.
        assertTrue(spineReport.contains("Split J'  = 0.0000"), spineReport);
        assertTrue(perfectReport.contains("Split J'  = 1.0000"), perfectReport);
        assertTrue(spineReport.contains("H'"), spineReport);
        assertTrue(spineReport.contains("Mitochondrial Eve"), spineReport);
        assertTrue(spineReport.contains("Broken-Stick Deviation"), spineReport);
    }

    // ── Finding 7: the published residency seam ─────────────────────────────────────────

    @Test
    @DisplayName("CacheEvolutionLoop.resident() answers for the serving primary, and does not bump recency")
    void residentSeamIsExercised() {
        CacheEvolutionLoop loop = new CacheEvolutionLoop(
                8, List.of(CacheGenome.of(0, 1)), 1, 1, MorphPolicy.defaults(), 7L);

        for (int k = 0; k < 8; k++) loop.lookup(k);
        for (int k = 0; k < 8; k++) {
            assertTrue(loop.resident(k), "key " + k + " was just admitted into a capacity-8 cache");
        }
        assertFalse(loop.resident(999), "a key never referenced is not resident");

        // A residency probe must be a pure read: peeking at the oldest key must not save it
        // from the eviction that the next admission causes.
        assertTrue(loop.resident(0));
        assertTrue(loop.resident(0));
        loop.lookup(100);
        assertFalse(loop.resident(0),
                "resident() must not bump recency — the seam exists so an external value cache "
                        + "can trim itself to the champion's real contents");
        assertTrue(loop.resident(100));
    }
}
