package test.core;

import io.github.richeyworks.csrbt.PersistentRankedSet;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleController;
import io.github.richeyworks.csrbt.ensemble.EnsembleController.HealthReport;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-005 P3 — ENGINE-tier ensemble membership. The {@code RankedSet} seam lets the
 * weight-balanced persistent engine (via {@link PersistentRankedSet}) join an
 * {@link EnsembleOrderedSet} as a first-class member: it mirrors every write, serves when
 * promoted, votes in VERIFIED, and is healed by the E3 pass through its own structural
 * self-check — all without the ensemble knowing it is not a strategy-driven tree. The one
 * deliberate asymmetry under test: the controller's StrategyId-driven scorer cannot rank an
 * engine member, so it is never promoted <em>automatically</em> — only explicitly or by failover.
 *
 * <p>Also covers the second half of P3: persistent-engine snapshots saved and loaded through
 * {@link FilePersistenceAdapter} via {@link KeySerializer} (flat ascending-key format).</p>
 */
@DisplayName("Ensemble ENGINE-tier member — persistent engine via the RankedSet seam (ADR-005 P3)")
public class EnsembleEngineMemberTest {

    private static final String ENGINE = "PersistentTreeEngine";

    private final FilePersistenceAdapter adapter = new FilePersistenceAdapter();
    private final List<String> created = new ArrayList<>();

    private String snap(String base) {
        String name = "test-p3-" + base + "-" + System.nanoTime();
        created.add(name);
        return name;
    }

    @AfterEach
    void cleanup() {
        for (String name : created) adapter.deleteSnapshot(name);
    }

    private static EnsembleOrderedSet<Integer> withEngineMember(EnsembleMode mode) {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .persistentMember()
                .mode(mode)
                .build();
    }

