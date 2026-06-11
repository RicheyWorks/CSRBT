package test.core;

import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-004 R2 — READ_REPLICA: left-right epoch reads over ensemble mirrors. The contracts under
 * test: (1) the two-phase write (non-serving first, flip, drain, old side) preserves exact-mirror
 * semantics op for op against a {@link TreeSet} oracle; (2) under concurrent write churn —
 * including promotions mid-stream — epoch readers never see torn structure (every snapshot
 * strictly ascending, no stray exceptions, no wedged drains); (3) the mode degrades loudly, not
 * silently: writes fail when no second exact ACTIVE member can take the flip, and the mode is
 * rejected outright when fewer than two exact members exist. A throughput line is printed for
 * reference (MIRROR's R1 path vs READ_REPLICA's epoch path under identical churn) — no timing
 * assertion, per CI-stability policy.
 */
@DisplayName("EnsembleOrderedSet — READ_REPLICA epoch reads (ADR-004 R2)")
public class EnsembleReplicaTest {

    private static EnsembleOrderedSet<Integer> replica() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .mode(EnsembleMode.READ_REPLICA)
                .build();
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String name) {
        for (EnsembleMember<Integer> m : ens.members()) if (m.strategyName().equals(name)) return m;
        throw new AssertionError("no member " + name);
    }

    @Test
    @DisplayName("two-phase writes keep every member an exact mirror (TreeSet oracle, mixed ops)")
    void twoPhaseWritesStayExact() {
        EnsembleOrderedSet<Integer> ens = replica();
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rng = new Random(11);
        for (int i = 0; i < 3000; i++) {
            int v = rng.nextInt(400);
            if (rng.nextBoolean()) {
                assertEquals(oracle.add(v), ens.add(v), "add parity at op " + i);
            } else {
                assertEquals(oracle.remove(v), ens.remove(v), "remove parity at op " + i);
            }
        }
        List<Integer> expected = new ArrayList<>(oracle);
        assertEquals(expected, ens.inOrder(), "epoch read sees the full logical set");
        for (EnsembleMember<Integer> m : ens.members()) {
            assertEquals(expected, m.set().inOrder(),
                    m.strategyName() + " stays an exact mirror under the left-right discipline");
            assertTrue(m.isExact(), m.strategyName() + " remains exact");
        }
    }

    @Test
    @DisplayName("epoch readers never see torn state under write churn with mid-stream promotions")
    void epochReadersSurviveChurn() throws InterruptedException {
        EnsembleOrderedSet<Integer> ens = replica();
        for (int i = 0; i < 2000; i += 2) ens.add(i);

        AtomicBoolean stop = new AtomicBoolean(false);
        AtomicReference<Throwable> failure = new AtomicReference<>();

        Thread writer = new Thread(() -> {
            Random rng = new Random(2);
            try {
                int ops = 0;
                while (!stop.get()) {
                    int v = rng.nextInt(4000);
                    if (rng.nextBoolean()) ens.add(v);
                    else                   ens.remove(v);
                    if (++ops % 512 == 0) {
                        // Mid-stream promotion: epoch-aware drain must keep readers safe.
                        ens.promote(memberNamed(ens, "AVLStrategy"));
                    }
                }
            } catch (Throwable t) {
                failure.compareAndSet(null, t);
            }
        }, "replica-writer");

        Thread[] readers = new Thread[3];
        for (int r = 0; r < readers.length; r++) {
            final long seed = 200L + r;
            readers[r] = new Thread(() -> {
                Random rng = new Random(seed);
                try {
                    int iter = 0;
                    while (!stop.get()) {
                        ens.contains(rng.nextInt(4000));
                        if (++iter % 64 == 0) {
                            List<Integer> snap = ens.inOrder();
                            for (int i = 1; i < snap.size(); i++) {
                                if (snap.get(i - 1) >= snap.get(i)) {
                                    throw new AssertionError("torn epoch snapshot ("
                                            + snap.get(i - 1) + " !< " + snap.get(i) + ")");
                                }
                            }
                            assertEquals(snap.size(), snap.stream().distinct().count(),
                                    "snapshot has no duplicates");
                        }
                    }
                } catch (Throwable t) {
                    failure.compareAndSet(null, t);
                }
            }, "replica-reader-" + r);
        }

        writer.start();
        for (Thread t : readers) t.start();
        Thread.sleep(350);
        stop.set(true);
        writer.join(5000);
        for (Thread t : readers) t.join(5000);

        assertFalse(writer.isAlive(), "writer wedged — drain never completed?");
        for (Thread t : readers) assertFalse(t.isAlive(), "reader wedged");
        if (failure.get() != null) {
            throw new AssertionError("replica churn failed: " + failure.get(), failure.get());
        }

        // Quiescent: all members converge to the same exact mirror.
        List<Integer> finals = ens.inOrder();
        for (EnsembleMember<Integer> m : ens.members()) {
            if (!m.isActive()) continue;
            assertEquals(finals, m.set().inOrder(), m.strategyName() + " converged");
        }
    }

    @Test
    @DisplayName("degraded loudly: with no second ACTIVE member the write fails, readers keep serving")
    void degradedReplicaFailsWritesLoudly() {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .mode(EnsembleMode.READ_REPLICA)
                .build();
        for (int i = 0; i < 50; i++) ens.add(i);

        EnsembleMember<Integer> other = null;
        for (EnsembleMember<Integer> m : ens.members()) if (m != ens.primary()) other = m;
        assertTrue(ens.quarantine(other), "drop the only flip target");

        assertThrows(IllegalStateException.class, () -> ens.add(1000),
                "READ_REPLICA must not mutate the serving member without a flip");
        assertEquals(50, ens.size(), "logical set untouched by the failed write");
        assertTrue(ens.contains(25), "reads keep serving from the healthy primary");

        assertTrue(ens.healFromPrimary(other), "heal restores the flip target");
        assertTrue(ens.add(1000), "writes resume once a second member is back");
        assertEquals(51, ens.size());
    }

    @Test
    @DisplayName("READ_REPLICA is rejected with fewer than two exact ACTIVE members")
    void modeRequiresTwoExactMembers() {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.1)
                .build();
        for (int i = 0; i < 50; i++) ens.add(i);   // the shadow drifts to inexact

        assertThrows(IllegalStateException.class, () -> ens.setMode(EnsembleMode.READ_REPLICA),
                "a sampled shadow cannot take the flip");

        for (EnsembleMember<Integer> m : ens.members()) {
            if (m != ens.primary()) ens.healFromPrimary(m);
        }
        ens.setMode(EnsembleMode.READ_REPLICA);
        assertEquals(EnsembleMode.READ_REPLICA, ens.mode(), "all-exact ensemble may serve replicas");
        assertTrue(ens.add(1000), "two-phase write proceeds");
    }

    @Test
    @DisplayName("reference throughput: epoch reads vs MIRROR reads under identical churn (printed)")
    void referenceThroughput() throws InterruptedException {
        System.out.println("[BENCHMARK ADR-004 R2] read throughput under 1-writer churn (reference only)");
        for (EnsembleMode mode : new EnsembleMode[]{EnsembleMode.MIRROR, EnsembleMode.READ_REPLICA}) {
            EnsembleOrderedSet<Integer> ens = replica();
            ens.setMode(mode);
            for (int i = 0; i < 2000; i += 2) ens.add(i);

            AtomicBoolean stop = new AtomicBoolean(false);
            AtomicLong reads = new AtomicLong();
            Thread writer = new Thread(() -> {
                Random rng = new Random(3);
                while (!stop.get()) {
                    int v = rng.nextInt(4000);
                    if (rng.nextBoolean()) ens.add(v);
                    else                   ens.remove(v);
                }
            }, "tp-writer");
            Thread reader = new Thread(() -> {
                Random rng = new Random(4);
                long n = 0;
                while (!stop.get()) {
                    ens.contains(rng.nextInt(4000));
                    n++;
                }
                reads.addAndGet(n);
            }, "tp-reader");

            writer.start();
            reader.start();
            Thread.sleep(250);
            stop.set(true);
            writer.join(5000);
            reader.join(5000);
            System.out.printf("  mode=%-13s reads=%,d in 250ms%n", mode, reads.get());
            assertTrue(reads.get() > 0, "reader made progress in " + mode);
        }
    }
}
