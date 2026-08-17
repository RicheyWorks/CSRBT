package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.experimental.TreeEcology;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (bug audit 2026-08-17, finding 27): {@code rKScore()} documents the range
 * [-1, +1] and {@code rKLabel()} names five bands across it, but a quarter of the weight
 * was {@code shannonEvenness()}, which is identically 1.0 on a duplicate-free BST
 * (audit 2026-08-09 EC-3, deep-sweep E-1). That constant +0.25 put a hard floor at
 * -0.5, so the "strongly r-selected" band was unreachable: a maximally degenerate
 * 15-node spine — the worst shape a BST can take — scored -0.4997 and was labelled
 * "weakly r-selected". The range and its labels described a score that did not exist.
 *
 * <p>The fix replaces the degenerate term with {@code subtreeEvenness()}, which measures
 * what the comment always claimed — the evenness of the subtree-size splits. These tests
 * pin both ends of the documented range to the shapes that should reach them, and pin the
 * middle too: dropping the term and reweighting the survivors would also have opened the
 * bottom band, but by pushing ordinary balanced trees into it.</p>
 */
@DisplayName("TreeEcology.rKScore — both ends of the documented range are reachable")
class TreeEcologyRkRangeProbeTest {

    @Test
    @DisplayName("a maximally degenerate spine scores at the bottom and reads strongly r-selected")
    void degenerateSpineHitsBottomBand() {
        // Splay tree, keys in ascending order: every insert splays the new maximum to the
        // root, leaving the rest hanging as a left spine — height n, the worst BST shape.
        TreeContext ctx = new TreeContext(new SplayStrategy<>());
        for (int k = 1; k <= 15; k++) ctx.add(k);

        TreeEcology eco = new TreeEcology(ctx);
        double score = eco.rKScore();
        assertEquals(0.0, eco.subtreeEvenness(), 1e-9, "every split strands one side");
        assertTrue(score >= -1.0 && score <= 1.0, "documented range is [-1, +1]; got " + score);
        assertTrue(score < -0.5,
                "the most pathological shape must reach the bottom band; got " + score);
        assertTrue(eco.rKLabel().startsWith("strongly r-selected"),
                "expected the bottom label, got: " + eco.rKLabel());
    }

    @Test
    @DisplayName("a perfect 15-node tree scores at the top and reads strongly K-selected")
    void perfectTreeHitsTopBand() {
        // Level order: a perfect BST shape that Red-Black builds without a single rotation.
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int k : new int[]{ 8, 4, 12, 2, 6, 10, 14, 1, 3, 5, 7, 9, 11, 13, 15 }) ctx.add(k);

        TreeEcology eco = new TreeEcology(ctx);
        assertEquals(1.0, eco.subtreeEvenness(), 1e-9, "every split halves the population");
        assertEquals(1.0, eco.rKScore(), 1e-9,
                "minimal height and every slot filled is the top of the range");
        assertTrue(eco.rKLabel().startsWith("strongly K-selected"),
                "expected the top label, got: " + eco.rKLabel());
    }

    @Test
    @DisplayName("an ordinary randomly-built tree stays in the middle bands, not the bottom one")
    void ordinaryTreeStaysMidRange() {
        // The bottom band names splay-like pathology; a healthy Red-Black tree must not
        // land in it just because the score was rebalanced to reach that band at all.
        java.util.List<Integer> keys = new java.util.ArrayList<>();
        for (int k = 1; k <= 500; k++) keys.add(k);
        java.util.Collections.shuffle(keys, new java.util.Random(7));

        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int k : keys) ctx.add(k);

        TreeEcology eco = new TreeEcology(ctx);
        assertTrue(eco.subtreeEvenness() > 0.8,
                "a randomly built tree splits fairly evenly; got " + eco.subtreeEvenness());
        assertTrue(eco.rKScore() > -0.5,
                "a healthy tree must not read as splay-like pathology; got " + eco.rKScore());
    }
}
