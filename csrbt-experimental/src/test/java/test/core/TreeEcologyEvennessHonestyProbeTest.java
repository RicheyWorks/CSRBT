package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.experimental.TreeEcology;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (audit 2026-08-09 EC-3, deep-sweep E-1): {@code shannonEvenness()} is Pielou's
 * J' asked of the tree's stored keys, and a BST stores each key exactly once — so every
 * species has abundance 1, S = n, H' = ln n, and J' is 1.0 for every tree that has ever
 * existed. The formula is right and the sample is wrong: the stored key set is a species
 * <i>list</i> (incidence data), and abundance-based evenness is not defined on incidence
 * data (Magurran 2004, ch. 2). The sixth pass stopped {@code rKScore()} from depending on
 * the constant (finding 27, {@code subtreeEvenness()}), but the accessor was still public
 * and the constant was still printed in {@code ecologyReport()}'s Shannon block, next to
 * real numbers, for a classroom audience.
 *
 * <p>The settlement is API honesty rather than a quiet redefinition: the accessor keeps
 * its value and is deprecated onto the two instruments that do measure something
 * ({@code CommunityMetrics.pielouEvenness} over access abundances;
 * {@code subtreeEvenness()} over structure), and the report says in words why no species
 * evenness is quoted, while printing the structural split evenness where it is used.</p>
 *
 * <p>These tests pin all three halves of that: the constant is still the constant (so the
 * documentation cannot silently rot), the API carries the warning, and the report no
 * longer shows a number that is the same for the best and the worst tree a BST can be.</p>
 */
@DisplayName("TreeEcology evenness — the constant is labelled, and the report measures")
class TreeEcologyEvennessHonestyProbeTest {

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

    @Test
    @DisplayName("shannonEvenness() is 1.0 for the best and the worst tree alike — the defect itself")
    @SuppressWarnings("deprecation")
    void shannonEvennessIsStructurallyConstant() {
        // Not a fix under test — the premise. If this ever stops holding, the deprecation
        // note and the report wording are both wrong and must be revisited together.
        assertEquals(1.0, new TreeEcology(spine()).shannonEvenness(), 1e-12);
        assertEquals(1.0, new TreeEcology(perfect()).shannonEvenness(), 1e-12);

        TreeContext singleton = new TreeContext(new RedBlackStrategy<>());
        singleton.add(42);
        assertEquals(1.0, new TreeEcology(singleton).shannonEvenness(), 1e-12);
        assertEquals(1.0, new TreeEcology(new TreeContext(new RedBlackStrategy<>())).shannonEvenness(), 1e-12);
    }

    @Test
    @DisplayName("the accessor is deprecated, so a caller is told before they quote it")
    void shannonEvennessIsDeprecated() throws NoSuchMethodException {
        assertTrue(TreeEcology.class.getMethod("shannonEvenness").isAnnotationPresent(Deprecated.class),
                "a public accessor that can only return 1.0 must carry the warning in the API, "
                        + "not only in an audit document");
        assertFalse(TreeEcology.class.getMethod("subtreeEvenness").isAnnotationPresent(Deprecated.class),
                "the structural replacement is the thing callers are being sent to");
    }

    @Test
    @DisplayName("ecologyReport() prints no species-evenness number at all")
    void reportQuotesNoConstantEvenness() {
        // "Evenness  = 1.0000" appeared identically on both trees below — the report's own
        // Shannon block was the delivery mechanism for the defect.
        Pattern quoted = Pattern.compile("Evenness\\s*=\\s*[0-9]");
        for (TreeContext ctx : new TreeContext[]{ spine(), perfect() }) {
            String report = new TreeEcology(ctx).ecologyReport();
            assertFalse(quoted.matcher(report).find(),
                    "a constant must not be formatted as a measurement:\n" + report);
            assertTrue(report.contains("Evenness"),
                    "the omission must be explained, not silent:\n" + report);
            assertTrue(report.contains("abundance 1"),
                    "the report must say why there is no evenness figure:\n" + report);
        }
    }

    @Test
    @DisplayName("the evenness the report does show varies with the tree it describes")
    void reportShowsAMeasuredEvenness() {
        String spineReport   = new TreeEcology(spine()).ecologyReport();
        String perfectReport = new TreeEcology(perfect()).ecologyReport();

        String spineJ   = splitJ(spineReport);
        String perfectJ = splitJ(perfectReport);
        assertNotEquals(spineJ, perfectJ,
                "the best and the worst BST must not read the same:\n" + spineReport + perfectReport);
        assertEquals("0.0000", spineJ, "every split of a spine strands one side");
        assertEquals("1.0000", perfectJ, "every split of a perfect tree halves the population");
    }

    /** The structural split-evenness figure as the report formats it. */
    private static String splitJ(String report) {
        var m = Pattern.compile("Split J'\\s*=\\s*([0-9.]+)").matcher(report);
        assertTrue(m.find(), "report carries no structural evenness figure:\n" + report);
        return m.group(1);
    }
}
