package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.SaveStatus;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The {@code fsyncOnCommit} option (ADR-026 amendment, 2026-08-18 — ADR-025's held {@code fsync}
 * item).
 *
 * <h2>What this can and cannot prove</h2>
 * <p>It cannot prove durability. Nothing running inside a JVM can observe whether a
 * {@code FileChannel.force} reached the platter, and a test that pulled the power would not be a
 * test. What it pins is everything else, which is what actually breaks: that the option is wired
 * and reachable, that the default is unchanged, that forcing does not alter a single byte of the
 * on-disk format, that a snapshot written with it still loads, and that the ADR-025 failure
 * reporting and the D-3 staging cleanup behave identically in both modes. The durability claim
 * itself lives where it can be argued rather than asserted: in
 * {@code FilePersistenceAdapter(boolean)}'s javadoc, with the measured cost next to it.</p>
 */
@DisplayName("FilePersistenceAdapter — the fsyncOnCommit durability option")
class SnapshotDurabilityOptionTest {

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
        String name = "fsync_" + base + "_" + System.nanoTime();
        litter.add(DIR.resolve(name + ".rbt"));
        return name;
    }

    private static TreeContext ctx(int n) {
        TreeContext c = new TreeContext(new RedBlackStrategy<>());
        for (int i = 1; i <= n; i++) c.add(i * 7 % 1000);
        c.getTree().getRoot().setTag("root-tag");
        return c;
    }

    @Test
    @DisplayName("off by default; on only when asked for")
    void theDefaultIsUnchanged() {
        assertFalse(new FilePersistenceAdapter().isFsyncOnCommit(),
                "every existing caller keeps the free write path");
        assertFalse(new FilePersistenceAdapter(false).isFsyncOnCommit());
        assertTrue(new FilePersistenceAdapter(true).isFsyncOnCommit());
    }

    @Test
    @DisplayName("forcing changes no byte of the file, and the snapshot still loads")
    void theOnDiskFormatIsUntouched() throws IOException {
        TreeContext source = ctx(200);

        String plain = snap("plain");
        String forced = snap("forced");
        new FilePersistenceAdapter(false).saveSnapshot(plain, source);
        new FilePersistenceAdapter(true).saveSnapshot(forced, source);

        byte[] a = Files.readAllBytes(DIR.resolve(plain + ".rbt"));
        byte[] b = Files.readAllBytes(DIR.resolve(forced + ".rbt"));
        // The header carries a timestamp, so compare from the data line onwards plus the header's
        // fixed fields — everything the format actually encodes.
        assertEquals(headerWithoutTimestamp(a), headerWithoutTimestamp(b),
                "a durability option must not change what a snapshot IS");
        assertArrayEquals(dataLine(a), dataLine(b), "…including every node token and tag");

        TreeContext round = new FilePersistenceAdapter(true).loadSnapshot(forced);
        assertNotNull(round, "a forced snapshot is an ordinary snapshot");
        assertEquals(source.inOrder(), round.inOrder());
    }

    private static String headerWithoutTimestamp(byte[] file) {
        String header = new String(file, java.nio.charset.StandardCharsets.UTF_8).split("\n", 2)[0];
        String[] f = header.split("\\|");
        f[1] = "<timestamp>";
        return String.join("|", f);
    }

    private static byte[] dataLine(byte[] file) {
        String s = new String(file, java.nio.charset.StandardCharsets.UTF_8);
        return s.substring(s.indexOf('\n') + 1).getBytes(java.nio.charset.StandardCharsets.UTF_8);
    }

    @Test
    @DisplayName("every save shape works with forcing on")
    void allFourSaveShapesStillCommit() {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter(true);

        String contextName = snap("ctx");
        assertEquals(SaveStatus.SAVED, adapter.trySaveSnapshot(contextName, ctx(50)).status());

        String setName = snap("set");
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < 50; i++) set.add(i);
        assertEquals(SaveStatus.SAVED,
                adapter.trySaveSnapshot(setName, set, KeySerializer.INTEGER).status());

        assertEquals(List.of(0, 1, 2),
                adapter.loadOrderedSet(setName, KeySerializer.INTEGER, Comparator.<Integer>naturalOrder())
                       .inOrder().subList(0, 3));
    }

    @Test
    @DisplayName("a failed save is reported and cleaned up the same way in both modes")
    void theFailurePathIsUnchanged() throws IOException {
        for (boolean fsync : new boolean[]{false, true}) {
            FilePersistenceAdapter adapter = new FilePersistenceAdapter(fsync);
            String name = snap("blocked" + fsync);

            // A non-empty directory at the target path: the commit rename cannot publish over it.
            // uid-independent, so it cannot silently pass as root.
            Path asDir = DIR.resolve(name + ".rbt");
            Files.createDirectories(asDir.resolve("occupied"));

            var outcome = adapter.trySaveSnapshot(name, ctx(20));
            assertEquals(SaveStatus.FAILED, outcome.status(), "fsync=" + fsync);
            assertNotNull(outcome.cause(), "fsync=" + fsync);

            // D-3: no staging file is left behind on the failure path, either.
            try (Stream<Path> leftovers = Files.list(DIR)) {
                assertTrue(leftovers.map(p -> p.getFileName().toString())
                                    .filter(n -> n.startsWith(name) && n.endsWith(".tmp"))
                                    .toList().isEmpty(),
                        "fsync=" + fsync + ": the staging file must be cleaned up");
            }
        }
    }
}
