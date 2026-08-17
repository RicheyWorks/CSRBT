package test.core;

import io.github.richeyworks.csrbt.BPlusTreeEngine;
import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentRankedSet;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.adapter.NavigableOrderedSet;
import io.github.richeyworks.csrbt.augment.GenericIntervalAugmentor;
import io.github.richeyworks.csrbt.augment.IntervalAugmentor;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.interfaces.RankedSet;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.LoadStatus;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.SaveResult;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.SaveStatus;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;
import io.github.richeyworks.csrbt.util.StrategyHealthCheck;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Random;
import java.util.TreeSet;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Edge-case hardening pass, 2026-08-17 — the degenerate ends of every dimension.
 *
 * <p>The suite before this class was strong on happy paths and on the specific defects six audits
 * found, and thin on boundaries: size 0/1/2 and the fanout floor, {@code Integer.MIN_VALUE} /
 * {@code MAX_VALUE} keys, comparators inconsistent with {@code equals} or that throw, inverted and
 * out-of-domain ranges, rank/percentile at and past the ends, {@code maxSize} of 0/1/exactly-n,
 * lifecycle after {@code close()}, and reentrancy. Each test below either <b>pins behaviour that
 * was already correct</b> (most of them) or <b>guards a defect this pass fixed</b> — the latter
 * are marked FIX and named in the class they live in.</p>
 *
 * <p>Fixes guarded here:</p>
 * <ul>
 *   <li><b>E-1</b> {@code OrderedSet.buildFromSorted} / {@code fromSorted} /
 *       {@code EnsembleOrderedSet.buildAllFromSorted} accepted a null key on a ONE-element list —
 *       the {@code add} hole audit 2026-08-17 item 1 (S6-44) closed, on the bulk path it missed.</li>
 *   <li><b>E-2</b> {@code EnsembleOrderedSet.add(null)} / {@code remove(null)} QUARANTINED every
 *       non-primary member for a caller argument error, and left a READ_REPLICA ensemble unable to
 *       accept any further write, ever.</li>
 *   <li><b>E-3</b> a {@code TreeEventListener} that called back into its own set parked the
 *       mutating thread forever on the non-reentrant {@code StampedLock}.</li>
 *   <li><b>E-4</b> the pre-order save path did not enforce {@code KeySerializer}'s token contract,
 *       so a serializer emitting {@code ';'} or {@code ','} wrote a file that only failed on
 *       load, in another process, with no hint at the cause.</li>
 * </ul>
 */
@DisplayName("Edge cases — the degenerate ends of every dimension (2026-08-17)")
class EdgeCaseBoundaryTest {

    private static final List<Supplier<TreeStrategy<Integer>>> STRATEGIES = List.of(
            RedBlackStrategy::new, AVLStrategy::new, SplayStrategy::new,
            WeightBalancedStrategy::new, HybridStrategy::new);

    private static OrderedSet<Integer> set(Supplier<TreeStrategy<Integer>> s) {
        return new OrderedSet<>(s.get(), Comparator.<Integer>naturalOrder());
    }

    private static OrderedSet<Integer> rb() {
        return new OrderedSet<>(new RedBlackStrategy<>(), Comparator.<Integer>naturalOrder());
    }

    // ── Size: empty, one, two, powers of two ± 1, multi-level ────────────────────────

    @Nested
    @DisplayName("size boundaries")
    class Size {

        @Test
        @DisplayName("every strategy is sound at 0, 1, 2 and around each power of two")
        void degenerateAndPowerOfTwoSizes() {
            int[] sizes = {0, 1, 2, 3, 4, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 1023, 1024, 1025};
            for (Supplier<TreeStrategy<Integer>> s : STRATEGIES) {
                for (int n : sizes) {
                    OrderedSet<Integer> t = set(s);
                    for (int i = 0; i < n; i++) t.add(i);
                    String at = s.get().getClass().getSimpleName() + " n=" + n;
                    assertEquals(n, t.size(), at);
                    assertEquals(List.of(), StrategyHealthCheck.validate(t.getEngine(), t.getStrategy(),
                            t.inOrder()), at);
                    if (n == 0) {
                        assertNull(t.minimum(), at);
                        assertNull(t.maximum(), at);
                        assertNull(t.median(), at);
                    } else {
                        assertEquals(0, t.minimum(), at);
                        assertEquals(n - 1, t.maximum(), at);
                        assertEquals(1, t.rank(0), at);
                        assertEquals(n, t.rank(n - 1), at);
                        assertEquals(0, t.select(1), at);
                        assertEquals(n - 1, t.select(n), at);
                    }
                }
            }
        }

        @Test
        @DisplayName("delete to empty then refill leaves every strategy sound")
        void deleteToEmptyThenRefill() {
            for (Supplier<TreeStrategy<Integer>> s : STRATEGIES) {
                OrderedSet<Integer> t = set(s);
                String at = s.get().getClass().getSimpleName();
                for (int i = 0; i < 200; i++) t.add(i);
                for (int i = 0; i < 200; i++) assertTrue(t.remove(i), at);
                assertEquals(0, t.size(), at);
                assertTrue(t.isEmpty(), at);
                assertTrue(t.getEngine().getRoot().isNil(), at + " root must be the NIL sentinel again");
                assertEquals(List.of(), t.inOrder(), at);
                for (int i = 0; i < 200; i++) t.add(i);
                assertEquals(200, t.size(), at);
                assertEquals(List.of(), StrategyHealthCheck.validate(t.getEngine(), t.getStrategy(),
                        t.inOrder()), at);
            }
        }

        @Test
        @DisplayName("alternating add/remove that keeps size constant tracks a TreeSet exactly")
        void constantSizeChurnMatchesOracle() {
            for (Supplier<TreeStrategy<Integer>> s : STRATEGIES) {
                OrderedSet<Integer> t = set(s);
                TreeSet<Integer> oracle = new TreeSet<>();
                String at = s.get().getClass().getSimpleName();
                for (int i = 0; i < 50; i++) { t.add(i); oracle.add(i); }
                for (int i = 50; i < 3000; i++) {
                    t.add(i);           oracle.add(i);
                    t.remove(i - 50);   oracle.remove(i - 50);
                    assertEquals(50, t.size(), at + " at op " + i);
                }
                assertEquals(new ArrayList<>(oracle), t.inOrder(), at);
                assertEquals(List.of(), StrategyHealthCheck.validate(t.getEngine(), t.getStrategy(),
                        t.inOrder()), at);
            }
        }

        @Test
        @DisplayName("morph and selfRepair are sound at n = 0, 1 and 2")
        void morphOnDegenerateSizes() {
            for (int n : new int[]{0, 1, 2}) {
                OrderedSet<Integer> t = rb();
                for (int i = 0; i < n; i++) t.add(i);
                assertTrue(t.setStrategy(new AVLStrategy<>()), "n=" + n);
                assertEquals(n, t.size(), "n=" + n);
                assertTrue(t.selfRepair(), "n=" + n);
                assertEquals(n, t.size(), "n=" + n);
                assertFalse(t.setStrategy(null), "null strategy is a refusal, not a crash");
                assertFalse(t.setStrategy(new AVLStrategy<>()), "same policy is a no-op");
            }
        }
    }

    // ── B+tree: the fanout boundary in both directions ───────────────────────────────

    @Nested
    @DisplayName("B+tree fanout boundary")
    class Fanout {

        @Test
        @DisplayName("fanout below MIN_FANOUT is refused, at and above is accepted")
        void fanoutFloor() {
            for (int bad : new int[]{Integer.MIN_VALUE, -1, 0, 1, BPlusTreeEngine.MIN_FANOUT - 1}) {
                assertThrows(IllegalArgumentException.class,
                        () -> BPlusTreeEngine.<Integer>withNaturalOrder(bad), "fanout " + bad);
            }
            assertNotNull(BPlusTreeEngine.<Integer>withNaturalOrder(BPlusTreeEngine.MIN_FANOUT));
            assertNotNull(BPlusTreeEngine.<Integer>withNaturalOrder(Integer.MAX_VALUE));
        }

