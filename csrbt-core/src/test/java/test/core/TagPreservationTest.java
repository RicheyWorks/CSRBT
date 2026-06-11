package test.core;

import core.TreeContext;
import core.TreeNode1;
import core.augment.IntervalAugmentor;
import core.persistence.FilePersistenceAdapter;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Per-node tags (interval high endpoints) must survive operations that rebuild
 * the backing tree from an in-order traversal: adaptive strategy morph, and
 * snapshot save/load. Before this fix only the int keys survived, so interval
 * trees silently degraded to point intervals.
 */
@DisplayName("Tag preservation across rebuilds")
public class TagPreservationTest {

    private static TreeContext intervalTree() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        IntervalAugmentor.insertInterval(ctx, 15, 20);
        IntervalAugmentor.insertInterval(ctx, 10, 30);   // small lo, large hi
        IntervalAugmentor.insertInterval(ctx, 5, 8);
        IntervalAugmentor.insertInterval(ctx, 25, 27);
        IntervalAugmentor.insertInterval(ctx, 17, 19);
        return ctx;
    }

    // ── Morph ────────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("Adaptive morph keeps interval data")
    class Morph {

        @Test
        @DisplayName("max-hi and overlap search survive a strategy morph")
        void morphPreservesIntervals() {
            TreeContext ctx = intervalTree();
            assertEquals(30, ctx.getTree().getRoot().getAugmentedValue(),
                    "precondition: root max-hi is 30 before morph");

            ctx.setStrategy(new AVLStrategy<>());   // rebuilds the whole tree

            assertEquals(30, ctx.getTree().getRoot().getAugmentedValue(),
                    "root max-hi must still be 30 after morph (tags preserved)");

            TreeNode1<Integer> hit = IntervalAugmentor.intervalSearch(ctx, 29, 31);
            assertNotNull(hit);
            assertFalse(hit.isNil(), "the [10,30] interval must still be found post-morph");
            assertEquals(5, ctx.getSize());
        }
    }

    // ── Snapshot ───────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("Snapshots persist tags")
    class Snapshot {

        @Test
        @DisplayName("interval high endpoints round-trip through save/load")
        void snapshotPreservesTags() {
            TreeContext ctx = intervalTree();
            FilePersistenceAdapter io = new FilePersistenceAdapter();
            String name = "tag-roundtrip";
            try {
                io.saveSnapshot(name, ctx);
                TreeContext loaded = io.loadSnapshot(name);
                assertNotNull(loaded);

                // The snapshot records the augmentor identity (B7), so an interval
                // tree round-trips with correct max-hi WITHOUT a manual setAugmentor.
                assertEquals(30, loaded.getTree().getRoot().getAugmentedValue(),
                        "restored interval augmentor must reproduce max-hi = 30");

                TreeNode1<Integer> hit = IntervalAugmentor.intervalSearch(loaded, 29, 31);
                assertTrue(hit != null && !hit.isNil(),
                        "overlap search works on the reloaded interval tree");
            } finally {
                io.deleteSnapshot(name);
            }
        }
    }
}
