package test.core;

import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-003 E6 — ensemble persistence. Saving an ensemble snapshots its <em>primary</em> (the
 * logical set; storing K mirrors would store the same keys K times), and loading replays the keys
 * through the facade into a caller-built ensemble, so every member is rebuilt by the normal write
 * path: exact copies in MIRROR, the sampled stride in SAMPLED_SHADOW. Member strategies, mode, and
 * comparator are runtime configuration, deliberately not serialized — the same snapshot can wake
 * up under a different member line-up.
 *
 * <p>Each test writes to the shared {@code snapshots/} directory under uniquely-prefixed names
 * and deletes them in {@link #cleanup()}.</p>
 */
@DisplayName("EnsembleOrderedSet snapshot persistence (ADR-003 E6)")
public class EnsemblePersistenceTest {

    private final FilePersistenceAdapter adapter = new FilePersistenceAdapter();
    private final List<String> created = new ArrayList<>();

    /** Register a uniquely-named snapshot for cleanup and return the name. */
    private String snap(String base) {
        String name = "test-ens-" + base + "-" + System.nanoTime();
        created.add(name);
        return name;
    }

    @AfterEach
    void cleanup() {
        for (String name : created) adapter.deleteSnapshot(name);
    }

    private static EnsembleOrderedSet<Integer> mirror() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .build();
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String name) {
        for (EnsembleMember<Integer> m : ens.members()) if (m.strategyName().equals(name)) return m;
        throw new AssertionError("no member " + name);
    }

    @Test
    @DisplayName("a MIRROR ensemble round-trips: the primary is snapshotted, every member is rebuilt")
    void mirrorRoundTrip() {
        EnsembleOrderedSet<Integer> ens = mirror();
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rng = new Random(99);
        for (int i = 0; i < 1500; i++) {
            int v = rng.nextInt(800);
            if (rng.nextBoolean()) { ens.add(v); oracle.add(v); }
            else                   { ens.remove(v); oracle.remove(v); }
        }
        // Promote a non-initial member first, proving it is the *primary* that gets snapshotted.
        ens.promote(memberNamed(ens, "AVLStrategy"));

        String name = snap("mirror");
        adapter.saveSnapshot(name, ens, KeySerializer.INTEGER);

        EnsembleOrderedSet<Integer> restored = mirror();
        assertTrue(adapter.loadEnsemble(name, KeySerializer.INTEGER, restored), "snapshot found and replayed");

        List<Integer> expected = new ArrayList<>(oracle);
        assertEquals(expected, restored.inOrder(), "logical set round-trips");
        assertEquals(oracle.size(), restored.size(), "size round-trips");
        for (EnsembleMember<Integer> m : restored.members()) {
            assertEquals(expected, m.set().inOrder(), m.strategyName() + " rebuilt as an exact mirror");
            assertTrue(m.isExact(), m.strategyName() + " is exact after a MIRROR replay");
        }
    }

    @Test
    @DisplayName("the same snapshot wakes up under SAMPLED_SHADOW: primary full, shadows their stride")
    void reloadIntoShadowMode() {
        EnsembleOrderedSet<Integer> ens = mirror();
        for (int i = 0; i < 1000; i++) ens.add(i);
        String name = snap("shadow");
        adapter.saveSnapshot(name, ens, KeySerializer.INTEGER);

        EnsembleOrderedSet<Integer> restored = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.1)
                .build();
        assertTrue(adapter.loadEnsemble(name, KeySerializer.INTEGER, restored), "replayed into shadow mode");

        assertEquals(1000, restored.size(), "primary holds the full logical set");
        for (EnsembleMember<Integer> m : restored.members()) {
            if (m == restored.primary()) continue;
            assertEquals(100, m.set().size(), m.strategyName() + " sampled its stride during the replay");
            assertFalse(m.isExact(), m.strategyName() + " is a shadow, exactly as if the keys arrived live");
        }
    }

    @Test
    @DisplayName("a saved SAMPLED_SHADOW ensemble persists the full set — the primary is the exact copy")
    void shadowEnsembleSavesFullSet() {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .mode(EnsembleMode.SAMPLED_SHADOW)
                .shadowSampleRate(0.1)
                .build();
        for (int i = 0; i < 500; i++) ens.add(i);
        String name = snap("from-shadow");
        adapter.saveSnapshot(name, ens, KeySerializer.INTEGER);

        EnsembleOrderedSet<Integer> restored = mirror();
        assertTrue(adapter.loadEnsemble(name, KeySerializer.INTEGER, restored));
        assertEquals(500, restored.size(), "the sketches never leak into the snapshot");
        assertEquals(ens.inOrder(), restored.inOrder(), "full logical set restored");
    }

    @Test
    @DisplayName("a missing snapshot reports false and leaves the target untouched")
    void missingSnapshotLeavesTargetUntouched() {
        EnsembleOrderedSet<Integer> target = mirror();
        target.add(7);
        target.add(3);

        assertFalse(adapter.loadEnsemble("test-ens-no-such-snapshot", KeySerializer.INTEGER, target),
                "missing snapshot -> false");
        assertEquals(List.of(3, 7), target.inOrder(), "target untouched on a failed load");
    }
}
