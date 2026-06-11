package test.core;

import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleMode;
import core.ensemble.EnsembleOrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.util.Comparator;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-007 — optimistic unanimous votes. The lock-free pass serves a VERIFIED read with no
 * writeLock when all voters agree; disagreement of any kind escalates to the locked E4 vote.
 * The properties under test, per ADR-007 §6: <b>safety</b> — read skew across a concurrent
 * write commit must never be mistaken for divergence (no false quarantines, ever, because
 * only the locked vote quarantines and under the lock skew is impossible); <b>correctness</b>
 * — answers for keys untouched by the churn are always right; <b>equivalence</b> — real
 * divergence is detected and repaired identically with the fast path on or off; and the
 * benchmark row showing what the lock cost under write pressure.
 *
 * <p>Bounded like its R1/R2/P2 siblings: fixed thread counts, finite iterations, hard
 * timeout.</p>
 */
@DisplayName("EnsembleOrderedSet — VERIFIED optimistic votes under write churn (ADR-007)")
public class EnsembleVerifiedConcurrencyTest {

    private static final int STABLE = 100;     // keys 0..99: present for the whole test, never churned
    private static final int CHURN_BASE = 1_000;

    private static EnsembleOrderedSet<Integer> verified() {
        EnsembleOrderedSet<Integer> ens =
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(() -> new RedBlackStrategy<Integer>())
                        .member(() -> new AVLStrategy<Integer>())
                        .member(() -> new SplayStrategy<Integer>())
                        .mode(EnsembleMode.VERIFIED)
                        .build();
        for (int i = 0; i < STABLE; i++) ens.add(i);
        return ens;
    }

    @Test
    @Timeout(30)
    @DisplayName("safety: skew across write commits never quarantines a healthy member, and stable keys never lie")
    void noFalseQuarantinesUnderChurn() throws InterruptedException {
        EnsembleOrderedSet<Integer> ens = verified();
        AtomicBoolean stop = new AtomicBoolean(false);
        List<String> failures = new CopyOnWriteArrayList<>();

        Thread writer = new Thread(() -> {
            int k = 0;
            while (!stop.get()) {
                ens.add(CHURN_BASE + (k % 500));
                ens.remove(CHURN_BASE + (k % 500));
                k++;
            }
        }, "churn-writer");

        Thread[] readers = new Thread[4];
        for (int t = 0; t < readers.length; t++) {
            final int seed = t;
            readers[t] = new Thread(() -> {
                for (int i = 0; i < 20_000 && failures.size() < 5; i++) {
                    int stable = (seed * 7 + i) % STABLE;
                    if (!ens.contains(stable)) {
                        failures.add("contains(" + stable + ") lied: stable key reported absent");
                    }
                    if (ens.contains(-1 - (i % 50))) {
                        failures.add("contains(negative) lied: never-added key reported present");
                    }
                    if (ens.rank(stable) < 1) {
                        failures.add("rank(" + stable + ") < 1");
                    }
                }
            }, "verified-reader-" + t);
        }

        writer.start();
        for (Thread r : readers) r.start();
        for (Thread r : readers) r.join();
        stop.set(true);
        writer.join();

        assertTrue(failures.isEmpty(), "verified reads under churn: " + failures);
        for (EnsembleMember<Integer> m : ens.members()) {
            assertEquals(EnsembleMember.State.ACTIVE, m.state(),
                    m.strategyName() + " — skew must escalate, adjudicate clean, and never quarantine");
        }
    }