        @Test
        @DisplayName("every n up to 3·fanout stays structurally valid through fill, empty and refill")
        void sizesAroundEveryNodeBoundary() {
            for (int fanout : new int[]{BPlusTreeEngine.MIN_FANOUT, 5, 6, 7}) {
                for (int n = 0; n <= 3 * fanout + 2; n++) {
                    for (String shape : new String[]{"asc", "desc", "outside-in"}) {
                        List<Integer> keys = shapedKeys(n, shape);
                        BPlusTreeEngine<Integer> b = BPlusTreeEngine.withNaturalOrder(fanout);
                        String at = "fanout=" + fanout + " n=" + n + " " + shape;
                        for (int k : keys) assertTrue(b.add(k), at);
                        assertEquals(List.of(), b.validateStructure(), at + " after fill");
                        assertEquals(n, b.size(), at);
                        for (int k : keys) assertTrue(b.remove(k), at);
                        assertEquals(0, b.size(), at + " after empty");
                        assertEquals(List.of(), b.validateStructure(), at + " after empty");
                        for (int k : keys) b.add(k);
                        assertEquals(List.of(), b.validateStructure(), at + " after refill");
                        assertEquals(n, b.inOrder().size(), at + " after refill");
                    }
                }
            }
        }

        private List<Integer> shapedKeys(int n, String shape) {
            List<Integer> keys = new ArrayList<>();
            for (int i = 0; i < n; i++) keys.add(i);
            if (shape.equals("desc")) Collections.reverse(keys);
            if (shape.equals("outside-in")) {
                List<Integer> alt = new ArrayList<>();
                for (int i = 0; i < n; i++) alt.add(i % 2 == 0 ? i / 2 : n - 1 - i / 2);
                keys = alt;
            }
            return keys;
        }

        @Test
        @DisplayName("a full node, a node at minimum occupancy, and the height collapse")
        void occupancyBoundaries() {
            BPlusTreeEngine<Integer> b = BPlusTreeEngine.withNaturalOrder(4);
            for (int i = 0; i < 4; i++) b.add(i);
            assertEquals(1, b.height(), "a full root leaf has not split yet");
            assertEquals(List.of(4), b.leafKeyCounts());
            b.add(4);
            assertEquals(2, b.height(), "the 5th key splits the root leaf");
            assertEquals(List.of(2, 3), b.leafKeyCounts(), "the split lands both halves at/above the floor");
            for (int i = 4; i >= 1; i--) b.remove(i);
            assertEquals(1, b.height(), "emptying back down collapses the height");
            assertEquals(List.of(1), b.leafKeyCounts());
            assertEquals(List.of(), b.validateStructure());
        }

        @Test
        @DisplayName("differential churn at the fanout floor tracks TreeSet exactly")
        void differentialAgainstTreeSetAtTheFloor() {
            for (int fanout : new int[]{BPlusTreeEngine.MIN_FANOUT, 5}) {
                for (long seed = 0; seed < 8; seed++) {
                    Random r = new Random(seed);
                    BPlusTreeEngine<Integer> b = BPlusTreeEngine.withNaturalOrder(fanout);
                    TreeSet<Integer> oracle = new TreeSet<>();
                    String at = "fanout=" + fanout + " seed=" + seed;
                    for (int i = 0; i < 1500; i++) {
                        int k = r.nextInt(60);          // tight range: constant splits and merges
                        if (r.nextBoolean()) assertEquals(oracle.add(k), b.add(k), at + " add " + k);
                        else                 assertEquals(oracle.remove(k), b.remove(k), at + " rm " + k);
                        assertEquals(List.of(), b.validateStructure(), at + " op " + i);
                        assertEquals(oracle.size(), b.size(), at + " op " + i);
                    }
                    assertEquals(new ArrayList<>(oracle), b.inOrder(), at);
                }
            }
        }
    }

    // ── Key domain: MIN/MAX, hash-vs-comparator disagreement, throwing comparators ───

    @Nested
    @DisplayName("key domain")
    class KeyDomain {

        @Test
        @DisplayName("Integer.MIN_VALUE and MAX_VALUE are ordinary keys on every implementation")
        void extremeIntegerKeys() {
            List<Integer> extremes = List.of(Integer.MIN_VALUE, Integer.MIN_VALUE + 1, -1, 0, 1,
                    Integer.MAX_VALUE - 1, Integer.MAX_VALUE);
            for (Supplier<TreeStrategy<Integer>> s : STRATEGIES) {
                OrderedSet<Integer> t = set(s);
                String at = s.get().getClass().getSimpleName();
                for (int k : extremes) assertTrue(t.add(k), at);
                assertEquals(extremes, t.inOrder(), at);
                assertEquals(extremes.size(), t.countInRange(Integer.MIN_VALUE, Integer.MAX_VALUE), at);
                assertEquals(Integer.MIN_VALUE, t.minimum(), at);
                assertEquals(Integer.MAX_VALUE, t.maximum(), at);
                assertEquals(extremes.size(), t.rank(Integer.MAX_VALUE), at);
                assertEquals(Integer.MIN_VALUE, t.floor(Integer.MIN_VALUE), at);
                assertNull(t.lower(Integer.MIN_VALUE), at + ": nothing is below MIN_VALUE");
                assertNull(t.higher(Integer.MAX_VALUE), at + ": nothing is above MAX_VALUE");
                assertEquals(Integer.MIN_VALUE + 1, t.higher(Integer.MIN_VALUE), at);
            }
            BPlusTreeEngine<Integer> b = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
            for (int k : extremes) b.add(k);
            assertEquals(extremes, b.inOrder());
            assertEquals(extremes.size(), b.countInRange(Integer.MIN_VALUE, Integer.MAX_VALUE));
            assertEquals(List.of(), b.validateStructure());
        }

        /** Ordered by id, {@code equals}/{@code hashCode} by name — hash collides, comparator does not. */
        private record Tagged(int id, String name) {
            @Override public boolean equals(Object o) { return o instanceof Tagged t && t.name.equals(name); }
            @Override public int hashCode() { return name.hashCode(); }
            @Override public String toString() { return id + ":" + name; }
        }

        @Test
        @DisplayName("keys that collide under hashCode but not the comparator survive a morph")
        void hashCollidingKeysSurviveAMorph() {
            OrderedSet<Tagged> t = new OrderedSet<>(new RedBlackStrategy<>(),
                    Comparator.comparingInt(Tagged::id));
            t.add(new Tagged(1, "a"));
            t.add(new Tagged(2, "a"));     // equals-identical to the first, compares greater
            t.add(new Tagged(3, "b"));
            assertEquals(3, t.size());
            assertTrue(t.setStrategy(new AVLStrategy<>()));
            assertEquals(3, t.size(), "the morph must not collapse equals-identical keys (finding 11)");
            assertEquals(List.of(1, 2, 3), t.inOrder().stream().map(Tagged::id).toList());
            assertTrue(t.selfRepair());
            assertEquals(3, t.size(), "selfRepair must not collapse them either");
        }

        @Test
        @DisplayName("keys equal under the comparator but not equals are one element")
        void comparatorEqualKeysAreOneElement() {
            OrderedSet<Tagged> t = new OrderedSet<>(new RedBlackStrategy<>(),
                    Comparator.comparingInt(Tagged::id));
            assertTrue(t.add(new Tagged(1, "a")));
            assertFalse(t.add(new Tagged(1, "different")), "the comparator is the identity authority");
            assertEquals(1, t.size());
        }

