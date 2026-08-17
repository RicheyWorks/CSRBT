package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.LoadResult;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.LoadStatus;
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

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-026 — snapshot <em>load</em> failure signaling. ADR-025's own held list, bullets 1 and 2:
 * {@code loadSnapshot} answered {@code null} for nine different things and {@code listSnapshots}
 * answered {@code []} for two, so a caller deciding what state to run on could not tell "there is
 * no checkpoint, start fresh" from "the checkpoint is corrupt" or "the disk would not read".
 *
 * <p>Every failure here is a <b>real</b> one produced against the real filesystem — files truncated,
 * emptied, re-headered and re-tokenized on disk, plus a genuine {@code IOException} from a directory
 * occupying the snapshot's path. That last probe is uid-independent, so it cannot silently pass when
 * the suite runs as root, which is the trap ADR-025 documents rejecting a read-only-directory probe
 * for. The only double is a {@code LegacyLoadAdapterDouble} implementing the published seam and
 * nothing else, which is what pins the additive defaults.</p>
 */
@DisplayName("ADR-026 — snapshot load failure signaling")
class SnapshotLoadSignalingTest {

    private static final Path DIR = Paths.get("snapshots");
    private final List<Path> litter = new ArrayList<>();

    @AfterEach
    void cleanUp() throws IOException {
        for (Path p : litter) {
            if (Files.isDirectory(p)) {
                try (Stream<Path> walk = Files.walk(p)) {
                    for (Path q : walk.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(q);
                }
            } else {
                Files.deleteIfExists(p);
            }
        }
        litter.clear();
        // The listing probe moves the shared directory aside; make certain it is back even if an
        // assertion escaped the try/finally that restores it.
        Files.createDirectories(DIR);
    }

    private String snap(String base) {
        return "adr026_" + base + "_" + System.nanoTime();
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

    /** Write a good snapshot under {@code name} and hand back its two lines for mutilation. */
    private String[] goodLines(FilePersistenceAdapter io, String name, int n) throws IOException {
        litter.add(DIR.resolve(name + ".rbt"));
        io.saveSnapshot(name, populated(n), KeySerializer.INTEGER);
        List<String> lines = Files.readAllLines(DIR.resolve(name + ".rbt"));
        return new String[]{lines.get(0), lines.get(1)};
    }

    /** Put an arbitrary two-line file at a fresh snapshot name and return the name. */
    private String fileWith(String base, String header, String data) throws IOException {
        String name = snap(base);
        Path p = DIR.resolve(name + ".rbt");
        litter.add(p);
        Files.write(p, data == null ? List.of(header) : List.of(header, data));
        return name;
    }

    /**
     * Cut a pre-order data line at a token boundary. Cutting mid-token would break the decoder
     * first ("unreadable content") and never reach the P-2 declared-size tripwire, which is the
     * refusal these tests are about — truncation that parses cleanly into a smaller tree is
     * exactly the case S6-03 exists to catch.
     */
    private static String truncatedAtTokenBoundary(String data) {
        return data.substring(0, data.lastIndexOf(';', data.length() / 2) + 1);
    }

    /** A directory occupying the snapshot's path: the reader's open/read throws {@code IOException}. */
    private String unreadableName() throws IOException {
        String name = snap("ioerr");
        Path p = DIR.resolve(name + ".rbt");
        Files.createDirectories(p);
        litter.add(p);
        return name;
    }

    // ── The nine causes are no longer one answer ──────────────────────────────────────────

    @Test
    @DisplayName("the nine ways a load returned null are now four distinguishable statuses")
    void theNineCausesAreNoLongerOneAnswer() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String[] good = goodLines(io, snap("src"), 200);
        String header = good[0], data = good[1];
        Comparator<Integer> order = Comparator.naturalOrder();

        // 1 — nothing there at all: the ONE case where "start fresh" is right.
        assertEquals(LoadStatus.ABSENT,
                io.tryLoadOrderedSet(snap("nothing"), KeySerializer.INTEGER, order).status());

        // 2..7 — the file is there and is not a usable snapshot.
        String empty = fileWith("empty", "", null);
        Files.write(DIR.resolve(empty + ".rbt"), new byte[0]);
        assertEquals(LoadStatus.MALFORMED,
                io.tryLoadOrderedSet(empty, KeySerializer.INTEGER, order).status(), "empty file");

        assertEquals(LoadStatus.MALFORMED,
                io.tryLoadOrderedSet(fileWith("hdr1", "garbage", data), KeySerializer.INTEGER, order).status(),
                "one-field header");

        String[] hf = header.split("\\|");
        hf[3] = "many";
        assertEquals(LoadStatus.MALFORMED,
                io.tryLoadOrderedSet(fileWith("nsize", String.join("|", hf), data),
                        KeySerializer.INTEGER, order).status(),
                "non-numeric size field");

        assertEquals(LoadStatus.MALFORMED,
                io.tryLoadOrderedSet(fileWith("nodata", header, null), KeySerializer.INTEGER, order).status(),
                "header present, no data line");

        assertEquals(LoadStatus.MALFORMED,
                io.tryLoadOrderedSet(fileWith("trunc", header, truncatedAtTokenBoundary(data)),
                        KeySerializer.INTEGER, order).status(),
                "truncated data line — the S6-03 declared-size tripwire");

        assertEquals(LoadStatus.MALFORMED,
                io.tryLoadOrderedSet(fileWith("badtok", header, data.replaceFirst("^[^,]+", "notanumber")),
                        KeySerializer.INTEGER, order).status(),
                "a key token that cannot be decoded");

        // 8 — the M-2 structural gate: keys that parse but are not a valid tree.
        String[] two = header.split("\\|");
        two[3] = "2";
        assertEquals(LoadStatus.MALFORMED,
                io.tryLoadOrderedSet(fileWith("outoforder", String.join("|", two), "1,BLACK;9,RED;#;#;#;"),
                        KeySerializer.INTEGER, order).status(),
                "a tree that parses and violates the strategy's own invariant");

        // 9 — the environment, not the file.
        assertEquals(LoadStatus.FAILED,
                io.tryLoadOrderedSet(unreadableName(), KeySerializer.INTEGER, order).status(),
                "an IOException is the disk, not the snapshot");
    }

    @Test
    @DisplayName("ABSENT is an answer, not an error: no value, no cause, no escalation")
    void absentIsAnAnswerNotAnError() {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String name = snap("gone");
        LoadResult<TreeContext> r = io.tryLoadSnapshot(name);

        assertTrue(r.absent(), "no file of that name: " + r);
        assertEquals(name, r.name());
        assertNull(r.value(), "an ABSENT result has nothing to carry");
        assertNull(r.cause(), "nothing threw");
        assertFalse(r.loaded());
        assertFalse(r.malformed());
        assertFalse(r.failed());
        assertSame(r, r.orThrow(), "'there is no snapshot' is what the caller asked; it must not throw");

        TreeContext fallback = context(3);
        assertSame(fallback, r.orElse(fallback), "orElse is the fall-back-and-rebuild one-liner");
        assertNull(io.loadSnapshot(name), "the published null return is unchanged");
    }

    @Test
    @DisplayName("a truncated snapshot is MALFORMED with the numbers, and the file is left in place")
    void truncatedIsMalformedAndTheFileSurvives() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String[] good = goodLines(io, snap("src"), 200);
        String name = fileWith("trunc", good[0], truncatedAtTokenBoundary(good[1]));

        LoadResult<OrderedSet<Integer>> r = io.tryLoadOrderedSet(name, KeySerializer.INTEGER,
                Comparator.<Integer>naturalOrder());
        assertTrue(r.malformed(), "a truncated file is found-and-unusable, not absent: " + r);
        assertTrue(r.detail().contains("size mismatch"), r.detail());
        assertTrue(r.detail().contains("header=200"), "the detail carries what the header claimed: " + r.detail());
        assertNull(r.cause(), "nothing threw — the bytes are simply wrong");
        assertTrue(Files.exists(DIR.resolve(name + ".rbt")),
                "MALFORMED must leave the file for inspection, not consume it");
        assertNull(io.loadOrderedSet(name, KeySerializer.INTEGER, Comparator.<Integer>naturalOrder()),
                "the published null return is unchanged");
    }

