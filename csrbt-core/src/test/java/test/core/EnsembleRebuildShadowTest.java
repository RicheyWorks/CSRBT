package test.core;

import core.control.RollingWorkloadMonitor;
import core.ensemble.EnsembleController;
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
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-003 Option C ({@code REBUILD_SHADOW}) and the "Revisit" memory controls. Option C is the
 * write-lean mode: the primary receives every write, shadows receive <em>none</em> and are
 * instead rebuilt wholesale from the primary every {@code rebuildEvery} writes — 1× steady-state
 * write cost, amortized O(n) rebuilds, redundancy that is warm only at cadence boundaries. The
 * memory controls are the ceiling latch ({@code memoryCeilingBytes} — observe and log, never
 * self-degrade) and the hard cap on K ({@code maxMembers}).
 */
@DisplayName("EnsembleOrderedSet — REBUILD_SHADOW (Option C) + memory ceiling / cap-K (ADR-003 Revisit)")
public class EnsembleRebuildShadowTest {

    private static EnsembleOrderedSet<Integer> rebuildEnsemble(int cadence) {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())   // primary
                .member(() -> new AVLStrategy<Integer>())        // rebuild shadow
                .member(() -> new SplayStrategy<Integer>())      // rebuild shadow
                .mode(EnsembleMode.REBUILD_SHADOW)
                .rebuildEvery(cadence)
                .build();
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String name) {
        for (EnsembleMember<Integer> m : ens.members()) if (m.strategyName().equals(name)) return m;
        throw new AssertionError("no member " + name);
    }

    @Test
    @DisplayName("shadows take no live writes; the cadence rebuild makes them exact and includes the triggering write")
    void cadenceRebuildCycle() {
        EnsembleOrderedSet<Integer> ens = rebuildEnsemble(100);
        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");

        for (int i = 1; i <= 99; i++) assertTrue(ens.add(i));
        assertEquals(99, ens.primary().set().size(), "primary receives every write");
        assertEquals(0, avl.set().size(), "shadows receive none of them");
        assertFalse(avl.isExact(), "inexact from the first skipped write");

        ens.add(100);   // 100th write: commit, then rebuild
        assertEquals(100, avl.set().size(), "rebuild copies the full logical set");
        assertTrue(avl.set().contains(100), "the rebuild runs after the triggering write commits");
        assertTrue(avl.isExact(), "a freshly rebuilt shadow is exact — a warm promotion target");

        ens.add(101);   // first write of the next cadence
        assertEquals(100, avl.set().size(), "shadows drift again immediately");
        assertFalse(avl.set().contains(101));
        assertFalse(avl.isExact(), "exactness lasts exactly until the next write");
        assertEquals(101, ens.size(), "reads are served by the primary throughout");
    }

    @Test
    @DisplayName("promoting a stale rebuild shadow is the O(n) sync-on-promote catch-up")
    void promoteStaleShadowSyncs() {
        EnsembleOrderedSet<Integer> ens = rebuildEnsemble(100);
        for (int i = 1; i <= 150; i++) ens.add(i);   // rebuilt at 100, stale 101..150

        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");
        assertFalse(avl.isExact());
        assertEquals(100, avl.set().size());

        assertTrue(ens.promote(avl));
        assertSame(avl, ens.primary());
        assertTrue(avl.isExact(), "sync-on-promote rebuilt it from the deposed primary");
        assertEquals(150, ens.size());
        assertTrue(ens.contains(150), "the catch-up included the post-rebuild writes");
        assertEquals(75, ens.rank(75), "order stats served by the new primary");
    }

    @Test
    @DisplayName("mid-cadence drift is design, not fault — the health pass repairs nothing; clear() reaches everyone")
    void driftIsNotAFault() {
        EnsembleOrderedSet<Integer> ens = rebuildEnsemble(100);
        EnsembleController<Integer> ctl =
                new EnsembleController<>(ens, new RollingWorkloadMonitor(512));
        for (int i = 1; i <= 150; i++) ctl.add(i);

        assertFalse(ctl.checkHealth().changed(),
                "stale shadows validate against their own contents, like sampled shadows (E5)");

        ens.clear();   // never skipped: a missed clear would strand dropped keys in a shadow
        for (EnsembleMember<Integer> m : ens.members()) {
            assertEquals(0, m.set().size(), m.strategyName() + " — clear fans out to shadows too");
        }
    }

    @Test
    @DisplayName("the memory ceiling latches on breach, recovers when back under, and never degrades the ensemble")
    void memoryCeilingLatchesAndRecovers() {
        // Two mirrors at the default ~96 bytes/node estimate: 2 * 96 * n > 9600 once n > 50.
        EnsembleOrderedSet<Integer> ens =
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(() -> new RedBlackStrategy<Integer>())
                        .member(() -> new AVLStrategy<Integer>())
                        .memoryCeilingBytes(9600)
                        .build();
        assertEquals(9600, ens.memoryCeilingBytes());
        assertFalse(ens.isOverMemoryCeiling());

        for (int i = 0; i < 60; i++) ens.add(i);
        assertTrue(ens.isOverMemoryCeiling(), "breach latched once the estimate passed the ceiling");
        assertTrue(ens.estimatedMemoryBytes() > 9600);
        assertEquals(60, ens.size(), "the ensemble observes and logs — it never refuses writes");

        for (int i = 0; i < 30; i++) ens.remove(i);
        assertFalse(ens.isOverMemoryCeiling(), "flag resets when the estimate drops back under");
    }

    @Test
    @DisplayName("maxMembers is a hard cap on K, enforced at build()")
    void maxMembersCapsK() {
        assertThrows(IllegalArgumentException.class, () ->
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(() -> new RedBlackStrategy<Integer>())
                        .member(() -> new AVLStrategy<Integer>())
                        .member(() -> new SplayStrategy<Integer>())
                        .maxMembers(2)
                        .build(), "three members under a cap of two must not build");

        assertThrows(IllegalArgumentException.class, () ->
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .maxMembers(1), "a one-member cap is not an ensemble");

        // At the cap is fine.
        EnsembleOrderedSet<Integer> ens =
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(() -> new RedBlackStrategy<Integer>())
                        .member(() -> new AVLStrategy<Integer>())
                        .maxMembers(2)
                        .build();
        ens.add(1);
        assertTrue(ens.contains(1));
    }
}