        @Test
        @DisplayName("a windowed set with equals-colliding keys still evicts by comparator identity")
        void windowWithHashCollidingKeys() {
            OrderedSet<Tagged> t = new OrderedSet<>(new RedBlackStrategy<>(),
                    Comparator.comparingInt(Tagged::id));
            t.setMaxSize(10);
            t.add(new Tagged(1, "a"));
            t.add(new Tagged(2, "a"));
            t.add(new Tagged(3, "b"));
            assertEquals(3, t.size(), "the FIFO window must not collapse equals-identical keys");
            t.setMaxSize(2);
            assertEquals(2, t.size());
            assertEquals(List.of(2, 3), t.inOrder().stream().map(Tagged::id).toList(),
                    "the oldest survivor is dropped, leaving the newest maxSize keys");
        }

        @Test
        @DisplayName("a throwing comparator propagates and leaves the set unchanged")
        void throwingComparatorLeavesTheSetIntact() {
            final boolean[] armed = {false};
            Comparator<Integer> fuse = (a, b) -> {
                if (armed[0]) throw new IllegalStateException("comparator refuses");
                return Integer.compare(a, b);
            };
            OrderedSet<Integer> t = new OrderedSet<>(new RedBlackStrategy<>(), fuse);
            for (int i = 0; i < 20; i++) t.add(i);
            List<Integer> before = t.inOrder();
            armed[0] = true;
            assertThrows(IllegalStateException.class, () -> t.add(99));
            assertThrows(IllegalStateException.class, () -> t.remove(5));
            assertThrows(IllegalStateException.class, () -> t.contains(5));
            armed[0] = false;
            assertEquals(20, t.size(), "a failed comparison must not have moved the size counter");
            assertEquals(before, t.inOrder(), "nor the contents");
            assertEquals(List.of(), StrategyHealthCheck.validate(t.getEngine(), t.getStrategy(),
                    t.inOrder()), "nor the structure");
        }

        @Test
        @DisplayName("keys whose compareTo has side effects are compared, never cached around")
        void comparatorIsTheOnlyOrderingAuthority() {
            final int[] calls = {0};
            Comparator<Integer> counting = (a, b) -> { calls[0]++; return Integer.compare(a, b); };
            OrderedSet<Integer> t = new OrderedSet<>(new RedBlackStrategy<>(), counting);
            for (int i = 0; i < 32; i++) t.add(i);
            int afterBuild = calls[0];
            assertTrue(afterBuild > 0, "the comparator is what orders the tree");
            assertTrue(t.contains(17));
            assertTrue(calls[0] > afterBuild, "a read consults the comparator, not a cached hash");
        }

        @Test
        @DisplayName("null is NPE on every key-taking method of every implementation, at every size")
        void nullIsUniformlyNpe() {
            for (int n : new int[]{0, 1, 2, 9}) {
                OrderedSet<Integer> os = rb();
                BPlusTreeEngine<Integer> bp = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
                PersistentRankedSet<Integer> pr = PersistentRankedSet.withNaturalOrder();
                for (int i = 1; i <= n; i++) { os.add(i); bp.add(i); pr.add(i); }
                for (RankedSet<Integer> s : List.<RankedSet<Integer>>of(os, bp, pr)) {
                    String at = s.getClass().getSimpleName() + " n=" + n;
                    assertThrows(NullPointerException.class, () -> s.add(null),         at + " add");
                    assertThrows(NullPointerException.class, () -> s.remove(null),      at + " remove");
                    assertThrows(NullPointerException.class, () -> s.contains(null),    at + " contains");
                    assertThrows(NullPointerException.class, () -> s.rank(null),        at + " rank");
                    assertThrows(NullPointerException.class, () -> s.successor(null),   at + " successor");
                    assertThrows(NullPointerException.class, () -> s.predecessor(null), at + " predecessor");
                    assertThrows(NullPointerException.class, () -> s.countInRange(null, 1), at + " countInRange lo");
                    assertThrows(NullPointerException.class, () -> s.countInRange(1, null), at + " countInRange hi");
                    assertThrows(NullPointerException.class, () -> s.rangeQuery(null, 1),   at + " rangeQuery lo");
                    assertThrows(NullPointerException.class, () -> s.rangeQuery(1, null),   at + " rangeQuery hi");
                    assertEquals(n, s.size(), at + ": a refused null must not have changed the set");
                }
                // OrderedSet's own navigation surface, which the RankedSet interface does not carry.
                assertThrows(NullPointerException.class, () -> os.searchDepth(null));
                assertThrows(NullPointerException.class, () -> os.floor(null));
                assertThrows(NullPointerException.class, () -> os.lower(null));
                assertThrows(NullPointerException.class, () -> os.ceiling(null));
                assertThrows(NullPointerException.class, () -> os.higher(null));
                assertThrows(NullPointerException.class, () -> os.countUpTo(null, true));
            }
        }

        @Test
        @DisplayName("FIX E-1: buildFromSorted refuses a null key instead of linking it in")
        void buildFromSortedRefusesNullKeys() {
            // The one-element list was the hole: the ascending check needs a PAIR, so a lone null
            // never reached a comparison and was built into the tree as a real element — size 1,
            // inOrder [null], and NPE on the next unrelated read.
            OrderedSet<Integer> lone = rb();
            assertThrows(NullPointerException.class,
                    () -> lone.buildFromSorted(Collections.singletonList(null)));
            assertEquals(0, lone.size(), "the refused build must leave the set empty");
            assertEquals(List.of(), lone.inOrder());
            assertFalse(lone.contains(1), "and still readable");

            OrderedSet<Integer> trailing = rb();
            assertThrows(NullPointerException.class,
                    () -> trailing.buildFromSorted(Arrays.asList(1, null)));
            assertEquals(0, trailing.size());

            OrderedSet<Integer> leading = rb();
            assertThrows(NullPointerException.class,
                    () -> leading.buildFromSorted(Arrays.asList(null, 1)));
            assertEquals(0, leading.size());

            assertThrows(NullPointerException.class, () -> rb().buildFromSorted(null));

            assertThrows(NullPointerException.class, () -> OrderedSet.fromSortedNatural(
                    Collections.<Integer>singletonList(null), new RedBlackStrategy<>()),
                    "the factories inherit the guard");
            assertThrows(NullPointerException.class, () -> OrderedSet.fromSorted(
                    Collections.<Integer>singletonList(null), new RedBlackStrategy<>(),
                    Comparator.<Integer>naturalOrder()));

            // Non-null builds are untouched, including the degenerate shapes.
            OrderedSet<Integer> ok = rb();
            ok.buildFromSorted(List.of());
            assertEquals(0, ok.size());
            OrderedSet<Integer> one = rb();
            one.buildFromSorted(List.of(42));
            assertEquals(List.of(42), one.inOrder());
            assertEquals(List.of(), StrategyHealthCheck.validate(one.getEngine(), one.getStrategy(),
                    one.inOrder()));
        }
    }

    // ── Ranges and order statistics ──────────────────────────────────────────────────

    @Nested
    @DisplayName("ranges and order statistics")
    class Ranges {

        @Test
        @DisplayName("inverted, single-point and out-of-domain bounds agree across implementations")
        void degenerateBounds() {
            OrderedSet<Integer> os = rb();
            BPlusTreeEngine<Integer> bp = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
            PersistentRankedSet<Integer> pr = PersistentRankedSet.withNaturalOrder();
            for (int i = 1; i <= 10; i++) { os.add(i); bp.add(i); pr.add(i); }
            for (RankedSet<Integer> s : List.<RankedSet<Integer>>of(os, bp, pr)) {
                String at = s.getClass().getSimpleName();
                assertEquals(1, s.countInRange(5, 5),  at + ": a single-point range holds its one key");
                assertEquals(List.of(5), s.rangeQuery(5, 5), at);
                assertEquals(0, s.countInRange(7, 3),  at + ": hi < lo is empty, not negative");
                assertEquals(List.of(), s.rangeQuery(7, 3), at);
                assertEquals(0, s.countInRange(-100, 0), at + ": entirely below the key domain");
                assertEquals(List.of(), s.rangeQuery(-100, 0), at);
                assertEquals(0, s.countInRange(100, 200), at + ": entirely above it");
                assertEquals(10, s.countInRange(Integer.MIN_VALUE, Integer.MAX_VALUE), at);
                assertEquals(0, s.countInRange(3, 2), at + ": adjacent inverted bounds");
                assertEquals(2, s.countInRange(3, 4), at);
            }
        }

