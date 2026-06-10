package test.core;

import core.RedBlackTree;
import core.control.CostModelStrategyScorer;
import core.control.MorphPolicy;
import core.control.RollingWorkloadMonitor;
import core.control.StrategyId;
import core.ensemble.EnsembleController;
import core.ensemble.EnsembleController.PromotionResult;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleOrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * EnsembleController (ADR-003, step E2): measured promotion via the reused control plane
 * (monitor -> cost-model scorer -> anti-thrash policy) with the executor swapped for the ensemble's
 * O(1) atomic primary swap. The headline test drives a skewed read stream and asserts the Splay
 * member is promoted <em>exactly once</em>, with <em>no rebuild</em> -- the promoted member's engine
 * is the same instance it always was, and every member is still an exact mirror of the logical set.
 */
@DisplayName("EnsembleController -- measured promotion, O(1) swap (E2)")
public class EnsembleControllerTest {

    private static EnsembleOrderedSet<Integer> rbAvlSplay() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())   // initial primary
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .build();
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String simpleName) {
        for (EnsembleMember<Integer> m : ens.members()) {
            if (m.strategyName().equals(simpleName)) return m;
        }
        throw new AssertionError("no member backed by " + simpleName);
    }

    @Test
    @DisplayName("a skewed read stream promotes the Splay member exactly once, with no rebuild")
    void skewedReadsPromoteSplayWithoutRebuild() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        // Small window so the read burst quickly dominates the decayed view.
        RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
        // Eager-but-stable: no cooldown wait, 20% margin, 2 consecutive wins before a switch.
        MorphPolicy policy = new MorphPolicy(0, 0.20, 2);
        EnsembleController<Integer> ctl =
                new EnsembleController<>(ens, monitor, new CostModelStrategyScorer(), policy);

        // Splay starts as a non-primary mirror; capture its engine to prove "no rebuild".
        EnsembleMember<Integer> splay = memberNamed(ens, "SplayStrategy");
        RedBlackTree<Integer> splayEngineBefore = splay.orderedSet().getEngine();
        assertSame(memberNamed(ens, "RedBlackStrategy"), ens.primary(), "RB is the initial primary");

        TreeSet<Integer> oracle = new TreeSet<>();

        // Seed a population (effective writes).
        for (int i = 0; i < 200; i++) { ctl.add(i); oracle.add(i); }

        // A heavily skewed, read-dominated stream: hammer one hot key, evaluate each round.
        final int HOT = 7;
        int promotions = 0;
        StrategyId promotedTo = null;
        for (int round = 0; round < 12; round++) {
            for (int i = 0; i < 300; i++) ctl.contains(HOT);   // hot-key reads
            PromotionResult r = ctl.evaluateAndMaybePromote(300);
            if (r.promoted()) { promotions++; promotedTo = r.to(); }
        }

        assertEquals(1, promotions, "a skewed read stream should promote exactly once");
        assertEquals(StrategyId.SPLAY, promotedTo, "the promotion target is the Splay member");
        assertSame(splay, ens.primary(), "Splay is now serving reads");

        // No rebuild: the promoted member's engine is the very same instance -- promote() is a
        // pointer swap, never OrderedSet.setStrategy()'s build-aside.
        assertSame(splayEngineBefore, splay.orderedSet().getEngine(),
                "promotion must not rebuild the member's engine");

        // Contents intact across the swap -- on the new primary and as a mirror on every member.
        List<Integer> sorted = new ArrayList<>(oracle);
        assertEquals(sorted, ens.inOrder(), "contents preserved after promotion");
        for (EnsembleMember<Integer> m : ens.members()) {
            assertEquals(sorted, m.set().inOrder(), m.strategyName() + " is still an exact mirror");
        }
    }

    @Test
    @DisplayName("a uniform write-heavy stream holds Red-Black (no needless promotion)")
    void writeHeavyHoldsRedBlack() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
        EnsembleController<Integer> ctl = new EnsembleController<>(
                ens, monitor, new CostModelStrategyScorer(), new MorphPolicy(0, 0.20, 2));

        EnsembleMember<Integer> rb = memberNamed(ens, "RedBlackStrategy");

        int promotions = 0;
        for (int round = 0; round < 10; round++) {
            for (int i = 0; i < 300; i++) ctl.add(round * 300 + i);   // distinct, skew-free writes
            PromotionResult r = ctl.evaluateAndMaybePromote(300);
            if (r.promoted()) promotions++;
        }

        assertEquals(0, promotions, "a write-heavy, skew-free stream keeps Red-Black");
        assertSame(rb, ens.primary(), "Red-Black is still primary");
    }

    @Test
    @DisplayName("promote() is an O(1) primary swap that preserves the mirror")
    void promoteSwapsPrimaryInPlace() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        for (int v : new int[]{50, 20, 80, 10, 30, 60, 90}) ens.add(v);

        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");
        RedBlackTree<Integer> avlEngineBefore = avl.orderedSet().getEngine();

        assertTrue(ens.promote(avl), "promoting a non-primary member changes the primary");
        assertSame(avl, ens.primary(), "AVL now serves reads");
        assertSame(avlEngineBefore, avl.orderedSet().getEngine(), "no rebuild on promote");
        assertFalse(ens.promote(avl), "promoting the current primary is a no-op");

        // Reads now come from AVL but answer identically (mirror invariant holds).
        assertEquals(List.of(10, 20, 30, 50, 60, 80, 90), ens.inOrder(), "order intact after the swap");
    }
}
