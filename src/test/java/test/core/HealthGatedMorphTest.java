package test.core;

import core.MutableTree;
import core.TreeContext;
import core.TreeNode1;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Health-gated morph (DESIGN §3.4): a strategy switch builds the candidate aside,
 * validates it, and only swaps it in on a full pass. A failed validation keeps the
 * incumbent untouched — no data loss.
 */
@DisplayName("Health-gated morph")
public class HealthGatedMorphTest {

    private static TreeContext rbWith(int... vs) {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int v : vs) ctx.add(v);
        return ctx;
    }

    @Test
    @DisplayName("a valid morph is accepted and preserves contents")
    void validMorphAccepted() {
        TreeContext ctx = rbWith(50, 20, 80, 10, 30, 60, 90, 5, 25);
        List<Integer> before = ctx.inOrder();

        boolean morphed = ctx.setStrategy(new AVLStrategy<>());

        assertTrue(morphed, "valid morph should be accepted");
        assertEquals("AVLStrategy", ctx.getTree().getStrategy().getClass().getSimpleName());
        assertEquals(before, ctx.inOrder(), "contents must be preserved across a morph");
        assertEquals(before.size(), ctx.getSize());
    }

    @Test
    @DisplayName("morph to the same strategy class is a no-op")
    void sameStrategyNoMorph() {
        TreeContext ctx = rbWith(1, 2, 3);
        assertFalse(ctx.setStrategy(new RedBlackStrategy<>()), "same strategy class → no morph");
        assertEquals("RedBlackStrategy", ctx.getTree().getStrategy().getClass().getSimpleName());
    }

    @Test
    @DisplayName("a broken strategy is rejected and the incumbent is kept intact")
    void brokenMorphRejected() {
        TreeContext ctx = rbWith(50, 20, 80, 10, 30, 60, 90);
        List<Integer> before = ctx.inOrder();

        boolean morphed = ctx.setStrategy(new DroppingStrategy());

        assertFalse(morphed, "a strategy that loses data must be rejected by the health gate");
        // Incumbent untouched: still RB, same contents and size.
        assertEquals("RedBlackStrategy", ctx.getTree().getStrategy().getClass().getSimpleName());
        assertEquals(before, ctx.inOrder(), "rejected morph must not alter the live tree");
        assertEquals(before.size(), ctx.getSize());
    }

    @Test
    @DisplayName("Splay is accepted (no balance invariant required)")
    void splayMorphAccepted() {
        TreeContext ctx = rbWith(7, 3, 11, 1, 5, 9, 13);
        List<Integer> before = ctx.inOrder();
        assertTrue(ctx.setStrategy(new SplayStrategy<>()));
        assertEquals(before, ctx.inOrder());
    }

    @Test
    @DisplayName("facade auto-morph is off by default and toggleable")
    void autoMorphOffByDefault() {
        TreeContext ctx = rbWith(1, 2, 3);
        assertFalse(ctx.isAutoMorphEnabled(), "auto-morph must default to off");
        ctx.setAutoMorphEnabled(true);
        assertTrue(ctx.isAutoMorphEnabled());
        // Morph authority is single by default: the facade does not self-morph.
        ctx.setAutoMorphEnabled(false);
        assertFalse(ctx.isAutoMorphEnabled());
    }

    /**
     * A deliberately broken strategy whose insert is a no-op, so the candidate it
     * builds ends up empty — the health gate must catch the size/content mismatch.
     */
    static final class DroppingStrategy implements TreeStrategy<Integer> {
        @Override public void insert(MutableTree<Integer> tree, TreeNode1<Integer> node) { /* drops everything */ }
        @Override public void fixInsert(MutableTree<Integer> tree, TreeNode1<Integer> node) { }
        @Override public void delete(MutableTree<Integer> tree, TreeNode1<Integer> node) { }
        @Override public TreeNode1<Integer> search(MutableTree<Integer> tree, Integer value) { return tree.getNIL(); }
    }
}
