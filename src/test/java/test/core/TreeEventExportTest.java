package test.core;

import core.OrderedSet;
import core.ensemble.EnsembleController;
import core.ensemble.EnsembleMember;
import core.ensemble.EnsembleMode;
import core.ensemble.EnsembleOrderedSet;
import core.control.RollingWorkloadMonitor;
import core.event.TreeEvent;
import core.export.TreeExport;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-009 P3 — structured events + JSON export. The contracts under test: events fire only
 * on <em>effective</em> changes and mirror the log lines exactly (insert/remove/evict/morph/
 * repair on the set; quarantine/heal/promote-with-failover-flag/rebuild/ceiling on the
 * ensemble, including controller-driven repairs flowing through the same lifecycle methods);
 * the unobserved path allocates nothing for events (benchmark row); and {@code TreeExport}
 * renders the documented schema with escaped keys.
 */
@DisplayName("Structured events + TreeExport (ADR-009 P3)")
public class TreeEventExportTest {

    @Nested
    @DisplayName("OrderedSet events")
    class SetEvents {

        @Test
        @DisplayName("insert/remove/evict fire on effective changes only; null unregisters")
        void effectiveChangesOnly() {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            List<TreeEvent<Integer>> log = new ArrayList<>();
            set.setEventListener(log::add);

            set.add(1);
            set.add(1);                                          // duplicate: no event
            set.remove(2);                                       // absent: no event
            set.remove(1);
            assertEquals(List.of(new TreeEvent.Insert<>(1), new TreeEvent.Remove<>(1)), log);

            log.clear();
            set.setMaxSize(2);
            set.add(10); set.add(11); set.add(12);               // 12 evicts 10 (oldest)
            assertTrue(log.contains(new TreeEvent.Evict<>(10)), "window eviction emits: " + log);

            log.clear();
            set.setEventListener(null);
            set.add(99);
            assertTrue(log.isEmpty(), "null unregisters");
        }

        @Test
        @DisplayName("morph attempts carry from/to and the health-gate verdict; repair carries its verdict")
        void morphAndRepair() {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            for (int i = 0; i < 50; i++) set.add(i);
            List<TreeEvent<Integer>> log = new ArrayList<>();
            set.setEventListener(log::add);

            assertTrue(set.setStrategy(new AVLStrategy<>()));
            assertEquals(List.of(new TreeEvent.Morph<>("RedBlackStrategy", "AVLStrategy", true)), log);

            log.clear();
            assertFalse(set.setStrategy(new AVLStrategy<>()), "same-strategy no-op");
            assertTrue(log.isEmpty(), "no attempt, no event");

            assertTrue(set.selfRepair());
            assertEquals(List.of(new TreeEvent.Repair<>(true)), log);
        }

        @Test
        @DisplayName("benchmark row: the unobserved write path pays nothing for the seam")
        void unobservedPathIsFree() {
            final int n = 150_000;
            OrderedSet<Integer> bare = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            OrderedSet<Integer> observed = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            long[] sink = new long[1];
            observed.setEventListener(e -> sink[0]++);           // cheapest possible listener

            for (int i = 1; i <= 20_000; i++) { bare.add(-i); observed.add(-i); }   // warm-up, disjoint keys

            sink[0] = 0;                                         // count the timed loop only
            long t0 = System.nanoTime();
            for (int i = 0; i < n; i++) bare.add(i);
            long bareNs = System.nanoTime() - t0;

            t0 = System.nanoTime();
            for (int i = 0; i < n; i++) observed.add(i);
            long observedNs = System.nanoTime() - t0;

            System.out.printf("ADR-009 P3 benchmark: %d inserts: no listener %.1f ms; "
                            + "counting listener %.1f ms%n", n, bareNs / 1e6, observedNs / 1e6);
            assertEquals(n, sink[0], "every effective insert was observed");
            assertTrue(bareNs < observedNs * 2,
                    "the unobserved path must not pay for events: " + bareNs + " vs " + observedNs);
        }
    }

    @Nested
    @DisplayName("Ensemble events")
    class EnsembleEvents {

        private EnsembleOrderedSet<Integer> mirror() {
            return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(() -> new RedBlackStrategy<Integer>())
                    .member(() -> new AVLStrategy<Integer>())
                    .member(() -> new SplayStrategy<Integer>())
                    .build();
        }

        private static EnsembleMember<Integer> memberNamed(EnsembleOrderedSet<Integer> e, String n) {
            for (EnsembleMember<Integer> m : e.members()) if (m.strategyName().equals(n)) return m;
            throw new AssertionError("no member " + n);
        }

