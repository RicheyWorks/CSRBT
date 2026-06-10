package test.core;

import core.OrderedSet;
import core.RedBlackTree;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleOrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-003 E5 benchmark: the ensemble's headline claim made concrete and assertable. Adapting a single
 * tree to a new strategy is an O(n) rebuild ({@code OrderedSet.setStrategy} builds a fresh engine and
 * re-inserts every key); adapting the ensemble is an O(1) primary swap (the winning member is already
 * warm). A StrategyBattleRunner-style comparison reduced to deterministic facts -- engine identity for
 * "rebuild vs swap", member sizes for the K-times steady-state write cost -- plus a wall-clock contrast
 * printed for reference.
 *
 * <p>Both sides adapt to AVL so the rebuilt tree stays O(log n) deep: the single-tree rebuild revalidates
 * via {@code StrategyHealthCheck}, whose invariant walks are recursive, so a deliberately degenerate
 * target (ascending inserts into a splay tree) would overflow the stack at large n -- a property of the
 * validator, not the ensemble. The ensemble's own Splay member is still built (it is never revalidated
 * or deeply recursed here).</p>
 */
@DisplayName("ADR-003 E5 -- ensemble (O(1) promote) vs single-tree morph (O(n) rebuild)")
public class EnsembleBenchmarkTest {

    private static OrderedSet<Integer> singleTree(int n) {
        OrderedSet<Integer> s = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < n; i++) s.add(i);
        return s;
    }

    private static EnsembleOrderedSet<Integer> ensemble(int n) {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())   // primary
                .member(() -> new AVLStrategy<Integer>())        // warm promotion target
                .member(() -> new SplayStrategy<Integer>())      // third member (k = 3)
                .build();
        for (int i = 0; i < n; i++) ens.add(i);
        return ens;
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String name) {
        for (EnsembleMember<Integer> m : ens.members()) if (m.strategyName().equals(name)) return m;
        throw new AssertionError("no member " + name);
    }

    @Test
    @DisplayName("single-tree morph rebuilds the engine (O(n)); ensemble promote swaps it (O(1))")
    void rebuildVsSwap() {
        final int n = 4000;

        // Single tree: setStrategy RB -> AVL builds a fresh engine and re-inserts every key.
        OrderedSet<Integer> single = singleTree(n);
        RedBlackTree<Integer> engineBefore = single.getEngine();
        assertTrue(single.setStrategy(new AVLStrategy<Integer>()), "morph applied");
        assertNotSame(engineBefore, single.getEngine(), "single-tree morph REBUILDS into a new engine");
        assertEquals(n, single.size(), "contents preserved across the rebuild");

        // Ensemble: promoting the warm AVL member is a pointer swap -- same engine, nothing rebuilt.
        EnsembleOrderedSet<Integer> ens = ensemble(n);
        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");
        RedBlackTree<Integer> avlEngineBefore = avl.orderedSet().getEngine();
        assertTrue(ens.promote(avl), "promotion applied");
        assertSame(avlEngineBefore, avl.orderedSet().getEngine(), "ensemble promote SWAPS: same engine, no rebuild");
        assertSame(avl, ens.primary(), "AVL now serves reads");
        assertEquals(n, ens.size(), "contents intact after the swap");
    }

    @Test
    @DisplayName("steady-state writes: the ensemble pays Kx fan-out for its O(1) adaptation")
    void steadyStateFanOut() {
        final int n = 2000;
        EnsembleOrderedSet<Integer> ens = ensemble(n);

        // Every one of the K members holds an exact copy -> Kx the write work of a single tree.
        int k = 0;
        for (EnsembleMember<Integer> m : ens.members()) {
            assertEquals(n, m.set().size(), m.strategyName() + " mirrors all writes");
            k++;
        }
        assertEquals(3, k, "k = 3 members");
        assertEquals(n, singleTree(n).size(), "the single tree does 1x the write work");
    }

    @Test
    @DisplayName("adaptation latency: an O(1) swap dwarfs an O(n) rebuild at scale")
    void adaptationLatency() {
        // Warm the JIT so the first large rebuild is not penalised by class-loading / compilation.
        for (int w = 0; w < 3; w++) {
            singleTree(500).setStrategy(new AVLStrategy<Integer>());
            EnsembleOrderedSet<Integer> e = ensemble(500);
            e.promote(memberNamed(e, "AVLStrategy"));
        }

        int[] sizes = {2000, 16000};
        long morphLarge = 0, promoteLarge = 0;
        System.out.println("[BENCHMARK ADR-003 E5] adaptation cost: single-tree morph (O(n) rebuild) vs ensemble promote (O(1) swap)");
        for (int n : sizes) {
            OrderedSet<Integer> single = singleTree(n);
            long t0 = System.nanoTime();
            single.setStrategy(new AVLStrategy<Integer>());
            long morphNs = System.nanoTime() - t0;

            EnsembleOrderedSet<Integer> ens = ensemble(n);
            EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");
            long t1 = System.nanoTime();
            ens.promote(avl);
            long promoteNs = System.nanoTime() - t1;

            System.out.printf("  n=%-6d  morph(rebuild)=%9.1f us   promote(swap)=%9.3f us%n",
                    n, morphNs / 1000.0, promoteNs / 1000.0);

            if (n == 16000) { morphLarge = morphNs; promoteLarge = promoteNs; }
        }

        // A pointer swap is cheaper than rebuilding every node...
        assertTrue(promoteLarge < morphLarge,
                "O(1) promote (" + promoteLarge + "ns) must beat O(n) rebuild (" + morphLarge + "ns) at n=16000");
        // ...and by a wide margin, the signature of O(1) vs O(n).
        assertTrue(morphLarge > promoteLarge * 100L,
                "rebuild should cost >100x the swap at n=16000 (rebuild=" + morphLarge + "ns, swap=" + promoteLarge + "ns)");
    }
}