        @Test
        @DisplayName("countBetween / rangeSnapshot cover every inclusivity combination on a live key")
        void everyInclusivityCombinationOnAnExistingKey() {
            OrderedSet<Integer> t = rb();
            for (int i = 1; i <= 10; i++) t.add(i);
            assertEquals(3, t.countBetween(3, true, 5, true));
            assertEquals(2, t.countBetween(3, true, 5, false));
            assertEquals(2, t.countBetween(3, false, 5, true));
            assertEquals(1, t.countBetween(3, false, 5, false));
            assertEquals(List.of(3, 4, 5), t.rangeSnapshot(3, true, 5, true));
            assertEquals(List.of(3, 4), t.rangeSnapshot(3, true, 5, false));
            assertEquals(List.of(4, 5), t.rangeSnapshot(3, false, 5, true));
            assertEquals(List.of(4), t.rangeSnapshot(3, false, 5, false));
            // Both bounds on the SAME existing key.
            assertEquals(1, t.countBetween(5, true, 5, true));
            assertEquals(0, t.countBetween(5, true, 5, false));
            assertEquals(0, t.countBetween(5, false, 5, true));
            assertEquals(0, t.countBetween(5, false, 5, false));
            assertEquals(List.of(5), t.rangeSnapshot(5, true, 5, true));
            assertEquals(List.of(), t.rangeSnapshot(5, false, 5, false));
            // Inverted, and null = unbounded by contract.
            assertEquals(0, t.countBetween(7, true, 3, true));
            assertEquals(List.of(), t.rangeSnapshot(7, true, 3, true));
            assertEquals(10, t.countBetween(null, true, null, true));
            assertEquals(t.inOrder(), t.rangeSnapshot(null, true, null, true));
        }

        @Test
        @DisplayName("rank 0, rank n and rank n+1 behave identically on every implementation")
        void rankAndSelectAtTheEnds() {
            for (int n : new int[]{0, 1, 2, 10}) {
                OrderedSet<Integer> os = rb();
                BPlusTreeEngine<Integer> bp = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
                PersistentRankedSet<Integer> pr = PersistentRankedSet.withNaturalOrder();
                for (int i = 1; i <= n; i++) { os.add(i); bp.add(i); pr.add(i); }
                for (RankedSet<Integer> s : List.<RankedSet<Integer>>of(os, bp, pr)) {
                    String at = s.getClass().getSimpleName() + " n=" + n;
                    assertThrows(IndexOutOfBoundsException.class, () -> s.select(0),     at + " select(0)");
                    assertThrows(IndexOutOfBoundsException.class, () -> s.select(n + 1), at + " select(n+1)");
                    assertThrows(IndexOutOfBoundsException.class,
                            () -> s.select(Integer.MIN_VALUE), at + " select(MIN)");
                    assertThrows(IndexOutOfBoundsException.class,
                            () -> s.select(Integer.MAX_VALUE), at + " select(MAX)");
                    if (n > 0) {
                        assertEquals(1, s.select(1), at);
                        assertEquals(n, s.select(n), at);
                        assertNull(s.successor(n),   at + ": nothing follows the maximum");
                        assertNull(s.predecessor(1), at + ": nothing precedes the minimum");
                    }
                    assertThrows(NoSuchElementException.class, () -> s.rank(n + 1), at + " rank(absent)");
                }
            }
        }

        @Test
        @DisplayName("percentile 0, 100 and out of range clamp identically on all three engines")
        void percentileDomain() {
            // Pinned, not changed: the rank is clamped to [1, n] on every implementation, so an
            // out-of-range percentile saturates instead of throwing. VERIFIED voting compares
            // thrown-exception classes, so one engine throwing here would quarantine it.
            for (int n : new int[]{0, 1, 2, 5, 10}) {
                OrderedSet<Integer> os = rb();
                BPlusTreeEngine<Integer> bp = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
                PersistentRankedSet<Integer> pr = PersistentRankedSet.withNaturalOrder();
                for (int i = 1; i <= n; i++) { os.add(i); bp.add(i); pr.add(i); }
                for (RankedSet<Integer> s : List.<RankedSet<Integer>>of(os, bp, pr)) {
                    String at = s.getClass().getSimpleName() + " n=" + n;
                    for (int pct : new int[]{Integer.MIN_VALUE, -1000, -1, 0, 100, 101, 1000,
                                             Integer.MAX_VALUE}) {
                        Integer got = s.percentile(pct);
                        if (n == 0) {
                            assertNull(got, at + " pct=" + pct + ": empty is null, never an exception");
                        } else if (pct <= 0) {
                            assertEquals(1, got, at + " pct=" + pct + ": clamps to the minimum");
                        } else if (pct >= 100) {
                            assertEquals(n, got, at + " pct=" + pct + ": clamps to the maximum");
                        }
                    }
                    if (n > 0) {
                        assertEquals(s.median(), s.percentile(50), at + ": percentile(50) is the median");
                    }
                }
            }
        }

        @Test
        @DisplayName("FIX E-5: an inverted interval query is refused by BOTH augmentors, alike")
        void invertedIntervalQueryIsRefusedByBothAugmentors() {
            // GenericIntervalAugmentor already refused it (pinned by GenericIntervalAugmentorTest);
            // the int IntervalAugmentor answered with the intervals that STRADDLE the inversion,
            // because the overlap test lo <= qhi && qlo <= hi is satisfied by exactly those. Two
            // implementations of one operation, one of them right.
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.setAugmentor(IntervalAugmentor.INSTANCE);
            IntervalAugmentor.insertInterval(ctx, 5, 5);
            IntervalAugmentor.insertInterval(ctx, Integer.MIN_VALUE, Integer.MAX_VALUE);
            assertThrows(IllegalArgumentException.class,
                    () -> IntervalAugmentor.intervalSearchAll(ctx, 9, 3));
            assertThrows(IllegalArgumentException.class,
                    () -> IntervalAugmentor.intervalSearch(ctx, 9, 3));
            assertThrows(IllegalArgumentException.class,
                    () -> IntervalAugmentor.insertInterval(ctx, 9, 3),
                    "the stored side already refused it");

            OrderedSet<Integer> gset = rb();
            GenericIntervalAugmentor<Integer> giv =
                    GenericIntervalAugmentor.over(Comparator.<Integer>naturalOrder());
            gset.setAugmentor(giv);
            giv.insertInterval(gset, 5, 5);
            giv.insertInterval(gset, Integer.MIN_VALUE, Integer.MAX_VALUE);
            assertThrows(IllegalArgumentException.class, () -> giv.intervalSearchAll(gset, 9, 3));
            assertThrows(IllegalArgumentException.class, () -> giv.intervalSearch(gset, 9, 3));

            // Well-formed degenerate queries still work on both, including the domain extremes.
            assertEquals(2, IntervalAugmentor.stabQuery(ctx, 5).size(), "a point query is qlo == qhi");
            assertEquals(1, IntervalAugmentor.stabQuery(ctx, Integer.MIN_VALUE).size());
            assertEquals(1, IntervalAugmentor.stabQuery(ctx, Integer.MAX_VALUE).size());
            assertEquals(1, IntervalAugmentor.intervalSearchAll(ctx, 0, 0).size());
            assertEquals(2, giv.stabQuery(gset, 5).size());
            assertEquals(1, giv.stabQuery(gset, Integer.MAX_VALUE).size());

            // An empty interval tree answers every well-formed query with nothing.
            TreeContext none = new TreeContext(new RedBlackStrategy<>());
            none.setAugmentor(IntervalAugmentor.INSTANCE);
            assertEquals(List.of(), IntervalAugmentor.stabQuery(none, 1));
            assertEquals(List.of(), IntervalAugmentor.intervalSearchAll(none, 1, 2));
        }

