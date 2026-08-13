package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.control.MorphHistory;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.evolution.PolicyEvolutionController;
import io.github.richeyworks.csrbt.evolution.PolicyGenome;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.export.TreeSessionRecorder;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probes (bug audit 2026-08-12, evolution/control sweep) — each red on unfixed code.
 *
 * <p>V-A: the (μ+λ) pool refill and elite slot never consulted the graveyard, so a
 * scored parent killed by the live invariant check re-entered the pool with its stale
 * score — "the dead must stay dead" held only by seed luck. V-B: an infinite
 * incumbent-cost sentinel (engine-backed primary) made the improvement fraction
 * ∞/∞ = NaN, silently blocking every promotion forever. B5: the cooldown clock could
 * overflow int and go negative, freezing morphing permanently. B4: log/observability
 * formatting used the default locale (comma decimals break the key=value pipeline).
 * B1/B2: the session recorder emitted a duplicate {@code "op"} JSON key on Lineage
 * events (last-wins parsers lose the op counter) and never escaped event strings.
 * G-C: a crossover child that mutated in the womb lost both parents, its CROSSED
 * origin, and double-bumped generation.</p>
 */
@DisplayName("Evolution & control probes — graveyard, sentinels, recorder, provenance")
class EvolutionControlProbeTest {

    // ── V-A ───────────────────────────────────────────────────────────────────

    private static EnsembleOrderedSet<Integer> ensemble(int slots) {
        EnsembleOrderedSet.Builder<Integer> b =
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(RedBlackStrategy::new);
        for (int i = 0; i < slots; i++) b.member(RedBlackStrategy::new);
        return b.mode(EnsembleMode.SAMPLED_SHADOW).shadowSampleRate(1.0).build();
    }

    @Test
    @DisplayName("V-A: dead genomes never re-enter the pool, the parents, or the trial list")
    void theDeadStayDead() {
        for (long seed = 40; seed <= 46; seed++) {
            EnsembleOrderedSet<Integer> ens = ensemble(3);
            List<EnsembleMember<Integer>> nursery =
                    ens.members().subList(1, ens.members().size());
            PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                    ens, nursery, new RollingWorkloadMonitor(), MorphPolicy.defaults(),
                    List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(5, 3)),
                    2, false, seed);
            Random rnd = new Random(seed);
            for (int gen = 0; gen < 8; gen++) {
                List<PolicyGenome> onTrial = c.beginGeneration();
                Set<PolicyGenome> dead = c.graveyard();
                for (PolicyGenome g : onTrial) {
                    assertFalse(dead.contains(g),
                            "seed " + seed + " gen " + gen + ": genome " + g
                            + " is on trial but in the graveyard " + dead);
                }
                // Delete-heavy churn: the workload that triggers live invariant deaths.
                for (int i = 0; i < 1500; i++) {
                    int key = rnd.nextInt(400);
                    if (rnd.nextInt(100) < 45) c.add(key);
                    else c.remove(key);
                    if (i % 4 == 0) c.contains(rnd.nextInt(400));
                }
                c.endGeneration(1500);
                Set<PolicyGenome> deadAfter = c.graveyard();
                for (PolicyGenome g : deadAfter) {
                    assertFalse(c.parents().stream().anyMatch(g::equals),
                            "seed " + seed + " gen " + gen + ": dead genome " + g
                            + " survived into parents " + c.parents());
                }
            }
        }
    }

    // ── V-B ───────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("V-B: an unscored (infinite-cost) incumbent auto-loses to any scored candidate")
    void infiniteIncumbentAutoLoses() {
        MorphPolicy policy = new MorphPolicy(0, 0.05, 1);
        assertTrue(policy.shouldMorph(Double.NEGATIVE_INFINITY, -1.0, 10_000, 10),
                "the ∞-cost sentinel means 'no comparable incumbent' — a scored candidate "
                + "must beat it, but ∞/∞ = NaN silently HOLDs forever");
    }

    // ── B5 ────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("B5: the cooldown clock saturates instead of overflowing negative")
    void cooldownClockSaturates() {
        MorphHistory h = MorphHistory.initial()
                .observed(null, Integer.MAX_VALUE)
                .observed(null, Integer.MAX_VALUE);
        assertTrue(h.opsSinceLastMorph() >= 0,
                "the ops-since-morph clock overflowed to " + h.opsSinceLastMorph()
                + " — a negative clock never clears the cooldown gate again");
        assertEquals(Integer.MAX_VALUE, h.opsSinceLastMorph(), "saturating add");
    }

    // ── B4 ────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("B4: workload features format with dots on comma-decimal-locale JVMs")
    void localeIndependentObservability() {
        java.util.Locale saved = java.util.Locale.getDefault();
        try {
            java.util.Locale.setDefault(java.util.Locale.GERMANY);
            String line = WorkloadFeatures.EMPTY.toString();
            assertFalse(line.contains(","),
                    "the key=value observability line must use dot decimals in every "
                    + "locale, got: " + line);
        } finally {
            java.util.Locale.setDefault(saved);
        }
    }

    // ── B1 + B2 ───────────────────────────────────────────────────────────────

    @Test
    @DisplayName("B1/B2: Lineage events keep the op counter and escape their strings")
    void recorderLineageJsonIsSound() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        TreeSessionRecorder<Integer> rec = new TreeSessionRecorder<>(set);
        rec.onEvent(new TreeEvent.Lineage<>(1, "child\"x", null, null, "founder"));
        String json = rec.toJson();

        assertTrue(json.contains("\"breedOp\": \"founder\""),
                "the Lineage operator must use its own key — a second \"op\" key in the "
                + "same object makes last-wins JSON parsers lose the op counter");
        assertFalse(json.contains("child\"x"),
                "event strings must be JSON-escaped — a raw quote corrupts the session");
        assertTrue(json.contains("child\\\"x"), "the quote must appear escaped");
    }

    // ── G-C ───────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("G-C: a crossover child keeps its parents, CROSSED origin, and generation")
    void crossoverKeepsProvenance() {
        TreeGenome a = TreeGenome.redBlackGenome();
        TreeGenome b = TreeGenome.avlGenome();
        // Force the in-womb trait mutation on every crossover (the buggy path).
        a.getMorphTraits().setMutationRate(1.0);
        b.getMorphTraits().setMutationRate(1.0);
        int expectedGeneration = Math.max(a.getGeneration(), b.getGeneration()) + 1;

        for (int i = 0; i < 50; i++) {
            TreeGenome child = TreeGenome.crossover(a, b);
            assertEquals(TreeGenome.GenomeOrigin.CROSSED, child.getOrigin(),
                    "an in-womb trait mutation must not rewrite the child's origin");
            assertEquals(a.getGenomeId(), child.getParentAId(),
                    "parentA must be the real parent, not the discarded intermediate");
            assertEquals(b.getGenomeId(), child.getParentBId(),
                    "parentB must survive the in-womb mutation");
            assertEquals(expectedGeneration, child.getGeneration(),
                    "generation must not double-bump");
        }
    }
}
