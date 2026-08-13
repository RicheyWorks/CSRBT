package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.TheoreticalModels;
import io.github.richeyworks.csrbt.experimental.ecology.TheoreticalModels.Environment;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-019 theory bench — fixed points, closed forms, convergence, and the abiotic
 * environment conventions, all hand-oracle.
 */
@DisplayName("TheoreticalModels — trajectories and the abiotic environment")
class TheoreticalModelsTest {

    private static final double EPS = 1e-9;

    @Test
    @DisplayName("Levins: p* = 1 − e/c, a trajectory started at p* stays there, others converge")
    void levinsOracles() {
        assertEquals(0.75, TheoreticalModels.levinsEquilibrium(0.4, 0.1), EPS);
        assertEquals(0.0, TheoreticalModels.levinsEquilibrium(0.1, 0.4), EPS); // e > c → empty
        assertEquals(0.0, TheoreticalModels.levinsEquilibrium(0.0, 0.1), EPS);

        double[][] atStar = TheoreticalModels.levinsTrajectory(0.4, 0.1, 0.75, 30);
        for (double[] pt : atStar) assertEquals(0.75, pt[1], 1e-12);

        double[][] fromBelow = TheoreticalModels.levinsTrajectory(0.4, 0.1, 0.05, 200);
        assertEquals(0.75, fromBelow[200][1], 1e-3);
        for (double[] pt : fromBelow) assertTrue(pt[1] >= 0 && pt[1] <= 1, "clamp violated");
    }

    @Test
    @DisplayName("logistic: exact closed form — midpoint at ln((K−N0)/N0)/r; extinct stays extinct")
    void logisticOracles() {
        double r = 0.1, k = 100, n0 = 10;
        double[][] t = TheoreticalModels.logisticTrajectory(r, k, n0, 100);
        assertEquals(n0, t[0][1], EPS);
        double tMid = Math.log((k - n0) / n0) / r;           // N(tMid) = K/2 analytically
        int near = (int) Math.round(tMid);
        assertEquals(k / 2, t[near][1], 1.0);
        assertTrue(t[100][1] < k && t[100][1] > 0.95 * k);

        double[][] extinct = TheoreticalModels.logisticTrajectory(r, k, 0, 10);
        for (double[] pt : extinct) assertEquals(0.0, pt[1], EPS);
    }

    @Test
    @DisplayName("island: S* = c/(c+e)·pool; empty island rises to it, overfull one relaxes down")
    void islandOracles() {
        assertEquals(75.0, TheoreticalModels.islandEquilibrium(0.3, 0.1, 100), EPS);
        assertEquals(0.0, TheoreticalModels.islandEquilibrium(0, 0, 100), EPS);

        double[][] rising = TheoreticalModels.islandTrajectory(0.3, 0.1, 100, 0, 50);
        assertEquals(0.0, rising[0][1], EPS);
        for (int i = 1; i < rising.length; i++) {
            assertTrue(rising[i][1] > rising[i - 1][1], "empty island must rise monotonically");
        }
        assertEquals(75.0, rising[50][1], 0.01);

        double[][] relaxing = TheoreticalModels.islandTrajectory(0.3, 0.1, 100, 100, 50);
        assertEquals(75.0, relaxing[50][1], 0.01);
        assertTrue(relaxing[1][1] < 100);
    }

    @Test
    @DisplayName("exponential: N(t) = N0·e^rt exactly")
    void exponentialOracle() {
        double[][] t = TheoreticalModels.exponentialTrajectory(0.2, 5, 10);
        assertEquals(5 * Math.exp(0.2 * 10), t[10][1], EPS);
    }

    @Test
    @DisplayName("competition: strong asymmetric competition excludes the weaker species")
    void competitionExclusion() {
        // α21 large: species 1 suppresses species 2 toward exclusion; 1 approaches K1.
        double[][][] t = TheoreticalModels.competitionTrajectories(
                0.4, 100, 0.4, 80, 0.2, 2.0, 5, 5, 400);
        assertEquals(100, t[0][400][1], 2.0);
        assertTrue(t[1][400][1] < 1.0, "species 2 should be near exclusion, got " + t[1][400][1]);
        for (double[] pt : t[1]) assertTrue(pt[1] >= 0);
    }

    @Test
    @DisplayName("predation: the classic cycles — prey oscillates around m/(ba), predator around r/a")
    void predationCycles() {
        double[][][] t = TheoreticalModels.predationTrajectories(
                0.5, 0.02, 0.3, 0.4, 40, 9, 200);
        double preyMin = Double.MAX_VALUE, preyMax = 0;
        for (double[] pt : t[0]) { preyMin = Math.min(preyMin, pt[1]); preyMax = Math.max(preyMax, pt[1]); }
        // Cycles: the prey population must both dip below and rise above its start.
        assertTrue(preyMin < 40 && preyMax > 40, "no oscillation: [" + preyMin + ", " + preyMax + "]");
        for (double[] pt : t[1]) assertTrue(pt[1] >= 0);
    }

    @Test
    @DisplayName("environment conventions: wind and temperature aid colonization, distance decays it, area buffers")
    void environmentConventions() {
        Environment env = new Environment(0.5, 0.9, 1.3, 0.8);
        assertEquals(0.4 * 1.3 * 0.9 * Math.exp(-0.8), env.colonization(0.4), EPS);
        assertEquals(0.1 / 0.5, env.extinction(0.1), EPS);
        assertEquals(0.15 * 0.9, env.growth(0.15), EPS);
        assertEquals(120 * 0.5, env.capacity(120), EPS);
        assertEquals(0.4, Environment.NEUTRAL.colonization(0.4), EPS);

        assertThrows(IllegalArgumentException.class, () -> new Environment(0, 1, 1, 0));
        assertThrows(IllegalArgumentException.class, () -> new Environment(1, -1, 1, 0));
    }
}
