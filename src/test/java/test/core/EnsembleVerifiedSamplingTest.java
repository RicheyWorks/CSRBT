package test.core;

import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleMode;
import core.ensemble.EnsembleOrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-006 — sampled verification. {@code verifyEvery(n)} makes VERIFIED's K× read
 * amplification a dial: every nth read runs the full E4 vote (majority serve, dissenter
 * quarantine, primary failover), the other n−1 serve from the primary alone, lock-free. The
 * contracts under test: the stride is deterministic (detection happens on exactly the nth
 * read, not before); the documented honest trade (a divergent <em>primary</em> serves up to
 * n−1 unverified answers before the vote deposes it); the default n=1 is E4 verbatim; and the
 * amplification reduction is measurable.
 */
@DisplayName("EnsembleOrderedSet — VERIFIED sampled verification (ADR-006)")
public class EnsembleVerifiedSamplingTest {

    private static EnsembleOrderedSet<Integer> verified(int verifyEvery, int n) {
        EnsembleOrderedSet<Integer> ens =
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(() -> new RedBlackStrategy<Integer>())   // primary
                        .member(() -> new AVLStrategy<Integer>())
                        .member(() -> new SplayStrategy<Integer>())
                        .mode(EnsembleMode.VERIFIED)
                        .verifyEvery(verifyEvery)
                        .build();
        for (int i = 0; i < n; i++) ens.add(i);
        return ens;
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String name) {
        for (EnsembleMember<Integer> m : ens.members()) if (m.strategyName().equals(name)) return m;
        throw new AssertionError("no member " + name);
    }

    @Test
    @DisplayName("the stride is deterministic: a divergent member survives n−1 reads and is caught on the nth")
    void detectionOnExactlyTheNthRead() {
        EnsembleOrderedSet<Integer> ens = verified(10, 100);
        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");
        avl.set().remove(42);   // out-of-band divergence — the post-R1 fault class

        for (int read = 1; read <= 9; read++) {
            assertTrue(ens.contains(42), "unverified reads serve the (healthy) primary");
            assertTrue(avl.isActive(), "read " + read + " is unverified — no vote, no detection");
        }
        assertTrue(ens.contains(42), "the 10th read votes: majority true wins");
        assertEquals(EnsembleMember.State.QUARANTINED, avl.state(),
                "the vote caught the dissenter on exactly the nth read");
    }

    @Test
    @DisplayName("the honest trade: a divergent primary serves n−1 wrong answers, then the vote deposes it")
    void divergentPrimaryWindowIsBounded() {
        EnsembleOrderedSet<Integer> ens = verified(5, 100);
        EnsembleMember<Integer> rb = ens.primary();
        rb.set().remove(42);    // the primary itself diverges

        for (int read = 1; read <= 4; read++) {
            assertFalse(ens.contains(42),
                    "read " + read + " is served by the divergent primary unverified — the documented window");
        }
        assertTrue(ens.contains(42), "the 5th read votes: the majority answer is served, not the primary's");
        assertNotSame(rb, ens.primary(), "the dissenting primary was deposed by the vote");
        assertEquals(EnsembleMember.State.QUARANTINED, rb.state());
        assertTrue(ens.contains(42), "subsequent reads serve the new, healthy primary");
    }

    @Test
    @DisplayName("default n=1 is E4 verbatim: every read votes, detection is immediate")
    void defaultVotesEveryRead() {
        EnsembleOrderedSet<Integer> ens =
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(() -> new RedBlackStrategy<Integer>())
                        .member(() -> new AVLStrategy<Integer>())
                        .member(() -> new SplayStrategy<Integer>())
                        .mode(EnsembleMode.VERIFIED)
                        .build();
        assertEquals(1, ens.verifyEvery(), "the dial defaults to every-read voting");
        for (int i = 0; i < 50; i++) ens.add(i);

        EnsembleMember<Integer> splay = memberNamed(ens, "SplayStrategy");
        splay.set().remove(7);
        assertTrue(ens.contains(7), "first read already votes");
        assertEquals(EnsembleMember.State.QUARANTINED, splay.state(), "immediate detection at n=1");
    }

    @Test
    @DisplayName("the dial is validated and reported")
    void dialValidatedAndReported() {
        assertThrows(IllegalArgumentException.class, () ->
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder()).verifyEvery(0));

        EnsembleOrderedSet<Integer> ens = verified(16, 10);
        assertEquals(16, ens.verifyEvery());
        assertTrue(ens.toString().contains("verifyEvery=16"),
                "a quietly-large n must be loud: " + ens);
    }

    @Test
    @DisplayName("benchmark row: sampled verification beats per-read voting on read throughput")
    void benchmarkSampledVsPerRead() {
        final int keys = 10_000, reads = 60_000;
        EnsembleOrderedSet<Integer> perRead = verified(1, keys);
        EnsembleOrderedSet<Integer> sampled = verified(16, keys);

        // Warm-up both paths, then time identical read streams.
        for (int i = 0; i < 5_000; i++) { perRead.contains(i % keys); sampled.contains(i % keys); }

        long t0 = System.nanoTime();
        for (int i = 0; i < reads; i++) perRead.contains(i % keys);
        long perReadNs = System.nanoTime() - t0;

        t0 = System.nanoTime();
        for (int i = 0; i < reads; i++) sampled.contains(i % keys);
        long sampledNs = System.nanoTime() - t0;

        System.out.printf("ADR-006 benchmark: %d verified reads (k=3, n=%d keys): "
                        + "per-read vote %.1f ms; verifyEvery=16 %.1f ms (%.1fx)%n",
                reads, keys, perReadNs / 1e6, sampledNs / 1e6, (double) perReadNs / sampledNs);
        assertTrue(sampledNs < perReadNs,
                "1-in-16 voting must be cheaper than 16-in-16 (3x member reads + lock per vote)");
    }
}
