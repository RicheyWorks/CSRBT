package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.ensemble.EnsembleController;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.evolution.Fitness;
import io.github.richeyworks.csrbt.evolution.PolicyBandit;
import io.github.richeyworks.csrbt.evolution.PolicyEvolutionController;
import io.github.richeyworks.csrbt.evolution.PolicyGenome;
import io.github.richeyworks.csrbt.evolution.PolicySearchController;
import io.github.richeyworks.csrbt.evolution.PolicySearchController.TrialResult;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;
import java.util.List;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-024 — per-member rotation metering, the refinement ADR-011 held and sixth-pass fix S6-12
 * deferred ("the meter is the <b>primary's</b> delta … per-member rotation meters remain the ADR's
 * held refinement").
 *
 * <p>S6-12 plumbed real rotation deltas into the fitness write term, but from the primary only, so
 * every member was priced on the primary's churn: in an ensemble whose members run genuinely
 * different policies — the whole point of the ensemble — a rotation-thrashing member and a
 * rotation-cheap one had <em>identical</em> write terms. These tests pin the three clauses of the
 * replacement rule: own churn, normalized per write actually received, used only when both sides of
 * a comparison have one.</p>
 */
@DisplayName("ADR-024 — per-member rotation meters")
class PerMemberRotationMeterTest {

    private static EnsembleOrderedSet.Builder<Integer> ensemble() {
        return EnsembleOrderedSet.builder(Comparator.<Integer>naturalOrder());
    }

    /** A write-heavy stream with a read minority, so both workload fractions are non-zero. */
    private static void streamWriteHeavy(PolicySearchController<Integer> c, int ops, long seed) {
        Random rnd = new Random(seed);
        for (int op = 0; op < ops; op++) {
            int key = rnd.nextInt(4_000);
            if (rnd.nextInt(100) < 80) c.add(key); else c.remove(key);
            if (op % 10 == 0) c.contains(rnd.nextInt(4_000));
        }
    }

    // ── Clause 1: the meter is the member's own, over the writes it actually received ─────

    @Test
    @DisplayName("clause 1: the denominator is the writes the member received, not the stream's")
    void theDenominatorIsTheWritesTheMemberActuallyReceived() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)          // primary: every write
                .member(RedBlackStrategy::new)          // shadow: every 10th write
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.1)
                .build();
        EnsembleMember<Integer> primary = ens.members().get(0);
        EnsembleMember<Integer> shadow  = ens.members().get(1);

        for (int i = 0; i < 200; i++) ens.add(i);        // 200 effective writes

        assertEquals(200L, primary.meteredWrites(), "the primary receives every write");
        assertEquals(20L, shadow.meteredWrites(),
                "a 0.1-rate shadow receives every 10th write — and only those may be its denominator");
        assertEquals(200, primary.set().size());
        assertEquals(20, shadow.set().size());

        // The rate, not the count, is what makes the two comparable: the shadow paid 10x fewer
        // rotations because it saw 10x fewer writes, and per received write the two land together.
        assertTrue(primary.meteredRotations() > shadow.meteredRotations(),
                "the shadow cannot have paid as many rotations — it saw a tenth of the stream");
        assertTrue(shadow.rotationsPerWrite() > 0.0 && primary.rotationsPerWrite() > 0.0,
                "both rates are real: shadow=" + shadow.rotationsPerWrite()
                + " primary=" + primary.rotationsPerWrite());
    }

    @Test
    @DisplayName("clause 1: members running different policies get different write terms")
    void differentPoliciesGetDifferentWriteTerms() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)          // amortized O(1) rotations per write
                .member(SplayStrategy::new)             // splays every accessed key to the root
                .build();
        RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
        EnsembleController<Integer> ctrl = new EnsembleController<>(ens, monitor);

        Random rnd = new Random(20_260_817L);
        for (int op = 0; op < 4_000; op++) {
            int key = rnd.nextInt(3_000);
            if (rnd.nextInt(100) < 80) ctrl.add(key); else ctrl.remove(key);
            if (op % 10 == 0) ctrl.contains(rnd.nextInt(3_000));
        }

        EnsembleMember<Integer> rb    = ens.members().get(0);
        EnsembleMember<Integer> splay = ens.members().get(1);
        assertEquals(rb.meteredWrites(), splay.meteredWrites(),
                "MIRROR: both members saw exactly the same writes, so only the policy differs");
        assertTrue(splay.rotationsPerWrite() > 3.0 * rb.rotationsPerWrite(),
                "the rotation thrasher must not look identical to the cheap member: splay="
                + splay.rotationsPerWrite() + " rb=" + rb.rotationsPerWrite());

        // ...and that difference reaches the fitness write term, which is the point of the meter.
        WorkloadFeatures f = monitor.snapshot();
        double rbWrite    = Fitness.evaluate(rb.pricedFeatures(f), 10.0, 2_000L).writeCost();
        double splayWrite = Fitness.evaluate(splay.pricedFeatures(f), 10.0, 2_000L).writeCost();
        assertTrue(splayWrite > rbWrite,
                "priced on its own churn the thrasher must cost more: splay=" + splayWrite
                + " rb=" + rbWrite);
        // Pre-ADR-024 both were priced on the SAME stream number, so both write terms were equal.
        assertEquals(Fitness.evaluate(f, 10.0, 2_000L).writeCost(),
                     Fitness.evaluate(f, 10.0, 2_000L).writeCost(),
                     "the stream vector prices every member identically — that was the defect");
    }

    @Test
    @DisplayName("clause 1: a clear is not a metered write, and an engine-tier member has no meter")
    void clearIsNotMeteredAndEngineTierHasNoMeter() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)
                .persistentMember()
                .build();
        EnsembleMember<Integer> strategyBacked = ens.members().get(0);
        EnsembleMember<Integer> engineTier     = ens.members().get(1);

        for (int i = 0; i < 40; i++) ens.add(i);
        long afterAdds = strategyBacked.meteredWrites();
        assertEquals(40L, afterAdds);

        ens.clear();
        assertEquals(afterAdds, strategyBacked.meteredWrites(),
                "a wholesale clear is not a keyed mutation; folding it in would dilute the rate");

        assertEquals(0L, engineTier.meteredWrites(), "an engine-tier member has no rotation counter");
        assertTrue(Double.isNaN(engineTier.rotationsPerWrite()),
                "no counter means no observation — not a free 0.0");
    }

    @Test
    @DisplayName("clause 2: below MIN_METERED_WRITES received writes there is no own-churn observation")
    void tooFewReceivedWritesIsNotAnObservation() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)
                .member(RedBlackStrategy::new)
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.02)                 // every 50th write
                .build();
        EnsembleMember<Integer> shadow = ens.members().get(1);

        for (int i = 0; i < 300; i++) ens.add(i);       // shadow receives 6 writes
        assertEquals(6L, shadow.meteredWrites());
        assertTrue(shadow.meteredWrites() < EnsembleMember.MIN_METERED_WRITES);
        assertTrue(Double.isNaN(shadow.rotationsPerWrite()),
                "six samples is not a rate — one rebalancing cascade would move it by a third");

        for (int i = 300; i < 500; i++) ens.add(i);     // now 10 received writes
        assertTrue(shadow.meteredWrites() >= EnsembleMember.MIN_METERED_WRITES);
        assertFalse(Double.isNaN(shadow.rotationsPerWrite()),
                "past the floor the member has a rate of its own: " + shadow.rotationsPerWrite());
    }

    // ── Clause 3: both sides of a comparison are priced per-member, or neither is ──────────

    @Test
    @DisplayName("V3: the arm and the incumbent are each priced on their OWN realized churn")
    void trialAndIncumbentArePricedOnTheirOwnChurn() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)          // incumbent primary
                .member(AVLStrategy::new)               // the laboratory
                .build();
        EnsembleMember<Integer> primary = ens.members().get(0);
        EnsembleMember<Integer> lab     = ens.members().get(1);
        RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, lab, monitor, new PolicyBandit(List.of(PolicyGenome.weightBalanced(3, 2))),
                new MorphPolicy(0, 0.90, 3));           // an unreachable margin: never promote

        c.beginTrial();
        streamWriteHeavy(c, 4_000, 20_260_817L);
        TrialResult r = c.endTrial(4_000);
        assertTrue(r.scored(), r.reason());
        assertSame(primary, ens.primary(), "the throne must not move — this test measures pricing");

        WorkloadFeatures f = monitor.snapshot();
        OrderedSet<Integer> labSet  = lab.orderedSet();
        OrderedSet<Integer> primSet = primary.orderedSet();

        assertFalse(Double.isNaN(lab.rotationsPerWrite()), "the lab has its own rate");
        assertFalse(Double.isNaN(primary.rotationsPerWrite()), "so does the incumbent");
        assertNotEquals(lab.rotationsPerWrite(), primary.rotationsPerWrite(), 1e-9,
                "non-vacuity: the two policies must actually differ in churn");

        double armOwn = Fitness.evaluate(lab.pricedFeatures(f),
                Fitness.meanDepth(labSet.getEngine()), labSet.size()).cost();
        double armStream = Fitness.evaluate(f,
                Fitness.meanDepth(labSet.getEngine()), labSet.size()).cost();
        double incumbentOwn = Fitness.evaluate(primary.pricedFeatures(f),
                Fitness.meanDepth(primSet.getEngine()), primSet.size()).cost();

        assertNotEquals(armStream, armOwn, 1e-9,
                "non-vacuity: pricing on the member's own churn must move the number");
        assertEquals(armOwn, r.armCost(), 1e-9,
                "the arm must be priced on ITS OWN churn, not the stream's (was: " + armStream + ")");
        assertEquals(incumbentOwn, r.incumbentCost(), 1e-9,
                "and the incumbent on its own — the same rule on both sides of the gate");
    }

    @Test
    @DisplayName("clause 3: when one side is short of evidence BOTH fall back to the stream's number")
    void whenOneSideCannotBeMeteredNeitherSideIs() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)
                .member(RedBlackStrategy::new)
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.02)                 // the lab receives every 50th write
                .build();
        EnsembleMember<Integer> primary = ens.members().get(0);
        EnsembleMember<Integer> lab     = ens.members().get(1);
        RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, lab, monitor, new PolicyBandit(List.of(PolicyGenome.weightBalanced(3, 2))),
                new MorphPolicy(0, 0.90, 3));

        c.beginTrial();
        // 300 writes: the lab receives 6 — enough keys to have a shape (finding 8's gate passes),
        // not enough received writes to have a rate of its own (ADR-024 clause 2).
        for (int i = 0; i < 300; i++) { c.add(i); if (i % 10 == 0) c.contains(i / 2); }
        TrialResult r = c.endTrial(300);
        assertTrue(r.scored(), "the lab has a measurable SHAPE, so the trial is still scored: " + r.reason());

        assertTrue(Double.isNaN(lab.rotationsPerWrite()), "the lab has no rate of its own");
        assertFalse(Double.isNaN(primary.rotationsPerWrite()),
                "non-vacuity: the incumbent DOES have one, so only clause 3 can force its fallback");

        WorkloadFeatures f = monitor.snapshot();
        OrderedSet<Integer> primSet = primary.orderedSet();
        double incumbentStream = Fitness.evaluate(f,
                Fitness.meanDepth(primSet.getEngine()), primSet.size()).cost();
        double incumbentOwn = Fitness.evaluate(primary.pricedFeatures(f),
                Fitness.meanDepth(primSet.getEngine()), primSet.size()).cost();
        assertNotEquals(incumbentStream, incumbentOwn, 1e-9,
                "non-vacuity: the incumbent's own rate differs from the stream's");
        assertEquals(incumbentStream, r.incumbentCost(), 1e-9,
                "with the other side unmeterable, the incumbent must be priced on the STREAM too — "
                + "half a per-member comparison is two different measurements in one ratio");
    }

    @Test
    @DisplayName("V4: a generation prices every body per-member, or none of them")
    void generationPricingIsAllOrNothing() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)
                .member(AVLStrategy::new)
                .build();
        EnsembleMember<Integer> primary = ens.members().get(0);
        EnsembleMember<Integer> body    = ens.members().get(1);
        RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
        PolicyEvolutionController<Integer> evo = new PolicyEvolutionController<>(
                ens, List.of(body), monitor, new MorphPolicy(0, 0.90, 3),
                List.of(PolicyGenome.weightBalanced(3, 2)), 1, false, 20_260_817L);

        evo.beginGeneration();
        Random rnd = new Random(20_260_817L);
        for (int op = 0; op < 4_000; op++) {
            int key = rnd.nextInt(4_000);
            if (rnd.nextInt(100) < 80) evo.add(key); else evo.remove(key);
            if (op % 10 == 0) evo.contains(rnd.nextInt(4_000));
        }
        PolicyEvolutionController.GenerationResult g = evo.endGeneration(4_000);
        assertTrue(g.evaluated() > 0, g.reason());
        assertSame(primary, ens.primary());

        WorkloadFeatures f = monitor.snapshot();
        OrderedSet<Integer> bodySet = body.orderedSet();
        OrderedSet<Integer> primSet = primary.orderedSet();
        assertNotEquals(body.rotationsPerWrite(), primary.rotationsPerWrite(), 1e-9,
                "non-vacuity: the genome and the throne must actually churn differently");

        double bodyOwn = Fitness.evaluate(body.pricedFeatures(f),
                Fitness.meanDepth(bodySet.getEngine()), bodySet.size()).cost();
        double bodyStream = Fitness.evaluate(f,
                Fitness.meanDepth(bodySet.getEngine()), bodySet.size()).cost();
        double incumbentOwn = Fitness.evaluate(primary.pricedFeatures(f),
                Fitness.meanDepth(primSet.getEngine()), primSet.size()).cost();

        assertNotEquals(bodyStream, bodyOwn, 1e-9, "non-vacuity");
        assertEquals(bodyOwn, g.bestCost(), 1e-9,
                "the nursery body must be priced on its own churn (stream price was " + bodyStream + ")");
        assertEquals(incumbentOwn, g.incumbentCost(), 1e-9,
                "and the throne it is ranked against on its own, in the same pool");
    }

    // ── The window ────────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("the meter is window-scoped: each trial prices its arm on the churn IT paid")
    void meterIsScopedToTheEvaluationWindow() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)
                .member(AVLStrategy::new)
                .build();
        EnsembleMember<Integer> lab = ens.members().get(1);
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, lab, new RollingWorkloadMonitor(512),
                new PolicyBandit(List.of(PolicyGenome.weightBalanced(3, 2))),
                new MorphPolicy(0, 0.90, 3));

        c.beginTrial();
        for (int i = 0; i < 500; i++) c.add(i);
        long firstWindow = lab.meteredWrites();
        assertEquals(500L, firstWindow);
        c.endTrial(500);

        c.beginTrial();                                  // a new window starts a new measurement
        assertEquals(0L, lab.meteredWrites(),
                "an arm must not inherit the churn the previous arm paid");
        for (int i = 500; i < 600; i++) c.add(i);
        assertEquals(100L, lab.meteredWrites());
        c.endTrial(100);
    }


    @Test
    @DisplayName("a promotion that leaves no strategy-backed trial slot still logs its evidence")
    void promotionWithNoRemainingTrialSlotStillReports() {
        // An ENGINE-tier primary is unscored (+inf) and auto-loses the margin gate (MorphPolicy
        // V-B), so the strategy-backed lab takes the throne — and the deposed engine member has no
        // strategy seam, so pickTrialSlot has nothing left to hand back. The evaluation must still
        // report the evidence it decided on, which is the PRE-swap pair.
        EnsembleOrderedSet<Integer> ens = ensemble()
                .persistentMember()                     // engine-tier primary: no strategy, no meter
                .member(RedBlackStrategy::new)          // the laboratory
                .build();
        EnsembleMember<Integer> lab = ens.members().get(1);
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, lab, new RollingWorkloadMonitor(512),
                new PolicyBandit(List.of(PolicyGenome.weightBalanced(3, 2))),
                new MorphPolicy(0, 0.01, 1));

        c.beginTrial();
        for (int i = 0; i < 400; i++) c.add(i);
        TrialResult r = c.endTrial(400);
        assertTrue(r.promoted(), "the engine-tier incumbent must lose the margin gate: " + r.reason());
        assertSame(lab, ens.primary());
        assertNull(c.trialMember(), "the repro needs pickTrialSlot to come back empty");
    }

    @Test
    @DisplayName("EnsembleController reports each member's own rotation rate on its morph_eval line")
    void ensembleControllerReportsPerMemberChurn() {
        EnsembleOrderedSet<Integer> ens = ensemble()
                .member(RedBlackStrategy::new)
                .member(SplayStrategy::new)
                .build();
        EnsembleController<Integer> ctrl = new EnsembleController<>(ens, new RollingWorkloadMonitor(512));
        for (int i = 0; i < 500; i++) ctrl.add(i);

        EnsembleMember<Integer> rb    = ens.members().get(0);
        EnsembleMember<Integer> splay = ens.members().get(1);
        assertEquals(500L, rb.meteredWrites());
        assertTrue(splay.rotationsPerWrite() > rb.rotationsPerWrite(),
                "sequential inserts: splay pays a rotation per level, red-black amortizes");

        ctrl.evaluateAndMaybePromote(500);
        assertEquals(0L, rb.meteredWrites(),
                "the evaluation is this controller's window boundary — the meters reset behind it");
        assertEquals(0L, splay.meteredWrites());
    }
}
