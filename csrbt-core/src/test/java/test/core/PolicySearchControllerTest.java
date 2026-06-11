package test.core;

import core.control.MorphPolicy;
import core.control.RollingWorkloadMonitor;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleMode;
import core.ensemble.EnsembleOrderedSet;
import core.evolution.PolicyBandit;
import core.evolution.PolicyGenome;
import core.evolution.PolicySearchController;
import core.export.TreeSessionRecorder;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.WeightBalancedStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-011 V3 — the search loop, end to end on a live ensemble. The trials run on a real
 * shadow member through the real health gate; scores are real {@code Fitness} numbers on
 * seeded streams (deterministic); the (5,3) unsoundness discovered in V1 is exercised as
 * the <em>live</em> disqualification mechanism; a genuinely better arm is promoted through
 * the MorphPolicy gates; and a recorded session replays the search for the arena.
 */
@DisplayName("PolicySearchController — bandit over ensemble shadows (ADR-011 V3)")
public class PolicySearchControllerTest {

    /** Primary + one trial shadow; shadows receive every write (p=1) so trials are exact. */
    private static EnsembleOrderedSet<Integer> ensemble(
            java.util.function.Supplier<core.strategy.TreeStrategy<Integer>> primary) {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(primary::get)                              // primary
                .member(() -> new RedBlackStrategy<Integer>())     // the trial slot
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(1.0)
                .build();
    }

    private static EnsembleMember<Integer> trialSlot(EnsembleOrderedSet<Integer> ens) {
        return ens.members().get(1);
    }

