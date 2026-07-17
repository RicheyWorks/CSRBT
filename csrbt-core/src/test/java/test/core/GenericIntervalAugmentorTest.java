package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.augment.GenericIntervalAugmentor;
import io.github.richeyworks.csrbt.augment.GenericIntervalAugmentor.Interval;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.TreeMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Outer-ring ADR Phase 7 — generic (typed) interval endpoints. Oracle-driven, house style:
 * every query answer is checked against a brute-force scan of a reference map, on deterministic
 * seeds. The endpoints are {@code long}s well past {@code Integer.MAX_VALUE} (epoch-millis
 * scale) — the exact values the int-bound {@link io.github.richeyworks.csrbt.augment.IntervalAugmentor}
 * cannot hold — plus a {@code String} tree to prove the comparator, not the type, is the
 * authority. Also pins the seams the additive {@code augmentedRef} slot must not disturb:
 * intrinsic size/order statistics, tags, morph/self-repair carry, and deepCopy alias safety.
 */
@DisplayName("Generic interval endpoints on the augmentedRef slot (outer-ring Phase 7)")
public class GenericIntervalAugmentorTest {

    /** Epoch-millis scale: far outside int range, so any int truncation would show. */
    private static final long SCALE = 1_000_000_000L;

    private static OrderedSet<Long> longSet() {
        return OrderedSet.withNaturalOrder(new RedBlackStrategy<Long>());
    }

    /** Brute-force oracle over the reference map: all [lo, hi] overlapping [qlo, qhi], sorted. */
    private static List<String> oracleOverlaps(Map<Long, Long> loToHi, long qlo, long qhi) {
        TreeMap<Long, Long> sorted = new TreeMap<>(loToHi);
        List<String> out = new ArrayList<>();
        for (Map.Entry<Long, Long> e : sorted.entrySet()) {
            if (e.getKey() <= qhi && qlo <= e.getValue()) {
                out.add(e.getKey() + "/" + e.getValue());
            }
        }
        return out;
    }

    private static List<String> canonical(List<Interval<Long>> hits) {
        return hits.stream().map(i -> i.lo() + "/" + i.hi()).sorted(
                java.util.Comparator.comparingLong((String s) -> Long.parseLong(s.split("/")[0]))
                        .thenComparingLong(s -> Long.parseLong(s.split("/")[1]))).toList();
    }

    @Test
    @DisplayName("CLRS 14.3 worked shape at epoch-millis scale: hit and proven miss")
    void clrsWorkedExampleAtLongScale() {
        OrderedSet<Long> set = longSet();
        GenericIntervalAugmentor<Long> iv = GenericIntervalAugmentor.natural();
        long[][] intervals = {{16, 21}, {8, 9}, {25, 30}, {5, 8}, {15, 23}, {17, 19}, {26, 26}, {0, 3}, {6, 10}, {19, 20}};
        for (long[] i : intervals) {
            iv.insertInterval(set, i[0] * SCALE, i[1] * SCALE);
        }

        // CLRS's own queries, scaled: [22,25] overlaps something; [11,14] falls in the gap.
        Interval<Long> hit = iv.intervalSearch(set, 22 * SCALE, 25 * SCALE);
        assertNotNull(hit, "CLRS guarantees an overlap is found when one exists");
        assertTrue(hit.lo() <= 25 * SCALE && 22 * SCALE <= hit.hi(), "returned interval must overlap the query");
        assertTrue(hit.hi() > Integer.MAX_VALUE, "endpoints genuinely exceed int range");

        assertNull(iv.intervalSearch(set, 11 * SCALE, 14 * SCALE),
                "CLRS theorem: null return proves NO interval overlaps [11,14]");
        assertEquals(intervals.length, set.size(), "distinct los -> one node each");
    }

