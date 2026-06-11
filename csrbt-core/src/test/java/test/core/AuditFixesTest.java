package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.augment.IntervalAugmentor;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Regression tests for the 2026-05-30 audit fixes (docs/code-audit-2026-05-30.md):
 *
 *   H1  TreeContext.size no longer drifts when duplicate keys are inserted, and
 *       a skipped duplicate does not record a phantom undo entry.
 *   H2  Interval-tree augmentation (max-hi) is maintained for nodes added after
 *       setAugmentor / via insertInterval, so interval search is correct.
 *   M2  A snapshot saved under HybridStrategy reloads as HybridStrategy.
 */
@DisplayName("Audit fix regressions (2026-05-30)")
public class AuditFixesTest {

    // ── H1  duplicate insert size / history ──────────────────────────────────

    @Nested
    @DisplayName("H1 duplicate inserts don't drift size or history")
    class DuplicateInserts {

        @Test
        @DisplayName("Re-adding an existing key leaves size unchanged")
        void sizeStable() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.add(10);
            ctx.add(20);
            ctx.add(10);   // duplicate
            ctx.add(20);   // duplicate
            ctx.add(30);

            assertEquals(3, ctx.getSize(), "size should count distinct keys only");
            assertEquals(List.of(10, 20, 30), ctx.inOrder());
        }

        @Test
        @DisplayName("A skipped duplicate records no undo entry, so undo can't delete a real key")
        void noPhantomHistory() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.add(5);
            int undoBefore = ctx.getHistory().undoDepth();
            ctx.add(5);    // duplicate — must not record anything
            assertEquals(undoBefore, ctx.getHistory().undoDepth(),
                    "duplicate add must not push an undo command");

            // The single real add is still undoable, and only it.
            assertTrue(ctx.getHistory().undo());
            assertEquals(0, ctx.getSize());
            assertFalse(ctx.contains(5));
        }
    }

    // ── H2  interval augmentation ────────────────────────────────────────────

    @Nested
    @DisplayName("H2 interval augmentation stays correct on later inserts")
    class IntervalAugmentation {

        @Test
        @DisplayName("subtree max-hi reflects high endpoints, not low endpoints")
        void maxHiMaintained() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            // Insert so that a node with a small lo carries a large hi deeper down.
            IntervalAugmentor.insertInterval(ctx, 15, 20);
            IntervalAugmentor.insertInterval(ctx, 10, 30);  // small lo, large hi
            IntervalAugmentor.insertInterval(ctx, 5, 8);
            IntervalAugmentor.insertInterval(ctx, 25, 27);

            TreeNode1<Integer> root = ctx.getTree().getRoot();
            // Root's augmented value must be the max hi across the whole tree (30),
            // which only holds if setTag-driven hi values were propagated.
            assertEquals(30, root.getAugmentedValue(),
                    "root max-hi must account for the [10,30] interval");
        }

        @Test
        @DisplayName("interval search finds an overlap that lives under a deep node")
        void searchFindsDeepOverlap() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            IntervalAugmentor.insertInterval(ctx, 17, 19);
            IntervalAugmentor.insertInterval(ctx, 5, 8);
            IntervalAugmentor.insertInterval(ctx, 21, 24);
            IntervalAugmentor.insertInterval(ctx, 4, 40);   // wide interval, small lo
            IntervalAugmentor.insertInterval(ctx, 15, 18);

            // Query [29,31] only overlaps [4,40]; the search must not be misled by
            // stale (size-based) augment values and must locate it.
            TreeNode1<Integer> hit = IntervalAugmentor.intervalSearch(ctx, 29, 31);
            assertNotNull(hit);
            assertFalse(hit.isNil(), "an overlapping interval exists and must be found");
            assertTrue(hit.getData() <= 31 && IntervalAugmentor.parseHi(hit) >= 29);
        }

        @Test
        @DisplayName("intervalSearchAll returns every overlap")
        void searchAll() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            IntervalAugmentor.insertInterval(ctx, 1, 5);
            IntervalAugmentor.insertInterval(ctx, 4, 9);
            IntervalAugmentor.insertInterval(ctx, 10, 12);
            IntervalAugmentor.insertInterval(ctx, 3, 3);

            // Point 4 is contained by [1,5] and [4,9].
            List<int[]> hits = IntervalAugmentor.stabQuery(ctx, 4);
            long count = hits.stream()
                    .filter(iv -> iv[0] <= 4 && iv[1] >= 4)
                    .count();
            assertEquals(2, count, "two intervals contain the point 4");
        }
    }

    // ── M2  Hybrid strategy round-trips through persistence ───────────────────

    @Nested
    @DisplayName("M2 snapshots preserve the Hybrid strategy")
    class HybridPersistence {

        @Test
        @DisplayName("a tree saved as Hybrid reloads as Hybrid, not RB")
        void hybridRoundTrip() {
            TreeContext ctx = new TreeContext(new HybridStrategy<>());
            for (int v : new int[]{8, 3, 12, 1, 6, 10, 14}) ctx.add(v);

            FilePersistenceAdapter io = new FilePersistenceAdapter();
            String name = "audit-hybrid-roundtrip";
            try {
                io.saveSnapshot(name, ctx);
                TreeContext loaded = io.loadSnapshot(name);
                assertNotNull(loaded);
                assertEquals("HybridStrategy",
                        loaded.getTree().getStrategy().getClass().getSimpleName());
                assertEquals(ctx.inOrder(), loaded.inOrder());
                assertEquals(ctx.getSize(), loaded.getSize());
            } finally {
                io.deleteSnapshot(name);
            }
        }
    }
}
