package test.core;

import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.PersistentTreeEngine.Snapshot;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The structural-heredity seam (ADR-017): {@code Snapshot.sharedNodeCount} — physical
 * node sharing under path copying, by reference identity. Oracles where the count is
 * exact (identical snapshots, rebuilt trees, empties), tight bounds where rebalancing
 * makes the exact copy count structure-dependent (a single edit copies the root-to-site
 * path plus O(1) rotation copies per path node — bounded by 3·(height+1)).
 */
@DisplayName("Snapshot.sharedNodeCount — physical inheritance under path copying")
class SnapshotSharingTest {

    @Test
    @DisplayName("exact oracles: self=size, no-op twin=size, rebuilt-with-same-keys=0, empty=0")
    void exactOracles() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        for (int k = 0; k < 100; k++) engine.add(k);
        Snapshot<Integer> s1 = engine.snapshot();
        Snapshot<Integer> s2 = engine.snapshot();       // no ops between: same root object

        assertEquals(100, s1.sharedNodeCount(s1));
        assertEquals(100, s1.sharedNodeCount(s2));

        PersistentTreeEngine<Integer> rebuilt = PersistentTreeEngine.withNaturalOrder();
        for (int k = 0; k < 100; k++) rebuilt.add(k);   // same keys, all-new nodes
        assertEquals(0, s1.sharedNodeCount(rebuilt.snapshot()));

        PersistentTreeEngine<Integer> empty = PersistentTreeEngine.withNaturalOrder();
        assertEquals(0, s1.sharedNodeCount(empty.snapshot()));
        assertEquals(0, empty.snapshot().sharedNodeCount(s1));
    }

    @Test
    @DisplayName("a single edit shares almost everything: size − 1 ≥ shared ≥ size − 3·(height+1)")
    void singleEditBounds() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        for (int k = 0; k < 500; k++) engine.add(k * 2);
        Snapshot<Integer> before = engine.snapshot();
        int height = engine.height();

        engine.add(999);                                 // one insert: path copy
        Snapshot<Integer> after = engine.snapshot();

        int shared = before.sharedNodeCount(after);
        assertTrue(shared <= before.size() - 1, "the root is always on the copied path");
        assertTrue(shared >= before.size() - 3 * (height + 1),
                "copies exceeded the path+rotation bound: shared=" + shared
                        + " size=" + before.size() + " height=" + height);
    }

    @Test
    @DisplayName("symmetry: the identity intersection reads the same from either side")
    void symmetry() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        for (int k = 0; k < 200; k++) engine.add(k);
        Snapshot<Integer> s1 = engine.snapshot();
        for (int k = 0; k < 40; k++) engine.remove(k * 5);
        for (int k = 1000; k < 1030; k++) engine.add(k);
        Snapshot<Integer> s2 = engine.snapshot();

        assertEquals(s1.sharedNodeCount(s2), s2.sharedNodeCount(s1));
        assertTrue(s1.sharedNodeCount(s2) > 0, "adjacent versions must share structure");
        assertTrue(s1.sharedNodeCount(s2) <= Math.min(s1.size(), s2.size()));
    }

    @Test
    @DisplayName("the headline gap: keys can be inherited while their nodes are not")
    void contentVersusStructure() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        for (int k = 0; k < 100; k++) engine.add(k);
        Snapshot<Integer> parent = engine.snapshot();
        engine.remove(50);                               // 99% of keys survive ...
        Snapshot<Integer> child = engine.snapshot();

        int shared = parent.sharedNodeCount(child);
        assertTrue(shared < 99,
                "path copying must rewrite ancestors of the removed key: shared=" + shared);
        assertTrue(shared > 0);
        // Deterministic: same edit, same count.
        assertEquals(shared, parent.sharedNodeCount(child));
    }
}
