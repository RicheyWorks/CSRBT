package test.core;

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

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;
import java.util.List;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Sixth-pass audit (2026-08-17) — the evolution half: findings 8 (an empty trial shadow scored a
 * free 0.0, beat every incumbent, and pinned the bandit forever) and 12 / AUDIT_2026-07-21
 * <b>F-E1</b> (the fitness write term was structurally 0 because every production facade passed
 * the {@code WorkloadMonitor}'s no-rotation overload).
 *
 * <p>The two interact — an unmeasurable shadow only wins <em>because</em> the write term cannot
 * carry any weight — so they are probed together.</p>
 */
@DisplayName("Sixth-pass audit — fitness observations and the rotation feed")
class SixthPassFitnessFeedProbeTest {

    // ── Finding 8: an uninformative trial is no observation ──────────────────────

    /** The audit's repro shape: a 2% sample rate, so the shadow takes every 50th write. */
    private static EnsembleOrderedSet<Integer> sampledShadowEnsemble() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())     // primary: sees every write
                .member(() -> new RedBlackStrategy<Integer>())     // the trial shadow
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.02)
                .build();
    }

    @Test
    @DisplayName("finding 8: an empty SAMPLED_SHADOW trial promotes nothing and records no observation")
    void emptyShadowIsNotAFreeWin() {
        EnsembleOrderedSet<Integer> ens = sampledShadowEnsemble();
        EnsembleMember<Integer> primary = ens.members().get(0);
        EnsembleMember<Integer> lab     = ens.members().get(1);

        PolicyBandit bandit = new PolicyBandit(
                List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(4, 2)));
        // A 50% margin: far beyond anything an honest candidate reaches against a same-workload
        // incumbent, but trivially cleared by a cost of exactly 0.0 — which is how the bug
        // promoted on trial one.
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, lab, new RollingWorkloadMonitor(512), bandit, new MorphPolicy(0, 0.50, 1));

        // Window 1 — the audit's exact repro: 40 keys in the primary, 0 in the shadow, on a
        // read-bearing stream (the read term is what the phantom 0.0 was undercutting).
        PolicyGenome first = c.beginTrial();
        for (int i = 0; i < 40; i++) {
            c.add(i);
            c.contains(i / 2);
            c.contains(i);
        }
        assertEquals(0, lab.set().size(), "the documented repro needs an empty trial shadow");
        assertEquals(40, primary.set().size());

        TrialResult r1 = c.endTrial(120);
        assertFalse(r1.promoted(), "an empty shadow must never be promoted: " + r1.reason());
        assertFalse(r1.scored(), "an empty window is no measurement: " + r1.reason());
        assertSame(primary, ens.primary(), "the incumbent keeps the throne");
        assertEquals(0, bandit.pulls(first),
                "an uninformative window must record NO observation — not a clamped one");
        assertNull(bandit.bestArm(), "nothing has been measured, so nothing can be best");

        // Window 2 — the same arm comes round again (still untried) and now sees real data.
        PolicyGenome second = c.beginTrial();
        assertEquals(first, second, "an unmeasured arm is still untried, so UCB1 offers it again");
        Random rnd = new Random(20_260_817L);
        for (int op = 0; op < 4_000; op++) {
            int key = rnd.nextInt(6_000);
            if (rnd.nextInt(100) < 70) c.add(key); else c.remove(key);
            if (op % 5 == 0) c.contains(rnd.nextInt(6_000));
        }
        assertTrue(lab.set().size() >= Fitness.MIN_INFORMATIVE_SIZE,
                "the shadow has finally accumulated a measurable tree");
        TrialResult r2 = c.endTrial(4_000);
        assertTrue(r2.scored(), "a shadow with a real shape is a real observation: " + r2.reason());
        assertEquals(1, bandit.pulls(second));
        assertTrue(bandit.meanCost(second) > 0.0,
                "the arm must carry its real cost, not a free 0.0 that pins bestArm() forever");
        assertFalse(r2.promoted(), "no honest candidate clears a 50% margin against a same-workload incumbent");

        // Window 3 — the bandit is still able to move on to a different arm.
        PolicyGenome third = c.beginTrial();
        assertNotEquals(second, third,
                "with the first arm finally measured, UCB1 must be free to try another");
        for (int op = 0; op < 2_000; op++) {
            int key = rnd.nextInt(6_000);
            if (rnd.nextInt(100) < 70) c.add(key); else c.remove(key);
        }
        TrialResult r3 = c.endTrial(2_000);
        assertTrue(r3.scored(), "the second arm is measurable too: " + r3.reason());
        assertNotNull(bandit.bestArm(), "with two real observations the bandit has an opinion");
        assertSame(primary, ens.primary(), "and the throne never changed hands on a phantom win");
    }

    @Test
    @DisplayName("finding 8: an empty nursery body is not scored and cannot take the throne (V4)")
    void emptyNurseryBodyIsNotSelected() {
        EnsembleOrderedSet<Integer> ens = sampledShadowEnsemble();
        EnsembleMember<Integer> primary = ens.members().get(0);
        EnsembleMember<Integer> body    = ens.members().get(1);

        PolicyEvolutionController<Integer> evo = new PolicyEvolutionController<>(
                ens, List.of(body), new RollingWorkloadMonitor(512), new MorphPolicy(0, 0.50, 1),
                List.of(PolicyGenome.weightBalanced(3, 2)), 1, false, 20_260_817L);

        evo.beginGeneration();
        for (int i = 0; i < 40; i++) {
            evo.add(i);
            evo.contains(i / 2);
            evo.contains(i);
        }
        assertEquals(0, body.set().size(), "the repro needs an empty nursery body");

        PolicyEvolutionController.GenerationResult g = evo.endGeneration(120);
        assertFalse(g.promoted(), "a genome with no measurable body must not be selected: " + g.reason());
        assertEquals(0, g.evaluated(), "an unmeasurable body is no observation");
        assertTrue(evo.parents().isEmpty(), "and it must not enter the parent pool at a free 0.0");
        assertTrue(evo.graveyard().isEmpty(), "unmeasured is not unsound — the genome stays breedable");
        assertSame(primary, ens.primary());
    }

    @Test
    @DisplayName("finding 8: Fitness.informative names the size below which a cost is not a measurement")
    void informativeIsTheGateOnComparability() {
        assertFalse(Fitness.informative(0L), "an empty tree costs 0.0 and beats everything");
        assertFalse(Fitness.informative(1L), "a single key has no shape — the read term is hard-zeroed");
        assertTrue(Fitness.informative(Fitness.MIN_INFORMATIVE_SIZE));
        assertTrue(Fitness.informative(4_000L));
    }

    // ── Finding 12 / F-E1: the rotation meter actually reaches the write term ─────

    private static EnsembleOrderedSet<Integer> mirrorEnsemble() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .build();
    }

    /** A write-heavy stream with a read minority, so both fractions are non-zero. */
    private static void streamWriteHeavy(java.util.function.IntConsumer add,
                                         java.util.function.IntConsumer remove,
                                         java.util.function.IntConsumer read) {
        Random rnd = new Random(20_260_817L);
        for (int op = 0; op < 5_000; op++) {
            int key = rnd.nextInt(4_000);
            if (rnd.nextInt(100) < 80) add.accept(key); else remove.accept(key);
            if (op % 10 == 0) read.accept(rnd.nextInt(4_000));
        }
    }

    @Test
    @DisplayName("finding 12: every ensemble facade feeds rotationsPerWrite from the live engine meter")
    void everyFacadeFeedsTheRotationMeter() {
        EnsembleOrderedSet<Integer> ens = mirrorEnsemble();
        RollingWorkloadMonitor ctrlMonitor = new RollingWorkloadMonitor(512);
        EnsembleController<Integer> ctrl = new EnsembleController<>(ens, ctrlMonitor);
        streamWriteHeavy(ctrl::add, ctrl::remove, ctrl::contains);
        assertTrue(ctrlMonitor.snapshot().rotationsPerWrite() > 0.0,
                "EnsembleController passed a literal 0 for rotations (finding 12): "
                + ctrlMonitor.snapshot());

        EnsembleOrderedSet<Integer> searchEns = mirrorEnsemble();
        RollingWorkloadMonitor searchMonitor = new RollingWorkloadMonitor(512);
        PolicySearchController<Integer> search = new PolicySearchController<>(
                searchEns, searchEns.members().get(1), searchMonitor,
                new PolicyBandit(List.of(PolicyGenome.weightBalanced(3, 2))), MorphPolicy.defaults());
        streamWriteHeavy(search::add, search::remove, search::contains);
        assertTrue(searchMonitor.snapshot().rotationsPerWrite() > 0.0,
                "PolicySearchController passed a literal 0 for rotations (finding 12): "
                + searchMonitor.snapshot());

        EnsembleOrderedSet<Integer> evoEns = mirrorEnsemble();
        RollingWorkloadMonitor evoMonitor = new RollingWorkloadMonitor(512);
        PolicyEvolutionController<Integer> evo = new PolicyEvolutionController<>(
                evoEns, List.of(evoEns.members().get(1)), evoMonitor, MorphPolicy.defaults(),
                List.of(PolicyGenome.weightBalanced(3, 2)), 1, false, 7L);
        streamWriteHeavy(evo::add, evo::remove, evo::contains);
        assertTrue(evoMonitor.snapshot().rotationsPerWrite() > 0.0,
                "PolicyEvolutionController passed a literal 0 for rotations (finding 12): "
                + evoMonitor.snapshot());
    }

    @Test
    @DisplayName("finding 12: a live write term damps a promotion that used to ride on read depth alone")
    void liveWriteTermDampsReadDepthOnlyPromotions() {
        EnsembleOrderedSet<Integer> ens = mirrorEnsemble();
        RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
        EnsembleController<Integer> ctrl = new EnsembleController<>(ens, monitor);
        streamWriteHeavy(ctrl::add, ctrl::remove, ctrl::contains);

        WorkloadFeatures live = monitor.snapshot();
        assertTrue(live.readFraction() > 0.0 && live.writeFraction() > 0.0, live.toString());
        assertTrue(live.rotationsPerWrite() > 0.0, "the write term has no feed: " + live);
        assertTrue(Fitness.evaluate(live, 10.0, 2_000L).writeCost() > 0.0,
                "writeCost = writeFraction x rotationsPerWrite must not be structurally 0");

        // The same vector with the meter dead — i.e. exactly what every caller used to report.
        WorkloadFeatures blind = new WorkloadFeatures(live.readFraction(), live.writeFraction(),
                live.accessSkew(), live.meanSearchDepth(), 0.0, live.size(), live.growthRate());

        // One candidate, meaningfully shallower than the incumbent, on a write-dominated diet:
        // the rotation-thrashing shape the audit describes.
        long n = 2_000L;
        double incumbentDepth = 10.0;
        double thrasherDepth  = 7.0;
        double blindIncumbent = Fitness.evaluate(blind, incumbentDepth, n).cost();
        double blindThrasher  = Fitness.evaluate(blind, thrasherDepth,  n).cost();
        double liveIncumbent  = Fitness.evaluate(live,  incumbentDepth, n).cost();
        double liveThrasher   = Fitness.evaluate(live,  thrasherDepth,  n).cost();

        double blindImprovement = (blindIncumbent - blindThrasher) / blindIncumbent;
        double liveImprovement  = (liveIncumbent  - liveThrasher)  / liveIncumbent;
        assertTrue(liveImprovement < blindImprovement,
                "the rotations the workload actually paid must dilute a pure read-depth claim: live="
                + liveImprovement + " blind=" + blindImprovement);

        // A margin between the two verdicts: read depth alone used to carry the morph; it no
        // longer does, because the realized write cost is now on both sides of the ledger.
        MorphPolicy gate = new MorphPolicy(0, (blindImprovement + liveImprovement) / 2.0, 1);
        assertTrue(gate.shouldMorph(-blindIncumbent, -blindThrasher, 10_000, 5),
                "with rotationsPerWrite structurally 0, read depth alone carried the promotion");
        assertFalse(gate.shouldMorph(-liveIncumbent, -liveThrasher, 10_000, 5),
                "with the meter alive the same candidate no longer clears the margin");
    }
}
