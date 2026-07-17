package io.github.richeyworks.csrbt.experimental;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.evolution.GenomeDrivenTreeController;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.export.TreeSessionRecorder;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

/**
 * Records the canonical replay-arena session (ADR-010 X2) — the file checked in at
 * {@code docs/arena-session.json} and replayed by {@code demo/visualizer.html}.
 *
 * <p>Nothing here is staged: the workload regimes run through
 * {@link GenomeDrivenTreeController}, the production default stack (control plane ON), and
 * every morph in the session is the controller's own decision, health-gated and recorded by
 * the {@link TreeSessionRecorder} the moment it commits. The script mirrors the proven
 * convergence tests (G3/G4): uniform build-up holds Red-Black; a hot-key read regime
 * converges to Splay; a heavy write regime flushes the window and returns to Red-Black.</p>
 *
 * <p>Run from the repo root (stdout is clean JSON):</p>
 * <pre>{@code ./gradlew :csrbt-experimental:arenaSession > docs/arena-session.json}</pre>
 */
public final class ArenaSession {

    private ArenaSession() { }

    public static void main(String[] args) {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        TreeSessionRecorder<Integer> recorder = TreeSessionRecorder.attach(ctx.getOrderedSet());
        GenomeDrivenTreeController controller = new GenomeDrivenTreeController(
                ctx, TreeGenome.redBlackGenome(), new MorphPolicy(0, 0.10, 1));

        // Regime 1 — uniform build-up: mixed keys, no skew. The controller holds RB.
        for (int i = 0; i < 64; i++) controller.add(i * 7919 % 997);

        // Regime 2 — hot-key reads: one key dominates (skew→1, reads→1). Expect RB → Splay.
        for (int i = 0; i < 600; i++) controller.contains(7 * 7919 % 997);

        // Regime 3 — heavy writes flush the read window. Expect Splay → RB. (The morph
        // lands a couple hundred writes in; 1,200 keeps the final snapshot replay-sized.)
        for (int i = 0; i < 1_200; i++) controller.add(1_000 + i);

        System.out.println(recorder.toJson());
    }
}