        @Test
        @DisplayName("NavigableOrderedSet views at their degenerate ends")
        void navigableViewEdges() {
            OrderedSet<Integer> base = rb();
            for (int i = 1; i <= 10; i++) base.add(i);
            NavigableOrderedSet<Integer> nav = new NavigableOrderedSet<>(base);
            assertEquals(0, nav.subSet(5, true, 5, false).size(), "a half-open point range is empty");
            assertEquals(List.of(5), new ArrayList<>(nav.subSet(5, true, 5, true)));
            assertThrows(IllegalArgumentException.class, () -> nav.subSet(7, true, 3, true),
                    "inverted bounds are refused, as NavigableSet requires");
            assertTrue(nav.headSet(1, false).isEmpty());
            assertTrue(nav.tailSet(10, false).isEmpty());
            assertTrue(nav.subSet(-5, true, -1, true).isEmpty(), "entirely below the key domain");
            assertTrue(nav.subSet(100, true, 200, true).isEmpty(), "entirely above it");

            NavigableOrderedSet<Integer> empty = new NavigableOrderedSet<>(rb());
            assertThrows(NoSuchElementException.class, empty::first);
            assertThrows(NoSuchElementException.class, empty::last);
            assertNull(empty.pollFirst());
            assertNull(empty.pollLast());
            assertNull(empty.floor(1));
            assertNull(empty.ceiling(1));
            assertNull(empty.lower(1));
            assertNull(empty.higher(1));
            assertEquals(0, empty.descendingSet().size());
            assertTrue(empty.subSet(1, true, 2, true).isEmpty());
        }
    }

    // ── Windows and bounds ───────────────────────────────────────────────────────────

    @Nested
    @DisplayName("sliding window bounds")
    class Window {

        @Test
        @DisplayName("maxSize of 0, 1, exactly n, below n, above n")
        void maxSizeAtEveryRelationToTheCurrentSize() {
            for (int bound : new int[]{0, 1, 3, 5, 10}) {
                OrderedSet<Integer> t = rb();
                for (int i = 1; i <= 5; i++) t.add(i);
                t.setMaxSize(bound);
                int expected = bound == 0 ? 5 : Math.min(5, bound);
                assertEquals(expected, t.size(), "bound=" + bound);
                assertEquals(bound, t.getMaxSize(), "bound=" + bound);
                if (bound > 0 && bound < 5) {
                    // FIFO survivors after a bound that bites are the newest `bound` keys.
                    List<Integer> expectedKeys = new ArrayList<>();
                    for (int i = 5 - bound + 1; i <= 5; i++) expectedKeys.add(i);
                    assertEquals(expectedKeys, t.inOrder(), "bound=" + bound);
                }
            }
        }

        @Test
        @DisplayName("a negative maxSize is normalised to unbounded, not to an empty set")
        void negativeMaxSizeIsUnbounded() {
            OrderedSet<Integer> t = rb();
            for (int i = 1; i <= 5; i++) t.add(i);
            t.setMaxSize(-1);
            assertEquals(0, t.getMaxSize());
            assertEquals(5, t.size(), "a negative bound must not empty the set");
            t.setMaxSize(Integer.MIN_VALUE);
            assertEquals(0, t.getMaxSize());
            assertEquals(5, t.size());
        }

        @Test
        @DisplayName("maxSize of 1 keeps exactly the newest key across a long insert run")
        void maxSizeOfOne() {
            OrderedSet<Integer> t = rb();
            t.setMaxSize(1);
            for (int i = 1; i <= 50; i++) {
                t.add(i);
                assertEquals(1, t.size(), "after add " + i);
                assertEquals(List.of(i), t.inOrder(), "after add " + i);
            }
        }

        @Test
        @DisplayName("setting maxSize twice tightens then relaxes without resurrecting evicted keys")
        void maxSizeSetTwice() {
            OrderedSet<Integer> t = rb();
            for (int i = 1; i <= 8; i++) t.add(i);
            t.setMaxSize(4);
            assertEquals(List.of(5, 6, 7, 8), t.inOrder());
            t.setMaxSize(2);
            assertEquals(List.of(7, 8), t.inOrder());
            t.setMaxSize(9);
            assertEquals(List.of(7, 8), t.inOrder(), "relaxing a bound does not bring keys back");
            assertEquals(9, t.getMaxSize());
            t.add(100);
            assertEquals(List.of(7, 8, 100), t.inOrder());
        }

        @Test
        @DisplayName("bulk build under an active window evicts down to the bound (finding 20's rule)")
        void buildFromSortedRespectsTheWindow() {
            OrderedSet<Integer> t = rb();
            t.setMaxSize(3);
            t.buildFromSorted(List.of(1, 2, 3, 4, 5, 6, 7));
            assertEquals(3, t.size());
            assertEquals(List.of(5, 6, 7), t.inOrder(), "the survivors are the newest maxSize keys");
            t.add(8);
            assertEquals(List.of(6, 7, 8), t.inOrder(), "the next add evicts exactly one");
        }

        @Test
        @DisplayName("an ensemble window bounds every member identically, and 0/1 behave as on one set")
        void ensembleWindowBounds() {
            try (EnsembleOrderedSet<Integer> e = mirror()) {
                e.setMaxSize(0);
                for (int i = 1; i <= 5; i++) e.add(i);
                assertEquals(5, e.size(), "0 is unbounded");
                e.setMaxSize(1);
                assertEquals(1, e.size());
                assertEquals(List.of(5), e.inOrder());
                for (EnsembleMember<Integer> m : e.members()) {
                    assertEquals(List.of(5), m.set().inOrder(), m.strategyName() + " must agree");
                }
                e.setMaxSize(-3);
                assertEquals(0, e.getMaxSize(), "a negative bound normalises to unbounded");
                assertEquals(1, e.size());
            }
        }

        @Test
        @DisplayName("an ensemble bulk build under a window bounds every member identically")
        void ensembleBulkBuildUnderAWindow() {
            try (EnsembleOrderedSet<Integer> e = mirror()) {
                e.setMaxSize(3);
                e.buildAllFromSorted(List.of(1, 2, 3, 4, 5, 6, 7));
                assertEquals(3, e.size());
                for (EnsembleMember<Integer> m : e.members()) {
                    assertEquals(List.of(5, 6, 7), m.set().inOrder(), m.strategyName());
                }
            }
        }

        @Test
        @DisplayName("setting maxSize during an iteration does not disturb the iteration in flight")
        void maxSizeSetDuringIteration() {
            // The adapter's iterators are snapshots by construction, so a window that bites
            // mid-iteration must not make the iterator throw or skip: it walks the set as it was
            // when iteration began, and the set afterwards is bounded.
            OrderedSet<Integer> base = rb();
            for (int i = 1; i <= 10; i++) base.add(i);
            NavigableOrderedSet<Integer> nav = new NavigableOrderedSet<>(base);
            List<Integer> walked = new ArrayList<>();
            java.util.Iterator<Integer> it = nav.iterator();
            while (it.hasNext()) {
                walked.add(it.next());
                if (walked.size() == 3) base.setMaxSize(4);   // bites right now
            }
            assertEquals(10, walked.size(), "the in-flight iteration is a snapshot and completes");
            assertEquals(4, base.size(), "and the bound took effect");
            assertEquals(List.of(7, 8, 9, 10), base.inOrder());
            assertEquals(List.of(7, 8, 9, 10), new ArrayList<>(nav));
        }