    @Test
    @DisplayName("seeded random oracle: searchAll/stab/search agree with brute force on long endpoints")
    void randomOracleLongEndpoints() {
        OrderedSet<Long> set = longSet();
        GenericIntervalAugmentor<Long> iv = GenericIntervalAugmentor.natural();
        Map<Long, Long> oracle = new LinkedHashMap<>();   // lo -> hi, last stamp wins
        Random rng = new Random(42);

        for (int i = 0; i < 300; i++) {
            long lo = Math.floorMod(rng.nextLong(), 1_000_000_000_000L);
            if (i % 10 == 9) {
                set.add(lo);                               // raw add: degenerate point [lo, lo]
                oracle.putIfAbsent(lo, lo);
            } else {
                long hi = lo + Math.floorMod(rng.nextLong(), 1_000_000_000L);
                iv.insertInterval(set, lo, hi);
                oracle.put(lo, hi);                        // add-or-restamp, like the int version
            }
        }
        assertEquals(oracle.size(), set.size(), "one node per distinct lo");

        for (int q = 0; q < 200; q++) {
            long qlo = Math.floorMod(rng.nextLong(), 1_100_000_000_000L);
            long qhi = qlo + Math.floorMod(rng.nextLong(), 5_000_000_000L);

            List<String> expected = oracleOverlaps(oracle, qlo, qhi);
            assertEquals(expected, canonical(iv.intervalSearchAll(set, qlo, qhi)),
                    "searchAll must equal brute force for query [" + qlo + ", " + qhi + "]");

            Interval<Long> one = iv.intervalSearch(set, qlo, qhi);
            if (expected.isEmpty()) {
                assertNull(one, "search must return null exactly when the oracle is empty");
            } else {
                assertNotNull(one);
                assertTrue(expected.contains(one.lo() + "/" + one.hi()),
                        "search must return a real, overlapping interval");
            }

            long p = qlo;   // stab at the query's left edge exercises boundary equality
            assertEquals(oracleOverlaps(oracle, p, p), canonical(iv.stabQuery(set, p)));
        }
    }

    @Test
    @DisplayName("String endpoints: the comparator is the ordering authority, not the type")
    void stringEndpointsWithComparator() {
        OrderedSet<String> set = new OrderedSet<>(new RedBlackStrategy<>(), String.CASE_INSENSITIVE_ORDER);
        GenericIntervalAugmentor<String> iv = GenericIntervalAugmentor.over(String.CASE_INSENSITIVE_ORDER);
        iv.insertInterval(set, "apple", "dog");
        iv.insertInterval(set, "fox", "kite");
        iv.insertInterval(set, "MOON", "zebra");

        assertEquals(1, iv.stabQuery(set, "cat").size(), "cat lies in [apple, dog]");
        assertEquals(iv.stabQuery(set, "cat"), iv.stabQuery(set, "CAT"),
                "case-insensitive comparator must make CAT equivalent to cat");
        assertEquals(2, iv.intervalSearchAll(set, "JAM", "nest").size(),
                "[JAM, nest] overlaps [fox, kite] and [MOON, zebra]");
        assertTrue(iv.stabQuery(set, "eel").isEmpty(), "eel falls between dog and fox");
        assertNull(iv.intervalSearch(set, "zzza", "zzzb"), "past zebra: proven miss");
    }

    @Test
    @DisplayName("add-or-restamp semantics and endpoint validation, mirroring the int version")
    void addOrRestampAndValidation() {
        OrderedSet<Long> set = longSet();
        GenericIntervalAugmentor<Long> iv = GenericIntervalAugmentor.natural();
        iv.insertInterval(set, 10L, 20L);
        iv.insertInterval(set, 10L, 50L);   // restamp the same lo

        assertEquals(1, set.size(), "same lo is one node");
        assertEquals(List.of("10/50"), canonical(iv.intervals(set)), "last stamp wins");
        assertTrue(iv.stabQuery(set, 40L).size() == 1, "new hi is live");
        assertTrue(iv.stabQuery(set, 60L).isEmpty(), "beyond the restamped hi");

        assertThrows(IllegalArgumentException.class, () -> iv.insertInterval(set, 5L, 1L));
        assertThrows(IllegalArgumentException.class, () -> iv.intervalSearchAll(set, 5L, 1L));
    }

