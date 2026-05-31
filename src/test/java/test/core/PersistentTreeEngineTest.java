package test.core;

import core.PersistentTreeEngine;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Correctness, persistence, and stack-safety for the path-copying engine.
 */
@DisplayName("PersistentTreeEngine")
public class PersistentTreeEngineTest {

    @Test
    @DisplayName("ordered-set semantics match a TreeSet oracle over random ops")
    void matchesOracle() {
        PersistentTreeEngine eng = new PersistentTreeEngine();
        TreeSet<Integer> oracle = new TreeSet<>();
        Random rng = new Random(2026);

        for (int i = 0; i < 4000; i++) {
            int v = rng.nextInt(600);
            switch (rng.nextInt(3)) {
                case 0 -> { eng.add(v); oracle.add(v); }
                case 1 -> { eng.remove(v); oracle.remove(v); }
                default -> assertEquals(oracle.contains(v), eng.contains(v), "contains(" + v + ")");
            }
            if (i % 200 == 0) {
                assertEquals(new ArrayList<>(oracle), eng.inOrder());
                assertEquals(oracle.size(), eng.size());
            }
        }
        assertEquals(new ArrayList<>(oracle), eng.inOrder());
        assertEquals(oracle.size(), eng.size());
    }

    @Test
    @DisplayName("duplicate add is ignored and records no new version")
    void duplicatesIgnored() {
        PersistentTreeEngine eng = new PersistentTreeEngine();
        eng.add(5);
        int versions = eng.versionCount();
        eng.add(5);                              // no structural change
        assertEquals(versions, eng.versionCount(), "duplicate must not create a version");
        assertEquals(1, eng.size());
    }

    @Test
    @DisplayName("past versions remain intact after later mutations")
    void versionsArePersistent() {
        PersistentTreeEngine eng = new PersistentTreeEngine();
        eng.add(10);
        eng.add(20);
        int vAfterTwo = eng.versionCount() - 1;     // version index with {10,20}
        eng.add(30);
        eng.remove(10);

        assertEquals(List.of(20, 30), eng.inOrder(), "current version reflects all ops");
        assertEquals(List.of(10, 20), eng.inOrderOfVersion(vAfterTwo),
                "an earlier version is unchanged by later mutations");
        assertEquals(List.of(), eng.inOrderOfVersion(0), "version 0 is empty");
    }

    @Test
    @DisplayName("clear empties without recording redundant empty versions")
    void clearNoRedundantVersion() {
        PersistentTreeEngine eng = new PersistentTreeEngine();
        eng.add(1);
        eng.clear();
        int versions = eng.versionCount();
        eng.clear();                             // already empty
        assertEquals(versions, eng.versionCount(), "clearing an empty set adds no version");
        assertEquals(0, eng.size());
        assertFalse(eng.contains(1));
    }

    @Test
    @DisplayName("large sorted insert does not overflow the stack (iterative path copy)")
    void deepSortedInputIsStackSafe() {
        PersistentTreeEngine eng = new PersistentTreeEngine();
        // Degenerate right-leaning chain deep enough that the old recursive
        // insert/traversal would StackOverflow. Kept modest because an unbalanced
        // tree makes sorted insertion O(n^2).
        int n = 10_000;
        for (int i = 0; i < n; i++) eng.add(i);
        assertEquals(n, eng.size());
        assertTrue(eng.contains(0) && eng.contains(n - 1));
        // inOrder traversal is also iterative — must not overflow on the deep tree.
        assertEquals(n, eng.inOrder().size());
        // delete from deep in the chain, still no overflow.
        eng.remove(0);
        eng.remove(n - 1);
        assertEquals(n - 2, eng.size());
    }
}
