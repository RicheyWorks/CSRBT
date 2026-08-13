package test.core;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleController;
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

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probes (bug audit 2026-08-12, ensemble sweep): the fault-tolerance machinery failing
 * at its own job — each shown failing against the unfixed code.
 *
 * <p>E-A: a VERIFIED vote let a divergent member's exception (rank/successor/select on
 * a key it silently lost) propagate to the caller instead of outvoting and quarantining
 * the dissenter — the vote only worked for non-throwing queries. E-B: the cadence
 * health check validated the primary only against its own inOrder, so a content-
 * divergent primary was "healthy" and every honest member was quarantined and healed
 * FROM it — permanent silent data loss. E-C: the health check skipped QUARANTINED
 * members entirely, so quarantine was permanent and VERIFIED silently degraded below
 * quorum. E-D: the "write did not commit" total-failure path threw before the
 * quarantine loop, leaving half-applied members ACTIVE and divergent. E-E: toString()
 * ran a vote (side-effecting diagnostic). E-F: double-quarantine returned true and
 * re-emitted the event.</p>
 */
@DisplayName("Ensemble resilience probes — votes, health checks, write failure")
class EnsembleResilienceProbeTest {

    private static EnsembleOrderedSet<Integer> verified3() {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(
                        Comparator.<Integer>naturalOrder())
                .member(RedBlackStrategy::new)
                .member(AVLStrategy::new)
                .member(SplayStrategy::new)
                .mode(EnsembleMode.VERIFIED)
                .build();
        for (int k = 1; k <= 100; k++) ens.add(k);
        return ens;
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens,
                                                       String simpleName) {
        for (EnsembleMember<Integer> m : ens.members()) {
            if (m.strategyName().equals(simpleName)) return m;
        }
        throw new AssertionError("no member backed by " + simpleName);
    }

    @Test
    @DisplayName("E-A: a member whose divergence makes a query THROW is outvoted, not propagated")
    void throwingDissenterIsOutvoted() {
        EnsembleOrderedSet<Integer> ens = verified3();
        // Content divergence: the AVL member silently loses key 57 (the ADR-006 fault class).
        memberNamed(ens, "AVLStrategy").orderedSet().remove(57);

        // rank(57) throws NoSuchElementException ON THE DIVERGENT MEMBER ONLY; the
        // 2/3 majority answer must be served and the dissenter quarantined.
        assertEquals(57, ens.rank(57),
                "the majority's rank must be served — a lone thrower must be outvoted");
        assertEquals(EnsembleMember.State.QUARANTINED,
                memberNamed(ens, "AVLStrategy").state(),
                "the throwing dissenter must be quarantined like any other dissenter");

        // And order statistics keep working afterwards.
        assertEquals(Integer.valueOf(58), ens.successor(57));
        assertEquals(Integer.valueOf(100), ens.select(100));
    }

    @Test
    @DisplayName("E-B: checkHealth must not heal the majority FROM a content-divergent primary")
    void divergentPrimaryDoesNotEraseTheMajority() {
        EnsembleOrderedSet<Integer> ens = verified3();
        EnsembleController<Integer> ctl =
                new EnsembleController<>(ens, new RollingWorkloadMonitor(512));

        // The PRIMARY silently loses key 42 — structurally valid, content-divergent.
        // Two of three members still hold 42: the majority evidence is intact.
        ens.primary().orderedSet().remove(42);

        ctl.checkHealth();

        assertTrue(ens.contains(42),
                "2 of 3 members held 42 — the health check must depose the divergent "
                + "primary (or leave the majority alone), never quarantine-and-heal the "
                + "honest members from it");
    }