    @Test
    @DisplayName("intrinsic size, order statistics, and tags are untouched by the ref slot")
    void orderStatisticsAndTagsCoexist() {
        OrderedSet<Long> set = longSet();
        GenericIntervalAugmentor<Long> iv = GenericIntervalAugmentor.natural();
        long[] los = {50, 10, 90, 30, 70};
        for (long lo : los) {
            iv.insertInterval(set, lo * SCALE, (lo + 5) * SCALE);
        }

        assertEquals(5, set.getEngine().getRoot().getSize(), "intrinsic size = node count (ADR-002)");
        assertEquals(Long.valueOf(10 * SCALE), set.select(1), "order statistics ride intrinsic size");
        assertEquals(Long.valueOf(50 * SCALE), set.median());
        assertEquals(Long.valueOf(90 * SCALE), set.maximum());
        assertEquals("", set.getEngine().getRoot().getTag(), "the generic encoding never touches tags");
    }

    @Test
    @DisplayName("payloads survive a strategy morph and selfRepair (the tag-carry, extended)")
    void morphAndRepairCarryRefs() {
        OrderedSet<Long> set = longSet();
        GenericIntervalAugmentor<Long> iv = GenericIntervalAugmentor.natural();
        Map<Long, Long> oracle = new LinkedHashMap<>();
        Random rng = new Random(17);
        for (int i = 0; i < 120; i++) {
            long lo = Math.floorMod(rng.nextLong(), 1_000_000_000_000L);
            long hi = lo + Math.floorMod(rng.nextLong(), 2_000_000_000L);
            iv.insertInterval(set, lo, hi);
            oracle.put(lo, hi);
        }
        long qlo = 200_000_000_000L, qhi = 600_000_000_000L;
        List<String> expected = oracleOverlaps(oracle, qlo, qhi);
        assertEquals(expected, canonical(iv.intervalSearchAll(set, qlo, qhi)), "precondition (RB)");

        assertTrue(set.setStrategy(new AVLStrategy<>()), "morph must apply");
        assertEquals(expected, canonical(iv.intervalSearchAll(set, qlo, qhi)),
                "typed his and max-hi must survive the RB->AVL rebuild");

        set.selfRepair();
        assertEquals(expected, canonical(iv.intervalSearchAll(set, qlo, qhi)),
                "typed his and max-hi must survive selfRepair's rebuild");
    }

    @Test
    @DisplayName("deepCopy shares immutable payloads without aliasing: mutating one side never bleeds")
    void deepCopyIsAliasSafe() {
        OrderedSet<Long> set = longSet();
        GenericIntervalAugmentor<Long> iv = GenericIntervalAugmentor.natural();
        iv.insertInterval(set, 10L, 20L);
        iv.insertInterval(set, 5L, 8L);
        iv.insertInterval(set, 30L, 45L);

        TreeNode1<Long> nil2 = TreeNode1.createNil(set.comparator());
        TreeNode1<Long> copy = set.getEngine().getRoot().deepCopy(nil2);
        assertEquals(Long.valueOf(45L), iv.subtreeMaxHi(copy), "copy carries the max-hi payload");

        iv.insertInterval(set, 30L, 9_999_999_999L);   // restamp on the ORIGINAL only
        assertEquals(Long.valueOf(9_999_999_999L), iv.subtreeMaxHi(set.getEngine().getRoot()),
                "original sees the restamp");
        assertEquals(Long.valueOf(45L), iv.subtreeMaxHi(copy),
                "copy must not: payloads are replaced, never mutated, so the shared refs are safe");
    }

    @Test
    @DisplayName("querying through the wrong augmentor fails loud instead of pruning wrong")
    void wrongAugmentorFailsLoud() {
        OrderedSet<Long> set = longSet();
        GenericIntervalAugmentor<Long> installed = GenericIntervalAugmentor.natural();
        GenericIntervalAugmentor<Long> stranger = GenericIntervalAugmentor.natural();
        assertTrue(stranger.stabQuery(set, 1L).isEmpty(), "an empty set is safely answerable by anyone");

        installed.insertInterval(set, 10L, 20L);
        assertThrows(IllegalStateException.class, () -> stranger.stabQuery(set, 15L),
                "a stranger's prune reads refs it does not maintain — must fail loud");
        assertEquals(1, installed.stabQuery(set, 15L).size(), "the installed instance keeps working");
    }
}
