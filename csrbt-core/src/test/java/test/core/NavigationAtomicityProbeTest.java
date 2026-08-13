package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.adapter.NavigableOrderedSet;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.NavigableSet;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * Probe (ADR-021; deep-sweep audit 2026-08-12, D-1): the adapter used to compose each
 * navigation answer from 2–4 independently lock-guarded reads on the base set, so a
 * write landing between the epochs made READ-ONLY navigation throw
 * ({@code select(0)} out of bounds) or violate its contract ({@code floor(k) > k},
 * {@code ceiling} skipping a continuously-present key) — 399 exceptions and 1,870
 * wrong answers in 3.7M calls against keys the writer never touched. ADR-021 gives
 * {@code OrderedSet} native single-acquisition navigation primitives and rebases the
 * adapter on them.
 */
@DisplayName("ADR-021 — navigation is atomic under the R1 single-writer model")
class NavigationAtomicityProbeTest {

    @Test
    @DisplayName("concurrent writer far away: navigation over a stable region never lies or throws")
    void navigationIsAtomicUnderConcurrentWrites() throws Exception {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        NavigableSet<Integer> nav = new NavigableOrderedSet<>(set);
        // Stable region the writer never touches: 10000..10099 (every even key).
        for (int k = 10_000; k < 10_100; k += 2) set.add(k);
        for (int k = 0; k < 1_000; k++) set.add(k);          // churn region

        AtomicBoolean stop = new AtomicBoolean(false);
        AtomicLong violations = new AtomicLong();
        AtomicLong exceptions = new AtomicLong();
        AtomicLong calls = new AtomicLong();

        Thread writer = new Thread(() -> {
            int i = 0;
            while (!stop.get()) {
                int k = i++ % 1_000;
                if ((i & 1) == 0) set.add(k); else set.remove(k);
            }
        });

        Runnable reader = () -> {
            while (!stop.get()) {
                try {
                    calls.incrementAndGet();
                    // floor of an absent odd key inside the stable region.
                    Integer f = nav.floor(10_051);
                    if (f == null || f != 10_050) violations.incrementAndGet();
                    Integer c = nav.ceiling(10_051);
                    if (c == null || c != 10_052) violations.incrementAndGet();
                    Integer l = nav.lower(10_050);
                    if (l == null || l != 10_048) violations.incrementAndGet();
                    Integer h = nav.higher(10_050);
                    if (h == null || h != 10_052) violations.incrementAndGet();
                    // A continuously-present key must be its own floor and ceiling.
                    Integer ff = nav.floor(10_020);
                    if (ff == null || ff != 10_020) violations.incrementAndGet();
                    // The stable sub-view's size never changes: 50 keys.
                    int viewSize = nav.subSet(10_000, true, 10_099, true).size();
                    if (viewSize != 50) violations.incrementAndGet();
                } catch (RuntimeException e) {
                    exceptions.incrementAndGet();
                }
            }
        };

        Thread[] readers = { new Thread(reader), new Thread(reader), new Thread(reader) };
        writer.start();
        for (Thread t : readers) t.start();
        Thread.sleep(2_500);
        stop.set(true);
        writer.join(5_000);
        for (Thread t : readers) t.join(5_000);

        assertEquals(0, exceptions.get(),
                "read-only navigation threw " + exceptions.get() + " times in "
                + calls.get() + " rounds — a write between lock epochs reached the caller");
        assertEquals(0, violations.get(),
                violations.get() + " contract violations in " + calls.get()
                + " rounds (floor/ceiling/view-size wrong on keys the writer never touched)");
    }

    @Test
    @DisplayName("the new primitives agree with single-threaded semantics at the boundaries")
    void primitivesMatchSemantics() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int k : new int[]{10, 20, 30, 40}) set.add(k);
        assertEquals(Integer.valueOf(20), set.floor(20));
        assertEquals(Integer.valueOf(20), set.floor(25));
        assertNull(set.floor(5));
        assertEquals(Integer.valueOf(10), set.lower(20));
        assertNull(set.lower(10));
        assertEquals(Integer.valueOf(20), set.ceiling(20));
        assertEquals(Integer.valueOf(30), set.ceiling(25));
        assertNull(set.ceiling(45));
        assertEquals(Integer.valueOf(30), set.higher(20));
        assertNull(set.higher(40));
        assertEquals(2, set.countUpTo(20, true));
        assertEquals(1, set.countUpTo(20, false));
        assertEquals(4, set.countBetween(null, true, null, true));
        assertEquals(2, set.countBetween(15, true, 35, true));
        assertEquals(1, set.countBetween(20, false, 40, false));
    }
}
