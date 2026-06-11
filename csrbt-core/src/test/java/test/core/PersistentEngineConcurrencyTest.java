package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.util.Comparator;
import java.util.List;
import java.util.Queue;
import java.util.Random;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-005 P2: the persistent engine's concurrency proof. Readers are wait-free by construction
 * (one volatile root read, then a walk of immutable nodes), so k concurrent readers under
 * 1-writer churn must see only fully consistent trees: strictly ascending {@code inOrder},
 * sizes that match contents, {@code select}/{@code rank} that agree with each other and with
 * the traversal — with no locks, retries, step bounds, or epochs anywhere on the read path.
 *
 * <p>Cross-thread assertion failures are collected in a queue and asserted empty on the main
 * thread (JUnit cannot see assertions thrown on worker threads). Thread counts, seeds, and
 * durations are fixed so the test stays CI-stable (ADR-005 §9).</p>
 */
@DisplayName("PersistentTreeEngine -- wait-free readers under churn (ADR-005 P2)")
public class PersistentEngineConcurrencyTest {

    private static final int READERS = 4;
    private static final int KEY_SPACE = 4000;
    private static final long RUN_MS = 250;

    @Test
    @Timeout(30)
    @DisplayName("k readers x 1 writer: every read sees a fully consistent tree")
    void readersSeeOnlyConsistentTrees() throws InterruptedException {
        PersistentTreeEngine<Integer> eng = PersistentTreeEngine.withNaturalOrder();
        for (int i = 0; i < KEY_SPACE; i += 2) eng.add(i);   // warm start, half the key space

        AtomicBoolean stop = new AtomicBoolean(false);
        Queue<String> failures = new ConcurrentLinkedQueue<>();
        AtomicLong readsTotal = new AtomicLong();

        Thread writer = new Thread(() -> {
            Random rng = new Random(2026);
            while (!stop.get()) {
                int v = rng.nextInt(KEY_SPACE);
                if (rng.nextBoolean()) eng.add(v);
                else                   eng.remove(v);
            }
        }, "p2-writer");

        Thread[] readers = new Thread[READERS];
        for (int r = 0; r < READERS; r++) {
            final int seed = 100 + r;
            readers[r] = new Thread(() -> {
                Random rng = new Random(seed);
                long n = 0;
                while (!stop.get()) {
                    try {
                        // A snapshot freezes one version: every cross-question must agree on it.
                        PersistentTreeEngine.Snapshot<Integer> snap = eng.snapshot();
                        List<Integer> io = snap.inOrder();
                        if (io.size() != snap.size()) {
                            failures.add("size " + snap.size() + " != inOrder length " + io.size());
                        }
                        for (int i = 1; i < io.size(); i++) {
                            if (io.get(i - 1) >= io.get(i)) {
                                failures.add("inOrder not strictly ascending at " + i);
                                break;
                            }
                        }
                        if (!io.isEmpty()) {
                            int mid = io.size() / 2 + 1;
                            if (!io.get(0).equals(snap.select(1))
                                    || !io.get(io.size() - 1).equals(snap.select(io.size()))
                                    || snap.rank(snap.select(mid)) != mid) {
                                failures.add("select/rank disagree with traversal");
                            }
                            if (snap.countInRange(io.get(0), io.get(io.size() - 1)) != io.size()) {
                                failures.add("countInRange(min,max) != size");
                            }
                        }
                        // Live wait-free reads: must never throw, whatever the writer is doing.
                        eng.contains(rng.nextInt(KEY_SPACE));
                        eng.select(Math.max(1, Math.min(eng.size(), 7)));
                        n++;
                    } catch (RuntimeException e) {
                        failures.add("read threw " + e);
                        break;
                    }
                }
                readsTotal.addAndGet(n);
            }, "p2-reader-" + r);
        }

        writer.start();
        for (Thread t : readers) t.start();
        Thread.sleep(RUN_MS);
        stop.set(true);
        writer.join(5000);
        for (Thread t : readers) t.join(5000);

        assertTrue(failures.isEmpty(), "concurrent readers observed inconsistency: " + failures.peek());
        assertTrue(readsTotal.get() > 0, "readers made progress");
        assertTrue(eng.validateInvariants().isEmpty(),
                "engine healthy after churn: " + eng.validateInvariants());
    }

    @Test
    @Timeout(60)
    @DisplayName("reference throughput: persistent snapshot reads vs R1 optimistic vs R2 READ_REPLICA (printed)")
    void referenceThroughput() throws InterruptedException {
        System.out.println("[BENCHMARK ADR-005 P2] contains() throughput under 1-writer churn (reference only)");

        // Persistent engine: volatile-root walk, wait-free.
        PersistentTreeEngine<Integer> persistent = PersistentTreeEngine.withNaturalOrder();
        for (int i = 0; i < 2000; i += 2) persistent.add(i);
        long persistentReads = churn("persistent",
                v -> { persistent.add(v); }, v -> { persistent.remove(v); },
                v -> { persistent.contains(v); });

        // Single tree under ADR-004 R1: optimistic stamped reads, locked fallback.
        OrderedSet<Integer> single = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < 2000; i += 2) single.add(i);
        long r1Reads = churn("R1-optimistic",
                v -> { single.add(v); }, v -> { single.remove(v); },
                v -> { single.contains(v); });

        // Ensemble under ADR-004 R2: epoch readers over mirrors.
        EnsembleOrderedSet<Integer> replica = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .mode(EnsembleMode.READ_REPLICA)
                .build();
        for (int i = 0; i < 2000; i += 2) replica.add(i);
        long r2Reads = churn("READ_REPLICA",
                v -> { replica.add(v); }, v -> { replica.remove(v); },
                v -> { replica.contains(v); });

        // Reference numbers, not a race: assert progress only (ADR-005 §5 P2 prints the trade).
        assertTrue(persistentReads > 0 && r1Reads > 0 && r2Reads > 0, "all readers made progress");
    }

    @FunctionalInterface
    private interface IntOp { void apply(int v); }

    /** One writer churning add/remove, one reader hammering contains, fixed 250ms; prints reads. */
    private static long churn(String label, IntOp add, IntOp remove, IntOp read)
            throws InterruptedException {
        AtomicBoolean stop = new AtomicBoolean(false);
        AtomicLong reads = new AtomicLong();
        Thread writer = new Thread(() -> {
            Random rng = new Random(3);
            while (!stop.get()) {
                int v = rng.nextInt(KEY_SPACE);
                if (rng.nextBoolean()) add.apply(v);
                else                   remove.apply(v);
            }
        }, "bench-writer");
        Thread reader = new Thread(() -> {
            Random rng = new Random(4);
            long n = 0;
            while (!stop.get()) {
                read.apply(rng.nextInt(KEY_SPACE));
                n++;
            }
            reads.addAndGet(n);
        }, "bench-reader");

        writer.start();
        reader.start();
        Thread.sleep(RUN_MS);
        stop.set(true);
        writer.join(5000);
        reader.join(5000);
        System.out.printf("  engine=%-14s reads=%,d in %dms%n", label, reads.get(), RUN_MS);
        return reads.get();
    }
}
