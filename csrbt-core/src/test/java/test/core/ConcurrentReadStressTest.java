package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.NoSuchElementException;
import java.util.Random;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-004 R1 — torn-read-free concurrent reads. One writer churns the set while reader threads
 * hammer membership, snapshots, and order statistics. The contract under test: readers never see
 * torn structure — no stray exceptions, no wedged walks (a reader chasing a transient cycle
 * without the step bound would hang), and every {@code inOrder} snapshot is strictly ascending
 * (a validated-or-locked snapshot can never interleave a half-applied rotation). Out-of-range
 * {@code select} and absent-key {@code rank} are <em>consistent</em> outcomes when racing a
 * writer and are tolerated; everything else is a failure. Run per strategy, including Splay,
 * whose public reads no longer splay (the R1a no-splay-on-read lookup — asserted separately).
 */
@DisplayName("ADR-004 R1 — concurrent reads are torn-read-free on every strategy")
public class ConcurrentReadStressTest {

    private static final int  KEY_SPACE   = 4000;
    private static final long RUN_MILLIS  = 350;
    private static final int  READERS     = 3;

    @Test
    @DisplayName("Red-Black: readers stay consistent under write churn")
    void redBlack() throws InterruptedException { stress("RB", RedBlackStrategy::new); }

    @Test
    @DisplayName("AVL: readers stay consistent under write churn")
    void avl() throws InterruptedException { stress("AVL", AVLStrategy::new); }

    @Test
    @DisplayName("Splay: readers stay consistent under write churn (reads never splay)")
    void splay() throws InterruptedException { stress("Splay", SplayStrategy::new); }

    @Test
    @DisplayName("Hybrid: readers stay consistent under write churn")
    void hybrid() throws InterruptedException { stress("Hybrid", HybridStrategy::new); }

    private void stress(String name, Supplier<TreeStrategy<Integer>> strategy) throws InterruptedException {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(strategy.get());
        for (int i = 0; i < 2000; i += 2) set.add(i);                  // seed the evens

        AtomicBoolean stop = new AtomicBoolean(false);
        AtomicReference<Throwable> failure = new AtomicReference<>();

        Thread writer = new Thread(() -> {
            Random rng = new Random(1);
            try {
                while (!stop.get()) {
                    int v = rng.nextInt(KEY_SPACE);
                    if (rng.nextBoolean()) set.add(v);
                    else                   set.remove(v);
                }
            } catch (Throwable t) {
                failure.compareAndSet(null, t);
            }
        }, name + "-writer");

        Thread[] readers = new Thread[READERS];
        for (int r = 0; r < READERS; r++) {
            final long seed = 100L + r;
            readers[r] = new Thread(() -> {
                Random rng = new Random(seed);
                try {
                    int iter = 0;
                    while (!stop.get()) {
                        set.contains(rng.nextInt(KEY_SPACE));          // hot optimistic path
                        if (++iter % 64 == 0) {
                            List<Integer> snap = set.inOrder();        // validated snapshot
                            for (int i = 1; i < snap.size(); i++) {
                                if (snap.get(i - 1) >= snap.get(i)) {
                                    throw new AssertionError(name + ": torn inOrder snapshot ("
                                            + snap.get(i - 1) + " !< " + snap.get(i) + " at " + i + ")");
                                }
                            }
                            try {
                                int n = set.size();
                                if (n > 0) set.select(1 + rng.nextInt(n));
                                set.countInRange(100, 300);
                                set.rank(snap.isEmpty() ? 0 : snap.get(rng.nextInt(snap.size())));
                            } catch (IndexOutOfBoundsException | NoSuchElementException racy) {
                                // size/membership raced the writer -- consistent, documented outcomes
                            }
                        }
                    }
                } catch (Throwable t) {
                    failure.compareAndSet(null, t);
                }
            }, name + "-reader-" + r);
        }

        writer.start();
        for (Thread t : readers) t.start();
        Thread.sleep(RUN_MILLIS);
        stop.set(true);
        writer.join(5000);
        for (Thread t : readers) t.join(5000);

        assertFalse(writer.isAlive(), name + ": writer wedged");
        for (Thread t : readers) {
            assertFalse(t.isAlive(), name + ": reader wedged -- unbounded walk on torn structure?");
        }
        if (failure.get() != null) {
            throw new AssertionError(name + ": " + failure.get(), failure.get());
        }

        // Quiescent sanity: traversal, size counter, and membership all agree.
        List<Integer> quiescent = set.inOrder();
        assertEquals(set.size(), quiescent.size(), name + ": size agrees with traversal at rest");
        for (int i = 1; i < quiescent.size(); i++) {
            assertTrue(quiescent.get(i - 1) < quiescent.get(i), name + ": quiescent order");
        }
    }

    @Test
    @DisplayName("R1a: public reads never splay; the write path keeps move-to-root")
    void splayReadsDoNotSplay() {
        OrderedSet<Integer> s = OrderedSet.withNaturalOrder(new SplayStrategy<Integer>());
        s.add(1);
        s.add(2);
        s.add(3);                                                       // insert splays: root = 3
        assertEquals(3, (int) s.getEngine().getRoot().getData(), "insert splays the new key to root");

        assertTrue(s.contains(1), "membership still answers correctly");
        assertEquals(3, (int) s.getEngine().getRoot().getData(), "a facade read must NOT splay");

        assertEquals(2, s.rank(2), "order statistics answer correctly");
        assertEquals(3, (int) s.getEngine().getRoot().getData(), "order statistics never splay");

        assertFalse(s.add(1), "duplicate add is rejected...");
        assertEquals(1, (int) s.getEngine().getRoot().getData(),
                "...but its write-path precheck splays: move-to-root adaptivity lives on writes");
    }
}
