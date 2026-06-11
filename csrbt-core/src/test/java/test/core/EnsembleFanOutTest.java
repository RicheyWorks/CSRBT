package test.core;

import core.MutableTree;
import core.TreeNode1;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleOrderedSet;
import core.ensemble.ParallelMemberExecutor;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-003 E5 — parallel write fan-out behind the MemberExecutor seam. The gates the ADR demands
 * before allowing concurrency: (1) the parallel path is behavior-transparent (oracle equivalence
 * with E1's sequential fan-out, op for op), (2) the write-failure rule holds under fan-out — a
 * throwing member is quarantined while the write commits to the rest, with failover first when the
 * thrower is the serving primary — and (3) the logical set stays linearizable when many threads
 * write through the facade at once (parallelism is within a write, never between writes).
 */
@DisplayName("EnsembleOrderedSet — parallel fan-out (E5)")
public class EnsembleFanOutTest {

    // ── Fault injection: a delegating strategy that can be armed to throw on insert/delete ──

    /** Delegates to Red-Black; throws on the write path while {@code fail} is set. */
    static final class FaultableStrategy<K> implements TreeStrategy<K> {
        private final TreeStrategy<K> inner = new RedBlackStrategy<>();
        final AtomicBoolean fail = new AtomicBoolean(false);

        private void maybeFail() {
            if (fail.get()) throw new IllegalStateException("injected write fault");
        }

        @Override public void insert(MutableTree<K> tree, TreeNode1<K> node)    { maybeFail(); inner.insert(tree, node); }
        @Override public void fixInsert(MutableTree<K> tree, TreeNode1<K> node) { inner.fixInsert(tree, node); }
        @Override public void delete(MutableTree<K> tree, TreeNode1<K> node)    { maybeFail(); inner.delete(tree, node); }
        @Override public TreeNode1<K> search(MutableTree<K> tree, K value)      { return inner.search(tree, value); }
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String name) {
        for (EnsembleMember<Integer> m : ens.members()) if (m.strategyName().equals(name)) return m;
        throw new AssertionError("no member " + name);
    }

    // ── Gate 1: behavior transparency ─────────────────────────────────────────────

    @Test
    @DisplayName("parallel fan-out tracks a TreeSet oracle exactly as the sequential fan-out does")
    void parallelMatchesOracleAndSequential() {
        EnsembleOrderedSet<Integer> parallel = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .parallelFanOut()
                .build();
        EnsembleOrderedSet<Integer> sequential = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .build();
        assertTrue(parallel.fanOutExecutor() instanceof ParallelMemberExecutor, "parallel executor wired");

        TreeSet<Integer> oracle = new TreeSet<>();
        Random rng = new Random(7);
        for (int i = 0; i < 4000; i++) {
            int v = rng.nextInt(500);                       // duplicates + absent removes
            if (rng.nextBoolean()) {
                boolean expected = oracle.add(v);
                assertEquals(expected, parallel.add(v), "parallel add() parity at op " + i);
                assertEquals(expected, sequential.add(v), "sequential add() parity at op " + i);
            } else {
                boolean expected = oracle.remove(v);
                assertEquals(expected, parallel.remove(v), "parallel remove() parity at op " + i);
                assertEquals(expected, sequential.remove(v), "sequential remove() parity at op " + i);
            }
        }

        List<Integer> sorted = new ArrayList<>(oracle);
        assertEquals(sorted, parallel.inOrder(), "parallel primary matches the oracle");
        assertEquals(sorted, sequential.inOrder(), "sequential primary matches the oracle");
        for (EnsembleMember<Integer> m : parallel.members()) {
            assertEquals(sorted, m.set().inOrder(), m.strategyName() + " is an exact mirror under parallel fan-out");
        }
        parallel.close();
    }

    // ── Gate 2: the write-failure rule under fan-out ──────────────────────────────

    @Test
    @DisplayName("a member that throws mid-write is quarantined; the write commits to the rest")
    void throwingMemberIsQuarantinedWriteCommits() {
        FaultableStrategy<Integer> faulty = new FaultableStrategy<>();
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())   // primary
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> faulty)
                .parallelFanOut()
                .build();
        for (int i = 0; i < 100; i++) ens.add(i);

        EnsembleMember<Integer> faultable = memberNamed(ens, "FaultableStrategy");
        faulty.fail.set(true);
        assertTrue(ens.add(1000), "the write commits to the survivors and reports the primary's result");
        faulty.fail.set(false);

        assertEquals(EnsembleMember.State.QUARANTINED, faultable.state(), "the thrower is quarantined");
        assertSame(memberNamed(ens, "RedBlackStrategy"), ens.primary(), "primary unaffected (it did not throw)");
        assertTrue(ens.contains(1000), "logical set has the write");
        assertEquals(101, ens.size(), "size reflects the committed write");
        assertEquals(101, memberNamed(ens, "AVLStrategy").set().size(), "healthy non-primary got the write too");

        // Quarantined members are skipped by subsequent writes...
        ens.add(2000);
        assertFalse(faultable.set().contains(2000), "no fan-out to a quarantined member");
        // ...until E3's heal rebuilds them from the primary.
        assertTrue(ens.healFromPrimary(faultable), "heal reactivates the member");
        assertEquals(ens.inOrder(), faultable.set().inOrder(), "healed member is an exact mirror again");
        ens.close();
    }

    @Test
    @DisplayName("a primary that throws mid-write fails over to a survivor, then is quarantined")
    void throwingPrimaryFailsOverThenQuarantines() {
        FaultableStrategy<Integer> faulty = new FaultableStrategy<>();
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> faulty)                            // initial primary
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .parallelFanOut()
                .build();
        for (int i = 0; i < 100; i++) ens.add(i);
        EnsembleMember<Integer> oldPrimary = ens.primary();
        assertEquals("FaultableStrategy", oldPrimary.strategyName(), "faultable member starts as primary");

        faulty.fail.set(true);
        assertTrue(ens.add(1000), "the write commits; the new primary's result is reported");
        faulty.fail.set(false);

        assertNotSame(oldPrimary, ens.primary(), "failover happened");
        assertTrue(ens.primary().isActive(), "reads are served by a healthy member");
        assertEquals(EnsembleMember.State.QUARANTINED, oldPrimary.state(), "deposed primary is quarantined");
        assertTrue(ens.contains(1000), "logical set follows the survivors");
        assertEquals(101, ens.size(), "committed write visible through the new primary");
        ens.close();
    }

    // ── Gate 3: linearizability across writer threads ─────────────────────────────

    @Test
    @DisplayName("concurrent writers through the facade stay linearizable (parallelism is within a write)")
    void concurrentWritersStayLinearizable() throws InterruptedException {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .parallelFanOut()
                .build();

        final int writers = 4, perWriter = 1000;
        Thread[] threads = new Thread[writers];
        for (int w = 0; w < writers; w++) {
            final int base = w * perWriter;                  // disjoint key ranges
            threads[w] = new Thread(() -> {
                for (int i = 0; i < perWriter; i++) ens.add(base + i);
                for (int i = 0; i < perWriter; i += 2) ens.remove(base + i);   // drop the evens
            }, "writer-" + w);
        }
        for (Thread t : threads) t.start();
        for (Thread t : threads) t.join();

        TreeSet<Integer> expected = new TreeSet<>();
        for (int w = 0; w < writers; w++) {
            for (int i = 1; i < perWriter; i += 2) expected.add(w * perWriter + i);
        }
        List<Integer> sorted = new ArrayList<>(expected);
        assertEquals(sorted, ens.inOrder(), "final logical set is the union of all writers' odd keys");
        for (EnsembleMember<Integer> m : ens.members()) {
            assertEquals(sorted, m.set().inOrder(), m.strategyName() + " mirrors the logical set exactly");
        }
        ens.close();
    }
}
