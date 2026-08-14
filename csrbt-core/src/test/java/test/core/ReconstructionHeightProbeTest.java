package test.core;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.util.TreeCloner;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe for the 2026-08-14 stale-height fix: {@code recomputeAugmentAndPropagate}
 * refreshed size/augment to the root but never heights, so every tree wired top-down
 * or in arbitrary order — snapshot deserialization ({@code deserializePreOrder}) and
 * two-pass deep copy ({@code TreeCloner.deepCopyTwoPass}) — converged to correct sizes
 * with STALE cached heights. AVL/Hybrid then computed balance factors against those
 * stale off-path values and genuinely violated their own invariant on the next insert
 * (probe-confirmed pre-fix: 30/30 clone seeds, 20/30 load seeds within 300 inserts).
 * The fix rides height + black-height on the same propagation walk as sizes.
 */
class ReconstructionHeightProbeTest {

    /** Real height by full recursion — the measured truth cached heights must match. */
    private static int realHeight(TreeNode1<Integer> n) {
        if (n == null || n.isNil()) return 0;
        return 1 + Math.max(realHeight(n.getLeft()), realHeight(n.getRight()));
    }

    /** Assert every node's cached height equals its real height. Returns nodes checked. */
    private static int assertHeightsFresh(TreeNode1<Integer> n, String where) {
        if (n == null || n.isNil()) return 0;
        assertEquals(realHeight(n), n.getHeight(),
                where + ": stale cached height at node " + n.getData());
        return 1 + assertHeightsFresh(n.getLeft(), where) + assertHeightsFresh(n.getRight(), where);
    }

    /** Max |balance factor| over the whole tree, from REAL (recomputed) heights. */
    private static int maxRealImbalance(TreeNode1<Integer> n) {
        if (n == null || n.isNil()) return 0;
        int here = Math.abs(realHeight(n.getLeft()) - realHeight(n.getRight()));
        return Math.max(here, Math.max(maxRealImbalance(n.getLeft()), maxRealImbalance(n.getRight())));
    }

    @Test
    @DisplayName("snapshot load: cached heights are fresh, and 300 inserts keep AVL balanced")
    void snapshotLoadKeepsAvlHealthy() {
        Random rng = new Random(11);
        TreeContext ctx = new TreeContext(new AVLStrategy<>());
        while (ctx.getSize() < 150) ctx.add(rng.nextInt(10_000));

        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String name = "height-probe-avl";
        try {
            io.saveSnapshot(name, ctx);
            TreeContext loaded = io.loadSnapshot(name);
            assertEquals(ctx.inOrder(), loaded.inOrder());

            MutableTree<Integer> tree = loaded.getTree();
            int checked = assertHeightsFresh(tree.getRoot(), "after load");
            assertEquals(loaded.getSize(), checked);

            for (int i = 0; i < 300; i++) {
                loaded.add(rng.nextInt(20_000));
                assertTrue(maxRealImbalance(tree.getRoot()) <= 1,
                        "AVL invariant violated after insert #" + (i + 1)
                                + " on a loaded snapshot");
            }
            assertHeightsFresh(tree.getRoot(), "after load + 300 inserts");
        } finally {
            io.deleteSnapshot(name);
        }
    }

    @Test
    @DisplayName("clone army: cached heights are fresh, and one insert per clone stays balanced")
    void cloneArmyKeepsAvlHealthy() {
        for (long seed = 1; seed <= 10; seed++) {
            Random rng = new Random(seed);
            TreeContext ctx = new TreeContext(new AVLStrategy<>());
            while (ctx.getSize() < 150) ctx.add(rng.nextInt(10_000));

            List<TreeContext> army = new TreeCloner(ctx).deployCloneArmy(1);
            TreeContext clone = army.get(0);
            assertEquals(ctx.inOrder(), clone.inOrder());
            assertHeightsFresh(clone.getTree().getRoot(), "clone (seed " + seed + ")");

            // Pre-fix this single insert produced |bf| violations up to 5, every seed.
            clone.add(20_000 + (int) seed);
            assertTrue(maxRealImbalance(clone.getTree().getRoot()) <= 1,
                    "AVL invariant violated by one insert on a clone (seed " + seed + ")");
        }
    }

    @Test
    @DisplayName("hybrid snapshot round-trip stays sound under continued inserts")
    void hybridSnapshotRoundTrip() {
        Random rng = new Random(7);
        TreeContext ctx = new TreeContext(new HybridStrategy<>());
        while (ctx.getSize() < 120) ctx.add(rng.nextInt(10_000));

        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String name = "height-probe-hybrid";
        try {
            io.saveSnapshot(name, ctx);
            TreeContext loaded = io.loadSnapshot(name);
            assertHeightsFresh(loaded.getTree().getRoot(), "hybrid after load");
            for (int i = 0; i < 200; i++) loaded.add(rng.nextInt(20_000));
            // Hybrid's balance comes from its AVL phase; same bound applies.
            assertTrue(maxRealImbalance(loaded.getTree().getRoot()) <= 1,
                    "Hybrid balance violated after inserts on a loaded snapshot");
            assertHeightsFresh(loaded.getTree().getRoot(), "hybrid after load + inserts");
        } finally {
            io.deleteSnapshot(name);
        }
    }
}
