package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.DeleteResult;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.DeleteStatus;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.DirectoryNotEmptyException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-026 amendment (2026-08-18) — snapshot <em>delete</em> outcome signaling. The last of the
 * three weak returns ADR-025 named the shape of: {@code deleteSnapshot} answered {@code false}
 * both for "there was nothing of that name" — which is the caller's own goal, already met — and
 * for "the delete was attempted and failed", which leaves the snapshot exactly where it was.
 *
 * <p>The failure here is a <b>real</b> one produced against the real filesystem: a non-empty
 * directory occupying the snapshot's path, which {@code Files.deleteIfExists} refuses with a
 * {@code DirectoryNotEmptyException}. That probe is uid-independent, so it cannot silently pass
 * when the suite runs as root — the trap ADR-025 documents rejecting a read-only-directory probe
 * for. The only double is a {@code LegacyDeleteAdapterDouble} implementing the published seam and
 * nothing else, which is what pins the additive default.</p>
 */
@DisplayName("ADR-026 amendment — snapshot delete outcome signaling")
class SnapshotDeleteSignalingTest {

    private static final Path DIR = Paths.get("snapshots");
    private final List<Path> litter = new ArrayList<>();

    @AfterEach
    void cleanUp() throws IOException {
        for (Path p : litter) {
            if (Files.isDirectory(p)) {
                try (Stream<Path> walk = Files.walk(p)) {
                    for (Path q : walk.sorted(Comparator.reverseOrder()).toList()) {
                        Files.deleteIfExists(q);
                    }
                }
            } else {
                Files.deleteIfExists(p);
            }
        }
        litter.clear();
    }

    private String snap(String base) {
        String name = "del_" + base + "_" + System.nanoTime();
        litter.add(DIR.resolve(name + ".rbt"));
        return name;
    }

    private static TreeContext ctx(int... keys) {
        TreeContext c = new TreeContext(new RedBlackStrategy<>());
        for (int k : keys) c.add(k);
        return c;
    }

    // ── The three outcomes ───────────────────────────────────────────────────────────────

    @Test
    @DisplayName("the two meanings of false are now two answers")
    void nothingToDeleteIsNotAFailedDelete() throws IOException {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();

        String present = snap("present");
        adapter.saveSnapshot(present, ctx(1, 2, 3));
        DeleteResult removed = adapter.tryDeleteSnapshot(present);
        assertEquals(DeleteStatus.DELETED, removed.status());
        assertNull(removed.cause());
        assertFalse(Files.exists(DIR.resolve(present + ".rbt")), "and the file is actually gone");

        DeleteResult again = adapter.tryDeleteSnapshot(present);
        assertEquals(DeleteStatus.ABSENT, again.status(),
                "a second delete of the same name found nothing — not a failure");

        // A directory occupying the snapshot's own path: deleteIfExists refuses it, and the
        // entry is still there afterwards. No permission bits involved, so root cannot bypass it.
        String blocked = snap("blocked");
        Path asDir = DIR.resolve(blocked + ".rbt");
        Files.createDirectories(asDir.resolve("occupied"));
        DeleteResult failed = adapter.tryDeleteSnapshot(blocked);
        assertEquals(DeleteStatus.FAILED, failed.status(),
                "an IOException is not 'there was nothing there'");
        assertInstanceOf(DirectoryNotEmptyException.class, failed.cause(),
                "and it carries the real exception: " + failed.detail());
        assertTrue(Files.exists(asDir), "the entry the delete could not remove is still there");

        // The three statuses are three distinct answers where the boolean had one.
        assertEquals(3, Stream.of(removed, again, failed).map(DeleteResult::status).distinct().count());
        assertFalse(removed.status() == again.status());
    }

    @Test
    @DisplayName("gone() is what a retention sweep is actually asking")
    void goneCoversTheTwoOutcomesThatSatisfyTheCaller() throws IOException {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        String present = snap("sweep");
        adapter.saveSnapshot(present, ctx(4, 5, 6));

        assertTrue(adapter.tryDeleteSnapshot(present).gone(), "removed → the name is free");
        assertTrue(adapter.tryDeleteSnapshot(present).gone(), "absent → the name is free");

        String blocked = snap("sweepblocked");
        Files.createDirectories(DIR.resolve(blocked + ".rbt").resolve("occupied"));
        assertFalse(adapter.tryDeleteSnapshot(blocked).gone(),
                "failed → the name is NOT free, and this is the case the boolean hid");

        assertFalse(DeleteResult.unreported(present).gone(),
                "an adapter that does not know has not said it is gone");
    }