    @Test
    @DisplayName("E-C: checkHealth heals quarantined members back to ACTIVE (E3's recover step)")
    void quarantinedMembersAreHealedByTheCadenceCheck() {
        EnsembleOrderedSet<Integer> ens = verified3();
        EnsembleController<Integer> ctl =
                new EnsembleController<>(ens, new RollingWorkloadMonitor(512));
        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");
        ens.quarantine(avl);
        assertEquals(EnsembleMember.State.QUARANTINED, avl.state());

        ctl.checkHealth();

        assertTrue(avl.isActive(),
                "E3 documents quarantine → heal → reactivate; the cadence check must "
                + "heal a quarantined member, not skip it forever");
        assertEquals(ens.primary().set().inOrder(), avl.set().inOrder(),
                "the healed member must be an exact mirror again");
    }

    /** Delegates to Red-Black but throws AFTER linking the poison key — half-applied. */
    private static final class HalfApplyStrategy implements TreeStrategy<Integer> {
        private final RedBlackStrategy<Integer> inner = new RedBlackStrategy<>();
        @Override public void insert(MutableTree<Integer> tree, TreeNode1<Integer> node) {
            inner.insert(tree, node);
            if (node.getData() == 400) throw new IllegalStateException("disk full (after link)");
        }
        @Override public void fixInsert(MutableTree<Integer> tree, TreeNode1<Integer> node) {
            inner.fixInsert(tree, node);
        }
        @Override public void delete(MutableTree<Integer> tree, TreeNode1<Integer> node) {
            inner.delete(tree, node);
        }
        @Override public TreeNode1<Integer> search(MutableTree<Integer> tree, Integer value) {
            return inner.search(tree, value);
        }
    }

    /** Throws BEFORE applying the poison key — nothing linked. */
    private static final class ThrowFirstStrategy implements TreeStrategy<Integer> {
        private final RedBlackStrategy<Integer> inner = new RedBlackStrategy<>();
        @Override public void insert(MutableTree<Integer> tree, TreeNode1<Integer> node) {
            if (node.getData() == 400) throw new IllegalStateException("disk full (before link)");
            inner.insert(tree, node);
        }
        @Override public void fixInsert(MutableTree<Integer> tree, TreeNode1<Integer> node) {
            inner.fixInsert(tree, node);
        }
        @Override public void delete(MutableTree<Integer> tree, TreeNode1<Integer> node) {
            inner.delete(tree, node);
        }
        @Override public TreeNode1<Integer> search(MutableTree<Integer> tree, Integer value) {
            return inner.search(tree, value);
        }
    }

    @Test
    @DisplayName("E-D: a write that fails on every member quarantines the failed non-primaries")
    void totalWriteFailureQuarantinesRecipients() {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(
                        Comparator.<Integer>naturalOrder())
                .member(HalfApplyStrategy::new)     // primary: links 400, then throws
                .member(ThrowFirstStrategy::new)    // throws before linking
                .build();
        for (int k = 1; k <= 10; k++) ens.add(k);

        assertThrows(IllegalStateException.class, () -> ens.add(400),
                "a write failing everywhere must not commit");

        EnsembleMember<Integer> second = ens.members().get(1);
        assertEquals(EnsembleMember.State.QUARANTINED, second.state(),
                "a member that failed the write must be quarantined (half-applied state "
                + "must not stay silently ACTIVE and divergent)");
    }

    @Test
    @DisplayName("E-E: toString() is side-effect free — it must not vote or quarantine")
    void toStringDoesNotVote() {
        EnsembleOrderedSet<Integer> ens = verified3();
        memberNamed(ens, "AVLStrategy").orderedSet().remove(57);

        ens.toString();   // a log line or debugger render

        assertTrue(memberNamed(ens, "AVLStrategy").isActive(),
                "rendering a diagnostic string must not run a vote and quarantine members");
    }

    @Test
    @DisplayName("E-F: quarantine is idempotent — a second call reports no transition")
    void quarantineIsIdempotent() {
        EnsembleOrderedSet<Integer> ens = verified3();
        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");
        assertTrue(ens.quarantine(avl), "first quarantine transitions");
        assertFalse(ens.quarantine(avl),
                "second quarantine must report no transition (and emit no duplicate event)");
    }
}
