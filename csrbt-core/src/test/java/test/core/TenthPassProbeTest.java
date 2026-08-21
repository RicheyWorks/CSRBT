package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.evolution.GenomeDrivenTreeController;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.LoadStatus;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.SaveStatus;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Tenth-pass probes (2026-08-20). Each shows a defect the hunt confirmed, now fixed.
 */
class TenthPassProbeTest {

    @Test
    @DisplayName("C4: a NaN trait is refused, not silently clamped through")
    void nanTraitIsRefused() {
        TreeGenome.BalanceTraits traits = new TreeGenome().getBalanceTraits();
        // Before the fix, NaN slipped through clamp() (NaN is neither < nor >), poisoned every
        // fitness comparison, and made recommendedStructure() silently answer RED_BLACK.
        assertThrows(IllegalArgumentException.class,
                () -> traits.setBalancePreference(Double.NaN),
                "a NaN trait must be rejected at the boundary");
        assertThrows(IllegalArgumentException.class,
                () -> new TreeGenome.BalanceTraits(Double.NaN, 0.5, 0.5),
                "a NaN trait must be rejected in the constructor too");
    }

    @Test
    @DisplayName("C2: a deep splay checkpoint restores without a StackOverflow")
    void deepCheckpointRestoreDoesNotOverflow() {
        TreeContext ctx = new TreeContext(new SplayStrategy<>());
        // Sequential inserts into a splay tree build a long right spine — exactly the depth
        // that made the recursive deepCopy overflow the stack on restore.
        for (int i = 0; i < 12_000; i++) {
            ctx.add(i);
        }
        ctx.getHistory().saveCheckpoint("deep");               // iterative — succeeds
        ctx.add(999_999);                                      // diverge from the checkpoint
        assertTrue(ctx.getHistory().restoreCheckpoint("deep"), // must NOT StackOverflow
                "the deep checkpoint restores via the iterative copy");
        assertEquals(12_000, ctx.getSize(), "and restores the checkpoint's contents exactly");
        assertTrue(ctx.contains(0) && ctx.contains(11_999), "boundary keys survive");
        assertTrue(!ctx.contains(999_999), "the post-checkpoint key is gone");
    }