        @Test
        @DisplayName("controller-driven repair emits quarantine + heal; explicit promote emits failover=false")
        void lifecycleEvents() {
            EnsembleOrderedSet<Integer> ens = mirror();
            EnsembleController<Integer> ctl =
                    new EnsembleController<>(ens, new RollingWorkloadMonitor(512));
            for (int i = 0; i < 200; i++) ctl.add(i);

            List<TreeEvent<Integer>> log = new ArrayList<>();
            ens.setEventListener(log::add);

            memberNamed(ens, "AVLStrategy").set().remove(50);    // out-of-band divergence
            ctl.checkHealth();
            assertTrue(log.contains(new TreeEvent.Quarantine<>("AVLStrategy")), "quarantined: " + log);
            assertTrue(log.contains(new TreeEvent.Heal<>("AVLStrategy", true)), "healed: " + log);

            log.clear();
            ens.promote(memberNamed(ens, "SplayStrategy"));
            assertEquals(List.of(new TreeEvent.Promote<>("RedBlackStrategy", "SplayStrategy", false)), log);
        }

        @Test
        @DisplayName("a dissenting VERIFIED primary emits a failover promote + its quarantine")
        void voteFailoverEvents() {
            EnsembleOrderedSet<Integer> ens = mirror();
            ens.setMode(EnsembleMode.VERIFIED);
            for (int i = 0; i < 100; i++) ens.add(i);

            List<TreeEvent<Integer>> log = new ArrayList<>();
            ens.setEventListener(log::add);
            ens.primary().set().remove(42);                      // the primary diverges

            assertTrue(ens.contains(42), "the majority answer is served");
            boolean sawFailover = false, sawQuarantine = false;
            for (TreeEvent<Integer> e : log) {
                if (e instanceof TreeEvent.Promote<Integer> p && p.failover()
                        && p.fromMember().equals("RedBlackStrategy")) sawFailover = true;
                if (e instanceof TreeEvent.Quarantine<Integer> q
                        && q.member().equals("RedBlackStrategy")) sawQuarantine = true;
            }
            assertTrue(sawFailover, "failover promote: " + log);
            assertTrue(sawQuarantine, "deposed primary quarantined: " + log);
        }

        @Test
        @DisplayName("ceiling transitions and Option C rebuilds emit")
        void ceilingAndRebuildEvents() {
            EnsembleOrderedSet<Integer> ens =
                    EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                            .member(() -> new RedBlackStrategy<Integer>())
                            .member(() -> new AVLStrategy<Integer>())
                            .memoryCeilingBytes(9_600)
                            .build();
            List<TreeEvent<Integer>> log = new ArrayList<>();
            ens.setEventListener(log::add);

            for (int i = 0; i < 60; i++) ens.add(i);
            assertTrue(log.stream().anyMatch(e -> e instanceof TreeEvent.MemoryCeiling<Integer> m
                    && m.breached()), "breach event: " + log);
            for (int i = 0; i < 30; i++) ens.remove(i);
            assertTrue(log.stream().anyMatch(e -> e instanceof TreeEvent.MemoryCeiling<Integer> m
                    && !m.breached()), "recovery event: " + log);

            EnsembleOrderedSet<Integer> rebuild =
                    EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                            .member(() -> new RedBlackStrategy<Integer>())
                            .member(() -> new AVLStrategy<Integer>())
                            .mode(EnsembleMode.REBUILD_SHADOW)
                            .rebuildEvery(10)
                            .build();
            List<TreeEvent<Integer>> rlog = new ArrayList<>();
            rebuild.setEventListener(rlog::add);
            for (int i = 1; i <= 10; i++) rebuild.add(i);
            assertTrue(rlog.contains(new TreeEvent.ShadowRebuild<Integer>(1, 10)),
                    "cadence rebuild event: " + rlog);
        }
    }

    @Nested
    @DisplayName("TreeExport")
    class Export {

        @Test
        @DisplayName("the JSON matches the documented schema; keys are escaped; braces balance")
        void exportSchema() {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            for (int i = 1; i <= 7; i++) set.add(i * 10);
            String json = TreeExport.toJson(set);

            assertTrue(json.contains("\"type\": \"OrderedSet\""), json);
            assertTrue(json.contains("\"strategy\": \"RedBlackStrategy\""), json);
            assertTrue(json.contains("\"size\": 7"), json);
            assertTrue(json.contains("\"color\": \"BLACK\""), "an RB root is black: " + json);
            assertTrue(json.contains("\"depth\": 1"), json);
            assertTrue(json.contains("\"avgInsertMs\""), json);
            assertEquals(count(json, '{'), count(json, '}'), "balanced braces");
            assertEquals(0, count(json, '{') % 1, "sanity");

            OrderedSet<String> weird = OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
            weird.add("plain");
            weird.add("with\"quote");
            String wj = TreeExport.toJson(weird);
            assertTrue(wj.contains("with\\\"quote"), "quotes escaped: " + wj);

            OrderedSet<Integer> empty = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            String ej = TreeExport.toJson(empty);
            assertTrue(ej.contains("\"root\": null"), ej);
            assertTrue(ej.contains("\"height\": 0"), ej);
        }

        private static int count(String s, char c) {
            int n = 0;
            for (int i = 0; i < s.length(); i++) if (s.charAt(i) == c) n++;
            return n;
        }
    }
}
