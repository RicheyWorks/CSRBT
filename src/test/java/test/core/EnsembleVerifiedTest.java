package test.core;

import core.MutableTree;
import core.TreeNode1;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleMode;
import core.ensemble.EnsembleOrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.TreeStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * EnsembleOrderedSet VERIFIED mode (ADR-003, step E4): N-version read voting. Every read fans out
 * to a quorum of members, the strict-majority answer is served, and a dissenting member is
 * quarantined -- with failover first if the dissenter is the serving primary. The fault is a
 * {@link BuggyContainsStrategy}: it builds a correct tree (writes delegate to Red-Black) but its
 * {@code search} always reports "not found", so {@code contains} lies while the structure stays
 * internally self-consistent -- exactly the bug the E3 per-member health check cannot catch.
 */
@DisplayName("EnsembleOrderedSet -- VERIFIED quorum voting (E4)")
public class EnsembleVerifiedTest {

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String simpleName) {
        for (EnsembleMember<Integer> m : ens.members()) {
            if (m.strategyName().equals(simpleName)) return m;
        }
        throw new AssertionError("no member backed by " + simpleName);
    }

    @Test
    @DisplayName("a buggy member is outvoted and quarantined; results stay correct")
    void buggyMemberOutvotedAndQuarantined() {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())        // primary, good
                .member(() -> new AVLStrategy<Integer>())             // good
                .member(() -> new BuggyContainsStrategy<Integer>())   // lies on contains
                .mode(EnsembleMode.VERIFIED)
                .build();
        for (int i = 0; i < 50; i++) ens.add(i);

        EnsembleMember<Integer> buggy = memberNamed(ens, "BuggyContainsStrategy");
        assertSame(EnsembleMember.State.ACTIVE, buggy.state(), "buggy member starts ACTIVE");

        // Two good members say contains(7)=true, the buggy one says false -> majority wins.
        assertTrue(ens.contains(7), "the majority serves the correct answer");
        assertSame(EnsembleMember.State.QUARANTINED, buggy.state(), "the outvoted member is quarantined");

        // Reads stay correct, now from the two healthy members.
        assertTrue(ens.contains(7));
        assertFalse(ens.contains(999));
    }

    @Test
    @DisplayName("a buggy primary is outvoted, fails over, and serves correct reads")
    void buggyPrimaryFailsOverUnderVote() {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new BuggyContainsStrategy<Integer>())   // primary, buggy
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .mode(EnsembleMode.VERIFIED)
                .build();
        for (int i = 0; i < 50; i++) ens.add(i);

        EnsembleMember<Integer> buggyPrimary = ens.primary();
        assertEquals("BuggyContainsStrategy", buggyPrimary.strategyName(), "the buggy member is the primary");

        // The vote serves the majority, not the wrong primary -- the case E3's self-check can't catch.
        assertTrue(ens.contains(7), "the majority answer is served, not the buggy primary's");
        assertNotSame(buggyPrimary, ens.primary(), "failed over off the buggy primary");
        assertSame(EnsembleMember.State.QUARANTINED, buggyPrimary.state(), "the deposed primary is quarantined");
        assertTrue(ens.contains(7), "reads stay correct from the new primary");
    }

    @Test
    @DisplayName("MIRROR mode serves from the primary and never votes or quarantines")
    void mirrorModeDoesNotVote() {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())        // good primary
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new BuggyContainsStrategy<Integer>())
                .build();                                             // MIRROR (default)
        for (int i = 0; i < 50; i++) ens.add(i);

        assertTrue(ens.contains(7), "served by the good primary");
        assertSame(EnsembleMember.State.ACTIVE, memberNamed(ens, "BuggyContainsStrategy").state(),
                "MIRROR never consults or quarantines a non-primary member");
    }

    @Test
    @DisplayName("VERIFIED mode requires at least three members to adjudicate")
    void verifiedNeedsThreeMembers() {
        assertThrows(IllegalArgumentException.class, () ->
                EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(() -> new RedBlackStrategy<Integer>())
                        .member(() -> new AVLStrategy<Integer>())
                        .mode(EnsembleMode.VERIFIED)
                        .build());
    }

    /**
     * A strategy that builds a correct tree -- inserts/deletes delegate to a real Red-Black strategy --
     * but whose {@code search} always returns the NIL sentinel, so {@code contains} reports every key
     * as absent while {@code inOrder}/{@code size} stay correct. A latent, self-consistent read bug.
     */
    static final class BuggyContainsStrategy<K> implements TreeStrategy<K> {
        private final RedBlackStrategy<K> real = new RedBlackStrategy<>();
        @Override public void insert(MutableTree<K> t, TreeNode1<K> n)    { real.insert(t, n); }
        @Override public void fixInsert(MutableTree<K> t, TreeNode1<K> n) { real.fixInsert(t, n); }
        @Override public void delete(MutableTree<K> t, TreeNode1<K> n)    { real.delete(t, n); }
        @Override public TreeNode1<K> search(MutableTree<K> t, K value)   { return t.getNIL(); }  // BUG
    }
}
