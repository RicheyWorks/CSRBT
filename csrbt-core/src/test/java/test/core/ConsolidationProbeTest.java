package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.export.TreeSessionRecorder;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.util.TreeHistory;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probes (consolidation pass 2026-08-12): the three remaining fixable items from the
 * audits' documented-not-fixed lists, each red against the unfixed code.
 *
 * <p>D-2: with a sliding window active, {@code add} can evict the oldest key but only
 * {@code ADD(v)} was recorded — undo dropped the evicted key permanently, against the
 * class's "undo restores the tree's contents" contract, and undo/redo cycles
 * compounded the loss. D-3: saves wrote directly to the final path, so a failed save
 * (e.g. an unencodable key) TRUNCATED an existing good snapshot at file-open before
 * failing — the previous snapshot was destroyed. B3: recorded sessions embedded
 * wall-clock meters, so two identical runs never produced identical bytes and the
 * checked-in canonical replay files always showed spurious diffs on regeneration.</p>
 */
@DisplayName("Consolidation probes — windowed undo, atomic saves, deterministic sessions")
class ConsolidationProbeTest {

    // ── D-2 ───────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("D-2: undo of a window-evicting add restores the evicted key")
    void undoRestoresWindowEvictedKey() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        ctx.setMaxSize(3);
        ctx.add(1);
        ctx.add(2);
        ctx.add(3);
        ctx.add(4);                                     // evicts 1 → [2,3,4]
        assertEquals(List.of(2, 3, 4), ctx.getOrderedSet().inOrder());

        TreeHistory history = ctx.getHistory();
        assertTrue(history.undo(), "the add must be undoable");
        assertEquals(List.of(1, 2, 3), ctx.getOrderedSet().inOrder(),
                "undo of add(4) must restore the evicted key 1, not just drop 4");

        // Redo RE-EXECUTES the add: the restored key re-entered at the FIFO tail, so
        // the re-run may evict a DIFFERENT key — the refreshed record tracks whichever
        // it was, and the follow-up undo must be exact again (the contents contract).
        assertTrue(history.redo());
        assertEquals(3, ctx.getOrderedSet().size(), "redo re-applies the bounded add");
        assertTrue(ctx.getOrderedSet().inOrder().contains(4), "redo re-inserts 4");
        assertTrue(history.undo());
        assertEquals(List.of(1, 2, 3), ctx.getOrderedSet().inOrder(),
                "a second undo must restore the full contents — no compounding loss");
    }

    // ── D-3 ───────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("D-3: a failed save leaves the previous snapshot intact (atomic write)")
    void failedSaveDoesNotDestroyPreviousSnapshot() {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        String name = "probe-atomic-" + System.nanoTime();

        OrderedSet<String> good = OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
        good.add("alpha");
        good.add("beta");
        adapter.saveSnapshot(name, good, KeySerializer.string());
        assertNotNull(adapter.loadOrderedSet(name, KeySerializer.string()), "baseline saved");

        // An unpaired surrogate cannot be UTF-8 encoded: the writer throws at
        // flush/close, AFTER the old file was already truncated by open (pre-fix).
        OrderedSet<String> poison = OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
        poison.add("a\uD800b");
        adapter.saveSnapshot(name, poison, KeySerializer.string());   // fails internally

        OrderedSet<String> reloaded = adapter.loadOrderedSet(name, KeySerializer.string());
        assertNotNull(reloaded,
                "the failed save must not destroy the existing snapshot (write must be "
                + "temp-file + atomic rename, not truncate-in-place)");
        assertEquals(good.inOrder(), reloaded.inOrder(),
                "the previous good contents must survive a failed overwrite");
        adapter.deleteSnapshot(name);
    }

    // ── B3 ────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("B3: two identical recorded runs produce byte-identical session JSON")
    void recordedSessionsAreByteDeterministic() {
        String a = recordOneRun();
        String b = recordOneRun();
        assertEquals(a, b,
                "identical op sequences must record identical bytes — wall-clock "
                + "meters in the embedded snapshots made every regeneration differ");
    }

    private static String recordOneRun() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        TreeSessionRecorder<Integer> rec = TreeSessionRecorder.attach(set);
        for (int k = 0; k < 200; k++) set.add(k * 37 % 500);
        for (int k = 0; k < 50; k++) set.remove(k * 91 % 500);
        set.setEventListener(null);
        return rec.toJson();
    }
}
