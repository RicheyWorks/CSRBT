package test.core;

import core.RedBlackTree;
import core.PersistentTreeEngine;
import core.evolution.StrategyBattleRunner;
import core.evolution.StrategyBattleRunner.BattleResult;
import core.evolution.StrategyBattleRunner.WorkloadType;
import core.TreeContext;
import core.TreeEngineRegistry;
import core.TreeNode1;
import core.evolution.TreeGenome.StructureType;
import core.interfaces.OrderedCollection;
import core.interfaces.TreeEngine;
import core.strategy.AVLStrategy;
import core.strategy.HybridStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;
import core.util.OrderStatisticsOps;
import core.util.TreeDiagnostics;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.MethodSource;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;
import java.util.function.Supplier;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * JUnit 5 suite for the current CSRBT architecture.
 *
 * This replaces the legacy BinarySearchTree1 suite, which targeted an API
 * (isFull/removeLeaves/trim/sum/...) that no longer exists. The current core
 * is TreeContext (facade) over RedBlackTree, driven by a pluggable
 * TreeStrategy. Tests are organized as:
 *
 *   - Core operations  : insert / contains / remove / size, on RedBlackStrategy
 *   - RB invariants     : red-black properties hold ONLY for RedBlackStrategy
 *                         (AVL/Splay/Hybrid don't maintain RB colors)
 *   - Cross-strategy    : ordering + membership hold for every strategy
 *   - Order statistics  : select / rank / range / successor / predecessor
 *   - Strategy morphing : setStrategy() preserves contents
 *   - Stress            : large randomized workload stays correct
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
@DisplayName("TreeContext / RedBlackTree current-API suite")
public class TreeContextTester {

    private TreeContext ctx;

    @BeforeEach
    void reset() {
        ctx = new TreeContext(new RedBlackStrategy());
    }

    /** In-order keys of the underlying tree, via diagnostics. */
    private List<Integer> inOrder(TreeContext c) {
        return new TreeDiagnostics(c).inOrderTraversal();
    }

    private static List<Integer> sortedCopy(List<Integer> in) {
        List<Integer> out = new ArrayList<>(in);
        Collections.sort(out);
        return out;
    }

    // ── Core operations (RedBlackStrategy) ─────────────────────────────────────

    @Test @Order(1)
    @DisplayName("empty tree: size 0, contains nothing")
    void emptyTree() {
        assertEquals(0, ctx.getSize(), "fresh tree should be empty");
        assertFalse(ctx.contains(10), "empty tree contains nothing");
        assertTrue(inOrder(ctx).isEmpty(), "empty in-order traversal");
    }

    @Test @Order(2)
    @DisplayName("insert grows size and membership")
    void insertAndContains() {
        for (int v : new int[]{10, 5, 15, 2, 7}) ctx.add(v);
        assertEquals(5, ctx.getSize(), "size tracks distinct inserts");
        for (int v : new int[]{10, 5, 15, 2, 7}) assertTrue(ctx.contains(v), "should contain " + v);
        assertFalse(ctx.contains(999), "should not contain unseen key");
    }

    @Test @Order(3)
    @DisplayName("in-order traversal is sorted")
    void inOrderSorted() {
        int[] vals = {42, 7, 19, 1, 88, 23, 5};
        for (int v : vals) ctx.add(v);
        List<Integer> io = inOrder(ctx);
        assertEquals(sortedCopy(io), io, "in-order traversal must be ascending");
        assertEquals(vals.length, io.size(), "traversal size matches inserts");
    }

    @Test @Order(4)
    @DisplayName("remove: existing decrements, missing is a no-op")
    void removeSemantics() {
        for (int v : new int[]{10, 5, 15, 2, 7}) ctx.add(v);
        ctx.remove(2);
        assertFalse(ctx.contains(2), "removed key gone");
        assertEquals(4, ctx.getSize(), "size drops after real remove");

        ctx.remove(12345);
        assertEquals(4, ctx.getSize(), "removing absent key does not change size");

        ctx.remove(10);
        assertFalse(ctx.contains(10), "removing root works");
        assertTrue(ctx.contains(5) && ctx.contains(15) && ctx.contains(7), "survivors remain");
    }

    @Test @Order(5)
    @DisplayName("clear empties the tree")
    void clearEmpties() {
        for (int v : new int[]{3, 1, 4, 1, 5, 9, 2, 6}) ctx.add(v);
        ctx.clear();
        assertEquals(0, ctx.getSize(), "size 0 after clear");
        assertTrue(inOrder(ctx).isEmpty(), "no keys after clear");
    }

    // ── Red-Black invariants (RedBlackStrategy only) ───────────────────────────

    @Test @Order(6)
    @DisplayName("red-black invariants hold after inserts")
    void rbInvariantsAfterInserts() {
        TreeDiagnostics diag = new TreeDiagnostics(ctx);
        for (int i = 1; i <= 64; i++) {          // sorted inserts: worst case for naive BST
            ctx.add(i);
            assertTrue(diag.isValidRedBlack(), "RB validity must hold at n=" + i);
            assertTrue(diag.hasNoRedRed(), "no red-red violation at n=" + i);
        }
        RedBlackTree t = ctx.getTree();
        assertTrue(t.getRoot().isBlack(), "root must be black");
    }

    @Test @Order(7)
    @DisplayName("red-black invariants hold after deletes")
    void rbInvariantsAfterDeletes() {
        TreeDiagnostics diag = new TreeDiagnostics(ctx);
        for (int i = 1; i <= 40; i++) ctx.add(i);
        for (int i = 1; i <= 40; i += 2) {       // delete the odds
            ctx.remove(i);
            assertTrue(diag.isValidRedBlack(), "RB validity must hold after removing " + i);
        }
    }

    @Test @Order(8)
    @DisplayName("selfRepair reports a valid tree")
    void selfRepairValid() {
        for (int v : new int[]{50, 25, 75, 10, 30, 60, 90}) ctx.add(v);
        assertTrue(ctx.selfRepair(), "a healthy tree should report valid after self-repair");
    }

    // ── Cross-strategy: ordering + membership ──────────────────────────────────

    static Stream<org.junit.jupiter.params.provider.Arguments> strategies() {
        return Stream.of(
            org.junit.jupiter.params.provider.Arguments.of("RedBlack", (Supplier<TreeStrategy>) RedBlackStrategy::new),
            org.junit.jupiter.params.provider.Arguments.of("AVL",      (Supplier<TreeStrategy>) AVLStrategy::new),
            org.junit.jupiter.params.provider.Arguments.of("Splay",    (Supplier<TreeStrategy>) SplayStrategy::new),
            org.junit.jupiter.params.provider.Arguments.of("Hybrid",   (Supplier<TreeStrategy>) HybridStrategy::new)
        );
    }

    @ParameterizedTest(name = "[{0}] keeps keys ordered and findable")
    @MethodSource("strategies")
    @DisplayName("every strategy maintains a searchable ordered set")
    void everyStrategyOrdersAndFinds(String name, Supplier<TreeStrategy> factory) {
        TreeContext c = new TreeContext(factory.get());
        int[] vals = {37, 12, 88, 3, 55, 21, 70, 9, 44, 61};
        for (int v : vals) c.add(v);

        for (int v : vals) assertTrue(c.contains(v), "[" + name + "] must contain " + v);
        assertFalse(c.contains(1000), "[" + name + "] must not contain unseen key");

        List<Integer> io = inOrder(c);
        assertEquals(sortedCopy(io), io, "[" + name + "] in-order must be ascending");
        assertEquals(vals.length, io.size(), "[" + name + "] traversal size matches inserts");
    }

    // ── Order statistics (CLRS Ch.14.1) ────────────────────────────────────────

    @Nested
    @DisplayName("OrderStatisticsOps")
    class OrderStats {
        // Inserted unsorted to prove OS-SELECT is not array indexing.
        private OrderStatisticsOps os() {
            TreeContext c = new TreeContext(new RedBlackStrategy());
            for (int v : new int[]{41, 38, 31, 12, 19, 8}) c.add(v);   // sorted: 8 12 19 31 38 41
            return new OrderStatisticsOps(c.getTree());
        }

        @Test
        @DisplayName("select returns the rank-th smallest")
        void select() {
            OrderStatisticsOps os = os();
            assertEquals(8,  os.select(1).getData(), "1st smallest");
            assertEquals(19, os.select(3).getData(), "3rd smallest");
            assertEquals(41, os.select(6).getData(), "6th smallest");
        }

        @Test
        @DisplayName("rank returns position of a key")
        void rank() {
            OrderStatisticsOps os = os();
            assertEquals(1, os.rank(8),  "rank of min");
            assertEquals(2, os.rank(12), "rank of 12");
            assertEquals(5, os.rank(38), "rank of 38");
        }

        @Test
        @DisplayName("min and max")
        void minMax() {
            OrderStatisticsOps os = os();
            assertEquals(8,  os.minimum().getData(), "minimum");
            assertEquals(41, os.maximum().getData(), "maximum");
        }

        @Test
        @DisplayName("median is one of the two central keys")
        void median() {
            int m = os().median().getData();
            assertTrue(m == 19 || m == 31, "median of even set is a central key, was " + m);
        }

        @Test
        @DisplayName("countInRange and rangeQuery are consistent")
        void range() {
            OrderStatisticsOps os = os();
            assertEquals(4, os.countInRange(12, 38), "12,19,31,38 are in [12,38]");
            assertEquals(List.of(12, 19, 31, 38), os.rangeQuery(12, 38), "range query ascending");
        }

        @Test
        @DisplayName("successor and predecessor")
        void neighbors() {
            OrderStatisticsOps os = os();
            assertEquals(31, os.successor(19).getData(),  "successor of 19");
            assertEquals(19, os.predecessor(31).getData(), "predecessor of 31");
        }
    }

    // ── Strategy morphing preserves contents ───────────────────────────────────

    @Test @Order(9)
    @DisplayName("setStrategy rebuilds with the same key set")
    void morphPreservesContents() {
        int[] vals = {15, 8, 22, 4, 11, 19, 27, 1};
        for (int v : vals) ctx.add(v);
        List<Integer> before = inOrder(ctx);

        ctx.setStrategy(new AVLStrategy());
        assertEquals(before, inOrder(ctx), "morph to AVL preserves ordered keys");
        for (int v : vals) assertTrue(ctx.contains(v), "AVL still contains " + v);

        ctx.setStrategy(new SplayStrategy());
        assertEquals(before, inOrder(ctx), "morph to Splay preserves ordered keys");
    }

    // ── Stress ─────────────────────────────────────────────────────────────────

    @Test @Order(10)
    @DisplayName("randomized stress stays correct and RB-balanced")
    void stress() {
        TreeDiagnostics diag = new TreeDiagnostics(ctx);
        Random rng = new Random(42);              // fixed seed → deterministic
        List<Integer> keys = new ArrayList<>();
        java.util.Set<Integer> seen = new java.util.TreeSet<>();
        while (seen.size() < 300) seen.add(rng.nextInt(5000));
        keys.addAll(seen);

        for (int k : keys) ctx.add(k);
        assertEquals(keys.size(), ctx.getSize(), "size matches distinct inserts");
        assertTrue(diag.isValidRedBlack(), "RB validity after bulk insert");

        Collections.shuffle(keys, rng);
        for (int i = 0; i < 150; i++) ctx.remove(keys.get(i));
        assertEquals(150, ctx.getSize(), "size after removing half");
        assertTrue(diag.isValidRedBlack(), "RB validity after bulk delete");

        List<Integer> io = inOrder(ctx);
        assertEquals(sortedCopy(io), io, "survivors remain ordered");
        for (int i = 150; i < keys.size(); i++) {
            assertTrue(ctx.contains(keys.get(i)), "survivor " + keys.get(i) + " still present");
        }
    }

    // ── Neutral abstractions (Phase 2 seam) ────────────────────────────────────

    @Nested
    @DisplayName("representation-neutral interfaces")
    class NeutralInterfaces {

        @Test
        @DisplayName("TreeContext is usable purely as an OrderedCollection")
        void asOrderedCollection() {
            OrderedCollection oc = new TreeContext(new RedBlackStrategy());
            assertTrue(oc.isEmpty(), "fresh collection is empty");
            for (int v : new int[]{30, 10, 20, 40, 5}) oc.add(v);
            assertEquals(5, oc.size(), "size via interface");
            assertFalse(oc.isEmpty(), "non-empty after inserts");
            assertTrue(oc.contains(20), "membership via interface");
            assertEquals(List.of(5, 10, 20, 30, 40), oc.inOrder(), "ordered via interface");
            oc.remove(20);
            assertFalse(oc.contains(20), "remove via interface");
            assertEquals(4, oc.size(), "size after remove");
            oc.clear();
            assertTrue(oc.isEmpty(), "clear via interface");
        }

        @Test
        @DisplayName("RedBlackTree is usable purely as a TreeEngine")
        void asTreeEngine() {
            TreeEngine engine = new core.RedBlackTree(new RedBlackStrategy());
            assertTrue(engine.isEmpty(), "fresh engine is empty");
            for (int v : new int[]{7, 3, 9, 1, 5}) engine.add(v);
            assertEquals(5, engine.size(), "size via engine");
            assertEquals(List.of(1, 3, 5, 7, 9), engine.inOrder(), "ordered via engine");
            assertTrue(engine.contains(5), "membership via engine");
            engine.remove(5);
            assertFalse(engine.contains(5), "remove via engine");
            assertEquals(4, engine.size(), "size after engine remove");
            engine.clear();
            assertTrue(engine.isEmpty() && engine.inOrder().isEmpty(), "clear via engine");
        }
    }

    // ── Phase 3: persistent engine + honest registry ───────────────────────────

    @Nested
    @DisplayName("PersistentTreeEngine")
    class Persistent {

        @Test
        @DisplayName("behaves as an ordered set")
        void orderedSet() {
            PersistentTreeEngine p = new PersistentTreeEngine();
            for (int v : new int[]{50, 20, 70, 20, 10, 60}) p.add(v); // 20 duplicated
            assertEquals(5, p.size(), "duplicate ignored (set semantics)");
            assertEquals(List.of(10, 20, 50, 60, 70), p.inOrder(), "ascending order");
            assertTrue(p.contains(60) && !p.contains(999), "membership");
            p.remove(50);
            assertEquals(List.of(10, 20, 60, 70), p.inOrder(), "remove keeps order");
        }

        @Test
        @DisplayName("old versions survive later mutations (persistence)")
        void versionsArePersistent() {
            PersistentTreeEngine p = new PersistentTreeEngine();
            p.add(5);
            p.add(3);
            p.add(8);
            int snapshot = p.versionCount() - 1;        // version with {3,5,8}
            List<Integer> atSnapshot = p.inOrderOfVersion(snapshot);
            assertEquals(List.of(3, 5, 8), atSnapshot, "snapshot captured");

            p.add(1);
            p.remove(5);                                  // mutate "current"
            assertEquals(List.of(1, 3, 8), p.inOrder(), "current reflects edits");
            assertEquals(List.of(3, 5, 8), p.inOrderOfVersion(snapshot),
                    "earlier version is unchanged by later edits");
        }
    }

    @Nested
    @DisplayName("TreeEngineRegistry (honest enum)")
    class Registry {

        @Test
        @DisplayName("every declared StructureType has a capability")
        void everyTypeMapped() {
            for (StructureType t : StructureType.values()) {
                assertTrue(TreeEngineRegistry.capability(t) != null, t + " must be mapped");
            }
        }

        @Test
        @DisplayName("supported types build a working engine")
        void supportedBuild() {
            for (StructureType t : TreeEngineRegistry.supportedTypes()) {
                TreeEngine e = TreeEngineRegistry.create(t);
                e.add(2); e.add(1); e.add(3);
                assertEquals(List.of(1, 2, 3), e.inOrder(), t + " engine must order keys");
            }
        }

        @Test
        @DisplayName("RB family + persistent are supported")
        void expectedSupported() {
            assertTrue(TreeEngineRegistry.isSupported(StructureType.RED_BLACK));
            assertTrue(TreeEngineRegistry.isSupported(StructureType.AVL));
            assertTrue(TreeEngineRegistry.isSupported(StructureType.SPLAY));
            assertTrue(TreeEngineRegistry.isSupported(StructureType.HYBRID));
            assertTrue(TreeEngineRegistry.isSupported(StructureType.PERSISTENT_TREE));
        }

        @Test
        @DisplayName("non-ordered-map types are unsupported and fail loudly")
        void unsupportedFailLoudly() {
            assertFalse(TreeEngineRegistry.isSupported(StructureType.FIBONACCI_HEAP));
            assertFalse(TreeEngineRegistry.isSupported(StructureType.VAN_EMDE_BOAS));
            assertThrows(UnsupportedOperationException.class,
                    () -> TreeEngineRegistry.create(StructureType.FIBONACCI_HEAP),
                    "creating an unsupported type must throw, not return null");
            assertThrows(UnsupportedOperationException.class,
                    () -> TreeEngineRegistry.create(StructureType.VAN_EMDE_BOAS));
        }
    }

    // ── StrategyBattleRunner regression smoke test (ADR item 8) ────────────────

    @Nested
    @DisplayName("StrategyBattleRunner regression")
    class BattleRegression {

        private static final int  OPS  = 500;
        private static final long SEED = 1234L;

        private List<BattleResult> run(WorkloadType wl) {
            return StrategyBattleRunner.run(wl, OPS, SEED);
        }

        @ParameterizedTest(name = "{0}")
        @EnumSource(WorkloadType.class)
        @DisplayName("every workload yields four well-formed, ranked results")
        void wellFormed(WorkloadType wl) {
            List<BattleResult> rs = run(wl);
            assertEquals(4, rs.size(), "RedBlack, AVL, Splay, Hybrid all compete");

            java.util.Set<Integer> ranks = new java.util.TreeSet<>();
            for (BattleResult r : rs) {
                assertEquals(OPS, r.totalOps, "totalOps matches workload size");
                assertTrue(r.finalSize >= 0 && r.finalSize <= OPS,
                        r.strategyName + " finalSize within [0, ops]");
                assertTrue(r.searchHits >= 0 && r.searchHits <= OPS,
                        r.strategyName + " searchHits within [0, ops]");
                assertTrue(r.avgSearchDepth >= 0, r.strategyName + " depth non-negative");
                ranks.add(r.rank);
            }
            assertEquals(java.util.Set.of(1, 2, 3, 4), ranks, "ranks are a permutation of 1..4");
        }

        @ParameterizedTest(name = "{0}")
        @EnumSource(WorkloadType.class)
        @DisplayName("all strategies agree on search hits (same ops ⇒ same membership)")
        void crossStrategyMembershipAgrees(WorkloadType wl) {
            List<BattleResult> rs = run(wl);
            int expected = rs.get(0).searchHits;
            for (BattleResult r : rs) {
                assertEquals(expected, r.searchHits,
                        r.strategyName + " must see identical search hits on identical ops");
            }
        }

        @ParameterizedTest(name = "{0}")
        @EnumSource(WorkloadType.class)
        @DisplayName("per-strategy results are deterministic for a fixed seed")
        void deterministic(WorkloadType wl) {
            // Rank order depends on wall-clock timing (compositeScore weights
            // time), so compare by strategy NAME, not list position. The
            // structural outcomes (search hits, final size) must be stable.
            java.util.Map<String, BattleResult> a = byName(run(wl));
            java.util.Map<String, BattleResult> b = byName(run(wl));
            assertEquals(a.keySet(), b.keySet(), "same competitors both runs");
            for (String name : a.keySet()) {
                assertEquals(a.get(name).searchHits, b.get(name).searchHits,
                        name + " search hits must be stable across runs");
                assertEquals(a.get(name).finalSize, b.get(name).finalSize,
                        name + " final size must be stable across runs");
            }
        }

        private java.util.Map<String, BattleResult> byName(List<BattleResult> rs) {
            java.util.Map<String, BattleResult> m = new java.util.HashMap<>();
            for (BattleResult r : rs) m.put(r.strategyName, r);
            return m;
        }
    }
}
