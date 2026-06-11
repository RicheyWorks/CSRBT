package test.core;

import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.evolution.PolicyEvolutionController;
import io.github.richeyworks.csrbt.evolution.PolicyGenome;
import io.github.richeyworks.csrbt.export.TreeSessionRecorder;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-011 V4 — evolution proper, on a live ensemble. Generations breed real offspring
 * (V2's operators) onto real shadow bodies through the real health gate; deaths are the
 * safety architecture's verdicts; selection keeps μ; promotion is gated; lineages land in
 * the recorder. Seeded throughout — same seed, same lineage.
 */
@DisplayName("PolicyEvolutionController — (μ+λ) over ensemble shadows (ADR-011 V4)")
public class PolicyEvolutionControllerTest {

    /** Primary + λ nursery slots; shadows receive every write (p=1) so trials are exact. */
    private static EnsembleOrderedSet<Integer> ensemble(
            java.util.function.Supplier<io.github.richeyworks.csrbt.strategy.TreeStrategy<Integer>> primary, int slots) {
        EnsembleOrderedSet.Builder<Integer> b =
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(primary::get);
        for (int i = 0; i < slots; i++) b.member(() -> new RedBlackStrategy<Integer>());
        return b.mode(EnsembleMode.SAMPLED_SHADOW).shadowSampleRate(1.0).build();
    }

    private static List<EnsembleMember<Integer>> nursery(EnsembleOrderedSet<Integer> ens) {
        return ens.members().subList(1, ens.members().size());
    }

    private static void churn(PolicyEvolutionController<Integer> c, Random rnd,
                              TreeSet<Integer> oracle, int ops) {
        for (int i = 0; i < ops; i++) {
            int key = rnd.nextInt(800);
            if (rnd.nextInt(100) < 55) { c.add(key); if (oracle != null) oracle.add(key); }
            else                       { c.remove(key); if (oracle != null) oracle.remove(key); }
            if (i % 4 == 0) c.contains(rnd.nextInt(800));
        }
    }

    @Test
    @DisplayName("generations evolve: founders → scored survivors → bred offspring, contents exact")
    void generationsEvolve() {
        EnsembleOrderedSet<Integer> ens = ensemble(RedBlackStrategy::new, 3);
        PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                ens, nursery(ens), new RollingWorkloadMonitor(), MorphPolicy.defaults(),
                List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(6, 2)),
                2, false, 11_2026L);

        List<TreeEvent.Lineage<Integer>> births = new ArrayList<>();
        c.setEventListener(e -> {
            if (e instanceof TreeEvent.Lineage<Integer> l) births.add(l);
        });

        TreeSet<Integer> oracle = new TreeSet<>();
        Random rnd = new Random(1);

        List<PolicyGenome> gen1 = c.beginGeneration();
        assertEquals(3, gen1.size());
        assertEquals(PolicyGenome.weightBalanced(3, 2), gen1.get(0), "founders first, in order");
        assertEquals(PolicyGenome.weightBalanced(6, 2), gen1.get(1));
        assertTrue(gen1.get(2).family().parameterized(), "slot 3 must be bred from a founder");
        churn(c, rnd, oracle, 1_200);
        PolicyEvolutionController.GenerationResult r1 = c.endGeneration(1_200);
        assertEquals(3, r1.evaluated());
        assertEquals(2, r1.survivors().size(), "μ=2 survive");
        assertEquals(1, r1.generation());
        assertEquals(new ArrayList<>(oracle), ens.inOrder(), "contents exact across materialization");

        List<PolicyGenome> gen2 = c.beginGeneration();
        assertEquals(r1.survivors().get(0), gen2.get(0), "slot 0 is the elite parent, re-scored");
        churn(c, rnd, oracle, 1_200);
        PolicyEvolutionController.GenerationResult r2 = c.endGeneration(1_200);
        assertEquals(2, r2.generation());
        assertEquals(new ArrayList<>(oracle), ens.inOrder());

        // Lineage: gen-1 founders + bred offspring, all in-box (the flag is off), parents named.
        assertTrue(births.size() >= 3, "births: " + births);
        assertTrue(births.stream().anyMatch(l -> "founder".equals(l.op())));
        assertTrue(births.stream().anyMatch(l -> !"founder".equals(l.op()) && l.parentA() != null),
                "bred offspring must name a parent: " + births);
        // Window discipline is loud.
        assertThrows(IllegalStateException.class, () -> c.endGeneration(1));
    }

    @Test
    @DisplayName("same seed, same lineage — the run is reproducible")
    void deterministicLineage() {
        List<List<PolicyGenome>> runs = new ArrayList<>();
        for (int run = 0; run < 2; run++) {
            EnsembleOrderedSet<Integer> ens = ensemble(RedBlackStrategy::new, 3);
            PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                    ens, nursery(ens), new RollingWorkloadMonitor(), MorphPolicy.defaults(),
                    List.of(PolicyGenome.weightBalanced(3, 2)), 2, false, 99L);
            Random rnd = new Random(7);
            List<PolicyGenome> seen = new ArrayList<>();
            for (int gen = 0; gen < 3; gen++) {
                seen.addAll(c.beginGeneration());
                churn(c, rnd, null, 800);
                c.endGeneration(800);
            }
            runs.add(seen);
        }
        assertEquals(runs.get(0), runs.get(1), "identical seeds must breed identical lineages");
    }

    @Test
    @DisplayName("an unsound genome dies by its own invariant; the population continues without it")
    void unsoundOffspringDies() {
        EnsembleOrderedSet<Integer> ens = ensemble(RedBlackStrategy::new, 2);
        PolicyGenome unsound = PolicyGenome.weightBalanced(5, 3);   // the V1 finding
        PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                ens, nursery(ens), new RollingWorkloadMonitor(), MorphPolicy.defaults(),
                List.of(PolicyGenome.weightBalanced(3, 2), unsound), 1, false, 11_2026L);

        Random rnd = new Random(11_2026 + 5 * 31 + 3);              // the discovering seed family
        TreeSet<Integer> oracle = new TreeSet<>();
        boolean died = false;
        for (int gen = 0; gen < 6 && !died; gen++) {
            c.beginGeneration();
            churn(c, rnd, oracle, 1_500);
            died = c.endGeneration(1_500).deaths() > 0;
        }
        assertTrue(died, "(5,3) must fail its own invariant under churn");
        assertTrue(c.graveyard().contains(unsound), "graveyard: " + c.graveyard());
        // Death is permanent: the dead genome is never bred or materialized again.
        for (int gen = 0; gen < 3; gen++) {
            assertFalse(c.beginGeneration().contains(unsound), "the dead must stay dead");
            churn(c, rnd, oracle, 400);
            c.endGeneration(400);
        }
        // And the safety thesis holds even through a death: no data lost anywhere.
        assertEquals(new ArrayList<>(oracle), ens.inOrder());
    }

    @Test
    @DisplayName("out-of-box exploration happens only behind the flag")
    void outOfBoxOnlyBehindFlag() {
        // Founder at the box edge: any +1 Δ-step must cross it. Flag on → crossing allowed.
        for (boolean flag : new boolean[]{false, true}) {
            EnsembleOrderedSet<Integer> ens = ensemble(RedBlackStrategy::new, 3);
            PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                    ens, nursery(ens), new RollingWorkloadMonitor(), MorphPolicy.defaults(),
                    List.of(PolicyGenome.weightBalanced(8, 4)), 2, flag, 4242L);
            Random rnd = new Random(3);
            boolean sawOutOfBox = false;
            for (int gen = 0; gen < 6; gen++) {
                for (PolicyGenome g : c.beginGeneration()) {
                    sawOutOfBox |= !g.inVerifiedBox();
                }
                churn(c, rnd, null, 600);
                c.endGeneration(600);
            }
            assertEquals(flag, sawOutOfBox,
                    "out-of-box genomes iff the flag is on (flag=" + flag + ")");
        }
    }

    @Test
    @DisplayName("promotion is selection: the winner takes the throne, the deposed joins the nursery")
    void promotionIsSelection() {
        EnsembleOrderedSet<Integer> ens = ensemble(SplayStrategy::new, 2);   // beatable incumbent
        EnsembleMember<Integer> oldPrimary = ens.primary();
        PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                ens, nursery(ens), new RollingWorkloadMonitor(), new MorphPolicy(1_000, 0.05, 2),
                List.of(PolicyGenome.weightBalanced(3, 2)), 1, false, 5L);

        Random rnd = new Random(42);
        boolean promoted = false;
        for (int gen = 0; gen < 8 && !promoted; gen++) {
            c.beginGeneration();
            for (int op = 0; op < 1_500; op++) {                    // read-heavy, uniform
                int key = rnd.nextInt(2_000);
                if (rnd.nextInt(100) < 25) { if (rnd.nextBoolean()) c.add(key); else c.remove(key); }
                else c.contains(key);
            }
            promoted = c.endGeneration(1_500).promoted();
        }
        assertTrue(promoted, "WB must depose a splay primary on uniform read-heavy churn");
        assertTrue(ens.primary().orderedSet().getStrategy() instanceof WeightBalancedStrategy);
        assertTrue(c.nursery().contains(oldPrimary), "the deposed primary must join the nursery");
        assertFalse(c.nursery().contains(ens.primary()), "the throne is not a nursery slot");
        // The loop keeps breeding after the succession.
        c.beginGeneration();
        churn(c, rnd, null, 300);
        assertTrue(c.endGeneration(300).evaluated() >= 1);
    }

    @Test
    @DisplayName("a recorded session carries the lineage: births and deaths in the arena JSON")
    void recordedLineage() {
        EnsembleOrderedSet<Integer> ens = ensemble(RedBlackStrategy::new, 2);
        EnsembleMember<Integer> slot0 = nursery(ens).get(0);
        PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                ens, nursery(ens), new RollingWorkloadMonitor(), MorphPolicy.defaults(),
                List.of(PolicyGenome.weightBalanced(3, 2)), 1, false, 8L);

        TreeSessionRecorder<Integer> recorder = TreeSessionRecorder.attach(slot0.orderedSet());
        c.setEventListener(recorder);
        Random rnd = new Random(9);
        for (int gen = 0; gen < 2; gen++) {
            c.beginGeneration();
            churn(c, rnd, null, 400);
            c.endGeneration(400);
        }
        c.setEventListener(null);
        slot0.orderedSet().setEventListener(null);

        String json = recorder.toJson();
        assertTrue(json.contains("\"type\": \"Lineage\""), "births must be in the session");
        assertTrue(json.contains("\"op\": \"founder\""));
        assertTrue(json.contains("\"type\": \"Trial\""));
        assertTrue(json.contains("\"phase\": \"CULLED\""), "selection deaths must be visible");
        assertFalse(json.contains("NaN"), "JSON must stay parseable");
    }
}
