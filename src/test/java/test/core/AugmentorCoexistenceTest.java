package test.core;

import core.TreeContext;
import core.TreeNode1;
import core.augment.IntervalAugmentor;
import core.strategy.RedBlackStrategy;
import core.util.OrderStatisticsOps;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

/**
 * ADR-002 step — intrinsic subtree size vs. the pluggable augment slot.
 *
 * Subtree size used to live in the SAME int field (augmentedValue) that the
 * pluggable augmentor writes, so order statistics and interval augmentation were
 * mutually exclusive: installing {@link IntervalAugmentor} made augmentedValue
 * hold max-hi, and {@link OrderStatisticsOps} then read that max-hi as if it were
 * a node count.
 *
 * Size is now an intrinsic node attribute ({@link TreeNode1#getSize()}), maintained
 * like height / black-height and independent of the augmentor. These tests prove
 * order statistics and interval max-hi now COEXIST on one tree, and that intrinsic
 * size stays correct through inserts and deletes.
 *
 * Pre-fix, every order-statistics assertion below would fail (or throw out-of-bounds)
 * because subtreeSize() returned the interval max-hi instead of the node count.
 */
@DisplayName("Intrinsic subtree size coexists with a custom augmentor (ADR-002)")
public class AugmentorCoexistenceTest {

    /** los = {5,10,15,17,25}; global max-hi = 30 (from the [10,30] interval). */
    private static TreeContext intervalTree() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy());
        IntervalAugmentor.insertInterval(ctx, 15, 20);
        IntervalAugmentor.insertInterval(ctx, 10, 30);
        IntervalAugmentor.insertInterval(ctx, 5, 8);
        IntervalAugmentor.insertInterval(ctx, 25, 27);
        IntervalAugmentor.insertInterval(ctx, 17, 19);
        return ctx;
    }

    @Test
    @DisplayName("order statistics run correctly on an interval-augmented tree")
    void orderStatisticsCoexistWithInterval() {
        TreeContext ctx = intervalTree();
        TreeNode1 root = ctx.getTree().getRoot();

        // Interval augmentation is live: max-hi sits in augmentedValue.
        assertEquals(30, root.getAugmentedValue(), "root max-hi must be 30");

        // Intrinsic size is the node count, NOT the max-hi.
        assertEquals(5, root.getSize(), "intrinsic subtree size = node count");
        assertEquals(ctx.getSize(), root.getSize(), "node size agrees with context count");

        // Order statistics over the LO keys {5,10,15,17,25} — correct only because
        // SELECT / RANK now read intrinsic size, not the max-hi in augmentedValue.
        OrderStatisticsOps os = new OrderStatisticsOps(ctx.getTree());
        assertEquals(5,  os.select(1).getData(), "select(1) = min lo");
        assertEquals(10, os.select(2).getData());
        assertEquals(15, os.select(3).getData());
        assertEquals(17, os.select(4).getData());
        assertEquals(25, os.select(5).getData(), "select(5) = max lo");

        assertEquals(1, os.rank(5));
        assertEquals(3, os.rank(15));
        assertEquals(5, os.rank(25));

        assertEquals(15, os.median().getData(), "median lo");
        assertEquals(3, os.countInRange(10, 17), "los in [10,17] = {10,15,17}");
        assertEquals(5, os.countInRange(5, 25));

        // ...and interval search still works at the same time.
        TreeNode1 hit = IntervalAugmentor.intervalSearch(ctx, 29, 31);
        assertFalse(hit.isNil(), "must still find the [10,30] overlap");
        assertEquals(10, hit.getData(), "overlapping interval lo = 10");
    }

    @Test
    @DisplayName("intrinsic size stays correct through deletes under the interval augmentor")
    void sizeCorrectAfterDeleteWithInterval() {
        TreeContext ctx = intervalTree();
        ctx.remove(15);   // drop interval [15,20]; los now {5,10,17,25}

        TreeNode1 root = ctx.getTree().getRoot();
        assertEquals(4, root.getSize(), "size tracks the delete");
        assertEquals(ctx.getSize(), root.getSize());
        assertEquals(30, root.getAugmentedValue(), "max-hi still 30 (from [10,30])");

        OrderStatisticsOps os = new OrderStatisticsOps(ctx.getTree());
        assertEquals(5,  os.select(1).getData());
        assertEquals(10, os.select(2).getData());
        assertEquals(17, os.select(3).getData());
        assertEquals(25, os.select(4).getData());
        assertEquals(4, os.countInRange(0, 100));
    }

    @Test
    @DisplayName("under the default augmentor, intrinsic size mirrors augmentedValue")
    void defaultAugmentorSizeMatches() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy());
        for (int v : new int[]{50, 20, 80, 10, 30, 70, 90, 5}) ctx.add(v);

        TreeNode1 root = ctx.getTree().getRoot();
        assertEquals(8, root.getSize());
        // The default augmentor writes subtree size into augmentedValue, so the
        // intrinsic field and the augment slot agree under the default.
        assertEquals(root.getSize(), root.getAugmentedValue(),
                "default augmentor mirrors subtree size");

        OrderStatisticsOps os = new OrderStatisticsOps(ctx.getTree());
        assertEquals(5,  os.select(1).getData());
        assertEquals(90, os.select(8).getData());
        assertEquals(30, os.median().getData());
    }
}
