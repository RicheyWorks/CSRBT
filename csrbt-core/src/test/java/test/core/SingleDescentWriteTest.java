package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.RedBlackTree;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Regression net for the single-descent write path (2026-07-14 write census, finding A).
 * {@code OrderedSet.add}/{@code remove} no longer run a {@code contains} precheck: the strategy's
 * insert descent detects duplicates itself and aborts unlinked ({@code RedBlackTree.addIfAbsent}
 * reads the link back), and {@code removeIfPresent} deletes the node its one search found. These
 * tests pin the contract the precheck used to guarantee, across every strategy in the family:
 * duplicate adds return false and change nothing, missing removes return false, set semantics
 * track a {@link TreeSet} oracle through churn, structural invariants survive, and the event
 * stream (Insert/Remove/Evict) still fires exactly once per effective mutation.
 */
@DisplayName("Single-descent writes -- duplicate-safe add/remove without the contains precheck")
class SingleDescentWriteTest {

    private static final long SEED = 20_260_714L;

    private static List<Supplier<TreeStrategy<Integer>>> family() {
        return List.of(
                RedBlackStrategy::new,
                AVLStrategy::new,
                SplayStrategy::new,
                HybridStrategy::new,
                WeightBalancedStrategy::new);
    }

    @Test
    @DisplayName("oracle churn with duplicates and misses, every strategy; invariants hold")
    void oracleChurnAcrossTheFamily() {
        for (Supplier<TreeStrategy<Integer>> s : family()) {
            TreeStrategy<Integer> strategy = s.get();
            String name = strategy.getClass().getSimpleName();
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(strategy);
            TreeSet<Integer> oracle = new TreeSet<>();
            Random rnd = new Random(SEED);
            for (int i = 0; i < 5_000; i++) {
                int k = rnd.nextInt(400);            // small space: plenty of duplicate adds / hit removes
                switch (rnd.nextInt(3)) {
                    case 0 -> assertEquals(oracle.add(k), set.add(k), name + " add(" + k + ") @op " + i);
                    case 1 -> assertEquals(oracle.remove(k), set.remove(k), name + " remove(" + k + ") @op " + i);
                    default -> assertEquals(oracle.contains(k), set.contains(k), name + " contains(" + k + ") @op " + i);
                }
            }
            assertEquals(oracle.size(), set.size(), name + " size after churn");
            assertEquals(new ArrayList<>(oracle), set.inOrder(), name + " inOrder after churn");
            assertTrue(strategy.validateInvariant(set.getEngine()).isEmpty(),
                    name + " structural invariants violated after single-descent churn");
        }
    }

    @Test
    @DisplayName("engine addIfAbsent returns the linked node once and null on the duplicate")
    void addIfAbsentContract() {
        for (Supplier<TreeStrategy<Integer>> s : family()) {
            TreeStrategy<Integer> strategy = s.get();
            String name = strategy.getClass().getSimpleName();
            RedBlackTree<Integer> engine = RedBlackTree.withNaturalOrder(strategy);

            TreeNode1<Integer> first = engine.addIfAbsent(42);
            assertNotNull(first, name + " first insert must link");
            assertEquals(42, first.getData(), name + " returned node carries the key");
            assertNull(engine.addIfAbsent(42), name + " duplicate insert must abort unlinked");
            assertTrue(engine.contains(42), name + " key present after duplicate no-op");

            // A duplicate against a deeper tree (root case above is special for splay: the
            // duplicate touch splays the found node to the root, still without linking).
            for (int k = 0; k < 40; k++) {
                engine.addIfAbsent(k);
            }
            assertNull(engine.addIfAbsent(17), name + " deep duplicate aborts unlinked");
            assertTrue(engine.contains(17), name);
            assertTrue(strategy.validateInvariant(engine).isEmpty(),
                    name + " invariants hold after duplicate touches");
        }
    }

    @Test
    @DisplayName("engine removeIfPresent reports presence with one descent")
    void removeIfPresentContract() {
        for (Supplier<TreeStrategy<Integer>> s : family()) {
            TreeStrategy<Integer> strategy = s.get();
            String name = strategy.getClass().getSimpleName();
            RedBlackTree<Integer> engine = RedBlackTree.withNaturalOrder(strategy);
            for (int k = 0; k < 30; k++) {
                engine.addIfAbsent(k);
            }
            assertTrue(engine.removeIfPresent(11), name + " present key removes");
            assertFalse(engine.removeIfPresent(11), name + " second remove is a miss");
            assertFalse(engine.removeIfPresent(999), name + " absent key is a miss");
            assertFalse(engine.contains(11), name);
            assertTrue(strategy.validateInvariant(engine).isEmpty(), name);
        }
    }

    @Test
    @DisplayName("facade events still fire once per effective mutation; window eviction intact")
    void eventsAndWindowSurviveTheRefactor() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        int[] inserts = {0};
        int[] removes = {0};
        int[] evicts = {0};
        set.setEventListener(e -> {
            if (e instanceof TreeEvent.Insert) {
                inserts[0]++;
            } else if (e instanceof TreeEvent.Remove) {
                removes[0]++;
            } else if (e instanceof TreeEvent.Evict) {
                evicts[0]++;
            }
        });

        assertTrue(set.add(1));
        assertTrue(set.add(2));
        assertFalse(set.add(1), "duplicate add is a no-op");
        assertTrue(set.remove(1));
        assertFalse(set.remove(1), "missing remove is a no-op");
        assertEquals(2, inserts[0], "one Insert event per effective add");
        assertEquals(1, removes[0], "one Remove event per effective remove");

        set.setMaxSize(3);
        for (int k = 10; k < 16; k++) {
            set.add(k);                                 // 1 live + 6 adds through a window of 3
        }
        assertEquals(3, set.size(), "window holds");
        assertEquals(8, inserts[0], "adds under the window still emit Insert");
        assertTrue(evicts[0] >= 4, "evictions rode the single-descent path and still emit Evict");
        assertEquals(new ArrayList<>(List.of(13, 14, 15)), set.inOrder(), "FIFO eviction kept the newest");
    }
}
