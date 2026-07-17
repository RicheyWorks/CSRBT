package io.github.richeyworks.csrbt.experimental;

import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.evolution.PolicyEvolutionController;
import io.github.richeyworks.csrbt.evolution.PolicyGenome;
import io.github.richeyworks.csrbt.export.TreeSessionRecorder;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import java.util.Comparator;
import java.util.List;
import java.util.Random;

/**
 * Records the canonical <b>search</b> replay session (ADR-011 V3/V4; roadmap "ship
 * visibility") — the file checked in at {@code docs/arena-search-session.json} and
 * replayed by {@code demo/visualizer.html}. Where {@code ArenaSession} shows the
 * controller choosing among the fixed four, this one shows the <b>evolution machine</b>:
 * genomes born ({@code Lineage}), tried through the health gate, scored, the unsound
 * (5,3) founder dying by its own invariant ({@code DISQUALIFIED} — V1's first finding,
 * replayed live), selection culls, and a winner promoted through the MorphPolicy gates
 * ({@code SELECTED}) off a splay primary. Nothing is staged: every event is the
 * controller's own decision on a seeded stream, snapshotted the moment it commits.
 *
 * <p>Run from the repo root (writes the file directly — unlike {@code ArenaSession} this run
 * logs WARN lines for the on-record deaths, so stdout is not clean JSON):</p>
 * <pre>{@code ./gradlew :csrbt-experimental:searchArenaSession
 *     [--args="docs/arena-search-session.json"]}</pre>
 */
public final class SearchArenaSession {

    private SearchArenaSession() { }

    public static void main(String[] args) {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new SplayStrategy<Integer>())      // a beatable incumbent
                .member(() -> new RedBlackStrategy<Integer>())   // nursery slot 0 (recorded)
                .member(() -> new RedBlackStrategy<Integer>())   // nursery slot 1
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(1.0)
                .build();
        List<EnsembleMember<Integer>> nursery = ens.members().subList(1, 3);

        PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                ens, nursery, new RollingWorkloadMonitor(), new MorphPolicy(800, 0.05, 2),
                List.of(PolicyGenome.weightBalanced(3, 2),       // the literature point
                        PolicyGenome.weightBalanced(5, 3)),      // V1's unsound finding
                1, false, 11_2026L);

        // The recorder watches nursery slot 0's tree; the controller feeds it the
        // search's decision stream (births, trials, deaths, culls, promotion).
        TreeSessionRecorder<Integer> recorder = TreeSessionRecorder.attach(nursery.get(0).orderedSet());
        c.setEventListener(recorder);

        Random rnd = new Random(11_2026 + 5 * 31 + 2);           // the discovering seed family

        // Act 1 — delete-heavy churn: enough remove pressure that WB(5,3)'s one-rotation
        // repair fails its own invariant and the genome dies on the record. The key range
        // is kept small so every snapshot stays replay-sized.
        for (int gen = 0; gen < 2; gen++) {
            c.beginGeneration();
            for (int op = 0; op < 1_000; op++) {
                int key = rnd.nextInt(160);
                if (rnd.nextInt(100) < 55) c.add(key); else c.remove(key);
            }
            c.endGeneration(1_000);
        }

        // Act 2 — uniform read-heavy: splay's worst diet. The surviving WB lineage wins
        // the gates (cooldown 800, 5% margin, 2 consecutive wins) and takes the throne.
        for (int gen = 0; gen < 4; gen++) {
            c.beginGeneration();
            for (int op = 0; op < 1_200; op++) {
                int key = rnd.nextInt(220);
                if (rnd.nextInt(100) < 25) { if (rnd.nextBoolean()) c.add(key); else c.remove(key); }
                else c.contains(key);
            }
            c.endGeneration(1_200);
        }

        c.setEventListener(null);
        java.nio.file.Path out = java.nio.file.Path.of(
                args.length > 0 ? args[0] : "docs/arena-search-session.json");
        try {
            java.nio.file.Files.writeString(out, recorder.toJson());
        } catch (java.io.IOException e) {
            throw new RuntimeException("could not write " + out, e);
        }
        System.err.println("wrote " + out);
        ens.close();
    }
}
