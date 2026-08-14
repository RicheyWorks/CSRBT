package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.adapter.NavigableOrderedSet;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.NavigableSet;
import java.util.NoSuchElementException;
import java.util.TreeSet;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Probes for the two 2026-08-14 NavigableOrderedSet fixes:
 *
 * <p>(1) Sub-view widening: {@code inRangeForBound} admitted a view's own endpoint
 * unconditionally, so re-admitting an EXCLUSIVE endpoint INCLUSIVELY
 * ({@code headSet(10,false).headSet(10,true)}) built a child view that escaped the
 * parent's range instead of throwing — TreeSet parity requires
 * {@code IllegalArgumentException} there.</p>
 *
 * <p>(2) Multi-epoch view reads: {@code Range.snapshot()} composed
 * isEmpty → minimum → maximum → rangeQuery across four lock epochs (NPE out of a
 * read-only iterator under a concurrent writer; pre-fix probe: 4 NPEs + 11 null
 * first() returns in 3s), and base {@code first()} composed isEmpty → minimum (a
 * null return {@code SortedSet.first()} must never make). Both are now single
 * guarded acquisitions ({@code OrderedSet.rangeSnapshot}).</p>
 */
class ViewBoundsParityProbeTest {

    private static NavigableOrderedSet<Integer> setOf0to20() {
        OrderedSet<Integer> s = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i <= 20; i++) s.add(i);
        return new NavigableOrderedSet<>(s);
    }

    private static NavigableSet<Integer> treeSetOf0to20() {
        NavigableSet<Integer> s = new TreeSet<>();
        for (int i = 0; i <= 20; i++) s.add(i);
        return s;
    }

    @Test
    @DisplayName("re-admitting an exclusive endpoint inclusively throws, like TreeSet")
    void exclusiveEndpointCannotBeReadmittedInclusively() {
        NavigableOrderedSet<Integer> nav = setOf0to20();
        NavigableSet<Integer> ref = treeSetOf0to20();

        // headSet(10,false) then headSet(10,true): TreeSet throws IAE.
        NavigableSet<Integer> parent = nav.headSet(10, false);
        NavigableSet<Integer> refParent = ref.headSet(10, false);
        assertThrows(IllegalArgumentException.class, () -> refParent.headSet(10, true));
        assertThrows(IllegalArgumentException.class, () -> parent.headSet(10, true),
                "child view escaped the parent's exclusive high endpoint");

        // tailSet(5,false) then tailSet(5,true): same on the low side.
        assertThrows(IllegalArgumentException.class,
                () -> nav.tailSet(5, false).tailSet(5, true));

        // subSet(2,true,10,false) then subSet(...,10,true): same via subSet.
        assertThrows(IllegalArgumentException.class,
                () -> nav.subSet(2, true, 10, false).subSet(5, true, 10, true));

        // Still-legal parity cases: re-admitting exclusively, and inclusive-inside.
        assertEquals(refParent.headSet(10, false).size(), parent.headSet(10, false).size());
        assertEquals(refParent.headSet(9, true).size(), parent.headSet(9, true).size());
        assertEquals(List.copyOf(ref.tailSet(5, true).tailSet(5, false)),
                List.copyOf(nav.tailSet(5, true).tailSet(5, false)));
    }

    @Test
    @DisplayName("view snapshots, navigation, and descending mirror match TreeSet")
    void viewReadsMatchTreeSet() {
        NavigableOrderedSet<Integer> nav = setOf0to20();
        NavigableSet<Integer> ref = treeSetOf0to20();

        int[][] ranges = {{3, 1, 17, 1}, {3, 0, 17, 0}, {0, 1, 20, 0}, {5, 0, 6, 1}, {5, 1, 5, 1}};
        for (int[] r : ranges) {
            NavigableSet<Integer> a = nav.subSet(r[0], r[1] == 1, r[2], r[3] == 1);
            NavigableSet<Integer> b = ref.subSet(r[0], r[1] == 1, r[2], r[3] == 1);
            String label = "subSet(" + r[0] + "," + (r[1] == 1) + "," + r[2] + "," + (r[3] == 1) + ")";
            assertEquals(List.copyOf(b), List.copyOf(a), label);
            assertEquals(b.size(), a.size(), label + ".size");
            for (int k = -1; k <= 21; k++) {
                assertEquals(b.floor(k), a.floor(k), label + ".floor(" + k + ")");
                assertEquals(b.ceiling(k), a.ceiling(k), label + ".ceiling(" + k + ")");
                assertEquals(b.lower(k), a.lower(k), label + ".lower(" + k + ")");
                assertEquals(b.higher(k), a.higher(k), label + ".higher(" + k + ")");
            }
            List<Integer> aDesc = new ArrayList<>(), bDesc = new ArrayList<>();
            a.descendingIterator().forEachRemaining(aDesc::add);
            b.descendingIterator().forEachRemaining(bDesc::add);
            assertEquals(bDesc, aDesc, label + " descending");
        }

        // Empty-view first()/last() throw; navigation answers null, not garbage.
        NavigableSet<Integer> empty = nav.subSet(5, false, 6, false);
        assertThrows(NoSuchElementException.class, empty::first);
        assertThrows(NoSuchElementException.class, empty::last);
        assertNull(empty.floor(10));
        assertNull(empty.ceiling(0));
        assertEquals(0, empty.size());
    }

    @Test
    @DisplayName("descendingIterator().remove() delegates to the live set (TreeSet parity)")
    void descendingIteratorRemoveWorks() {
        NavigableOrderedSet<Integer> nav = setOf0to20();
        Iterator<Integer> it = nav.descendingIterator();
        int first = it.next();
        assertEquals(20, first);
        it.remove();
        assertEquals(19, (int) nav.last());
        assertEquals(20, nav.size());
    }

    @Test
    @DisplayName("view iteration and first() never throw NPE / return null under a concurrent writer")
    void viewReadsSurviveConcurrentClear() throws Exception {
        OrderedSet<Integer> s = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 0; i < 64; i++) s.add(i);
        NavigableOrderedSet<Integer> nav = new NavigableOrderedSet<>(s);
        NavigableSet<Integer> view = nav.headSet(500, true);

        AtomicBoolean stop = new AtomicBoolean(false);
        AtomicReference<Throwable> readerFault = new AtomicReference<>();
        AtomicBoolean sawNullFirst = new AtomicBoolean(false);

        Thread reader = new Thread(() -> {
            try {
                while (!stop.get()) {
                    for (Integer k : view) {           // snapshot() — must never throw
                        if (k == null) sawNullFirst.set(true);
                    }
                    try {
                        Integer f = nav.first();       // may throw NoSuchElementException…
                        if (f == null) sawNullFirst.set(true);   // …but must never be null
                    } catch (NoSuchElementException expectedWhenEmpty) {
                        // legal: the writer emptied the set
                    }
                }
            } catch (Throwable t) {
                readerFault.set(t);
            }
        });
        reader.start();

        long until = System.currentTimeMillis() + 1_000;
        while (System.currentTimeMillis() < until) {
            s.clear();
            for (int i = 0; i < 64; i++) s.add(i);
        }
        stop.set(true);
        reader.join(5_000);

        if (readerFault.get() != null) {
            fail("read-only view read threw under a concurrent writer: " + readerFault.get());
        }
        assertTrue(!sawNullFirst.get(), "first()/iterator yielded null under a concurrent writer");
    }
}