    @Test
    @DisplayName("an I/O failure is FAILED and carries the real IOException, on every load shape")
    void ioFailureIsReportedOnEveryLoadShape() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        Comparator<Integer> order = Comparator.naturalOrder();

        String n1 = unreadableName();
        LoadResult<TreeContext> r1 = io.tryLoadSnapshot(n1);
        assertTrue(r1.failed(), "the TreeContext path must report the failure: " + r1);
        assertInstanceOf(IOException.class, r1.cause());
        assertTrue(r1.detail().contains("Exception"), "the detail names the failure: " + r1.detail());

        String n2 = unreadableName();
        assertTrue(io.tryLoadOrderedSet(n2, KeySerializer.INTEGER, order).failed(),
                "the generic OrderedSet path must report the failure");

        String n3 = unreadableName();
        assertTrue(io.tryLoadPersistent(n3, KeySerializer.INTEGER, order).failed(),
                "the persistent flat path must report the failure");

        String n4 = unreadableName();
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.builder(order)
                .member(RedBlackStrategy::new).member(AVLStrategy::new).build();
        assertTrue(io.tryLoadEnsemble(n4, KeySerializer.INTEGER, ens).failed(),
                "the ensemble path must report the failure");
    }

    @Test
    @DisplayName("a wrong-format file is MALFORMED, not ABSENT — telling a caller it is absent invites the overwrite")
    void wrongFormatIsMalformedNotAbsent() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String name = snap("structured");
        litter.add(DIR.resolve(name + ".rbt"));
        io.saveSnapshot(name, populated(30), KeySerializer.INTEGER);

        LoadResult<PersistentTreeEngine<Integer>> r =
                io.tryLoadPersistent(name, KeySerializer.INTEGER, Comparator.<Integer>naturalOrder());
        assertTrue(r.malformed(), "a structured snapshot is not a persistent one: " + r);
        assertTrue(r.detail().contains("not a persistent snapshot"), r.detail());
        assertNull(io.loadPersistent(name, KeySerializer.INTEGER, Comparator.<Integer>naturalOrder()));
    }

    @Test
    @DisplayName("a good snapshot round-trips through every reporting twin")
    void successIsReportedOnEveryLoadShape() {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        Comparator<Integer> order = Comparator.naturalOrder();

        String n1 = snap("okctx");
        litter.add(DIR.resolve(n1 + ".rbt"));
        io.saveSnapshot(n1, context(64));
        LoadResult<TreeContext> r1 = io.tryLoadSnapshot(n1);
        assertTrue(r1.loaded(), r1.toString());
        assertEquals(64, r1.value().getSize());
        assertSame(r1, r1.orThrow());
        assertSame(r1.value(), r1.orElse(null), "orElse hands back the loaded value");

        String n2 = snap("okset");
        litter.add(DIR.resolve(n2 + ".rbt"));
        io.saveSnapshot(n2, populated(50), KeySerializer.INTEGER);
        assertEquals(50, io.tryLoadOrderedSet(n2, KeySerializer.INTEGER).value().size(),
                "the natural-order convenience overload reports too");

        String n3 = snap("okpers");
        litter.add(DIR.resolve(n3 + ".rbt"));
        PersistentTreeEngine<Integer> pe = new PersistentTreeEngine<>(order);
        for (int i = 0; i < 20; i++) pe.add(i);
        io.saveSnapshot(n3, pe.snapshot(), KeySerializer.INTEGER);
        LoadResult<PersistentTreeEngine<Integer>> r3 = io.tryLoadPersistent(n3, KeySerializer.INTEGER);
        assertTrue(r3.loaded(), r3.toString());
        assertEquals(20, r3.value().size());

        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.builder(order)
                .member(RedBlackStrategy::new).member(AVLStrategy::new).build();
        LoadResult<EnsembleOrderedSet<Integer>> r4 = io.tryLoadEnsemble(n2, KeySerializer.INTEGER, ens);
        assertTrue(r4.loaded(), r4.toString());
        assertSame(ens, r4.value(), "the ensemble result carries the target it replayed into");
        assertEquals(50, ens.size());
    }

    // ── What the signal is worth: the caller can act on it ────────────────────────────────

    @Test
    @DisplayName("a malformed snapshot leaves the ensemble untouched AND says why it is not absent")
    void theEnsembleKeepsItsContentsAndLearnsWhy() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        Comparator<Integer> order = Comparator.naturalOrder();
        String[] good = goodLines(io, snap("src"), 300);
        String bad = fileWith("enstrunc", good[0], truncatedAtTokenBoundary(good[1]));

        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.builder(order)
                .member(RedBlackStrategy::new).member(AVLStrategy::new).build();
        for (int i = 1000; i < 1007; i++) ens.add(i);

        LoadResult<EnsembleOrderedSet<Integer>> r = io.tryLoadEnsemble(bad, KeySerializer.INTEGER, ens);
        assertTrue(r.malformed(), "S6-04's refusal, now with a reason: " + r);
        assertTrue(r.detail().contains("size mismatch"), r.detail());
        assertNull(r.value(), "a refused load carries no value");
        assertEquals(7, ens.size(), "the target must be exactly as it was (S6-04's guarantee)");
        assertFalse(io.loadEnsemble(bad, KeySerializer.INTEGER, ens),
                "the published boolean return is unchanged");
        assertEquals(7, ens.size());
    }

    @Test
    @DisplayName("orThrow escalates FAILED and MALFORMED — the two 'you do not have your data' states")
    void orThrowEscalatesTheTwoFailureStates() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        Comparator<Integer> order = Comparator.naturalOrder();

        String io1 = unreadableName();
        LoadResult<TreeContext> failed = io.tryLoadSnapshot(io1);
        UncheckedIOException boom = assertThrows(UncheckedIOException.class, failed::orThrow);
        assertTrue(boom.getMessage().contains(io1), boom.getMessage());
        assertSame(failed.cause(), boom.getCause(),
                "the escalation must carry the original IOException, not a fresh one");

        String[] good = goodLines(io, snap("src"), 60);
        String bad = fileWith("throwbad", good[0], truncatedAtTokenBoundary(good[1]));
        LoadResult<OrderedSet<Integer>> malformed = io.tryLoadOrderedSet(bad, KeySerializer.INTEGER, order);
        UncheckedIOException boom2 = assertThrows(UncheckedIOException.class, malformed::orThrow,
                "a corrupt snapshot is not something a caller should be able to ignore by accident");
        assertTrue(boom2.getMessage().contains("not usable"), boom2.getMessage());
        assertNotNull(boom2.getCause(), "UncheckedIOException always has one; it is synthesized from the detail");
        assertTrue(boom2.getCause().getMessage().contains("size mismatch"), "the synthesized cause keeps the detail");
    }

    // ── The listing ───────────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("a listing reports whether the directory was read — an empty list is no longer two facts")
    void listingSeparatesEmptyFromUnreadable() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        String name = snap("listed");
        litter.add(DIR.resolve(name + ".rbt"));
        io.saveSnapshot(name, populated(4), KeySerializer.INTEGER);

        LoadResult<List<String>> ok = io.tryListSnapshots();
        assertTrue(ok.loaded(), "the directory was read: " + ok);
        assertEquals(TreePersistenceAdapter.ALL_SNAPSHOTS, ok.name(),
                "a listing asks about the whole directory, not one snapshot");
        assertTrue(ok.value().contains(name), "and the names really are the names");

        // The same call with the directory gone. The suite runs serially (no parallel forks are
        // configured), and the directory is moved rather than deleted so no other test's snapshots
        // are destroyed by this probe; the finally puts it straight back.
        Path stash = Paths.get("snapshots-adr026-stash");
        Files.move(DIR, stash);
        LoadResult<List<String>> gone;
        try {
            gone = io.tryListSnapshots();
            assertEquals(List.of(), io.listSnapshots(),
                    "the published empty-list return is unchanged");
        } finally {
            Files.move(stash, DIR);
        }
        assertTrue(gone.failed(), "a directory that is not there is a fact about the disk: " + gone);
        assertInstanceOf(IOException.class, gone.cause());
        assertFalse(gone.loaded(), "and it is emphatically not 'there are no snapshots'");
    }

    // ── Source compatibility: nothing that used to work stopped working ───────────────────

    @Test
    @DisplayName("the published load entry points are unchanged: still null / false / empty, still no throw")
    void thePublishedReturnsAreUnchanged() throws IOException {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        Comparator<Integer> order = Comparator.naturalOrder();
        String[] good = goodLines(io, snap("src"), 120);
        String trunc = fileWith("compat", good[0], truncatedAtTokenBoundary(good[1]));
        String unreadable = unreadableName();
        String missing = snap("missing");

        for (String n : new String[]{trunc, unreadable, missing}) {
            assertNull(io.loadSnapshot(n), n);
            assertNull(io.loadOrderedSet(n, KeySerializer.INTEGER, order), n);
            assertNull(io.loadPersistent(n, KeySerializer.INTEGER, order), n);
            EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.builder(order)
                    .member(RedBlackStrategy::new).member(AVLStrategy::new).build();
            assertFalse(io.loadEnsemble(n, KeySerializer.INTEGER, ens), n);
        }

        // And the facade still leaves its live contents alone rather than throwing. TreeContext
        // builds its own FilePersistenceAdapter over the same directory, which is the path the
        // ADR's in-repo consumer actually takes.
        TreeContext live = context(9);
        live.loadSnapshot(trunc);
        assertEquals(9, live.getSize(), "a snapshot that cannot load must not disturb the live context");
        live.loadSnapshot(missing);
        assertEquals(9, live.getSize());
    }

    @Test
    @DisplayName("a caller defect still throws — a bad name is not an environmental failure")
    void argumentValidationStillThrows() {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        Comparator<Integer> order = Comparator.naturalOrder();
        for (String bad : new String[]{"../escape", "a/b", "a\\b", ""}) {
            assertThrows(IllegalArgumentException.class, () -> io.tryLoadSnapshot(bad),
                    "tryLoadSnapshot must reject the name the same way loadSnapshot does: " + bad);
            assertThrows(IllegalArgumentException.class, () -> io.loadSnapshot(bad), bad);
        }
        assertThrows(IllegalArgumentException.class,
                () -> io.tryLoadOrderedSet(snap("nullks"), null, order));
        assertThrows(IllegalArgumentException.class,
                () -> io.tryLoadPersistent(snap("nullorder"), KeySerializer.INTEGER, null));
        assertThrows(IllegalArgumentException.class,
                () -> io.tryLoadEnsemble(snap("nulltarget"), KeySerializer.INTEGER, null));
    }

    // ── The additive defaults: an adapter that has not opted in says what it can ───────────

    /**
     * A third-party adapter written against the published 0.2.0 seam and nothing else. It compiles
     * unchanged against the ADR-026 interface (that is the point), and its inherited
     * {@code tryLoadSnapshot} must report what it can honestly infer — never more.
     */
    private static final class LegacyLoadAdapterDouble implements TreePersistenceAdapter {
        TreeContext next;
        List<String> names = List.of();
        int loads;

        @Override public void saveSnapshot(String name, TreeContext snapshot) { }
        @Override public TreeContext loadSnapshot(String name) { loads++; return next; }
        @Override public List<String> listSnapshots() { return names; }
        @Override public boolean deleteSnapshot(String name) { return false; }
    }

    @Test
    @DisplayName("the default infers what it honestly can: LOADED from a value, UNREPORTED from a null")
    void theDefaultReportsOnlyWhatItKnows() {
        LegacyLoadAdapterDouble legacy = new LegacyLoadAdapterDouble();

        LoadResult<TreeContext> nothing = legacy.tryLoadSnapshot("anything");
        assertEquals(1, legacy.loads, "the default must still do the work, through loadSnapshot");
        assertEquals(LoadStatus.UNREPORTED, nothing.status(),
                "the null might be absent, malformed or an I/O error; claiming any of them would be a guess");
        assertFalse(nothing.loaded());
        assertFalse(nothing.absent(), "UNREPORTED is not 'there is no snapshot' — that is the whole point");
        assertFalse(nothing.failed());
        assertNull(nothing.cause());
        assertSame(nothing, nothing.orThrow(), "an unknown outcome must not be escalated as a failure");

        // A non-null return, by contrast, IS knowledge — and that is where this default is
        // deliberately unlike trySaveSnapshot's, which can never know anything from a void.
        legacy.next = context(5);
        LoadResult<TreeContext> got = legacy.tryLoadSnapshot("anything");
        assertTrue(got.loaded(), "a load that handed back a context has demonstrably loaded one");
        assertSame(legacy.next, got.value());

        assertEquals(LoadStatus.UNREPORTED, legacy.tryListSnapshots().status(),
                "an empty list might be an unreadable directory");
        legacy.names = List.of("a", "b");
        LoadResult<List<String>> listed = legacy.tryListSnapshots();
        assertTrue(listed.loaded(), "a non-empty list was certainly read");
        assertEquals(List.of("a", "b"), listed.value());
    }

    @Test
    @DisplayName("LoadResult's states are exclusive: LOADED carries a value, FAILED carries a cause")
    void resultStatesAreWellFormed() {
        assertThrows(IllegalArgumentException.class,
                () -> new LoadResult<String>("n", LoadStatus.LOADED, null, "d", null),
                "a LOADED result with nothing in it is not a usable signal");
        assertThrows(IllegalArgumentException.class,
                () -> new LoadResult<String>("n", LoadStatus.ABSENT, "v", "d", null),
                "only LOADED carries a value — otherwise 'absent' could hand back data");
        assertThrows(IllegalArgumentException.class,
                () -> new LoadResult<String>("n", LoadStatus.FAILED, null, "d", null),
                "a FAILED result without a cause is not a usable signal");
        assertThrows(IllegalArgumentException.class,
                () -> new LoadResult<String>("n", LoadStatus.MALFORMED, null, "d", new IOException("x")),
                "MALFORMED means the bytes are wrong, not that something threw");
        assertThrows(NullPointerException.class,
                () -> new LoadResult<String>(null, LoadStatus.ABSENT, null, "d", null));

        assertTrue(LoadResult.loaded("n", "v").loaded());
        assertTrue(LoadResult.absent("n").absent());
        assertTrue(LoadResult.malformed("n", "truncated").malformed());
        assertTrue(LoadResult.malformed("n", "truncated").detail().contains("truncated"));
        assertTrue(LoadResult.failed("n", new IOException("disk gone")).failed());
        assertTrue(LoadResult.failed("n", new IOException("disk gone")).detail().contains("disk gone"),
                "the detail must carry enough to tell a transient blip from a bad configuration");
        assertEquals(LoadStatus.UNREPORTED, LoadResult.unreported("n").status());
        assertThrows(NullPointerException.class, () -> LoadResult.loaded("n", null));
        assertThrows(NullPointerException.class, () -> LoadResult.malformed("n", null));
    }
}
