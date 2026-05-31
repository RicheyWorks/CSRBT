package test.core;

import core.TreeContext;
import core.TreeNode1;
import core.augment.IntervalAugmentor;
import core.strategy.RedBlackStrategy;
import core.util.TreeCloner;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Regression for backend finding B2: TreeCloner.snapshot must preserve a
 * non-default augmentor, so cloned/checkpointed interval trees keep correct
 * max-hi values rather than silently reverting to subtree-size augmentation.
 */
@DisplayName("Clone preserves augmentor (B2)")
public class CloneAugmentorTest {

    private static TreeContext intervalTree() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy());
        IntervalAugmentor.insertInterval(ctx, 15, 20);
        IntervalAugmentor.insertInterval(ctx, 10, 30);   // small lo, large hi
        IntervalAugmentor.insertInterval(ctx, 5, 8);
        IntervalAugmentor.insertInterval(ctx, 25, 27);
        return ctx;
    }

    @Test
    @DisplayName("snapshot keeps interval max-hi and overlap search")
    void snapshotKeepsIntervalAugment() {
        TreeContext ctx = intervalTree();
        assertEquals(30, ctx.getTree().getRoot().getAugmentedValue(), "precondition");

        TreeContext clone = new TreeCloner(ctx).snapshot();

        assertEquals(30, clone.getTree().getRoot().getAugmentedValue(),
                "clone root max-hi must be 30, not the subtree size");
        TreeNode1 hit = IntervalAugmentor.intervalSearch(clone, 29, 31);
        assertNotNull(hit);
        assertFalse(hit.isNil(), "clone must still find the [10,30] overlap");
        assertEquals(4, clone.getSize());
    }

    @Test
    @DisplayName("clone is independent of the original")
    void cloneIsIndependent() {
        TreeContext ctx = intervalTree();
        TreeContext clone = new TreeCloner(ctx).snapshot();

        clone.add(100);                       // mutate the clone only
        assertTrue(clone.contains(100));
        assertFalse(ctx.contains(100), "original must be unaffected by clone mutation");
    }

    @Test
    @DisplayName("checkpoint restore (which clones) keeps interval data")
    void checkpointKeepsIntervalAugment() {
        TreeContext ctx = intervalTree();
        ctx.getHistory().saveCheckpoint("base");   // snapshots via TreeCloner
        ctx.getHistory().restoreCheckpoint("base");

        assertEquals(30, ctx.getTree().getRoot().getAugmentedValue(),
                "restored checkpoint must retain max-hi = 30");
    }
}