    @Test
    @DisplayName("orThrow escalates a failed delete and only a failed delete")
    void orThrowEscalatesTheOneStateThatDefeatsTheCaller() throws IOException {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        String name = snap("throw");
        adapter.saveSnapshot(name, ctx(7));

        assertSame(DeleteStatus.DELETED, adapter.tryDeleteSnapshot(name).orThrow().status());
        assertSame(DeleteStatus.ABSENT, adapter.tryDeleteSnapshot(name).orThrow().status(),
                "ABSENT is the caller's own goal, met — escalating it would fire on the "
                        + "successful half of gone()");

        String blocked = snap("throwblocked");
        Files.createDirectories(DIR.resolve(blocked + ".rbt").resolve("occupied"));
        UncheckedIOException boom =
                assertThrows(UncheckedIOException.class, () -> adapter.tryDeleteSnapshot(blocked).orThrow());
        assertInstanceOf(DirectoryNotEmptyException.class, boom.getCause());
        assertTrue(boom.getMessage().contains(blocked), boom.getMessage());
    }

    // ── The published contract is untouched ──────────────────────────────────────────────

    @Test
    @DisplayName("deleteSnapshot's boolean means exactly what it always meant")
    void thePublishedReturnIsUnchanged() throws IOException {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        String name = snap("published");
        adapter.saveSnapshot(name, ctx(1, 2));

        assertTrue(adapter.deleteSnapshot(name), "true: this call removed one");
        assertFalse(adapter.deleteSnapshot(name), "false: nothing of that name");

        String blocked = snap("publishedblocked");
        Files.createDirectories(DIR.resolve(blocked + ".rbt").resolve("occupied"));
        assertFalse(adapter.deleteSnapshot(blocked), "false: the delete failed — as before");
    }

    @Test
    @DisplayName("argument validation still throws, before any I/O")
    void callerDefectsStillThrow() {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        assertThrows(IllegalArgumentException.class, () -> adapter.tryDeleteSnapshot(""));
        assertThrows(IllegalArgumentException.class, () -> adapter.tryDeleteSnapshot("../escape"));
        assertThrows(IllegalArgumentException.class, () -> adapter.tryDeleteSnapshot("sub/dir"));
    }

    // ── The additive default ─────────────────────────────────────────────────────────────

    /** A third-party adapter written against the published 0.2.0 seam and nothing else. */
    private static final class LegacyDeleteAdapterDouble implements TreePersistenceAdapter {
        boolean present = true;
        @Override public void saveSnapshot(String name, TreeContext snapshot) { }
        @Override public TreeContext loadSnapshot(String name) { return null; }
        @Override public List<String> listSnapshots() { return List.of(); }
        @Override public boolean deleteSnapshot(String name) {
            boolean was = present;
            present = false;
            return was;
        }
    }

    @Test
    @DisplayName("the default reports only what a boolean can prove")
    void theDefaultReportsOnlyWhatItKnows() {
        LegacyDeleteAdapterDouble legacy = new LegacyDeleteAdapterDouble();

        DeleteResult first = legacy.tryDeleteSnapshot("x");
        assertEquals(DeleteStatus.DELETED, first.status(),
                "true is unambiguous evidence that a snapshot was removed");

        DeleteResult second = legacy.tryDeleteSnapshot("x");
        assertEquals(DeleteStatus.UNREPORTED, second.status(),
                "false is the ambiguous half — guessing ABSENT here would be the signal lying, "
                        + "which is what ADR-025 built this shape to avoid");
        assertFalse(second.gone(), "and an unreported outcome must not claim the name is free");
        assertSame(second, second.orThrow(), "nor escalate: nothing is known to have failed");
    }

    // ── The record's own invariants ──────────────────────────────────────────────────────

    @Test
    @DisplayName("a FAILED result carries its cause and no other status may")
    void resultStatesAreWellFormed() {
        IOException io = new IOException("disk went away");

        assertThrows(IllegalArgumentException.class,
                () -> new DeleteResult("n", DeleteStatus.FAILED, "no cause", null));
        assertThrows(IllegalArgumentException.class,
                () -> new DeleteResult("n", DeleteStatus.DELETED, "cause but not failed", io));
        assertThrows(NullPointerException.class,
                () -> new DeleteResult(null, DeleteStatus.ABSENT, "d", null));
        assertThrows(NullPointerException.class, () -> DeleteResult.failed("n", null));

        DeleteResult failed = DeleteResult.failed("n", io);
        assertSame(io, failed.cause());
        assertTrue(failed.failed());
        assertFalse(failed.gone());
        assertTrue(failed.detail().contains("disk went away"), failed.detail());
        assertNotNull(DeleteResult.absent("n").detail());
        assertTrue(DeleteResult.deleted("n").toString().contains("DELETED"));
    }
}
