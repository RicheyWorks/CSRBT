package test.core;

import core.RedBlackTree;
import core.TreeContext;
import core.TreeNode1;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-010 X1 — the strategy-aware repair gate. {@code TreeContext.selfRepair()} used to
 * short-circuit on {@code isValidRedBlack()} regardless of the current strategy: after a
 * morph to AVL/Splay/Hybrid, a perfectly healthy tree failed RB color discipline and every
 * repair call paid a needless O(n) rebuild. The gate now validates against the current
 * strategy via {@code StrategyHealthCheck}. Observable proof: {@code getTree()} returns the
 * <em>same engine instance</em> when the short-circuit fires, and a fresh one after a real
 * rebuild — no timers, no log scraping.
 */
@DisplayName("TreeContext.selfRepair — strategy-aware gate (ADR-010 X1)")
public class SelfRepairGateTest {

    private static TreeContext populated() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int i = 1; i <= 200; i++) ctx.add(i);
        return ctx;
    }

    @Test
    @DisplayName("a healthy RB tree short-circuits: same engine, no rebuild")
    void healthyRbShortCircuits() {
        TreeContext ctx = populated();
        RedBlackTree<Integer> engine = ctx.getTree();
        assertTrue(ctx.selfRepair());
        assertSame(engine, ctx.getTree(), "no rebuild on a healthy tree");
    }

    @Test
    @DisplayName("the fixed case: healthy morphed trees short-circuit instead of rebuilding")
    void healthyMorphedTreesShortCircuit() {
        TreeContext ctx = populated();

        assertTrue(ctx.setStrategy(new AVLStrategy<>()), "morph RB -> AVL");
        RedBlackTree<Integer> avlEngine = ctx.getTree();
        assertTrue(ctx.selfRepair());
        assertSame(avlEngine, ctx.getTree(),
                "a healthy AVL tree must not be rebuilt for failing RB color rules");

        assertTrue(ctx.setStrategy(new SplayStrategy<>()), "morph AVL -> Splay");
        RedBlackTree<Integer> splayEngine = ctx.getTree();
        assertTrue(ctx.selfRepair());
        assertSame(splayEngine, ctx.getTree(),
                "a healthy Splay tree must not be rebuilt either");
        assertEquals(200, ctx.getTree().size(), "contents untouched throughout");
    }

    @Test
    @DisplayName("a genuinely corrupted tree still repairs: fresh engine, invariant restored")
    void corruptionStillRepairs() {
        TreeContext ctx = populated();
        RedBlackTree<Integer> before = ctx.getTree();
        before.getRoot().setColor(TreeNode1.Color.RED);   // out-of-band: break root blackness

        assertTrue(ctx.selfRepair(), "repair rebuilds and validates");
        assertNotSame(before, ctx.getTree(), "the engine was rebuilt wholesale");
        assertEquals(200, ctx.getTree().size(), "no data loss");
        assertSame(TreeNode1.Color.BLACK, ctx.getTree().getRoot().getColor(),
                "the rebuilt tree satisfies the RB invariant again");
    }
}
