package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.experimental.TreeEcology;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (bug audit 2026-08-12, deep sweep): {@code rKScore()} promises a score in
 * [-1, +1] but returned values far outside it. Two causes: (a) it read the node's
 * CACHED height, which only AVL/Hybrid maintain — under Red-Black a perfect 7-node
 * tree reports height 2 (true 3), driving {@code efficiency} above 1 (no lower clamp
 * on {@code h − hMin}) and {@code density = n/(2^h − 1)} above 1; (b) {@code hMin}
 * used {@code floor(log2(n+1))}, understating the true minimum height for every
 * non-perfect n, so optimally balanced trees were charged imbalance. Observed:
 * score 2.539 for the perfect 7-node RB tree. Fix: measure the height by traversal,
 * use {@code ceil}, and clamp both components into [0, 1].
 */
@DisplayName("TreeEcology.rKScore — stays inside its documented [-1, +1] range")
class TreeEcologyRkScoreProbeTest {

    @Test
    @DisplayName("a perfect 7-node RB tree scores within [-1, 1] and reads K-selected")
    void perfectTreeInRange() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int k : new int[]{4, 2, 6, 1, 3, 5, 7}) ctx.add(k);   // no rotations: perfect shape
        double score = new TreeEcology(ctx).rKScore();
        assertTrue(score >= -1.0 && score <= 1.0,
                "documented range is [-1, +1] but rKScore = " + score);
        assertTrue(score > 0.5,
                "a perfect tree is the strongest K-selected shape; score = " + score);
    }

    @Test
    @DisplayName("non-perfect sizes also stay in range")
    void nonPerfectSizesInRange() {
        for (int n : new int[]{2, 3, 5, 6, 10, 33}) {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int k = 1; k <= n; k++) ctx.add(k);               // RB keeps this balanced
            double score = new TreeEcology(ctx).rKScore();
            assertTrue(score >= -1.0 && score <= 1.0,
                    "n=" + n + ": rKScore = " + score + " is outside [-1, 1]");
        }
    }
}
