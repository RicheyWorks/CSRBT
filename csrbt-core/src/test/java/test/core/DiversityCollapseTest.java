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

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-012 E2 — diversity as a first-class output. {@link TreeEvent.Diversity} is emitted
 * once per generation (survivor count, distinct founder lineages, mean pairwise parameter
 * spread, deaths split disqualified/culled), recorded by {@link TreeSessionRecorder}, and
 * read back into <em>nothing</em> — mechanisms are E4's.
 *
 * <p>House discipline: correctness hard (one Diversity event per generation, fields
 * consistent with the {@code GenerationResult}, recorder serializes it); the dynamics —
 * how fast (μ+λ) finds E1's two-cell sliver from deliberately bad founders, and how fast
 * diversity collapses once it has — are printed per generation with one
 * {@code event=adr012_e2_collapse} line per seed, never hard-asserted beyond existence.</p>
 *
 * <p>E1 sharpened the thesis: with only (3,2)/(4,2) viable, "the population converges"
 * is near-tautological in-box. The numbers worth quantifying are <b>G_sliver</b> (first
 * generation a survivor sits in the viable sliver — the gate + selection <em>finding</em>
 * it from founders that are all unsound) and <b>G_collapse</b> (first generation the
 * survivors are one lineage at spread ≤ 1 — the V5 collapse, measured).</p>
 */
@DisplayName("ADR-012 E2 — the diversity collapse, measured")
class DiversityCollapseTest {

    private static final int GENERATIONS = 12;
    private static final int OPS_PER_GEN = 1_200;
    private static final long[] SEEDS = { 11L, 2026L, 42L };

    @Test
    @DisplayName("Diversity events: one per generation, consistent, recorded; collapse printed")
    void collapseMeasured() {
        StringBuilder verdicts = new StringBuilder();
        for (long seed : SEEDS) {
            EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(() -> new RedBlackStrategy<Integer>())   // incumbent
                    .member(() -> new RedBlackStrategy<Integer>())   // nursery ×4 (λ=4)
                    .member(() -> new RedBlackStrategy<Integer>())
                    .member(() -> new RedBlackStrategy<Integer>())
                    .member(() -> new RedBlackStrategy<Integer>())
                    .mode(EnsembleMode.SAMPLED_SHADOW)
                    .shadowSampleRate(1.0)
                    .build();
            List<EnsembleMember<Integer>> nursery = ens.members().subList(1, 5);

            // Founders: all four deliberately OUTSIDE E1's viable sliver — diverse corners
            // of the box. The search must find (3,2)/(4,2) by walking, or stay unsound.
            PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                    ens, nursery, new RollingWorkloadMonitor(), new MorphPolicy(800, 0.05, 2),
                    List.of(PolicyGenome.weightBalanced(2, 1),
                            PolicyGenome.weightBalanced(6, 1),
                            PolicyGenome.weightBalanced(5, 4),
                            PolicyGenome.weightBalanced(8, 7)),
                    2, false, seed);

            TreeSessionRecorder<Integer> recorder = TreeSessionRecorder.attach(nursery.get(0).orderedSet());
            List<TreeEvent.Diversity<Integer>> divs = new ArrayList<>();
            c.setEventListener(e -> {
                if (e instanceof TreeEvent.Diversity<Integer> d) divs.add(d);
                recorder.onEvent(e);
            });

            Random rnd = new Random(seed);
            int gSliver = -1;
            int gCollapse = -1;
            System.out.println("seed " + seed + " — gen | surv | lineages | spread | dq | culled | survivors");
            for (int gen = 1; gen <= GENERATIONS; gen++) {
                c.beginGeneration();
                for (int op = 0; op < OPS_PER_GEN; op++) {
                    int key = rnd.nextInt(512);
                    int kind = rnd.nextInt(100);
                    if (kind < 40)      c.add(key);
                    else if (kind < 70) c.remove(key);
                    else                c.contains(key);
                }
                PolicyEvolutionController.GenerationResult r = c.endGeneration(OPS_PER_GEN);

                // ── Hard: exactly one Diversity event, consistent with the result. ──
                assertEquals(gen, divs.size(), "one Diversity event per generation");
                TreeEvent.Diversity<Integer> d = divs.get(gen - 1);
                assertEquals(gen, d.generation());
                assertEquals(r.survivors().size(), d.survivors(), "survivors agree with result");
                assertEquals(r.deaths(), d.disqualified(), "disqualified = the result's deaths");
                assertTrue(d.lineages() <= Math.max(1, d.survivors()), "lineages ≤ survivors");
                if (d.survivors() >= 1) assertTrue(d.lineages() >= 1, "≥1 lineage when anyone lives");
                if (d.survivors() < 2)  assertTrue(Double.isNaN(d.meanPairwiseDistance()),
                        "spread is NaN below two parameterized survivors");

                boolean inSliver = r.survivors().contains(PolicyGenome.weightBalanced(3, 2))
                                || r.survivors().contains(PolicyGenome.weightBalanced(4, 2));
                if (gSliver < 0 && inSliver) gSliver = gen;
                if (gCollapse < 0 && d.survivors() >= 1 && d.lineages() == 1
                        && (Double.isNaN(d.meanPairwiseDistance()) || d.meanPairwiseDistance() <= 1.0)) {
                    gCollapse = gen;
                }
                System.out.printf("        %3d  | %4d | %8d | %6s | %2d | %6d | %s%n",
                        gen, d.survivors(), d.lineages(),
                        Double.isNaN(d.meanPairwiseDistance()) ? "—"
                                : String.format("%.2f", d.meanPairwiseDistance()),
                        d.disqualified(), d.culled(), r.survivors());
            }
            c.setEventListener(null);

            // ── Hard: the recorder serializes Diversity decisions. ──
            String json = recorder.toJson();
            assertTrue(json.contains("\"type\": \"Diversity\""),
                    "recorder carries Diversity decision points");
            assertTrue(json.contains("\"lineages\""), "diversity fields serialized");

            String line = "event=adr012_e2_collapse seed=" + seed
                    + " gSliver=" + gSliver + " gCollapse=" + gCollapse
                    + " finalLineages=" + divs.get(divs.size() - 1).lineages()
                    + " finalSpread=" + (Double.isNaN(divs.get(divs.size() - 1).meanPairwiseDistance())
                            ? "NaN" : String.format("%.2f", divs.get(divs.size() - 1).meanPairwiseDistance()));
            System.out.println(line);
            verdicts.append(line).append('\n');
            ens.close();
        }
        System.out.print(verdicts);
    }
}
