package test.core;

import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleController;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import org.junit.jupiter.api.Test;

import java.util.Comparator;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The 2026-07-08 ensemble seams: the sliding window fanned across members
 * ({@link EnsembleOrderedSet#setMaxSize}) and depth-measuring reads
 * ({@link EnsembleOrderedSet#searchDepth}) that leave vote semantics untouched.
 */
class EnsembleWindowDepthTest {

    private static EnsembleOrderedSet<Integer> mirror() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .build();
    }

    @Test
    void windowedMirrorEvictsUniformlyAcrossMembers() {
        try (EnsembleOrderedSet<Integer> ens = mirror()) {
            ens.setMaxSize(10);
            for (int i = 0; i < 100; i++) {
                ens.add(i);
            }
            assertEquals(10, ens.size(), "window bound holds");
            assertEquals(90, ens.minimum(), "oldest-inserted (smallest) keys evicted");
            assertEquals(99, ens.maximum());
            assertEquals(10, ens.getMaxSize());

            // Every member must have evicted the identical keys: mirrors stay exact.
            List<Integer> expected = ens.members().get(0).set().inOrder();
            for (EnsembleMember<Integer> m : ens.members()) {
                assertEquals(expected, m.set().inOrder(),
                        "member " + m.strategyName() + " diverged under the window");
                assertEquals(10, m.set().size());
            }
        }
    }

    @Test
    void windowRefusesEngineTierMembers() {
        try (EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .persistentMember()
                .build()) {
            assertFalse(ens.supportsWindow(), "an engine member has no window");
            assertThrows(IllegalStateException.class, () -> ens.setMaxSize(5),
                    "a half-windowed ensemble would silently diverge; must refuse");
        }
    }

    @Test
    void searchDepthMeasuresInMirrorMode() {
        try (EnsembleOrderedSet<Integer> ens = mirror()) {
            for (int i = 0; i < 128; i++) {
                ens.add(i);
            }
            int present = ens.searchDepth(64);
            assertTrue(present >= 1, "present key: measured depth, was " + present);
            int absent = ens.searchDepth(10_000);
            assertTrue(absent < 0, "absent key: complement-encoded, was " + absent);
            assertTrue(~absent >= 1, "absent walk on a non-empty primary still touches nodes");
            assertTrue(ens.contains(64));
            assertFalse(ens.contains(10_000));
        }
    }

    @Test
    void verifiedSearchDepthVotesContainmentAndReportsUnmeasured() {
        try (EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .mode(EnsembleMode.VERIFIED)
                .build()) {
            for (int i = 0; i < 32; i++) {
                ens.add(i);
            }
            // verifyEvery defaults to 1: every read votes, so depth is honestly unmeasured —
            // members with different shapes must never vote on depths.
            assertEquals(0, ens.searchDepth(5), "voted read, present: unmeasured encoding");
            assertEquals(~0, ens.searchDepth(999), "voted read, absent: unmeasured encoding");
            assertTrue(ens.contains(5));
            assertFalse(ens.contains(999));
        }
    }

    @Test
    void controllerRecordsRealDepthsInMirrorMode() {
        try (EnsembleOrderedSet<Integer> ens = mirror()) {
            RollingWorkloadMonitor monitor = new RollingWorkloadMonitor();
            EnsembleController<Integer> c = new EnsembleController<>(ens, monitor);
            for (int i = 0; i < 128; i++) {
                c.add(i);
            }
            for (int i = 0; i < 64; i++) {
                assertTrue(c.contains(i));
            }
            assertFalse(c.contains(10_000));
            assertTrue(monitor.snapshot().meanSearchDepth() > 0.0,
                    "the scorer's shape signal must carry realized depths; was "
                            + monitor.snapshot());
        }
    }
}