    @Test
    @DisplayName("C3: loadSnapshot discards stale undo history instead of eating restored keys")
    void loadSnapshotClearsUndoHistory() {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>(), io);
        String name = "c3-probe-" + System.nanoTime();
        try {
            ctx.add(1); ctx.add(2); ctx.add(3); ctx.add(4); ctx.add(5);
            ctx.saveSnapshot(name);
            ctx.add(6);                                        // a mutation recorded in undo history
            ctx.loadSnapshot(name);                            // wholesale content replacement
            assertEquals(List.of(1, 2, 3, 4, 5), ctx.inOrder(), "the snapshot's contents restored");

            // Before the fix, undo replayed "inverse of ADD(6)" then "inverse of ADD(5)" against
            // the restored snapshot and silently deleted key 5. Now the history is empty.
            ctx.getHistory().undo();
            ctx.getHistory().undo();
            assertEquals(List.of(1, 2, 3, 4, 5), ctx.inOrder(),
                    "no stale undo may delete a legitimately-restored key");
        } finally {
            io.deleteSnapshot(name);
        }
    }

    private static String snap(String base) {
        return base + "-" + System.nanoTime();                 // unique; snapshots/ is scratch
    }

    @Test
    @DisplayName("C5: an invalid-UTF-8 snapshot is MALFORMED (quarantine), not FAILED (retry forever)")
    void invalidUtf8IsMalformedNotRetryable() throws IOException {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        String name = snap("c5-badutf8");
        Path file = Path.of("snapshots", name + ".rbt");
        Files.createDirectories(file.getParent());
        try {
            // 0xFF is never a legal UTF-8 byte, so the reader throws MalformedInputException — a
            // deterministic property of the file. Before the fix loadFailure lumped every
            // IOException into FAILED ("retryable"), so an ADR-026 caller would retry a
            // permanently-corrupt file forever instead of quarantining it.
            Files.write(file, new byte[]{(byte) 0xFF, (byte) 0xFE, 'x', '\n'});
            var result = adapter.tryLoadOrderedSet(name, KeySerializer.INTEGER);
            assertEquals(LoadStatus.MALFORMED, result.status(),
                    "corrupt bytes must be quarantined, not reported retryable");
        } finally {
            Files.deleteIfExists(file);
        }
    }

    @Test
    @DisplayName("C6: data appended after a valid tree is refused, not silently ignored")
    void trailingDataAfterTreeIsRefused() throws IOException {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int k = 1; k <= 5; k++) set.add(k);
        String name = snap("c6-trailing");
        adapter.saveSnapshot(name, set, KeySerializer.INTEGER);
        Path file = Path.of("snapshots", name + ".rbt");
        try {
            // The node stream (line 1) ends exactly when the tree is complete; the size tripwire
            // can't catch garbage APPENDED past a valid tree (the node count still matches). Before
            // the fix, deserializePreOrder loaded the prefix and dropped the tail silently.
            List<String> lines = Files.readAllLines(file);
            lines.set(1, lines.get(1) + "GARBAGE");
            Files.write(file, lines);
            var result = adapter.tryLoadOrderedSet(name, KeySerializer.INTEGER);
            assertEquals(LoadStatus.MALFORMED, result.status(),
                    "trailing data past the tree is corruption, not a bigger tree");
        } finally {
            adapter.deleteSnapshot(name);
        }
    }

    @Test
    @DisplayName("C7: the flat writer refuses a control-char key instead of saving an unloadable file")
    void flatSaveRefusesControlCharKey() {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        // A caller-supplied serializer that does NOT encode reserved characters (the defect the
        // finding names): its token carries a raw '\n', which would split the flat format's single
        // data line. The flat writer used to check only ';', report SAVED, and leave a file that
        // could never load. Now it fails loudly at save time.
        KeySerializer<String> rawUnsafe = new KeySerializer<>() {
            @Override public String serialize(String key)   { return key; }   // no encoding
            @Override public String deserialize(String tok) { return tok; }
        };
        PersistentTreeEngine<String> engine = PersistentTreeEngine.withNaturalOrder();
        engine.add("apple");
        engine.add("bad\nkey");
        engine.add("mango");
        String name = snap("c7-flatctl");
        try {
            assertThrows(IllegalArgumentException.class,
                    () -> adapter.trySaveSnapshot(name, engine.snapshot(), rawUnsafe),
                    "a key serializing to a control character must be refused, not saved unloadable");
        } finally {
            adapter.deleteSnapshot(name);
        }
    }

    @Test
    @DisplayName("C8: a filesystem without atomic rename fails the save, keeping the previous snapshot")
    void nonAtomicFilesystemFailsSave() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int k = 1; k <= 3; k++) set.add(k);
        String name = snap("c8-nonatomic");
        FilePersistenceAdapter normal = new FilePersistenceAdapter();
        normal.saveSnapshot(name, set, KeySerializer.INTEGER);  // establish a previous good snapshot

        // An adapter whose publish rename behaves as it would on a filesystem with no atomic move.
        FilePersistenceAdapter atomicless = new FilePersistenceAdapter() {
            @Override protected void moveIntoPlace(java.nio.file.Path tmp, java.nio.file.Path target)
                    throws java.io.IOException {
                throw new java.nio.file.AtomicMoveNotSupportedException(
                        String.valueOf(tmp), String.valueOf(target), "simulated: no atomic rename");
            }
        };
        try {
            // Before the fix this fell back to a non-atomic overwrite and still reported SAVED,
            // risking the previous snapshot. Now the save fails loudly instead.
            var result = atomicless.trySaveSnapshot(name, set, KeySerializer.INTEGER);
            assertEquals(SaveStatus.FAILED, result.status(),
                    "a non-atomic filesystem must fail the save, not silently degrade to SAVED");
            OrderedSet<Integer> reloaded = normal.loadOrderedSet(name, KeySerializer.INTEGER);
            assertEquals(List.of(1, 2, 3), reloaded.inOrder(),
                    "the previous good snapshot survives a refused non-atomic save");
        } finally {
            normal.deleteSnapshot(name);
        }
    }

    @Test
    @DisplayName("C9: a dead process's orphan .tmp staging file is swept on construction")
    void orphanStagingIsSwept() throws IOException {
        Path dir = Path.of("snapshots");
        Files.createDirectories(dir);
        long deadPid = 900_000L;
        while (ProcessHandle.of(deadPid).isPresent()) deadPid++;   // a pid that is NOT a live process
        String base = "c9-" + System.nanoTime();
        Path orphan   = dir.resolve(base + ".rbt." + deadPid + ".1.tmp");
        Path mineLive = dir.resolve(base + ".rbt." + ProcessHandle.current().pid() + ".1.tmp");
        Path realSnap = dir.resolve(base + ".rbt");
        Files.write(orphan,   new byte[]{1, 2, 3});
        Files.write(mineLive, new byte[]{4, 5, 6});
        Files.write(realSnap, new byte[]{7, 8, 9});
        try {
            new FilePersistenceAdapter();                          // construction sweeps orphans
            assertTrue(Files.notExists(orphan), "a dead process's staging file must be swept");
            assertTrue(Files.exists(mineLive), "a live process's in-flight staging must be left alone");
            assertTrue(Files.exists(realSnap), "a real snapshot must never be swept");
        } finally {
            Files.deleteIfExists(orphan);
            Files.deleteIfExists(mineLive);
            Files.deleteIfExists(realSnap);
        }
    }

    @Test
    @DisplayName("C12: a missing snapshot is ABSENT (not FAILED), opened directly with no TOCTOU pre-check")
    void missingSnapshotIsAbsent() {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        String name = snap("c12-missing");                         // never created
        assertEquals(LoadStatus.ABSENT,
                adapter.tryLoadOrderedSet(name, KeySerializer.INTEGER).status(),
                "a missing snapshot loads as ABSENT via the direct-open path");
        assertEquals(LoadStatus.ABSENT, adapter.tryLoadSnapshot(name).status(),
                "the int path agrees");
    }

    @Test
    @DisplayName("C10: a refused morph advances neither the morph count nor the morph log")
    void refusedMorphIsNoPhantom() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int i = 0; i < 32; i++) ctx.add(i);
        List<Integer> before = ctx.inOrder();
        // A controller whose strategy factory always yields a candidate the health gate rejects
        // (DroppingStrategy builds an empty tree). Before the fix, applyStructure returned void, so
        // evaluateViaGenome/forceMorph committed decision=MORPH, the streak reset, and a morphLog
        // entry for a morph that never happened.
        GenomeDrivenTreeController controller =
                new GenomeDrivenTreeController(ctx, new TreeGenome()) {
                    @Override protected TreeStrategy<Integer> buildStrategy(TreeGenome.StructureType t) {
                        return new HealthGatedMorphTest.DroppingStrategy();
                    }
                };
        int countBefore = controller.getMorphCount();
        boolean morphed = controller.forceMorph();
        assertFalse(morphed, "a health-gate refusal must report false, not a phantom success");
        assertEquals(countBefore, controller.getMorphCount(), "a refused morph must not bump the count");
        assertTrue(controller.getMorphLog().isEmpty(), "and must not append a phantom morph event");
        assertEquals(before, ctx.inOrder(), "the incumbent tree is untouched");
        assertEquals("RedBlackStrategy", ctx.getTree().getStrategy().getClass().getSimpleName(),
                "the incumbent strategy is unchanged");
    }

    @Test
    @DisplayName("C11: HYBRID is scored competitively, not suppressed by a phantom 0.0 slot")
    void hybridIsNotStructurallySuppressed() {
        TreeGenome g = TreeGenome.hybridGenome();
        TreeGenome.ScoreCard card = g.scoreCard();
        double hybrid = card.scoreOf(TreeGenome.StructureType.HYBRID);
        double sum = 0.0;
        int n = 0;
        for (TreeGenome.StructureType t : TreeGenome.StructureType.values()) {
            if (t == TreeGenome.StructureType.HYBRID) continue;
            sum += card.scoreOf(t);
            n++;
        }
        double avgReal = sum / n;
        // Before the fix, HYBRID's self-score took range()/average() over a ScoreCard carrying a
        // placeholder 0.0 in HYBRID's own slot — the 0.0 was the range's minimum (inflating the
        // spread penalty) and dragged the mean down, so HYBRID scored ~0.19 next to peers near 0.78
        // and could practically never be recommended. It must now be central to the seven real scores.
        assertTrue(hybrid >= 0.6 * avgReal,
                "HYBRID (" + hybrid + ") must be central to the seven real scores (avg " + avgReal
                + "), not dragged toward 0 by the old placeholder slot");
    }

    @Test
    @DisplayName("C13: a control-plane morph is recorded in the morph log, not just counted")
    void controlPlaneMorphIsLogged() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        // Eager control policy (no cooldown, one stability win) so a skewed read workload morphs
        // RB → Splay without the 4000-op production cooldown — the ControllerConvergenceTest seam.
        GenomeDrivenTreeController c = new GenomeDrivenTreeController(
                ctx, TreeGenome.redBlackGenome(), new MorphPolicy(0, 0.10, 1));
        for (int i = 0; i < 64; i++) ctx.add(i);
        for (int i = 0; i < 600; i++) c.contains(7);               // one hot key → a control-plane morph
        assertTrue(c.getMorphCount() >= 1, "the skewed read workload triggers a control-plane morph");
        assertEquals(c.getMorphCount(), c.getMorphLog().size(),
                "every counted control-plane morph must appear in the morph log (no silent morph)");
    }
}
