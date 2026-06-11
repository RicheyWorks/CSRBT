package test.core;

import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.control.StrategyId;
import io.github.richeyworks.csrbt.ensemble.EnsembleController;
import io.github.richeyworks.csrbt.ensemble.EnsembleController.HealthReport;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * EnsembleController health / quarantine / heal + failover (ADR-003, step E3): the cadence health
 * check validates each member, quarantines and heals a member that drifts or breaks its invariant,
 * and -- when the serving primary itself is corrupt -- promotes a healthy member instantly (the E2
 * O(1) swap) before the bad primary can serve a read. Faults are injected by reaching past the
 * ensemble fan-out into a single member's backing tree.
 */
@DisplayName("EnsembleController -- health / quarantine / heal + failover (E3)")
public class EnsembleHealthTest {

    private static EnsembleOrderedSet<Integer> rbAvlSplay() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())   // initial primary
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .build();
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String simpleName) {
        for (EnsembleMember<Integer> m : ens.members()) {
            if (m.strategyName().equals(simpleName)) return m;
        }
        throw new AssertionError("no member backed by " + simpleName);
    }

    private static EnsembleController<Integer> seededController(EnsembleOrderedSet<Integer> ens,
                                                                TreeSet<Integer> oracle, int n) {
        EnsembleController<Integer> ctl = new EnsembleController<>(ens, new RollingWorkloadMonitor(512));
        for (int i = 0; i < n; i++) { ens.add(i); oracle.add(i); }
        return ctl;
    }

    @Test
    @DisplayName("a corrupt non-primary member is quarantined and healed; queries are uninterrupted")
    void corruptNonPrimaryIsQuarantinedAndHealed() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        TreeSet<Integer> oracle = new TreeSet<>();
        EnsembleController<Integer> ctl = seededController(ens, oracle, 120);

        EnsembleMember<Integer> rb  = ens.primary();                 // RB serves reads
        EnsembleMember<Integer> avl = memberNamed(ens, "AVLStrategy");

        // Corrupt the AVL member by dropping a key straight from its tree, behind the fan-out.
        assertTrue(avl.set().remove(57), "precondition: the key to drop is present");
        assertNotEquals(rb.set().inOrder(), avl.set().inOrder(), "the member has drifted out of sync");

        HealthReport r = ctl.checkHealth();

        // Queries uninterrupted: the primary never changed and still answers correctly.
        assertSame(rb, ens.primary(), "a non-primary fault must not disturb the serving primary");
        assertEquals(new ArrayList<>(oracle), ens.inOrder(), "reads stay correct throughout");

        // The faulty member was quarantined, then healed back to an exact mirror.
        assertEquals(1, r.quarantined(), "the drifted member is quarantined");
        assertEquals(1, r.healed(), "and healed from the primary");
        assertFalse(r.failedOver(), "no failover for a non-primary fault");
        assertSame(EnsembleMember.State.ACTIVE, avl.state(), "healed member is ACTIVE again");
        assertEquals(rb.set().inOrder(), avl.set().inOrder(), "AVL re-mirrors the primary after heal");
    }

    @Test
    @DisplayName("a structurally corrupt primary fails over instantly to a healthy member")
    void corruptPrimaryFailsOver() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        TreeSet<Integer> oracle = new TreeSet<>();
        EnsembleController<Integer> ctl = seededController(ens, oracle, 120);

        EnsembleMember<Integer> rb = ens.primary();
        assertEquals("RedBlackStrategy", rb.strategyName(), "RB is the initial primary");

        // Corrupt the primary's structure: paint the root red (a red-black tree's root must be black).
        TreeNode1<Integer> root = rb.orderedSet().getEngine().getRoot();
        root.setColor(TreeNode1.Color.RED);

        HealthReport r = ctl.checkHealth();

        // Instant failover: a healthy member now serves, and reads are correct from it.
        assertTrue(r.failedOver(), "a structurally bad primary must fail over");
        assertNotSame(rb, ens.primary(), "a different, healthy member now serves reads");
        assertEquals(StrategyId.RED_BLACK, r.from(), "failed over from Red-Black");
        assertEquals(StrategyId.AVL, r.to(), "to the first healthy member (AVL)");
        assertEquals(new ArrayList<>(oracle), ens.inOrder(), "reads are correct after failover");

        // The deposed primary was quarantined and then healed from the new primary.
        assertEquals(1, r.healed(), "the deposed primary is healed");
        assertSame(EnsembleMember.State.ACTIVE, rb.state(), "and returns to ACTIVE as a standby mirror");
        assertEquals(ens.primary().set().inOrder(), rb.set().inOrder(), "deposed primary re-mirrors the new one");
    }

    @Test
    @DisplayName("a healthy ensemble reports no repair")
    void healthyEnsembleIsACleanBill() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        TreeSet<Integer> oracle = new TreeSet<>();
        EnsembleController<Integer> ctl = seededController(ens, oracle, 60);

        EnsembleMember<Integer> rb = ens.primary();
        HealthReport r = ctl.checkHealth();

        assertFalse(r.changed(), "nothing to repair");
        assertEquals(0, r.quarantined());
        assertEquals(0, r.healed());
        assertSame(rb, ens.primary(), "primary unchanged");
        for (EnsembleMember<Integer> m : ens.members()) {
            assertSame(EnsembleMember.State.ACTIVE, m.state(), m.strategyName() + " stays ACTIVE");
        }
    }
}
