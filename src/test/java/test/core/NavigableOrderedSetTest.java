package test.core;

import core.OrderedSet;
import core.adapter.NavigableOrderedSet;
import core.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.NavigableSet;
import java.util.NoSuchElementException;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-009 P2 — the {@link NavigableSet} adapter, pinned against {@code TreeSet} (the
 * reference implementation of the contract). Navigation parity is exhaustively probed over
 * present, absent, below-range, and above-range keys; view contents/size/navigation are
 * compared against {@code TreeSet}'s views over identical data; the deliberate divergence —
 * views are read-only — is asserted loudly, as is the snapshot iteration semantics.
 */
@DisplayName("NavigableOrderedSet — NavigableSet adapter (ADR-009 P2)")
public class NavigableOrderedSetTest {

    /** ~120 keys, even values only, in [0, 400) — odd probes are always absent. */
    private static Object[] populated() {
        OrderedSet<Integer> base = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        NavigableOrderedSet<Integer> nav = new NavigableOrderedSet<>(base);
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rnd = new Random(2026);
        while (oracle.size() < 120) {
            int k = rnd.nextInt(200) * 2;
            nav.add(k);
            oracle.add(k);
        }
        return new Object[] {nav, oracle};
    }

    @Nested
    @DisplayName("navigation parity with TreeSet")
    class Navigation {

        @Test
        @DisplayName("lower/floor/ceiling/higher agree with TreeSet for present, absent, and out-of-range probes")
        void navigationParity() {
            Object[] p = populated();
            @SuppressWarnings("unchecked") NavigableOrderedSet<Integer> nav = (NavigableOrderedSet<Integer>) p[0];
            TreeSet<Integer> oracle = (TreeSet<Integer>) p[1];

            for (int probe = -3; probe <= 402; probe++) {       // sweeps every boundary class
                assertEquals(oracle.lower(probe), nav.lower(probe), "lower(" + probe + ")");
                assertEquals(oracle.floor(probe), nav.floor(probe), "floor(" + probe + ")");
                assertEquals(oracle.ceiling(probe), nav.ceiling(probe), "ceiling(" + probe + ")");
                assertEquals(oracle.higher(probe), nav.higher(probe), "higher(" + probe + ")");
            }
            assertEquals(oracle.first(), nav.first());
            assertEquals(oracle.last(), nav.last());
            assertEquals(new ArrayList<>(oracle), new ArrayList<>(nav), "iteration order");
        }

        @Test
        @DisplayName("poll, iterator.remove, and clear mutate the base; empty-set edges match the contract")
        void mutationAndEmptyEdges() {
            Object[] p = populated();
            @SuppressWarnings("unchecked") NavigableOrderedSet<Integer> nav = (NavigableOrderedSet<Integer>) p[0];
            TreeSet<Integer> oracle = (TreeSet<Integer>) p[1];

            assertEquals(oracle.pollFirst(), nav.pollFirst());
            assertEquals(oracle.pollLast(), nav.pollLast());
            assertEquals(oracle.size(), nav.size());
            assertEquals(oracle.size(), nav.base().size(), "polls hit the base OrderedSet");

            Iterator<Integer> it = nav.iterator();
            int victim = it.next();
            it.remove();
            assertFalse(nav.contains(victim), "iterator.remove delegates to the base");
            oracle.remove(victim);
            assertEquals(oracle.size(), nav.size());

            nav.clear();
            assertTrue(nav.isEmpty());
            assertNull(nav.pollFirst());
            assertNull(nav.floor(10));
            assertThrows(NoSuchElementException.class, nav::first);
            assertThrows(NullPointerException.class, () -> nav.floor(null));
        }
    }

    @Nested
    @DisplayName("views")
    class Views {