    @Test
    @DisplayName("trial windows: arms tried in UCB order, scored with real fitness, contents exact")
    void trialLoopScoresArms() {
        EnsembleOrderedSet<Integer> ens = ensemble(RedBlackStrategy::new);
        PolicyBandit bandit = new PolicyBandit(
                List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(4, 2)));
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, trialSlot(ens), new RollingWorkloadMonitor(), bandit, MorphPolicy.defaults());

        TreeSet<Integer> oracle = new TreeSet<>();
        Random rnd = new Random(11_2026);
        for (int window = 0; window < 4; window++) {
            PolicyGenome arm = c.beginTrial();
            assertNotNull(arm);
            for (int op = 0; op < 500; op++) {
                int key = rnd.nextInt(600);
                if (rnd.nextInt(100) < 60) { c.add(key); oracle.add(key); }
                else                       { c.remove(key); oracle.remove(key); }
                if (op % 3 == 0) c.contains(rnd.nextInt(600));
            }
            PolicySearchController.TrialResult r = c.endTrial(500);
            assertTrue(r.scored(), "sound arm must be scored: " + r.reason());
            assertTrue(r.armCost() >= 0.0);
            assertEquals(new ArrayList<>(oracle), ens.inOrder(),
                    "logical contents must survive trial morphs");
        }
        assertEquals(4, bandit.totalPulls());
        assertTrue(bandit.pulls(PolicyGenome.weightBalanced(3, 2)) >= 1);
        assertTrue(bandit.pulls(PolicyGenome.weightBalanced(4, 2)) >= 1);

        // Window discipline is loud, not silent.
        assertThrows(IllegalStateException.class, () -> c.endTrial(1));
        c.beginTrial();
        assertThrows(IllegalStateException.class, c::beginTrial);
    }

    @Test
    @DisplayName("the (5,3) arm self-disqualifies live, at endTrial, via its own invariant")
    void unsoundArmDisqualifiesLive() {
        EnsembleOrderedSet<Integer> ens = ensemble(RedBlackStrategy::new);
        PolicyBandit bandit = new PolicyBandit(List.of(PolicyGenome.weightBalanced(5, 3)));
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, trialSlot(ens), new RollingWorkloadMonitor(), bandit, MorphPolicy.defaults());

        List<String> phases = new ArrayList<>();
        c.setEventListener(e -> {
            if (e instanceof core.event.TreeEvent.Trial<Integer> t) phases.add(t.phase());
        });

        // V1's discovering recipe: seeded churn, delete-heavy enough to break the repair.
        Random rnd = new Random(11_2026 + 5 * 31 + 3);   // the discovering seed family
        boolean disqualified = false;
        for (int window = 0; window < 8 && !disqualified; window++) {
            c.beginTrial();
            for (int op = 0; op < 1_000; op++) {
                int key = rnd.nextInt(700);
                if (rnd.nextInt(100) < 55) c.add(key); else c.remove(key);
            }
            PolicySearchController.TrialResult r = c.endTrial(1_000);
            disqualified = !r.scored();
        }
        assertTrue(disqualified, "the unsound arm must fail its own invariant under churn");
        assertTrue(bandit.isDisqualified(PolicyGenome.weightBalanced(5, 3)));
        assertTrue(phases.contains("DISQUALIFIED"), "events: " + phases);
        // The search space is now empty — the next window must fail loudly.
        assertThrows(IllegalStateException.class, c::beginTrial);
        // And even the unsound arm lost no data (the V1 thesis, intact in the loop).
        assertEquals(ens.primary().set().inOrder(), trialSlot(ens).set().inOrder());
    }

    @Test
    @DisplayName("a better arm is promoted through the gates; throne and laboratory trade places")
    void promotionThroughGates() {
        // Splay primary under uniform read-heavy churn: reliably deeper than WB(3,2).
        EnsembleOrderedSet<Integer> ens = ensemble(SplayStrategy::new);
        EnsembleMember<Integer> lab = trialSlot(ens);
        PolicyBandit bandit = new PolicyBandit(List.of(PolicyGenome.weightBalanced(3, 2)));
        // Real gates, tuned to the test's window budget: 1k-op cooldown, 5% margin, 2 wins.
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, lab, new RollingWorkloadMonitor(), bandit, new MorphPolicy(1_000, 0.05, 2));

        List<String> phases = new ArrayList<>();
        c.setEventListener(e -> {
            if (e instanceof core.event.TreeEvent.Trial<Integer> t) phases.add(t.phase());
        });

        Random rnd = new Random(42);
        boolean promoted = false;
        for (int window = 0; window < 6 && !promoted; window++) {
            c.beginTrial();
            for (int op = 0; op < 1_500; op++) {
                int key = rnd.nextInt(2_000);
                if (rnd.nextInt(100) < 25) { if (rnd.nextBoolean()) c.add(key); else c.remove(key); }
                else c.contains(key);                       // read-heavy, uniform: splay's bad diet
            }
            promoted = c.endTrial(1_500).promoted();
        }
        assertTrue(promoted, "WB(3,2) must beat a splay primary on uniform read-heavy churn");
        assertEquals(lab, ens.primary(), "the trial member must now serve");
        assertTrue(ens.primary().orderedSet().getStrategy() instanceof WeightBalancedStrategy,
                "the promoted primary must run the winning arm");
        assertNotNull(c.trialMember());
        assertFalse(c.trialMember() == ens.primary(), "the lab must not be the throne");
        assertTrue(phases.contains("SELECTED"), "events: " + phases);
    }

    @Test
    @DisplayName("a recorded session replays the search: Trial decisions in the arena JSON")
    void recordedSearchSession() {
        EnsembleOrderedSet<Integer> ens = ensemble(RedBlackStrategy::new);
        EnsembleMember<Integer> lab = trialSlot(ens);
        PolicyBandit bandit = new PolicyBandit(
                List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(4, 2)));
        PolicySearchController<Integer> c = new PolicySearchController<>(
                ens, lab, new RollingWorkloadMonitor(), bandit, MorphPolicy.defaults());

        // The recorder watches the trial tree; the controller feeds it Trial decisions.
        TreeSessionRecorder<Integer> recorder = TreeSessionRecorder.attach(lab.orderedSet());
        c.setEventListener(recorder);

        Random rnd = new Random(7);
        for (int window = 0; window < 2; window++) {
            c.beginTrial();
            for (int op = 0; op < 300; op++) {
                int key = rnd.nextInt(400);
                if (rnd.nextInt(100) < 60) c.add(key); else c.remove(key);
            }
            c.endTrial(300);
        }
        c.setEventListener(null);
        lab.orderedSet().setEventListener(null);

        assertTrue(recorder.decisionCount() >= 4, "TRIED+SCORED per window = ≥4 decisions");
        String json = recorder.toJson();
        assertTrue(json.contains("\"version\": 1"));
        assertTrue(json.contains("\"type\": \"Trial\""), "session must carry Trial decisions");
        assertTrue(json.contains("\"phase\": \"TRIED\""));
        assertTrue(json.contains("\"phase\": \"SCORED\""));
        assertTrue(json.contains("WB(Δ=3,Γ=2)"), "arm identity must be readable in the replay");
        assertTrue(json.contains("\"cost\": null"), "unscored phases render cost as null, not NaN");
        assertFalse(json.contains("NaN"), "JSON must stay parseable — no NaN anywhere");
    }
}
