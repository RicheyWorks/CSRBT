package test.core;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The per-instance {@code Builder.optimisticVotes(boolean)} pin (hardening L-1) — the one ADR-007
 * surface with no direct coverage until now. The process-global {@link EnsembleOrderedSet#OPTIMISTIC_VOTES}
 * kill switch is exercised by {@code EnsembleVerifiedConcurrencyTest}; this test covers the pin:
 * a builder-set value must route THIS ensemble's VERIFIED votes down the pinned path regardless of
 * what any other code does to the static.
 *
 * <p>The two paths ({@code vote}'s lock-free unanimity pass vs {@code voteLocked}) are contractually
 * answer-identical, so the assertions are (a) oracle parity of every read under each pin, and
 * (b) the E4 quarantine machinery still fires through whichever path the pin selects — pinned-false
 * forces every vote through {@code voteLocked}; pinned-true forces the optimistic first pass even
 * with the global switch off. Deterministic, single-threaded, seeded.
 */
@DisplayName("EnsembleOrderedSet -- per-instance optimisticVotes pin (ADR-007, hardening L-1)")
class EnsembleOptimisticVotesKnobTest {

    private static final long SEED = 20_260_713L;

    private static EnsembleOrderedSet<Integer> verifiedEnsemble(Boolean pin, boolean withBuggyMember) {
        EnsembleOrderedSet.Builder<Integer> b = EnsembleOrderedSet.builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(withBuggyMember
                        ? () -> new SilentDropStrategy<Integer>()
                        : () -> new SplayStrategy<Integer>())
                .mode(EnsembleMode.VERIFIED);
        if (pin != null) {
            b.optimisticVotes(pin);
        }
        return b.build();
    }

    /** Seeded add/remove/contains churn; every answer checked against a TreeSet oracle. */
    private static void oracleChurn(EnsembleOrderedSet<Integer> ens) {
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rnd = new Random(SEED);
        for (int i = 0; i < 2_000; i++) {
            int k = rnd.nextInt(300);
            switch (rnd.nextInt(3)) {
                case 0 -> assertEquals(oracle.add(k), ens.add(k), "add(" + k + ") @op " + i);
                case 1 -> assertEquals(oracle.remove(k), ens.remove(k), "remove(" + k + ") @op " + i);
                default -> assertEquals(oracle.contains(k), ens.contains(k), "contains(" + k + ") @op " + i);
            }
        }
        assertEquals(oracle.size(), ens.size(), "size after churn");
        assertEquals(oracle.stream().toList(), ens.inOrder(), "inOrder after churn");
    }

    @Test
    @DisplayName("pinned false: every vote runs under the lock; answers stay oracle-correct")
    void pinnedFalseServesCorrectlyThroughTheLockedPath() {
        boolean saved = EnsembleOrderedSet.OPTIMISTIC_VOTES;
        EnsembleOrderedSet.OPTIMISTIC_VOTES = true;               // global says optimistic...
        try {
            oracleChurn(verifiedEnsemble(false, false));          // ...the pin forces voteLocked anyway
        } finally {
            EnsembleOrderedSet.OPTIMISTIC_VOTES = saved;
        }
    }

    @Test
    @DisplayName("pinned true: immune to the global kill switch; answers stay oracle-correct")
    void pinnedTrueIsImmuneToTheGlobalKillSwitch() {
        boolean saved = EnsembleOrderedSet.OPTIMISTIC_VOTES;
        EnsembleOrderedSet.OPTIMISTIC_VOTES = false;              // global says locked...
        try {
            oracleChurn(verifiedEnsemble(true, false));           // ...the pin keeps the optimistic pass
        } finally {
            EnsembleOrderedSet.OPTIMISTIC_VOTES = saved;
        }
    }

    @Test
    @DisplayName("unpinned: the ensemble follows the global switch (both positions, oracle-correct)")
    void unpinnedFollowsTheGlobalSwitch() {
        boolean saved = EnsembleOrderedSet.OPTIMISTIC_VOTES;
        try {
            EnsembleOrderedSet.OPTIMISTIC_VOTES = false;
            oracleChurn(verifiedEnsemble(null, false));
            EnsembleOrderedSet.OPTIMISTIC_VOTES = true;
            oracleChurn(verifiedEnsemble(null, false));
        } finally {
            EnsembleOrderedSet.OPTIMISTIC_VOTES = saved;
        }
    }

    @Test
    @DisplayName("quarantine still fires under both pin positions (divergence escalates either way)")
    void quarantineFiresUnderBothPins() {
        boolean saved = EnsembleOrderedSet.OPTIMISTIC_VOTES;
        try {
            for (boolean pin : new boolean[]{false, true}) {
                // Set the global to the OPPOSITE of the pin, so any quarantine observed below
                // provably rode the pinned path, not the global one.
                EnsembleOrderedSet.OPTIMISTIC_VOTES = !pin;
                EnsembleOrderedSet<Integer> ens = verifiedEnsemble(pin, true);
                for (int i = 0; i < 50; i++) {
                    ens.add(i);
                }
                EnsembleMember<Integer> buggy = null;
                for (EnsembleMember<Integer> m : ens.members()) {
                    if (m.strategyName().equals("SilentDropStrategy")) {
                        buggy = m;
                    }
                }
                assertSame(EnsembleMember.State.ACTIVE, buggy.state(), "buggy member starts ACTIVE (pin=" + pin + ")");
                assertTrue(ens.contains(7), "majority answer served (pin=" + pin + ")");
                assertSame(EnsembleMember.State.QUARANTINED, buggy.state(),
                        "divergence escalates and quarantines through the pinned path (pin=" + pin + ")");
                assertTrue(ens.contains(7), "reads stay correct post-quarantine (pin=" + pin + ")");
                assertFalse(ens.contains(999), "absent key stays absent (pin=" + pin + ")");
            }
        } finally {
            EnsembleOrderedSet.OPTIMISTIC_VOTES = saved;
        }
    }

    /**
     * Same fault as {@code EnsembleVerifiedTest}'s: a self-consistent tree that silently drops one
     * key on insert — invisible to the structural health check, caught only by E4 answer voting.
     */
    static final class SilentDropStrategy<K> implements TreeStrategy<K> {
        static final Integer POISON = 7;
        private final RedBlackStrategy<K> real = new RedBlackStrategy<>();
        private boolean poisoned(TreeNode1<K> n) { return POISON.equals(n.getData()); }
        @Override public void insert(MutableTree<K> t, TreeNode1<K> n)    { if (!poisoned(n)) real.insert(t, n); }
        @Override public void fixInsert(MutableTree<K> t, TreeNode1<K> n) { if (!poisoned(n)) real.fixInsert(t, n); }
        @Override public void delete(MutableTree<K> t, TreeNode1<K> n)    { real.delete(t, n); }
        @Override public TreeNode1<K> search(MutableTree<K> t, K value)   { return real.search(t, value); }
    }
}
