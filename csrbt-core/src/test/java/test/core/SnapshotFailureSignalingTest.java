package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.SaveResult;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.SaveStatus;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-025 — {@code saveSnapshot} failure signaling. The held ADR candidate the 2026-08-14 wiring
 * audit recorded ("the three {@code FilePersistenceAdapter.saveSnapshot} variants log-and-swallow
 * {@code IOException} with a {@code void} return — a caller cannot programmatically detect a failed
 * save") and the sixth pass carried forward unchanged.
 *
 * <p>Every failure here is a <b>real</b> one produced against the real filesystem — a commit rename
 * that cannot publish because a directory occupies the target path, and an open that cannot create
 * the staging file because the name exceeds the filesystem's component limit — plus one adapter
 * double that implements the published seam and nothing else. Nothing here mocks
 * {@code FilePersistenceAdapter}'s own logic.</p>
 */
@DisplayName("ADR-025 — snapshot save failure signaling")
class SnapshotFailureSignalingTest {

    private static final Path DIR = Paths.get("snapshots");
    private final List<Path> litter = new ArrayList<>();

    @AfterEach
    void cleanUp() throws IOException {
        for (Path p : litter) {
            if (Files.isDirectory(p)) {
                try (Stream<Path> walk = Files.walk(p)) {
                    List<Path> all = walk.sorted(Comparator.reverseOrder()).toList();
                    for (Path q : all) Files.deleteIfExists(q);
                }
            } else {
                Files.deleteIfExists(p);
            }
        }
        litter.clear();
    }

    private String snap(String base) {
        return "adr024_" + base + "_" + System.nanoTime();
    }

    /**
     * Make the commit rename fail for {@code name}: a NON-EMPTY DIRECTORY at the target path.
     * {@code Files.move} onto it fails with a {@code FileSystemException} on every POSIX
     * filesystem, regardless of the running user — so the probe is not a no-op under a uid that
     * bypasses permission bits, which is exactly how a naive read-only-directory probe silently
     * passes when the suite runs as root.
     */
    private void blockCommit(String name) throws IOException {
        Path target = DIR.resolve(name + ".rbt");
        Files.createDirectories(target.resolve("occupant"));
        litter.add(target);
    }

    /** A name whose staging path exceeds the 255-byte component limit: the open itself fails. */
    private static String unopenableName() {
        return "adr024_" + "x".repeat(240);
    }

    private static OrderedSet<Integer> populated(int n) {
        OrderedSet<Integer> set = new OrderedSet<>(new RedBlackStrategy<Integer>(),
                Comparator.<Integer>naturalOrder());
        for (int i = 0; i < n; i++) set.add(i);
        return set;
    }

    private static TreeContext context(int n) {
        TreeContext ctx = new TreeContext(new RedBlackStrategy<Integer>());
        for (int i = 0; i < n; i++) ctx.add(i);
        return ctx;
    }

    private static long strayStagingFiles() throws IOException {
        try (Stream<Path> paths = Files.list(DIR)) {
            return paths.filter(p -> p.toString().endsWith(".tmp")).count();
        }
    }

    // ── The signal exists, and it is right ────────────────────────────────────────────────

    @Test
    @DisplayName("a commit rename that cannot publish is reported FAILED, on every save shape")
    void commitFailureIsReportedOnEverySaveShape() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();

        String n1 = snap("ctx");
        blockCommit(n1);
        SaveResult r1 = io.trySaveSnapshot(n1, context(20));
        assertTrue(r1.failed(), "the TreeContext path must report the failure: " + r1);
        assertEquals(SaveStatus.FAILED, r1.status());
        assertNotNull(r1.cause(), "a FAILED result carries the IOException that caused it");
        assertInstanceOf(IOException.class, r1.cause());
        assertEquals(n1, r1.name());

        String n2 = snap("generic");
        blockCommit(n2);
        SaveResult r2 = io.trySaveSnapshot(n2, populated(50), KeySerializer.INTEGER);
        assertTrue(r2.failed(), "the generic OrderedSet path must report the failure: " + r2);

        String n3 = snap("persistent");
        blockCommit(n3);
        PersistentTreeEngine<Integer> pe = new PersistentTreeEngine<>(Comparator.<Integer>naturalOrder());
        for (int i = 0; i < 20; i++) pe.add(i);
        SaveResult r3 = io.trySaveSnapshot(n3, pe.snapshot(), KeySerializer.INTEGER);
        assertTrue(r3.failed(), "the persistent-engine path must report the failure: " + r3);

        String n4 = snap("ensemble");
        blockCommit(n4);
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.builder(Comparator.<Integer>naturalOrder())
                .member(RedBlackStrategy::new)
                .member(AVLStrategy::new)
                .build();
        for (int i = 0; i < 30; i++) ens.add(i);
        SaveResult r4 = io.trySaveSnapshot(n4, ens, KeySerializer.INTEGER);
        assertTrue(r4.failed(), "the ensemble path must report its single underlying save: " + r4);

        assertEquals(0L, strayStagingFiles(), "a failed save must not leave staging files behind");
    }

    @Test
    @DisplayName("a staging file that cannot even be created is reported FAILED")
    void unopenableStagingPathIsReportedFailed() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String name = unopenableName();
        SaveResult r = io.trySaveSnapshot(name, populated(20), KeySerializer.INTEGER);
        assertTrue(r.failed(), "an open that cannot create the staging file is a failed save: " + r);
        assertInstanceOf(IOException.class, r.cause());
        assertTrue(r.detail().contains("Exception"), "the detail names the failure: " + r.detail());
        assertFalse(Files.exists(DIR.resolve(name + ".rbt")));
        assertEquals(0L, strayStagingFiles());
    }

    @Test
    @DisplayName("a save that works is reported SAVED, and the snapshot really is loadable")
    void successIsReportedAndIsReal() {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String name = snap("ok");
        litter.add(DIR.resolve(name + ".rbt"));

        SaveResult r = io.trySaveSnapshot(name, populated(64), KeySerializer.INTEGER);
        assertTrue(r.saved(), "an ordinary save must report SAVED: " + r);
        assertFalse(r.failed());
        assertNull(r.cause(), "nothing failed, so there is no cause");
        assertSame(r, r.orThrow(), "orThrow is a no-op on a good save and returns the result");

        OrderedSet<Integer> back = io.loadOrderedSet(name, KeySerializer.INTEGER,
                Comparator.<Integer>naturalOrder());
        assertNotNull(back, "SAVED must mean the file is really there and really loadable");
        assertEquals(64, back.size());
    }

    // ── What the signal is worth: the caller can act on it ────────────────────────────────

    @Test
    @DisplayName("a failed overwrite reports FAILED and the previous snapshot is still loadable")
    void aFailedOverwriteLeavesThePreviousSnapshotIntactAndSaysSo() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String good = snap("keep");
        litter.add(DIR.resolve(good + ".rbt"));
        assertTrue(io.trySaveSnapshot(good, populated(40), KeySerializer.INTEGER).saved());

        // Same name, and this time the commit cannot publish: the D-3 staging scheme means the
        // committed file is untouched. Before ADR-025 that guarantee held but was invisible —
        // the caller could not tell "saved the new one" from "kept the old one".
        Path target = DIR.resolve(good + ".rbt");
        Path stash = DIR.resolve(good + ".rbt.stash");
        litter.add(stash);            // so an assertion failure below cannot leave the stash behind
        Files.move(target, stash);
        Files.createDirectories(target.resolve("occupant"));   // block the rename
        SaveResult r = io.trySaveSnapshot(good, populated(400), KeySerializer.INTEGER);
        assertTrue(r.failed(), "the overwrite could not be published: " + r);

        try (Stream<Path> walk = Files.walk(target)) {
            for (Path q : walk.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(q);
        }
        Files.move(stash, target);

        OrderedSet<Integer> back = io.loadOrderedSet(good, KeySerializer.INTEGER,
                Comparator.<Integer>naturalOrder());
        assertNotNull(back);
        assertEquals(40, back.size(),
                "the failed overwrite must not have replaced or truncated the good snapshot");
    }

    @Test
    @DisplayName("orThrow escalates a known failure to an UncheckedIOException carrying the cause")
    void orThrowEscalatesAFailure() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String name = snap("throw");
        blockCommit(name);
        SaveResult r = io.trySaveSnapshot(name, populated(20), KeySerializer.INTEGER);
        UncheckedIOException boom = assertThrows(UncheckedIOException.class, r::orThrow);
        assertTrue(boom.getMessage().contains(name), boom.getMessage());
        assertSame(r.cause(), boom.getCause(),
                "the escalation must carry the original IOException, not a fresh one");
    }

    // ── Source compatibility: nothing that used to work stopped working ───────────────────

    @Test
    @DisplayName("the void saveSnapshot entry points are unchanged: still void, still swallowing")
    void theVoidEntryPointsStillSwallow() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String n1 = snap("void_ctx");
        String n2 = snap("void_generic");
        blockCommit(n1);
        blockCommit(n2);

        // Exactly the pre-ADR-025 call shapes, compiling and behaving exactly as before.
        assertDoesNotThrow(() -> io.saveSnapshot(n1, context(20)));
        assertDoesNotThrow(() -> io.saveSnapshot(n2, populated(20), KeySerializer.INTEGER));
        assertEquals(0L, strayStagingFiles());
    }

    @Test
    @DisplayName("a caller defect still throws — a bad name is not an environmental failure")
    void argumentValidationStillThrows() {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        TreeContext ctx = context(5);
        for (String bad : new String[]{"../escape", "a/b", "a\\b", ""}) {
            assertThrows(IllegalArgumentException.class, () -> io.trySaveSnapshot(bad, ctx),
                    "trySaveSnapshot must reject the name the same way saveSnapshot does: " + bad);
            assertThrows(IllegalArgumentException.class, () -> io.saveSnapshot(bad, ctx), bad);
        }
        assertThrows(IllegalArgumentException.class,
                () -> io.trySaveSnapshot(snap("nullks"), populated(3), null));
        assertThrows(IllegalArgumentException.class,
                () -> io.trySaveSnapshot(snap("nullset"), (OrderedSet<Integer>) null,
                        KeySerializer.INTEGER));
    }

    // ── The additive default: an adapter that has not opted in says so ────────────────────

    /**
     * A third-party adapter written against the published 0.2.0 seam — {@code void saveSnapshot}
     * and nothing else. It compiles unchanged against the ADR-025 interface (that is the point)
     * and its inherited {@code trySaveSnapshot} must not claim a success it cannot know about.
     */
    private static final class LegacyAdapterDouble implements TreePersistenceAdapter {
        int saves;
        boolean everythingFails = true;

        @Override public void saveSnapshot(String name, TreeContext snapshot) {
            saves++;
            if (everythingFails) return;   // swallowed, exactly like the 0.2.0 file adapter
        }
        @Override public TreeContext loadSnapshot(String name) { return null; }
        @Override public List<String> listSnapshots() { return List.of(); }
        @Override public boolean deleteSnapshot(String name) { return false; }
    }

    @Test
    @DisplayName("an adapter that does not report says UNREPORTED, never a fabricated SAVED")
    void anAdapterThatDoesNotReportSaysSo() {
        LegacyAdapterDouble legacy = new LegacyAdapterDouble();
        SaveResult r = legacy.trySaveSnapshot("anything", context(5));

        assertEquals(1, legacy.saves, "the default must still do the work, through saveSnapshot");
        assertEquals(SaveStatus.UNREPORTED, r.status(),
                "the save silently failed; claiming SAVED would be the signal lying");
        assertFalse(r.saved(), "UNREPORTED is not success");
        assertFalse(r.failed(), "and it is not a failure either — it is 'this adapter cannot say'");
        assertNull(r.cause());
        assertSame(r, r.orThrow(), "an unknown outcome must not be escalated as a failure");
    }

    @Test
    @DisplayName("SaveResult's states are exclusive and a FAILED result always carries its cause")
    void resultStatesAreWellFormed() {
        assertThrows(IllegalArgumentException.class,
                () -> new SaveResult("n", SaveStatus.FAILED, "no cause", null),
                "a FAILED result without a cause is not a usable signal");
        assertThrows(IllegalArgumentException.class,
                () -> new SaveResult("n", SaveStatus.SAVED, "with cause", new IOException("x")),
                "a success does not carry a cause");
        assertThrows(NullPointerException.class,
                () -> new SaveResult(null, SaveStatus.SAVED, "d", null));

        assertTrue(SaveResult.saved("n").saved());
        assertTrue(SaveResult.failed("n", new IOException("disk full")).failed());
        assertTrue(SaveResult.failed("n", new IOException("disk full")).detail().contains("disk full"),
                "the detail must carry enough to tell a full disk from a bad configuration");
        assertEquals(SaveStatus.UNREPORTED, SaveResult.unreported("n").status());
    }
}
