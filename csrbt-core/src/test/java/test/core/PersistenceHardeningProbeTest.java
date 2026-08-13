package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probes (bug audit 2026-08-12, deep sweep): three persistence defects, each shown
 * failing against the unfixed code.
 *
 * <p>P-1: the string serializer escaped inline delimiters but not line terminators,
 * so a key containing {@code \n}/{@code \r} split the line-based format and the set
 * silently loaded wrong (or empty). P-2: the header SIZE was advisory — a truncated
 * pre-order prefix parses cleanly (token exhaustion reads as NIL), so a partially
 * written file loaded as a smaller, wrong tree instead of being refused. P-3:
 * {@code resolveStrategy} fell back to Red-Black for unknown names, so every
 * WeightBalanced snapshot failed the RB structural gate on load and round-trips
 * always returned null.</p>
 */
@DisplayName("Persistence hardening probes — newline keys, truncation, WB round-trip")
class PersistenceHardeningProbeTest {

    private static String snap(String base) {
        return base + "-" + System.nanoTime();   // unique per run; snapshots/ is scratch
    }

    @Test
    @DisplayName("P-1: a key containing a newline round-trips (or the save must fail loudly)")
    void newlineKeyRoundTrips() {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        OrderedSet<String> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
        set.add("apple");
        set.add("line1\nline2");
        set.add("mango");
        set.add("carriage\rreturn");
        String name = snap("probe-newline");
        adapter.saveSnapshot(name, set, KeySerializer.string());
        OrderedSet<String> loaded = adapter.loadOrderedSet(name, KeySerializer.string());
        assertNotNull(loaded, "a set with newline keys must load back (not silently fail)");
        assertEquals(set.inOrder(), loaded.inOrder(),
                "newline/CR keys must round-trip intact — the serializer promises "
                + "any non-empty string round-trips");
        adapter.deleteSnapshot(name);
    }

    @Test
    @DisplayName("P-2: a truncated snapshot file is refused, never loaded as a smaller wrong tree")
    void truncatedSnapshotRefused() throws IOException {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int k = 1; k <= 7; k++) set.add(k);
        String name = snap("probe-trunc");
        adapter.saveSnapshot(name, set, KeySerializer.INTEGER);
        Path file = Path.of("snapshots", name + ".rbt");
        byte[] full = Files.readAllBytes(file);
        List<Integer> original = set.inOrder();

        try {
            // Every possible truncation: the load must either refuse (null) or produce
            // the original contents — never a smaller tree that "passes".
            for (int cut = full.length - 1; cut > 0; cut--) {
                byte[] truncated = new byte[cut];
                System.arraycopy(full, 0, truncated, 0, cut);
                Files.write(file, truncated);
                OrderedSet<Integer> loaded =
                        adapter.loadOrderedSet(name, KeySerializer.INTEGER);
                if (loaded != null) {
                    assertEquals(original, loaded.inOrder(),
                            "truncation at byte " + cut + " loaded a WRONG tree "
                            + loaded.inOrder() + " instead of being refused");
                }
            }
        } finally {
            Files.write(file, full);
            adapter.deleteSnapshot(name);
        }
    }

    @Test
    @DisplayName("P-3: a WeightBalancedStrategy snapshot round-trips")
    void weightBalancedRoundTrips() {
        FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new WeightBalancedStrategy<Integer>());
        for (int k = 1; k <= 20; k++) set.add(k * 7 % 31);
        String name = snap("probe-wb");
        adapter.saveSnapshot(name, set, KeySerializer.INTEGER);
        OrderedSet<Integer> loaded = adapter.loadOrderedSet(name, KeySerializer.INTEGER);
        assertNotNull(loaded, "a WB snapshot must load (resolveStrategy must not fall back "
                + "to Red-Black and fail the structural gate)");
        assertEquals(set.inOrder(), loaded.inOrder());
        assertTrue(loaded.getStrategy() instanceof WeightBalancedStrategy,
                "the loaded set must carry the strategy the file recorded");
        adapter.deleteSnapshot(name);
    }
}
