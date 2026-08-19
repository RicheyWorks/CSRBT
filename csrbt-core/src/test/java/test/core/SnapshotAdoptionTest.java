package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.event.TreeEventListener;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * What survives {@code TreeContext.loadSnapshot}'s wholesale set adoption (audit 2026-08-18,
 * item A).
 *
 * <p>A load does not mutate the live {@link OrderedSet} — it <em>replaces</em> it with the one the
 * adapter deserialized, and everything a caller had attached to the old object goes with it unless
 * the load carries it across by hand. The seventh pass found and fixed the first instance (the
 * sliding-window bound, which came back as 0 and unbounded a bounded context); this is the second,
 * and the tests below also pin the pieces that are deliberately <em>not</em> carried, so the next
 * reader can tell an audited decision from an oversight.</p>
 *
 * <p>Nothing is mocked: the snapshots go through the real {@code FilePersistenceAdapter} and the
 * real filesystem, and the listener is a real {@link TreeEventListener} recording real events.</p>
 */
@DisplayName("TreeContext.loadSnapshot — what the set adoption carries across")
class SnapshotAdoptionTest {

    private static final Path DIR = Paths.get("snapshots");
    private final List<Path> litter = new ArrayList<>();

    @AfterEach
    void cleanUp() throws IOException {
        for (Path p : litter) Files.deleteIfExists(p);
        litter.clear();
    }

    private String snap(String base) {
        String name = "adopt_" + base + "_" + System.nanoTime();
        litter.add(DIR.resolve(name + ".rbt"));
        return name;
    }

    /** Records every event it is handed, in order. */
    private static final class Recorder implements TreeEventListener<Integer> {
        final List<TreeEvent<Integer>> seen = new ArrayList<>();
        @Override public void onEvent(TreeEvent<Integer> event) { seen.add(event); }
    }

    private static TreeContext ctx(int... keys) {
        TreeContext c = new TreeContext(new RedBlackStrategy<>());
        for (int k : keys) c.add(k);
        return c;
    }

    // ── The defect ───────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("a registered event listener still receives events after a load")
    void theListenerSurvivesTheAdoption() {
        TreeContext live = ctx(1, 2, 3);
        Recorder recorder = new Recorder();
        live.getOrderedSet().setEventListener(recorder);

        String name = snap("listener");
        ctx(10, 20, 30).saveSnapshot(name);

        OrderedSet<Integer> before = live.getOrderedSet();
        live.loadSnapshot(name);
        assertNotSame(before, live.getOrderedSet(), "the load must actually adopt a different set");
        assertEquals(List.of(10, 20, 30), live.inOrder(), "and actually load the snapshot");

        assertSame(recorder, live.getOrderedSet().getEventListener(),
                "the live context's listener must be re-attached to the adopted set");

        // The observable half: the registration is worth nothing unless events arrive.
        recorder.seen.clear();
        live.add(40);
        live.remove(10);
        assertEquals(2, recorder.seen.size(),
                "an insert and a remove after the load must reach the listener, not the "
                        + "discarded set: " + recorder.seen);
        assertEquals(new TreeEvent.Insert<>(40), recorder.seen.get(0));
        assertEquals(new TreeEvent.Remove<>(10), recorder.seen.get(1));
    }

    @Test
    @DisplayName("an unobserved context stays unobserved — the snapshot brings no listener")
    void nothingIsInventedForAnUnobservedContext() {
        TreeContext live = ctx(1, 2, 3);
        String name = snap("unobserved");

        TreeContext source = ctx(7, 8, 9);
        source.getOrderedSet().setEventListener(new Recorder());   // the SAVER's observer
        source.saveSnapshot(name);

        live.loadSnapshot(name);
        assertNull(live.getOrderedSet().getEventListener(),
                "a listener is an observer of a context, not payload on disk — the snapshot's "
                        + "must not arrive with its keys");
    }

