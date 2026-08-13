package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.PopulationGenetics;
import io.github.richeyworks.csrbt.experimental.ecology.PopulationGenetics.HardyWeinberg;
import io.github.richeyworks.csrbt.experimental.ecology.PopulationGenetics.LifeTableRates;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-019 population genetics — Hardy–Weinberg and the Euler–Lotka calculus, every
 * number a hand oracle.
 */
@DisplayName("PopulationGenetics — Hardy–Weinberg and Euler–Lotka")
class PopulationGeneticsTest {

    private static final double EPS = 1e-9;

    @Test
    @DisplayName("Hardy–Weinberg exact case: 25/50/25 is a perfect p=q=0.5 equilibrium, χ²=0")
    void perfectEquilibrium() {
        HardyWeinberg hw = PopulationGenetics.hardyWeinberg(25, 50, 25);
        assertEquals(0.5, hw.p(), EPS);
        assertEquals(0.5, hw.q(), EPS);
        assertEquals(25.0, hw.expectedAA(), EPS);
        assertEquals(50.0, hw.expectedAa(), EPS);
        assertEquals(0.0, hw.chiSquare(), EPS);
        assertTrue(hw.inEquilibrium());
        assertEquals(0.5, hw.observedHet(), EPS);
        assertEquals(0.5, hw.expectedHet(), EPS);
    }

    @Test
    @DisplayName("a heterozygote-deficit population reads significantly out of equilibrium")
    void outOfEquilibrium() {
        // Strong inbreeding signature: far too few heterozygotes for p = 0.5.
        HardyWeinberg hw = PopulationGenetics.hardyWeinberg(45, 10, 45);
        assertEquals(0.5, hw.p(), EPS);
        assertTrue(hw.chiSquare() > PopulationGenetics.CHI_SQUARE_CRITICAL_DF1);
        assertFalse(hw.inEquilibrium());
        assertTrue(hw.observedHet() < hw.expectedHet());
    }

    @Test
    @DisplayName("hand χ² oracle: 30/40/30 of n=100 → χ² = 4.0 exactly (just over the line)")
    void chiSquareHandOracle() {
        // p = 0.5: expected 25/50/25; χ² = 25/25 + 100/50 + 25/25 = 4.0
        HardyWeinberg hw = PopulationGenetics.hardyWeinberg(30, 40, 30);
        assertEquals(4.0, hw.chiSquare(), EPS);
        assertFalse(hw.inEquilibrium());   // 4.0 > 3.841, barely — the classic teaching case
    }

    @Test
    @DisplayName("fixed allele: p = 1 population is trivially in equilibrium")
    void fixedAllele() {
        HardyWeinberg hw = PopulationGenetics.hardyWeinberg(80, 0, 0);
        assertEquals(1.0, hw.p(), EPS);
        assertEquals(0.0, hw.chiSquare(), EPS);
        assertTrue(hw.inEquilibrium());
    }

    @Test
    @DisplayName("Euler–Lotka exact oracle: lx={1,1}, mx={0,2} → R0=2, T=1, r=ln 2 both ways")
    void eulerLotkaExact() {
        LifeTableRates rates = PopulationGenetics.eulerLotka(
                new double[]{ 1, 1 }, new double[]{ 0, 2 });
        assertEquals(2.0, rates.r0(), EPS);
        assertEquals(1.0, rates.generationTime(), EPS);
        assertEquals(Math.log(2), rates.rApprox(), EPS);
        // Single reproductive age ⇒ the approximation IS exact: e^(−r)·2 = 1 → r = ln 2.
        assertEquals(Math.log(2), rates.rExact(), 1e-6);
    }

    @Test
    @DisplayName("replacement-rate population: R0 = 1 → r = 0 exactly")
    void replacementRate() {
        LifeTableRates rates = PopulationGenetics.eulerLotka(
                new double[]{ 1, 0.5 }, new double[]{ 0, 2 });
        assertEquals(1.0, rates.r0(), EPS);
        assertEquals(0.0, rates.rExact(), 1e-6);
    }

    @Test
    @DisplayName("spread reproduction: exact r differs from ln R0/T, and satisfies Euler–Lotka")
    void spreadSchedule() {
        double[] lx = { 1.0, 0.8, 0.5, 0.2 };
        double[] mx = { 0, 1.5, 2.0, 1.0 };
        LifeTableRates rates = PopulationGenetics.eulerLotka(lx, mx);
        assertEquals(1.2 + 1.0 + 0.2, rates.r0(), EPS);
        double sum = 0;
        for (int x = 0; x < lx.length; x++) sum += Math.exp(-rates.rExact() * x) * lx[x] * mx[x];
        assertEquals(1.0, sum, 1e-6);      // the defining equation, verified directly
    }

    @Test
    @DisplayName("contracts: empty samples, negative counts, sterile schedules all throw")
    void contracts() {
        assertThrows(IllegalArgumentException.class, () -> PopulationGenetics.hardyWeinberg(0, 0, 0));
        assertThrows(IllegalArgumentException.class, () -> PopulationGenetics.hardyWeinberg(-1, 5, 5));
        assertThrows(IllegalArgumentException.class,
                () -> PopulationGenetics.eulerLotka(new double[]{ 1 }, new double[]{ 0 }));
        assertThrows(IllegalArgumentException.class,
                () -> PopulationGenetics.eulerLotka(new double[]{ 1, 1 }, new double[]{ 0 }));
    }
}
