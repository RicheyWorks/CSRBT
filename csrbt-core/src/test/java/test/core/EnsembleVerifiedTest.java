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
 * {@link SilentDropStrategy}: writes delegate to a real Red-Black strategy, except that one poison
 * key is silently never inserted, so the member holds a self-consistent tree whose <em>content</em>
 * diverges -- exactly the bug the E3 per-member health check cannot catch.
 *
 * <p>History: this fault was originally a strategy whose {@code search} lied ("not found" for every
 * key). ADR-004 R1 made that fault class structurally impossible -- public reads never consult the
 * strategy any more (they descend the tree directly), so a read-path lie is unobservable by
 * construction. Post-R1, the divergence VERIFIED voting exists to catch is divergent tree content,
 * which is what this strategy injects.</p>
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
                .member(() -> new SilentDropStrategy<Integer>())      // silently drops key 7
                .mode(EnsembleMode.VERIFIED)
                .build();
        for (int i = 0; i < 50; i++) ens.add(i);

        EnsembleMember<Integer> buggy = memberNamed(ens, "SilentDropStrategy");
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
                .member(() -> new SilentDropStrategy<Integer>())      // primary, buggy
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .mode(EnsembleMode.VERIFIED)
                .build();
        for (int i = 0; i < 50; i++) ens.add(i);

        EnsembleMember<Integer> buggyPrimary = ens.primary();
        assertEquals("SilentDropStrategy", buggyPrimary.strategyName(), "the buggy member is the primary");

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
                .member(() -> new SilentDropStrategy<Integer>())
                .build();                                             // MIRROR (default)
        for (int i = 0; i < 50; i++) ens.add(i);

        assertTrue(ens.contains(7), "served by the good primary");
        assertSame(EnsembleMember.State.ACTIVE, memberNamed(ens, "SilentDropStrategy").state(),
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
     * A strategy that silently drops one poisoned key on insert -- every other write delegates to a
     * real Red-Black strategy. The result is a perfectly valid, self-consistent tree that simply
     * lacks one key its siblings hold: invisible to E3's structural health check, caught only by
     * comparing answers across members (E4 voting).
     */
    static final class SilentDropStrategy<K> implements TreeStrategy<K> {
        static final Integer POISON = 7;
        private final RedBlackStrategy<K> real = new RedBlackStrategy<>();
        private boolean poisoned(TreeNode1<K> n) { return POISON.equals(n.getData()); }
        @Override public void insert(MutableTree<K> t, TreeNode1<K> n)    { if (!poisoned(n)) real.insert(t, n); }     // BUG: drops 7
        @Override public void fixInsert(MutableTree<K> t, TreeNode1<K> n) { if (!poisoned(n)) real.fixInsert(t, n); }
        @Override public void delete(MutableTree<K> t, TreeNode1<K> n)    { real.delete(t, n); }
        @Override public TreeNode1<K> search(MutableTree<K> t, K value)   { return real.search(t, value); }
    }
}