    @Test
    @DisplayName("the load itself emits nothing, bound or unbound")
    void theLoadIsNotAStreamOfMutations() {
        TreeContext live = ctx(1, 2, 3);
        live.setMaxSize(2);                       // an over-tight bound: the load must evict
        Recorder recorder = new Recorder();
        live.getOrderedSet().setEventListener(recorder);
        recorder.seen.clear();                    // ignore the eviction setMaxSize(2) just did

        String name = snap("quiet");
        ctx(10, 20, 30, 40).saveSnapshot(name);
        live.loadSnapshot(name);

        assertEquals(2, live.size(), "the live bound still caps the load");
        assertTrue(recorder.seen.isEmpty(),
                "a load emits no Insert for the keys it brings in, so it must emit no Evict for "
                        + "the ones the bound drops either: " + recorder.seen);

        // …and the listener is live again immediately afterwards.
        live.add(99);
        assertEquals(1, recorder.seen.stream().filter(e -> e instanceof TreeEvent.Insert).count(),
                "the listener resumes at the next real mutation: " + recorder.seen);
    }

    @Test
    @DisplayName("a failed load leaves the listener exactly as it was")
    void aRefusedLoadTouchesNothing() throws IOException {
        TreeContext live = ctx(1, 2, 3);
        Recorder recorder = new Recorder();
        live.getOrderedSet().setEventListener(recorder);
        OrderedSet<Integer> before = live.getOrderedSet();

        String name = snap("truncated");
        ctx(10, 20, 30).saveSnapshot(name);
        Path file = DIR.resolve(name + ".rbt");
        List<String> lines = Files.readAllLines(file);
        // Truncate the data line: the declared-size tripwire refuses this (ADR-026 MALFORMED).
        Files.write(file, List.of(lines.get(0), lines.get(1).substring(0, lines.get(1).length() / 2)));

        live.loadSnapshot(name);
        assertSame(before, live.getOrderedSet(), "a refused load adopts nothing");
        assertSame(recorder, live.getOrderedSet().getEventListener());
        assertEquals(List.of(1, 2, 3), live.inOrder());
    }

    // ── The rest of the adoption, pinned as audited decisions ─────────────────────────────

    @Test
    @DisplayName("the strategy and the augmentor come from the file, by design")
    void thePayloadCarriesItsOwnStrategy() {
        TreeContext live = ctx(1, 2, 3);
        String name = snap("strategy");
        TreeContext source = new TreeContext(new io.github.richeyworks.csrbt.strategy.AVLStrategy<>());
        for (int k : new int[]{10, 20, 30}) source.add(k);
        source.saveSnapshot(name);

        live.loadSnapshot(name);
        assertEquals("AVLStrategy", live.getStrategy().getClass().getSimpleName(),
                "the header records the strategy and the load restores it — the snapshot's, not "
                        + "the live context's");
    }

    @Test
    @DisplayName("a load resets the stress signal, like every other wholesale rebuild")
    void theStressSignalDoesNotOutliveTheTreeItDescribes() throws Exception {
        TreeContext live = ctx(1, 2, 3);

        // The red-red stress counter is written only by updateMetadata, and only a strategy that
        // leaves a red-red edge at the inserted node ever drives it above zero — measured over
        // 5,000 random inserts per strategy, that is HybridStrategy alone (684 inserts non-zero,
        // peak 3); RedBlack, AVL and Splay are flat 0. Rather than couple this pin to another
        // module's balancing internals, the state is installed directly: what is under test is
        // that a load clears it, not how it comes to be non-zero.
        stressOf(live).put("redRedViolations", 3);

        String name = snap("stress");
        ctx(10, 20, 30).saveSnapshot(name);
        live.loadSnapshot(name);

        assertTrue(stressOf(live).isEmpty(),
                "a counter describing a tree the load just replaced must not survive it — "
                        + "selfRepair() and clear() both reset it: " + stressOf(live));
    }

    @SuppressWarnings("unchecked")
    private static java.util.Map<String, Integer> stressOf(TreeContext c) throws Exception {
        java.lang.reflect.Field f = TreeContext.class.getDeclaredField("stressEvents");
        f.setAccessible(true);
        return (java.util.Map<String, Integer>) f.get(c);
    }

    @Test
    @DisplayName("a load leaves this context's own collaborators alone")
    void theContainerKeepsWhatIsTheContainers() {
        TreeContext live = ctx(1, 2, 3);
        live.setAutoMorphEnabled(true);
        var history = live.getHistory();
        var adapter = live.getPersistenceAdapter();

        String name = snap("collaborators");
        ctx(10, 20, 30).saveSnapshot(name);
        live.loadSnapshot(name);

        assertSame(history, live.getHistory(), "history is the container's");
        assertSame(adapter, live.getPersistenceAdapter(), "so is the persistence adapter");
        assertTrue(live.isAutoMorphEnabled(), "and so is the auto-morph switch");
    }
}
