package test.core;

import core.RedBlackTree;
import core.control.WorkloadFeatures;
import core.evolution.Fitness;
import core.strategy.RedBlackStrategy;
import core.strategy.WeightBalancedStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-011 V2 — the explainable fitness function. Hand-built vectors hit exact expected
 * numbers (the cost arithmetic is a pure function of scalars), the partial costs move
 * the right direction (deeper → worse reads, more rotations → worse writes), the
 * evaluation explains itself from one line, and the structural measurement agrees with
 * hand-computed shapes.
 */
@DisplayName("Fitness — explainable, deterministic (ADR-011 V2)")
public class FitnessTest {

    /** read/write mix and realized rotations; the rest of the vector is irrelevant here. */
    private static WorkloadFeatures features(double read, double write, double rotPerWrite) {
        return new WorkloadFeatures(read, write, 0.0, 0.0, rotPerWrite, 0L, 0.0);
    }

    @Nested
    @DisplayName("the cost arithmetic, on hand-built vectors")
    class Arithmetic {

        @Test
        @DisplayName("exact value: read=0.6 write=0.4 rot=2 depth=4 n=15 → cost 1.4")
        void exactVector() {
            // bound = log₂(16) = 4 exactly, so readCost = 0.6 × (4/4) = 0.6
            // writeCost = 0.4 × 2.0 = 0.8; cost = 1.4
            Fitness.Evaluation e = Fitness.evaluate(features(0.6, 0.4, 2.0), 4.0, 15L);
            assertEquals(0.8, e.writeCost(), 1e-12);
            assertEquals(0.6, e.readCost(), 1e-12);
            assertEquals(1.4, e.cost(), 1e-12);
            assertEquals(4.0, e.balancedDepthBound(), 1e-12);
        }

        @Test
        @DisplayName("deterministic: the same inputs give the same value, always")
        void deterministic() {
            Fitness.Evaluation a = Fitness.evaluate(features(0.3, 0.7, 1.25), 7.5, 100L);
            Fitness.Evaluation b = Fitness.evaluate(features(0.3, 0.7, 1.25), 7.5, 100L);
            assertEquals(a, b);
        }

        @Test
        @DisplayName("partial costs move the right direction")
        void monotone() {
            WorkloadFeatures f = features(0.5, 0.5, 1.0);
            assertTrue(Fitness.evaluate(f, 12.0, 100L).readCost()
                     > Fitness.evaluate(f,  7.0, 100L).readCost(),
                    "deeper tree must cost more reads");
            assertTrue(Fitness.evaluate(features(0.5, 0.5, 3.0), 7.0, 100L).writeCost()
                     > Fitness.evaluate(features(0.5, 0.5, 1.0), 7.0, 100L).writeCost(),
                    "more rotations must cost more writes");
        }

        @Test
        @DisplayName("n ≤ 1: every shape is the same shape, so the read term is 0")
        void degenerateSizes() {
            assertEquals(0.0, Fitness.evaluate(features(1.0, 0.0, 0.0), 1.0, 0L).readCost(), 1e-12);
            assertEquals(0.0, Fitness.evaluate(features(1.0, 0.0, 0.0), 1.0, 1L).readCost(), 1e-12);
        }

        @Test
        @DisplayName("bad inputs fail loudly")
        void validation() {
            assertThrows(IllegalArgumentException.class, () -> Fitness.evaluate(null, 1.0, 1L));
            assertThrows(IllegalArgumentException.class,
                    () -> Fitness.evaluate(features(1.0, 0.0, 0.0), -0.5, 1L));
            assertThrows(IllegalArgumentException.class,
                    () -> Fitness.evaluate(features(1.0, 0.0, 0.0), 1.0, -1L));
        }

        @Test
        @DisplayName("an evaluation explains itself: every named input is in the line")
        void explainable() {
            String line = Fitness.evaluate(features(0.6, 0.4, 2.0), 4.0, 15L).toString();
            assertTrue(line.contains("cost=1.4000"), line);
            assertTrue(line.contains("writeCost=0.8000"), line);
            assertTrue(line.contains("readCost=0.6000"), line);
            assertTrue(line.contains("rotPerWrite=2.0000"), line);
            assertTrue(line.contains("depth=4.00"), line);
        }
    }

    @Nested
    @DisplayName("the structural measurement: meanDepth")
    class MeanDepth {

        @Test
        @DisplayName("hand-computed shapes: empty → 0, single → 1, three balanced → 5/3")
        void handComputedShapes() {
            RedBlackTree<Integer> tree =
                    RedBlackTree.withNaturalOrder(new RedBlackStrategy<Integer>());
            assertEquals(0.0, Fitness.meanDepth(tree), 1e-12);

            tree.add(2);
            assertEquals(1.0, Fitness.meanDepth(tree), 1e-12);

            tree.add(1);
            tree.add(3);   // RB: root 2, leaves 1 and 3 → (1 + 2 + 2) / 3
            assertEquals(5.0 / 3.0, Fitness.meanDepth(tree), 1e-12);
        }

        @Test
        @DisplayName("under WB(3,2), 1023 sequential inserts stay near the balanced bound")
        void logarithmicUnderBalance() {
            RedBlackTree<Integer> tree =
                    RedBlackTree.withNaturalOrder(new WeightBalancedStrategy<Integer>());
            for (int i = 1; i <= 1023; i++) tree.add(i);

            double meanDepth = Fitness.meanDepth(tree);
            // Perfectly balanced 1023 nodes: meanDepth ≈ 8.99; sorted input is WB's worst
            // diet, so allow slack — but a degenerate spine would be ~512.
            assertTrue(meanDepth >= 1.0 && meanDepth < 2.0 * 10.0,
                    "meanDepth not logarithmic: " + meanDepth);

            // And the full evaluation wires through: a pure-read workload on this shape
            // costs about meanDepth / log₂(1024).
            Fitness.Evaluation e = Fitness.evaluate(features(1.0, 0.0, 0.0), meanDepth, 1023L);
            assertEquals(meanDepth / 10.0, e.readCost(), 1e-12);
        }
    }
}