    @Test
    @DisplayName("equivalence: real divergence is caught and repaired identically, fast path on or off")
    void divergenceDetectedBothPaths() {
        boolean saved = EnsembleOrderedSet.OPTIMISTIC_VOTES;
        try {
            for (boolean optimistic : new boolean[] {true, false}) {
                EnsembleOrderedSet.OPTIMISTIC_VOTES = optimistic;
                EnsembleOrderedSet<Integer> ens = verified();
                EnsembleMember<Integer> avl = null;
                for (EnsembleMember<Integer> m : ens.members()) {
                    if (m.strategyName().equals("AVLStrategy")) avl = m;
                }
                avl.set().remove(42);   // persistent divergence — the disagreement is genuine

                assertTrue(ens.contains(42), "majority serves the right answer (optimistic=" + optimistic + ")");
                assertEquals(EnsembleMember.State.QUARANTINED, avl.state(),
                        "dissenter quarantined (optimistic=" + optimistic + ")");
            }
        } finally {
            EnsembleOrderedSet.OPTIMISTIC_VOTES = saved;
        }
    }

    @Test
    @Timeout(60)
    @DisplayName("benchmark row: under a concurrent writer, lock-free unanimity beats locked votes")
    void benchmarkOptimisticVsLockedUnderWriter() throws InterruptedException {
        // Wall-clock is weather (the V5 rule): this was the suite's only hard assert
        // comparing two timings, and it failed CI exactly that way (2026-06-11, both
        // matrix JDKs, green locally under the same ant invocation). The flip was then
        // REPRODUCED locally under deliberate 6-way CPU saturation (optimistic 0.9x on
        // attempt 1, 1.8x on attempt 2) — on a persistently saturated runner even
        // best-of-N can lose. So this row now follows the house convention for in-suite
        // benchmarks (printed rows, soft verdicts): up to three attempts are printed; if
        // optimistic never wins, a loud warning is printed but the build stays green —
        // the lock-free path's CORRECTNESS is hard-asserted by the functional tests
        // above; its speed claim is a benchmark, and benchmarks don't red the build
        // (ADR-009 G1 holds the real rig).
        boolean saved = EnsembleOrderedSet.OPTIMISTIC_VOTES;
        try {
            final int reads = 30_000;
            final int attempts = 3;
            boolean optimisticEverWon = false;

            for (int attempt = 1; attempt <= attempts && !optimisticEverWon; attempt++) {
                long[] elapsed = new long[2];   // [0] = optimistic, [1] = locked

                for (int phase = 0; phase < 2; phase++) {
                    EnsembleOrderedSet.OPTIMISTIC_VOTES = (phase == 0);
                    EnsembleOrderedSet<Integer> ens = verified();
                    AtomicBoolean stop = new AtomicBoolean(false);
                    Thread writer = new Thread(() -> {
                        int k = 0;
                        while (!stop.get()) {
                            ens.add(CHURN_BASE + (k % 500));
                            ens.remove(CHURN_BASE + (k % 500));
                            k++;
                        }
                    }, "bench-writer-" + attempt + "-" + phase);
                    writer.start();

                    for (int i = 0; i < 2_000; i++) ens.contains(i % STABLE);   // warm-up
                    long t0 = System.nanoTime();
                    for (int i = 0; i < reads; i++) ens.contains(i % STABLE);
                    elapsed[phase] = System.nanoTime() - t0;

                    stop.set(true);
                    writer.join();
                }

                System.out.printf("ADR-007 benchmark (attempt %d/%d): %d verified reads vs a "
                                + "saturating writer (k=3): optimistic %.1f ms; locked %.1f ms (%.1fx)%n",
                        attempt, attempts, reads,
                        elapsed[0] / 1e6, elapsed[1] / 1e6, (double) elapsed[1] / elapsed[0]);
                optimisticEverWon = elapsed[0] < elapsed[1];
            }

            if (!optimisticEverWon) {
                System.out.println("WARNING: ADR-007 benchmark — optimistic never beat locked in "
                        + attempts + " attempts. Weather on a saturated runner, or a fast-path "
                        + "regression: check the rows above and the functional ADR-007 tests "
                        + "(which hard-assert correctness) before reading anything into it.");
            }
        } finally {
            EnsembleOrderedSet.OPTIMISTIC_VOTES = saved;
        }
    }
}
