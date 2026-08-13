package test.core;

import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.experimental.ecology.SnapshotLineage;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-016 §E2 — descent bookkeeping over persistent snapshots: the path-copying
 * engine's snapshots as a generational record; inherited fraction, gains/losses,
 * divergence, and turnover, all hand-oracle on constructed edit sequences.
 */
@DisplayName("SnapshotLineage — generational record over the persistent engine")
class SnapshotLineageTest {

    private static final double EPS = 1e-9;

    @Test
    @DisplayName("hand oracle: 10 keys, replace 2 → inherited 0.8, gains 2, losses 2, divergence 1 − 8/12")
    void handOracle() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        SnapshotLineage<Integer> lineage = new SnapshotLineage<>();

        for (int i = 0; i < 10; i++) engine.add(i);
        lineage.capture(engine);              // generation 0: {0..9}

        engine.remove(0);
        engine.remove(1);
        engine.add(100);
        engine.add(101);
        lineage.capture(engine);              // generation 1: {2..9, 100, 101}

        assertEquals(0.8, lineage.inheritedFraction(0), EPS);
        assertEquals(2, lineage.gains(0));
        assertEquals(2, lineage.losses(0));
        // |∩| = 8, |∪| = 12 → J = 8/12, divergence = 1/3
        assertEquals(1.0 - 8.0 / 12.0, lineage.divergence(0, 1), EPS);
        assertEquals(0.0, lineage.divergence(0, 0), EPS);
    }

    @Test
    @DisplayName("snapshots are true pasts: mutating after capture does not rewrite the record")
    void snapshotsAreImmutablePasts() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        SnapshotLineage<Integer> lineage = new SnapshotLineage<>();

        engine.add(1);
        lineage.capture(engine);              // generation 0: {1}
        engine.add(2);
        engine.add(3);
        lineage.capture(engine);              // generation 1: {1,2,3}
        engine.clear();                       // present is emptied ...
        assertEquals(1, lineage.retained().get(0).size());   // ... the record is not
        assertEquals(3, lineage.retained().get(1).size());
        assertEquals(1.0, lineage.inheritedFraction(0), EPS); // {1} fully inherited
    }

    @Test
    @DisplayName("turnover per generation: constant-drift oracle at 25% replacement per step")
    void turnoverOracle() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        SnapshotLineage<Integer> lineage = new SnapshotLineage<>();

        for (int i = 0; i < 8; i++) engine.add(i);
        lineage.capture(engine);
        // each generation: remove 2 of 8, add 2 new → |∩|=6, |∪|=10, distance = 0.4
        int next = 100;
        for (int g = 0; g < 3; g++) {
            engine.remove(g * 2);
            engine.remove(g * 2 + 1);
            engine.add(next++);
            engine.add(next++);
            lineage.capture(engine);
        }
        assertEquals(0.4, lineage.turnoverPerGeneration(), EPS);
        assertEquals(4, lineage.generations());
    }

    @Test
    @DisplayName("bounded retention: oldest generations evicted, absolute numbering kept, misses throw")
    void boundedRetention() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        SnapshotLineage<Integer> lineage = new SnapshotLineage<>(3);

        for (int g = 0; g < 5; g++) {
            engine.add(g);
            lineage.capture(engine);
        }
        assertEquals(5, lineage.generations());
        assertEquals(3, lineage.retained().size());
        assertEquals(2, lineage.retained().get(0).index()); // 0 and 1 evicted
        assertThrows(IllegalArgumentException.class, () -> lineage.divergence(0, 4));
        assertEquals(1.0, lineage.inheritedFraction(2), EPS); // additions only: all kept
    }

    @Test
    @DisplayName("empty-parent convention and constructor contract")
    void contracts() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        SnapshotLineage<Integer> lineage = new SnapshotLineage<>();
        lineage.capture(engine);              // generation 0: {}
        engine.add(1);
        lineage.capture(engine);              // generation 1: {1}
        assertEquals(1.0, lineage.inheritedFraction(0), EPS); // nothing to lose
        assertEquals(1, lineage.gains(0));
        assertEquals(0, lineage.losses(0));
        assertThrows(IllegalArgumentException.class, () -> new SnapshotLineage<Integer>(1));
    }

    @Test
    @DisplayName("ADR-017 structural heredity: no-op twin inherits 100% physically; edits open the gap")
    void structuralInheritance() {
        PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
        SnapshotLineage<Integer> lineage = new SnapshotLineage<>();
        for (int k = 0; k < 100; k++) engine.add(k);
        lineage.capture(engine);              // generation 0
        lineage.capture(engine);              // generation 1: no ops → same root object
        assertEquals(1.0, lineage.structuralInheritance(0), EPS);
        assertEquals(1.0, lineage.inheritedFraction(0), EPS);

        engine.remove(50);                    // 99% of keys survive; their ancestors do not
        lineage.capture(engine);              // generation 2
        double content = lineage.inheritedFraction(1);
        double structural = lineage.structuralInheritance(1);
        assertEquals(0.99, content, EPS);
        assertTrue(structural < content,
                "path copying must rewrite ancestors: structural=" + structural);
        assertTrue(structural > 0.5, "one edit cannot destroy most of the structure");

        // Means over the retained window: structural ≤ content, both in (0, 1].
        assertTrue(lineage.meanStructuralInheritance() <= lineage.meanContentInheritance() + EPS);
        assertTrue(lineage.meanStructuralInheritance() > 0);
    }

    @Test
    @DisplayName("determinism: identical edit sequences give identical lineage numbers")
    void determinism() {
        double[] runs = new double[2];
        for (int run = 0; run < 2; run++) {
            PersistentTreeEngine<Integer> engine = PersistentTreeEngine.withNaturalOrder();
            SnapshotLineage<Integer> lineage = new SnapshotLineage<>();
            for (int i = 0; i < 30; i++) engine.add(i * 7 % 30);
            lineage.capture(engine);
            for (int i = 0; i < 10; i++) engine.remove(i * 3);
            for (int i = 0; i < 10; i++) engine.add(1000 + i);
            lineage.capture(engine);
            runs[run] = lineage.divergence(0, 1);
        }
        assertEquals(runs[0], runs[1]);
    }
}
