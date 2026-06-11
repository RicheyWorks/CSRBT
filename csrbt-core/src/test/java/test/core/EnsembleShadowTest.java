package test.core;

import core.control.RollingWorkloadMonitor;
import core.ensemble.EnsembleController;
import core.ensemble.EnsembleController.HealthReport;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleMode;
import core.ensemble.EnsembleOrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-003 E5 — SAMPLED_SHADOW, the memory-lean mode (Option B). The primary stays the one exact
 * copy and receives every write; shadows receive a deterministic 1-in-ceil(1/p) stride of the write
 * stream, so they cost ~p of a mirror. The mode's contracts under test: shadows hold the sampled
 * fraction and are marked inexact; reads are served by the primary alone; promoting a shadow is the
 * ADR's O(n) <em>sync-on-promote</em> (after which the deposed primary drifts in its turn); shadows
 * never vote or fail over; and the E3 health check treats a shadow's divergence from the primary as
 * design, not fault.
 */
@DisplayName("EnsembleOrderedSet — SAMPLED_SHADOW mode (E5)")
public class EnsembleShadowTest {

    private static EnsembleOrderedSet<Integer> shadowEnsemble(double p) {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())   // primary — the one exact copy
                .member(() -> new AVLStrategy<Integer>())        // shadow
                .member(() -> new SplayStrategy<Integer>())      // shadow
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(p)
                .build();
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String name) {
        for (EnsembleMember<Integer> m : ens.members()) if (m.strategyName().equals(name)) return m;
        throw new AssertionError("no member " + name);
    }

    @Test
    @DisplayName("shadows hold exactly the sampled fraction and are marked inexact; the primary holds all")
    void shadowsHoldSampledFraction() {
        EnsembleOrderedSet<Integer> ens = shadowEnsemble(0.1);
        for (int i = 0; i < 1000; i++) assertTrue(ens.add(i), "effective-change comes from the primary");

        EnsembleMember<Integer> primary = ens.primary();
        assertEquals(1000, primary.set().size(), "primary receives every write");
        assertTrue(primary.isExact(), "primary is the one exact copy");

        for (EnsembleMember<Integer> m : ens.members()) {
            if (m == primary) continue;
            assertEquals(100, m.set().size(), m.strategyName() + " holds the 1-in-10 stride exactly");
            assertFalse(m.isExact(), m.strategyName() + " is inexact from its first skipped write");
            assertTrue(m.set().contains(9), "stride writes 10,20,... land keys 9,19,...");
            assertFalse(m.set().contains(0), "skipped writes never reach a shadow");
        }
    }

    @Test
    @DisplayName("reads and order statistics are served by the primary alone")
    void readsServedByPrimaryOnly() {
        EnsembleOrderedSet<Integer> ens = shadowEnsemble(0.1);
        for (int i = 0; i < 1000; i++) ens.add(i);

        assertTrue(ens.contains(0), "key 0 is absent from every shadow but the primary serves it");
        assertEquals(1000, ens.size(), "size is the primary's, not a shadow's");
        assertEquals(Integer.valueOf(0), ens.minimum(), "order stats come from the primary");
        assertEquals(500, ens.rank(499), "rank served by the primary's augment");
        List<Integer> all = ens.inOrder();
        assertEquals(1000, all.size(), "inOrder is the full logical set");
    }

    @Test
    @DisplayName("promoting a shadow is sync-on-promote: O(n) catch-up, then the swap; the deposed primary drifts")
    void syncOnPromoteCatchesShadowUp() {
        EnsembleOrderedSet<Integer> ens = shadowEnsemble(0.1);
        for (int i = 0; i < 1000; i++) ens.add(i);

        EnsembleMember<Integer> rb  = memberNamed(ens, "RedBlackStrategy");
        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");
        assertEquals(100, avl.set().size(), "precondition: AVL is a 10% sketch");

        assertTrue(ens.promote(avl), "promotion applies");
        assertSame(avl, ens.primary(), "the shadow now serves");
        assertTrue(avl.isExact(), "caught up to an exact mirror before serving");
        assertEquals(1000, avl.set().size(), "sync-on-promote rebuilt the full logical set");
        assertEquals(rb.set().inOrder(), avl.set().inOrder(), "new primary mirrors the old exactly");

        // The deposed primary is still exact at the instant of the swap, then drifts on the first
        // write the stride skips it.
        assertTrue(rb.isExact(), "deposed primary has missed nothing yet");
        ens.add(5000);                                   // write 1001 — not a stride hit
        assertFalse(rb.isExact(), "first skipped write turns the deposed primary into a shadow");
        assertTrue(ens.contains(5000), "logical set keeps flowing through the new primary");
    }

    @Test
    @DisplayName("shadows cannot vote: VERIFIED is rejected until shadows are healed back to exact mirrors")
    void shadowsCannotVote() {
        EnsembleOrderedSet<Integer> ens = shadowEnsemble(0.1);
        for (int i = 0; i < 100; i++) ens.add(i);

        assertThrows(IllegalStateException.class, () -> ens.setMode(EnsembleMode.VERIFIED),
                "fewer than three exact ACTIVE members -> no majority possible");

        // Heal every shadow back to an exact mirror; now a quorum exists.
        for (EnsembleMember<Integer> m : ens.members()) {
            if (m != ens.primary()) assertTrue(ens.healFromPrimary(m), "heal rebuilds the shadow");
        }
        ens.setMode(EnsembleMode.VERIFIED);
        assertEquals(EnsembleMode.VERIFIED, ens.mode(), "all-exact ensemble may verify");
        assertEquals(100, ens.size(), "quorum agrees on the logical set");
    }

    @Test
    @DisplayName("a primary write failure with only shadows around fails the write — shadows cannot fail over")
    void primaryFailureWithOnlyShadowsFailsTheWrite() {
        EnsembleFanOutTest.FaultableStrategy<Integer> faulty = new EnsembleFanOutTest.FaultableStrategy<>();
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> faulty)                            // primary
                .member(() -> new AVLStrategy<Integer>())        // shadow
                .member(() -> new SplayStrategy<Integer>())      // shadow
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.1)
                .build();
        for (int i = 0; i < 20; i++) ens.add(i);                 // shadows are inexact sketches now

        faulty.fail.set(true);
        assertThrows(IllegalStateException.class, () -> ens.add(1000),
                "no exact member can stand in for the primary -> the write must fail loudly");
        faulty.fail.set(false);
        assertEquals(20, ens.size(), "logical set unchanged by the failed write");
    }

    @Test
    @DisplayName("the E3 health check treats shadow divergence as design, not fault")
    void healthCheckLeavesShadowsAlone() {
        EnsembleOrderedSet<Integer> ens = shadowEnsemble(0.1);
        EnsembleController<Integer> ctl = new EnsembleController<>(ens, new RollingWorkloadMonitor(512));
        for (int i = 0; i < 1000; i++) ens.add(i);

        HealthReport r = ctl.checkHealth();

        assertEquals(0, r.quarantined(), "diverging-by-design shadows are not quarantined");
        assertFalse(r.failedOver(), "healthy primary keeps serving");
        for (EnsembleMember<Integer> m : ens.members()) {
            assertSame(EnsembleMember.State.ACTIVE, m.state(), m.strategyName() + " stays ACTIVE");
            if (m != ens.primary()) {
                assertEquals(100, m.set().size(), m.strategyName() + " sketch untouched by the check");
                assertFalse(m.isExact(), m.strategyName() + " remains a shadow");
            }
        }
    }
}