        @Test
        @DisplayName("a windowed ensemble refuses the bound when any member is engine-tier")
        void engineTierMembersRefuseAWindow() {
            try (EnsembleOrderedSet<Integer> e = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new)
                    .engineMember(() -> BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT), "BPLUS")
                    .build()) {
                assertFalse(e.supportsWindow());
                IllegalStateException boom = assertThrows(IllegalStateException.class, () -> e.setMaxSize(3));
                assertTrue(boom.getMessage().contains("strategy-backed"),
                        "the refusal names why: " + boom.getMessage());
            }
        }
    }

    // ── Lifecycle: close, clear, quarantine, reentrancy ──────────────────────────────

    @Nested
    @DisplayName("lifecycle")
    class Lifecycle {

        @Test
        @DisplayName("an ensemble read still works after close(); every write is refused")
        void readsSurviveCloseAndWritesDoNot() {
            EnsembleOrderedSet<Integer> e = mirror();
            for (int i = 1; i <= 5; i++) e.add(i);
            e.close();
            assertTrue(e.isClosed());
            e.close();                                       // idempotent
            assertEquals(5, e.size(), "a closed ensemble is a frozen snapshot, not a corpse");
            assertTrue(e.contains(3));
            assertEquals(List.of(1, 2, 3, 4, 5), e.inOrder());
            assertEquals(1, e.minimum());
            assertThrows(IllegalStateException.class, () -> e.add(99));
            assertThrows(IllegalStateException.class, () -> e.remove(1));
            assertThrows(IllegalStateException.class, e::clear);
            assertThrows(IllegalStateException.class, () -> e.setMaxSize(4));
            assertThrows(IllegalStateException.class, () -> e.buildAllFromSorted(List.of(1, 2)));
            assertEquals(5, e.size(), "and none of the refusals moved the set");
        }

        @Test
        @DisplayName("operations on an emptied set are the same as on a never-used one")
        void clearedSetBehavesLikeANewOne() {
            OrderedSet<Integer> t = rb();
            for (int i = 1; i <= 100; i++) t.add(i);
            t.clear();
            assertEquals(0, t.size());
            assertTrue(t.isEmpty());
            assertNull(t.minimum());
            assertNull(t.maximum());
            assertNull(t.median());
            assertNull(t.percentile(50));
            assertNull(t.floor(50));
            assertNull(t.ceiling(50));
            assertFalse(t.contains(50));
            assertEquals(List.of(), t.inOrder());
            assertEquals(0, t.countInRange(Integer.MIN_VALUE, Integer.MAX_VALUE));
            assertThrows(IndexOutOfBoundsException.class, () -> t.select(1));
            assertThrows(NoSuchElementException.class, () -> t.rank(1));
            assertTrue(t.add(7), "and it is writable again");
            assertEquals(List.of(7), t.inOrder());
        }

        @Test
        @DisplayName("a quarantined member is not fanned to, and cannot be promoted")
        void quarantinedMemberStaysOutOfService() {
            FaultingStrategy<Integer> faulty = new FaultingStrategy<>();
            try (EnsembleOrderedSet<Integer> e = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new)
                    .member(AVLStrategy::new)
                    .member(() -> faulty)
                    .build()) {
                for (int i = 1; i <= 10; i++) e.add(i);
                EnsembleMember<Integer> victim = e.members().get(2);
                faulty.failing = true;
                assertTrue(e.add(11), "the write commits to the survivors");
                faulty.failing = false;
                assertEquals(EnsembleMember.State.QUARANTINED, victim.state());
                int sizeWhenQuarantined = victim.set().size();
                assertTrue(e.add(12));
                assertEquals(sizeWhenQuarantined, victim.set().size(),
                        "a quarantined member receives no further writes");
                assertThrows(IllegalStateException.class, () -> e.promote(victim),
                        "and cannot be promoted");
            }
        }

        @Test
        @DisplayName("a retired member is never served, fanned to, or promoted")
        void retiredMemberIsOutOfServiceForGood() {
            try (EnsembleOrderedSet<Integer> e = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new)
                    .member(AVLStrategy::new)
                    .member(SplayStrategy::new)
                    .build()) {
                for (int i = 1; i <= 10; i++) e.add(i);
                EnsembleMember<Integer> victim = e.members().get(2);
                assertTrue(e.retire(victim));
                assertEquals(EnsembleMember.State.RETIRED, victim.state());
                int frozen = victim.set().size();
                assertTrue(e.add(11), "the write still commits to the living members");
                assertEquals(frozen, victim.set().size(), "a retired member is not fanned to");
                assertThrows(IllegalStateException.class, () -> e.promote(victim),
                        "and is never promoted");
                assertFalse(e.healFromPrimary(victim), "healing a retired member is refused, not silently done");
                assertEquals(EnsembleMember.State.RETIRED, victim.state());
                assertThrows(IllegalStateException.class, () -> e.retire(e.primary()),
                        "the serving primary cannot be retired out from under the reads");
            }
        }

        @Test
        @DisplayName("constructing with a null strategy, comparator or delegate is refused up front")
        void constructionArgumentsAreValidated() {
            assertThrows(IllegalArgumentException.class,
                    () -> new OrderedSet<Integer>(null, Comparator.<Integer>naturalOrder()));
            assertThrows(IllegalArgumentException.class,
                    () -> new OrderedSet<Integer>(new RedBlackStrategy<>(), null));
            assertThrows(IllegalArgumentException.class,
                    () -> new BPlusTreeEngine<Integer>(BPlusTreeEngine.MIN_FANOUT, null));
            assertThrows(NullPointerException.class, () -> new NavigableOrderedSet<Integer>(null));
            assertThrows(IllegalArgumentException.class, () -> EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new)
                    .build(), "one member is not an ensemble");
            assertThrows(IllegalArgumentException.class, () -> EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder()).build(),
                    "nor is none");
            assertThrows(IllegalArgumentException.class, () -> EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new)
                    .member(AVLStrategy::new)
                    .mode(EnsembleMode.VERIFIED)
                    .build(), "two members cannot form a majority");
        }

        @Test
        @DisplayName("FIX E-3: a listener that mutates its own set is refused, not deadlocked")
        void reentrantListenerIsRefused() {
            // Before this fix the mutating thread parked forever on the (non-reentrant) StampedLock
            // held for the callback: no exception, no stack overflow, no progress. assertTimeout*
            // is what turns a regression back into a failure instead of a hung suite.
            assertTimeoutPreemptively(java.time.Duration.ofSeconds(10), () -> {
                OrderedSet<Integer> t = rb();
                final RuntimeException[] seen = {null};
                t.setEventListener(e -> {
                    try {
                        if (e instanceof TreeEvent.Insert<Integer> ins) t.add(ins.key() + 1000);
                    } catch (RuntimeException caught) {
                        seen[0] = caught;
                    }
                });
                assertTrue(t.add(1), "the outer write still commits");
                assertNotNull(seen[0], "the reentrant add must have been refused");
                assertTrue(seen[0] instanceof IllegalStateException, "with IllegalStateException");
                assertTrue(seen[0].getMessage().contains("must not call back"),
                        "naming the cause: " + seen[0].getMessage());
                assertEquals(List.of(1), t.inOrder(), "and the set holds only the real write");

                // Every mutator, not just add — the listener sees eviction and morph events too.
                for (Runnable reentrant : List.<Runnable>of(
                        () -> t.remove(1), t::clear, () -> t.setMaxSize(2),
                        () -> t.setStrategy(new AVLStrategy<>()), t::selfRepair,
                        () -> t.buildFromSorted(List.of(9)), t::resyncFromEngine)) {
                    seen[0] = null;
                    t.setEventListener(e -> {
                        try { reentrant.run(); } catch (RuntimeException caught) { seen[0] = caught; }
                    });
                    t.add(500 + t.size());
                    assertTrue(seen[0] instanceof IllegalStateException,
                            "a reentrant mutator must be refused, got " + seen[0]);
                }
                t.setEventListener(null);
            });
        }

        @Test
        @DisplayName("a listener that only throws still cannot break the write (M-1 regression guard)")
        void throwingListenerIsStillSwallowed() {
            OrderedSet<Integer> t = rb();
            t.setEventListener(e -> { throw new RuntimeException("listener bomb"); });
            assertTrue(t.add(1));
            assertTrue(t.remove(1));
            assertEquals(0, t.size());
            t.setEventListener(null);
            assertTrue(t.add(2), "and the set is not poisoned afterwards");
        }

        @Test
        @DisplayName("a listener reading the set it observes is still allowed")
        void readOnlyListenerIsUnaffected() {
            OrderedSet<Integer> t = rb();
            final int[] sizeSeen = {-1};
            t.setEventListener(e -> sizeSeen[0] = t.size());
            t.add(1);
            assertEquals(1, sizeSeen[0], "reads from a listener are not the reentrancy this refuses");
            t.setEventListener(null);
        }
    }

    // ── Ensemble null semantics ──────────────────────────────────────────────────────

    @Nested
    @DisplayName("FIX E-2 — an ensemble write with a null key")
    class EnsembleNullWrite {

        @Test
        @DisplayName("add(null) / remove(null) throw NPE and quarantine nobody, in every mode")
        void nullWriteNeverQuarantinesAMember() {
            for (EnsembleMode mode : EnsembleMode.values()) {
                try (EnsembleOrderedSet<Integer> e = EnsembleOrderedSet
                        .<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(RedBlackStrategy::new)
                        .member(AVLStrategy::new)
                        .member(SplayStrategy::new)
                        .mode(mode)
                        .build()) {
                    for (int i = 1; i <= 20; i++) e.add(i);
                    assertThrows(NullPointerException.class, () -> e.add(null),
                            mode + ": a caller argument is not a member failure");
                    assertThrows(NullPointerException.class, () -> e.remove(null), mode.toString());
                    for (EnsembleMember<Integer> m : e.members()) {
                        assertEquals(EnsembleMember.State.ACTIVE, m.state(),
                                mode + ": " + m.strategyName() + " must still be ACTIVE");
                    }
                    assertEquals(20, e.size(), mode + ": the refused write changed nothing");
                    assertTrue(e.add(21), mode + ": and the ensemble is still writable");
                    assertTrue(e.contains(21), mode.toString());
                }
            }
        }

        @Test
        @DisplayName("buildAllFromSorted refuses a null key without touching any member")
        void nullBulkBuildIsRefused() {
            try (EnsembleOrderedSet<Integer> e = mirror()) {
                assertThrows(NullPointerException.class,
                        () -> e.buildAllFromSorted(Collections.singletonList(null)));
                assertThrows(NullPointerException.class,
                        () -> e.buildAllFromSorted(Arrays.asList(1, null, 3)));
                assertThrows(NullPointerException.class, () -> e.buildAllFromSorted(null));
                assertEquals(0, e.size(), "every refusal left the ensemble empty");
                for (EnsembleMember<Integer> m : e.members()) {
                    assertEquals(0, m.set().size(), m.strategyName());
                    assertEquals(EnsembleMember.State.ACTIVE, m.state(), m.strategyName());
                }
                e.buildAllFromSorted(List.of(1, 2, 3));
                assertEquals(3, e.size(), "and a valid build still works");
            }
        }

        @Test
        @DisplayName("null reads throw NPE too, so a VERIFIED vote stays unanimous")
        void nullReadsAreNpeOnTheFacade() {
            try (EnsembleOrderedSet<Integer> e = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new)
                    .member(AVLStrategy::new)
                    .member(SplayStrategy::new)
                    .mode(EnsembleMode.VERIFIED)
                    .build()) {
                for (int i = 1; i <= 10; i++) e.add(i);
                assertThrows(NullPointerException.class, () -> e.contains(null));
                assertThrows(NullPointerException.class, () -> e.rank(null));
                for (EnsembleMember<Integer> m : e.members()) {
                    assertEquals(EnsembleMember.State.ACTIVE, m.state(), m.strategyName());
                }
            }
        }
    }

    // ── Persistence ──────────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("persistence at the degenerate ends")
    class Persistence {

        private final FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        private final List<String> created = new ArrayList<>();

        private String snap(String base) {
            String name = "test-edge-" + base + "-" + System.nanoTime();
            created.add(name);
            return name;
        }

        @AfterEach
        void cleanup() throws Exception {
            for (String name : created) {
                adapter.deleteSnapshot(name);
                Path p = Path.of("snapshots", name + ".rbt");
                if (Files.isDirectory(p)) Files.delete(p);
            }
        }

        @Test
        @DisplayName("an empty set round-trips through all three snapshot formats")
        void emptySetRoundTrips() {
            String intName = snap("empty-int");
            adapter.saveSnapshot(intName, new TreeContext(new RedBlackStrategy<>()));
            TreeContext back = adapter.loadSnapshot(intName);
            assertNotNull(back, "an empty snapshot is a valid snapshot, not a malformed one");
            assertEquals(0, back.getSize());

            String genName = snap("empty-gen");
            adapter.saveSnapshot(genName, rb(), KeySerializer.INTEGER);
            OrderedSet<Integer> gen = adapter.loadOrderedSet(genName, KeySerializer.INTEGER);
            assertNotNull(gen);
            assertEquals(0, gen.size());

            String flatName = snap("empty-flat");
            adapter.saveSnapshot(flatName,
                    new PersistentTreeEngine<Integer>(Comparator.<Integer>naturalOrder()).snapshot(),
                    KeySerializer.INTEGER);
            PersistentTreeEngine<Integer> flat = adapter.loadPersistent(flatName, KeySerializer.INTEGER);
            assertNotNull(flat);
            assertEquals(0, flat.size());
        }

        @Test
        @DisplayName("a one-key set round-trips through all three formats")
        void oneKeyRoundTrips() {
            OrderedSet<Integer> one = rb();
            one.add(7);
            String genName = snap("one-gen");
            adapter.saveSnapshot(genName, one, KeySerializer.INTEGER);
            assertEquals(List.of(7), adapter.loadOrderedSet(genName, KeySerializer.INTEGER).inOrder());

            PersistentRankedSet<Integer> pr = PersistentRankedSet.withNaturalOrder();
            pr.add(7);
            String flatName = snap("one-flat");
            adapter.saveSnapshot(flatName, pr.engine().snapshot(), KeySerializer.INTEGER);
            assertEquals(List.of(7),
                    adapter.loadPersistent(flatName, KeySerializer.INTEGER).inOrder());
        }

        @Test
        @DisplayName("a zero-byte file, a header-only file and a directory are each reported distinctly")
        void degenerateFilesAreReported() throws Exception {
            String zero = snap("zero");
            Files.writeString(Path.of("snapshots", zero + ".rbt"), "");
            assertEquals(LoadStatus.MALFORMED, adapter.tryLoadSnapshot(zero).status());
            assertEquals(LoadStatus.MALFORMED,
                    adapter.tryLoadOrderedSet(zero, KeySerializer.INTEGER).status());
            assertEquals(LoadStatus.MALFORMED,
                    adapter.tryLoadPersistent(zero, KeySerializer.INTEGER).status());

            String hdr = snap("hdr");
            Files.writeString(Path.of("snapshots", hdr + ".rbt"),
                    "CSRBT-1.0|2026-08-17T00:00:00Z|RedBlackStrategy|0|DEFAULT\n");
            assertEquals(LoadStatus.MALFORMED, adapter.tryLoadSnapshot(hdr).status());
            assertTrue(adapter.tryLoadSnapshot(hdr).detail().contains("no node data line"));

            String dir = snap("isdir");
            Files.createDirectories(Path.of("snapshots", dir + ".rbt"));
            assertEquals(LoadStatus.FAILED, adapter.tryLoadSnapshot(dir).status(),
                    "a directory on the path is an environment failure, not a malformed file");
            assertEquals(SaveStatus.FAILED, adapter.trySaveSnapshot(dir,
                    new TreeContext(new RedBlackStrategy<>())).status(),
                    "and saving onto it is a reported failure, not an escaping IOException");

            assertEquals(LoadStatus.ABSENT, adapter.tryLoadSnapshot(snap("nosuch")).status());
        }

        @Test
        @DisplayName("a snapshot loads with, without, and with extra trailing newlines")
        void trailingNewlineVariants() throws Exception {
            OrderedSet<Integer> src = rb();
            for (int i = 1; i <= 20; i++) src.add(i);
            String base = snap("nl-base");
            adapter.saveSnapshot(base, src, KeySerializer.INTEGER);
            String bytes = Files.readString(Path.of("snapshots", base + ".rbt"));

            for (String variant : List.of(bytes.stripTrailing(), bytes, bytes + "\n\n")) {
                String name = snap("nl");
                Files.writeString(Path.of("snapshots", name + ".rbt"), variant);
                OrderedSet<Integer> back = adapter.loadOrderedSet(name, KeySerializer.INTEGER);
                assertNotNull(back, "trailing newlines must not decide whether a file is readable");
                assertEquals(src.inOrder(), back.inOrder());
            }
        }

        @Test
        @DisplayName("keys containing the separators and the escape character round-trip")
        void hostileStringKeysRoundTrip() {
            List<String> hostile = List.of(";", ",", "#", "%", "|", "%3B", "%25", "%2C", "a;b",
                    "a,b", "\n", "\t", "\r", " ", "##", "\\", "\"", "a\rb", "é");
            OrderedSet<String> src = new OrderedSet<>(new RedBlackStrategy<>(),
                    Comparator.<String>naturalOrder());
            for (String k : hostile) src.add(k);
            String name = snap("hostile");
            adapter.saveSnapshot(name, src, KeySerializer.string());
            OrderedSet<String> back = adapter.loadOrderedSet(name, KeySerializer.string(),
                    Comparator.<String>naturalOrder());
            assertNotNull(back, "the string serializer escapes every reserved character");
            assertEquals(src.inOrder(), back.inOrder());

            PersistentRankedSet<String> flat = new PersistentRankedSet<>(Comparator.<String>naturalOrder());
            for (String k : hostile) flat.add(k);
            String flatName = snap("hostile-flat");
            adapter.saveSnapshot(flatName, flat.engine().snapshot(), KeySerializer.string());
            assertEquals(src.inOrder(),
                    adapter.loadPersistent(flatName, KeySerializer.string(),
                            Comparator.<String>naturalOrder()).inOrder());
        }

        @Test
        @DisplayName("an empty-string key is refused loudly rather than written as a NIL marker")
        void emptyStringKeyIsRefused() {
            OrderedSet<String> src = new OrderedSet<>(new RedBlackStrategy<>(),
                    Comparator.<String>naturalOrder());
            src.add("");
            String name = snap("empty-key");
            assertThrows(IllegalArgumentException.class,
                    () -> adapter.saveSnapshot(name, src, KeySerializer.string()));
        }

        @Test
        @DisplayName("FIX E-4: a serializer emitting a reserved character fails at save, both paths")
        void serializerViolatingTheTokenContractFailsAtSave() {
            for (String suffix : List.of(";x", ",x", "\nx")) {
                KeySerializer<Integer> leaky = new KeySerializer<>() {
                    @Override public String serialize(Integer k) { return k + suffix; }
                    @Override public Integer deserialize(String t) { return Integer.valueOf(t.trim()); }
                };
                OrderedSet<Integer> src = rb();
                for (int i = 1; i <= 5; i++) src.add(i);
                IllegalArgumentException boom = assertThrows(IllegalArgumentException.class,
                        () -> adapter.saveSnapshot(snap("leaky"), src, leaky),
                        "pre-order path, suffix " + suffix.trim());
                assertTrue(boom.getMessage().contains("cannot be persisted"),
                        "the message names the cause: " + boom.getMessage());
            }
            // The flat path already refused ';' — same rule, same moment, still true.
            KeySerializer<Integer> semi = new KeySerializer<>() {
                @Override public String serialize(Integer k) { return k + ";x"; }
                @Override public Integer deserialize(String t) { return Integer.valueOf(t.trim()); }
            };
            PersistentRankedSet<Integer> pr = PersistentRankedSet.withNaturalOrder();
            pr.add(1);
            assertThrows(IllegalArgumentException.class,
                    () -> adapter.saveSnapshot(snap("leaky-flat"), pr.engine().snapshot(), semi));
        }

        @Test
        @DisplayName("a snapshot name too long for the filesystem is a reported failure, not a crash")
        void oversizedSnapshotNameIsReported() {
            // Which length the filesystem refuses is not ours to assert; that the adapter answers
            // with a value instead of letting an IOException escape is (ADR-025).
            for (int len : new int[]{200, 250, 300, 1000}) {
                String name = "x".repeat(len);
                created.add(name);
                SaveResult r = adapter.trySaveSnapshot(name, new TreeContext(new RedBlackStrategy<>()));
                assertNotNull(r, "len=" + len);
                if (r.status() == SaveStatus.FAILED) {
                    assertNotNull(r.cause(), "len=" + len + ": a FAILED save carries its IOException");
                    assertNull(adapter.loadSnapshot(name),
                            "len=" + len + ": nothing was published");
                } else {
                    assertEquals(SaveStatus.SAVED, r.status(), "len=" + len);
                    assertNotNull(adapter.loadSnapshot(name), "len=" + len + ": and it loads back");
                }
            }
        }

        @Test
        @DisplayName("an illegal snapshot name is refused before any I/O")
        void illegalSnapshotNames() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (String bad : List.of("", "a/b", "a\\b", "..", "../x")) {
                assertThrows(IllegalArgumentException.class, () -> adapter.saveSnapshot(bad, ctx),
                        "name '" + bad + "'");
            }
            assertThrows(IllegalArgumentException.class, () -> adapter.saveSnapshot(null, ctx));
        }
    }

    /** A Red-Black strategy with an injectable write fault, for the quarantine path. */
    static final class FaultingStrategy<K> implements io.github.richeyworks.csrbt.strategy.TreeStrategy<K> {
        private final TreeStrategy<K> inner = new RedBlackStrategy<>();
        volatile boolean failing = false;

        private void maybeFail() {
            if (failing) throw new IllegalStateException("injected write fault");
        }

        @Override public void insert(io.github.richeyworks.csrbt.MutableTree<K> t,
                                     io.github.richeyworks.csrbt.TreeNode1<K> n) { maybeFail(); inner.insert(t, n); }
        @Override public void fixInsert(io.github.richeyworks.csrbt.MutableTree<K> t,
                                        io.github.richeyworks.csrbt.TreeNode1<K> n) { inner.fixInsert(t, n); }
        @Override public void delete(io.github.richeyworks.csrbt.MutableTree<K> t,
                                     io.github.richeyworks.csrbt.TreeNode1<K> n) { maybeFail(); inner.delete(t, n); }
        @Override public io.github.richeyworks.csrbt.TreeNode1<K> search(
                io.github.richeyworks.csrbt.MutableTree<K> t, K v) { return inner.search(t, v); }
    }

    private static EnsembleOrderedSet<Integer> mirror() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(RedBlackStrategy::new)
                .member(AVLStrategy::new)
                .build();
    }
}