        @Test
        @DisplayName("subSet/headSet/tailSet match TreeSet's views in contents, size, and navigation")
        void rangeViewParity() {
            Object[] p = populated();
            @SuppressWarnings("unchecked") NavigableOrderedSet<Integer> nav = (NavigableOrderedSet<Integer>) p[0];
            TreeSet<Integer> oracle = (TreeSet<Integer>) p[1];

            int[][] ranges = {{50, 250}, {0, 400}, {99, 101}, {130, 130}, {37, 363}};
            boolean[] flags = {true, false};
            for (int[] r : ranges) {
                for (boolean fi : flags) {
                    for (boolean ti : flags) {
                        NavigableSet<Integer> v = nav.subSet(r[0], fi, r[1], ti);
                        NavigableSet<Integer> ov = oracle.subSet(r[0], fi, r[1], ti);
                        String tag = "subSet(" + r[0] + "," + fi + "," + r[1] + "," + ti + ")";
                        assertEquals(ov.size(), v.size(), tag + " size");
                        assertEquals(new ArrayList<>(ov), new ArrayList<>(v), tag + " contents");
                        for (int probe : new int[] {r[0] - 1, r[0], (r[0] + r[1]) / 2, r[1], r[1] + 1}) {
                            assertEquals(ov.floor(probe), v.floor(probe), tag + " floor(" + probe + ")");
                            assertEquals(ov.ceiling(probe), v.ceiling(probe), tag + " ceiling(" + probe + ")");
                            assertEquals(ov.lower(probe), v.lower(probe), tag + " lower(" + probe + ")");
                            assertEquals(ov.higher(probe), v.higher(probe), tag + " higher(" + probe + ")");
                        }
                    }
                }
            }

            assertEquals(new ArrayList<>(oracle.headSet(200, true)),
                         new ArrayList<>(nav.headSet(200, true)));
            assertEquals(new ArrayList<>(oracle.tailSet(200, false)),
                         new ArrayList<>(nav.tailSet(200, false)));
            assertEquals(oracle.headSet(1).isEmpty(), nav.headSet(1).isEmpty(), "empty head view");
            assertThrows(NoSuchElementException.class, () -> nav.headSet(0, false).first());
            assertThrows(IllegalArgumentException.class, () -> nav.subSet(300, 100));
            assertThrows(IllegalArgumentException.class,
                    () -> nav.subSet(100, true, 300, false).subSet(50, true, 200, false),
                    "sub-range bounds must stay inside the view");
        }

        @Test
        @DisplayName("descending views mirror TreeSet; nested view composition holds")
        void descendingParity() {
            Object[] p = populated();
            @SuppressWarnings("unchecked") NavigableOrderedSet<Integer> nav = (NavigableOrderedSet<Integer>) p[0];
            TreeSet<Integer> oracle = (TreeSet<Integer>) p[1];

            assertEquals(new ArrayList<>(oracle.descendingSet()), new ArrayList<>(nav.descendingSet()));
            assertEquals(oracle.descendingSet().first(), nav.descendingSet().first());
            for (int probe : new int[] {-1, 100, 101, 399, 401}) {
                assertEquals(oracle.descendingSet().floor(probe), nav.descendingSet().floor(probe),
                        "desc floor(" + probe + ")");
                assertEquals(oracle.descendingSet().higher(probe), nav.descendingSet().higher(probe),
                        "desc higher(" + probe + ")");
            }
            // desc(desc(x)) == x; desc of a range view; range of a desc view
            assertEquals(new ArrayList<>(nav), new ArrayList<>(nav.descendingSet().descendingSet()));
            assertEquals(new ArrayList<>(oracle.subSet(50, true, 250, false).descendingSet()),
                         new ArrayList<>(nav.subSet(50, true, 250, false).descendingSet()));
            assertEquals(new ArrayList<>(oracle.descendingSet().subSet(250, true, 50, false)),
                         new ArrayList<>(nav.descendingSet().subSet(250, true, 50, false)),
                    "subSet on a descending view uses the reversed order");
        }

        @Test
        @DisplayName("the honesty clause: every view mutator throws, the base stays the mutation point")
        void viewsAreReadOnly() {
            Object[] p = populated();
            @SuppressWarnings("unchecked") NavigableOrderedSet<Integer> nav = (NavigableOrderedSet<Integer>) p[0];

            NavigableSet<Integer> range = nav.subSet(50, true, 250, false);
            NavigableSet<Integer> desc = nav.descendingSet();
            assertThrows(UnsupportedOperationException.class, () -> range.add(60));
            assertThrows(UnsupportedOperationException.class, () -> range.remove(60));
            assertThrows(UnsupportedOperationException.class, range::clear);
            assertThrows(UnsupportedOperationException.class, range::pollFirst);
            assertThrows(UnsupportedOperationException.class, () -> desc.add(60));
            assertThrows(UnsupportedOperationException.class, desc::pollLast);

            int sizeBefore = range.size();
            nav.add(61);                               // mutate through the base...
            assertEquals(sizeBefore + 1, range.size(), "...and the live view sees it");
            assertTrue(range.contains(61));
        }
    }
}