    private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> ens, String name) {
        for (EnsembleMember<Integer> m : ens.members()) if (m.strategyName().equals(name)) return m;
        throw new AssertionError("no member " + name);
    }

    // ── Membership ───────────────────────────────────────────────────────────────

    @Test
    @DisplayName("an engine member mirrors every write exactly, like any strategy member")
    void engineMemberMirrorsWrites() {
        EnsembleOrderedSet<Integer> ens = withEngineMember(EnsembleMode.MIRROR);
        for (int i = 0; i < 500; i++) assertTrue(ens.add(i));
        for (int i = 0; i < 500; i += 2) assertTrue(ens.remove(i));

        EnsembleMember<Integer> engine = memberNamed(ens, ENGINE);
        assertFalse(engine.isStrategyBacked(), "engine member carries no TreeStrategy");
        assertThrows(IllegalStateException.class, engine::orderedSet,
                "strategy machinery must refuse an engine member loudly");
        assertTrue(engine.isExact(), "a mirror member is exact");
        assertEquals(250, engine.set().size());
        assertEquals(ens.primary().set().inOrder(), engine.set().inOrder(),
                "engine member holds exactly the logical set");
        assertTrue(engine.set().validateStructure().isEmpty(), "weight invariant holds under churn");
    }

    @Test
    @DisplayName("explicit promotion makes the engine member serve — reads and order stats included")
    void explicitPromotionServes() {
        EnsembleOrderedSet<Integer> ens = withEngineMember(EnsembleMode.MIRROR);
        for (int i = 1; i <= 100; i++) ens.add(i);

        EnsembleMember<Integer> engine = memberNamed(ens, ENGINE);
        assertTrue(ens.promote(engine));
        assertSame(engine, ens.primary(), "the engine member is now the serving primary");

        assertTrue(ens.contains(50));
        assertEquals(100, ens.size());
        assertEquals(Integer.valueOf(25), ens.select(25), "order stats served by the engine's counts");
        assertEquals(73, ens.rank(73));
        assertEquals(Integer.valueOf(51), ens.successor(50));
        assertEquals(10, ens.countInRange(11, 20));

        assertTrue(ens.add(101), "writes keep fanning out after the swap");
        assertEquals(101, memberNamed(ens, "RedBlackStrategy").set().size(),
                "deposed members stay exact mirrors");
    }

    @Test
    @DisplayName("VERIFIED quorum reads work with an engine member voting")
    void verifiedVotingIncludesEngineMember() {
        EnsembleOrderedSet<Integer> ens = withEngineMember(EnsembleMode.VERIFIED);
        for (int i = 0; i < 200; i++) ens.add(i);

        assertTrue(ens.contains(123), "all three voters (two strategies + engine) agree");
        assertEquals(200, ens.size());
        assertEquals(Integer.valueOf(99), ens.select(100), "order statistics survive the vote");
        assertEquals(Integer.valueOf(0), ens.minimum());
        for (EnsembleMember<Integer> m : ens.members()) {
            assertTrue(m.isActive(), m.strategyName() + " — agreeing voters are never quarantined");
        }
    }

    // ── Health (E3 pass over a non-strategy member) ──────────────────────────────

    @Test
    @DisplayName("the health pass validates an engine member by self-check + content, and heals divergence")
    void healthPassHealsDivergentEngineMember() {
        EnsembleOrderedSet<Integer> ens = withEngineMember(EnsembleMode.MIRROR);
        EnsembleController<Integer> ctl =
                new EnsembleController<>(ens, new RollingWorkloadMonitor(512));
        for (int i = 0; i < 300; i++) ctl.add(i);

        assertFalse(ctl.checkHealth().changed(), "a healthy ensemble needs no repair");

        // Corrupt the engine member out-of-band: drop a key the logical set still holds.
        // StrategyHealthCheck cannot see this member; the P3 path (validateStructure + content
        // equality against the trusted primary) must catch it.
        EnsembleMember<Integer> engine = memberNamed(ens, ENGINE);
        engine.set().remove(150);
        assertEquals(299, engine.set().size());

        HealthReport report = ctl.checkHealth();
        assertFalse(report.failedOver(), "the primary was never unhealthy");
        assertEquals(1, report.quarantined(), "the divergent engine member is quarantined");
        assertEquals(1, report.healed(), "and rebuilt from the primary");
        assertTrue(engine.isActive());
        assertEquals(300, engine.set().size(), "heal restored the full logical set");
        assertTrue(engine.set().contains(150));
        assertFalse(ctl.checkHealth().changed(), "stable after repair");
    }

    @Test
    @DisplayName("the controller never auto-promotes an engine member — the scorer cannot rank it")
    void controllerNeverAutoPromotesEngineMember() {
        EnsembleOrderedSet<Integer> ens = withEngineMember(EnsembleMode.MIRROR);
        EnsembleController<Integer> ctl =
                new EnsembleController<>(ens, new RollingWorkloadMonitor(512));

        // Drive enough mixed work for several evaluation windows.
        for (int round = 0; round < 6; round++) {
            for (int i = 0; i < 200; i++) ctl.add(round * 200 + i);
            for (int i = 0; i < 200; i++) ctl.contains(i);
            ctl.evaluateAndMaybePromote(400);
            assertTrue(ens.primary().isStrategyBacked(),
                    "automatic promotion must only ever select strategy-backed members");
        }
    }

    // ── Snapshot persistence (KeySerializer flat-key format) ─────────────────────

    @Test
    @DisplayName("a persistent-engine snapshot round-trips through the adapter (flat ascending keys)")
    void persistentSnapshotRoundTrip() {
        PersistentRankedSet<Integer> set = PersistentRankedSet.withNaturalOrder();
        for (int i = 0; i < 500; i++) set.add(i * 7 % 500);   // permutation of 0..499
        PersistentTreeEngine.Snapshot<Integer> frozen = set.engine().snapshot();
        set.add(1000);   // mutate after freezing — the snapshot must not see it

        String name = snap("roundtrip");
        adapter.saveSnapshot(name, frozen, KeySerializer.INTEGER);

        PersistentTreeEngine<Integer> loaded =
                adapter.loadPersistent(name, KeySerializer.INTEGER, Comparator.naturalOrder());
        assertTrue(loaded != null, "snapshot file exists and parses");
        assertEquals(500, loaded.size(), "the frozen version, not the mutated one");
        assertEquals(frozen.inOrder(), loaded.inOrder());
        assertFalse(loaded.contains(1000));
        assertTrue(loaded.validateInvariants().isEmpty(),
                "ascending replay rebuilds a weight-balanced tree");
    }

    @Test
    @DisplayName("loading a missing or foreign snapshot returns null; a ';'-producing key fails loudly")
    void persistentSnapshotEdges() {
        assertNull(adapter.loadPersistent("test-p3-no-such-snapshot",
                KeySerializer.INTEGER, Comparator.naturalOrder()));

        // A serializer that leaks the field delimiter must be rejected at save time: silently
        // dropping a KEY (unlike a tag) would corrupt the set on reload.
        PersistentRankedSet<String> set = new PersistentRankedSet<>(Comparator.naturalOrder());
        set.add("a;b");
        PersistentTreeEngine.Snapshot<String> frozen = set.engine().snapshot();
        KeySerializer<String> leaky = new KeySerializer<String>() {
            @Override public String serialize(String key)    { return key; }
            @Override public String deserialize(String tok)  { return tok; }
        };
        String name = snap("leaky");
        assertThrows(IllegalArgumentException.class,
                () -> adapter.saveSnapshot(name, frozen, leaky));
    }
}
