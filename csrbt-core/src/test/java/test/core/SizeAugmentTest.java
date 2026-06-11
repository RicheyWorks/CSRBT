package test.core;

import core.OrderedSet;
import core.RedBlackTree;
import core.TreeContext;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-009 P1 — O(1) {@code size()} via the size augment. {@code RedBlackTree.size()} now
 * reads {@code root.getSize()} — the same intrinsic metadata {@code select}/{@code rank}
 * have always trusted — instead of walking all n nodes. These tests pin size parity against
 * an oracle through every path that mutates structure: random churn, duplicate inserts and
 * misses, strategy morphs (full rebuilds), undo/redo replay, and clear. A drift between the
 * augment and the true count would also have been an order-statistics bug, so these double
 * as a regression floor for the augment itself.
 */
@DisplayName("RedBlackTree.size() — O(1) via the size augment (ADR-009 P1)")
public class SizeAugmentTest {

    @Test
    @DisplayName("size matches an oracle through random churn, duplicates, and misses")
    void sizeParityUnderChurn() {
        RedBlackTree<Integer> tree = RedBlackTree.withNaturalOrder(new RedBlackStrategy<Integer>());
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rnd = new Random(9_2026);

        for (int op = 1; op <= 4_000; op++) {
            int key = rnd.nextInt(600);            // dense range: plenty of duplicates/misses
            if (rnd.nextBoolean()) {
                tree.add(key);
                oracle.add(key);
            } else {
                tree.remove(key);
                oracle.remove(key);
            }
            assertEquals(oracle.size(), tree.size(), "op " + op);
        }
        assertEquals(oracle.size(), tree.inOrder().size(), "augment agrees with enumeration");
        tree.clear();
        assertEquals(0, tree.size(), "clear resets to the NIL sentinel's size");
    }

    @Test
    @DisplayName("size survives strategy morphs (full rebuilds) on the facade")
    void sizeParityAcrossMorphs() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < 1_000; i++) set.add(i * 3);

        assertTrue(set.setStrategy(new AVLStrategy<>()), "morph RB -> AVL");
        assertEquals(1_000, set.size());
        assertEquals(1_000, set.getEngine().size(), "engine path agrees after rebuild");

        assertTrue(set.setStrategy(new SplayStrategy<>()), "morph AVL -> Splay");
        set.remove(0);
        set.remove(999 * 3);
        assertEquals(998, set.size());
        assertEquals(998, set.getEngine().size());
    }

    @Test
    @DisplayName("size survives undo/redo replay on the Integer adapter")
    void sizeParityAcrossUndoRedo() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int i = 1; i <= 50; i++) ctx.add(i);
        assertEquals(50, ctx.getTree().size());

        ctx.remove(25);
        ctx.add(100);
        assertEquals(50, ctx.getTree().size());

        assertTrue(ctx.getHistory().undo());       // un-add 100
        assertEquals(49, ctx.getTree().size());
        assertTrue(ctx.getHistory().undo());       // un-remove 25
        assertEquals(50, ctx.getTree().size());
        assertTrue(ctx.getHistory().redo());       // re-remove 25
        assertEquals(49, ctx.getTree().size());
    }

    @Test
    @Timeout(10)
    @DisplayName("the before/after row: 20k size() calls on a 50k-key tree are effectively free")
    void sizeIsConstantTime() {
        RedBlackTree<Integer> tree = RedBlackTree.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < 50_000; i++) tree.add(i);

        long t0 = System.nanoTime();
        long checksum = 0;
        for (int i = 0; i < 20_000; i++) checksum += tree.size();
        long elapsed = System.nanoTime() - t0;

        assertEquals(20_000L * 50_000L, checksum);
        System.out.printf("ADR-009 P1: 20k size() calls on n=50k: %.2f ms "
                + "(O(n) traversal was ~1G node visits)%n", elapsed / 1e6);
        assertTrue(elapsed < 500_000_000L,
                "O(1) reads must not look like 20k full traversals: " + (elapsed / 1e6) + " ms");
    }
}
