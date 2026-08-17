package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;
import io.github.richeyworks.csrbt.experimental.ecology.PopulationGenetics;
import io.github.richeyworks.csrbt.experimental.ecology.PopulationGenetics.LifeTableRates;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (bug audit 2026-08-17, finding 16): the Euler–Lotka bisection ran on a hardcoded
 * [-5, +5] bracket with no containment check, so a schedule whose root lay outside it got
 * the nearest bracket ENDPOINT back — printed as "(exact)" beside a correct r ≈ ln R₀/T
 * that disagreed with it. lx = {1,1}, mx = {0,250} (R₀ = 250, T = 1) has r = ln 250 =
 * 5.5215 and reported 5.0000; the mirror case reported -5.0 for r = -6.9078. Both are
 * reachable from a student's protocol file ({@code model: eulerlotka 1:0 1:250}).
 *
 * <p>The fix expands the bracket geometrically until it truly contains the root, and
 * reports honestly when no r solves the schedule at all rather than returning an endpoint.</p>
 */
@DisplayName("Euler–Lotka bracket probe — the exact r is the root, or it is reported")
class PopulationGeneticsBracketProbeTest {

    /** Σ e^(−rx)·lx·mx at the returned r — must be 1 for a genuine root. */
    private static double euler(double[] lx, double[] mx, double r) {
        double s = 0;
        for (int x = 0; x < lx.length; x++) s += Math.exp(-r * x) * lx[x] * mx[x];
        return s;
    }

    @Test
    @DisplayName("R₀ = 250 at T = 1: exact r is ln 250 = 5.5215, not the old bracket end 5.0")
    void rootAboveOldBracket() {
        double[] lx = { 1, 1 }, mx = { 0, 250 };
        LifeTableRates rates = PopulationGenetics.eulerLotka(lx, mx);
        assertEquals(250.0, rates.r0(), 1e-9);
        assertEquals(1.0, rates.generationTime(), 1e-9);
        // Single reproductive age ⇒ ln R0/T IS the exact answer; the two must agree.
        assertEquals(Math.log(250), rates.rApprox(), 1e-9);
        assertEquals(Math.log(250), rates.rExact(), 1e-9);
        assertEquals(1.0, euler(lx, mx, rates.rExact()), 1e-9);
    }

    @Test
    @DisplayName("R₀ ≪ 1 at T = 1: exact r is ln 0.001 = -6.9078, not the old bracket end -5.0")
    void rootBelowOldBracket() {
        double[] lx = { 1, 1 }, mx = { 0, 0.001 };
        LifeTableRates rates = PopulationGenetics.eulerLotka(lx, mx);
        assertEquals(0.001, rates.r0(), 1e-12);
        assertEquals(Math.log(0.001), rates.rApprox(), 1e-9);
        assertEquals(Math.log(0.001), rates.rExact(), 1e-9);
        assertEquals(1.0, euler(lx, mx, rates.rExact()), 1e-9);
    }

    @Test
    @DisplayName("a root inside [-5, +5] is unchanged — no regression on ordinary schedules")
    void inBracketRootUnchanged() {
        // The classroom schedule from the sample protocol: root well inside the old bracket.
        double[] lx = { 1.0, 0.8, 0.5, 0.2 }, mx = { 0, 1.5, 2.0, 1.0 };
        LifeTableRates spread = PopulationGenetics.eulerLotka(lx, mx);
        assertEquals(2.4, spread.r0(), 1e-9);
        assertEquals(1.0, euler(lx, mx, spread.rExact()), 1e-9);
        assertTrue(spread.rExact() > -5 && spread.rExact() < 5);

        // And the two hand oracles either side of replacement.
        assertEquals(Math.log(2), PopulationGenetics.eulerLotka(
                new double[]{ 1, 1 }, new double[]{ 0, 2 }).rExact(), 1e-9);
        assertEquals(0.0, PopulationGenetics.eulerLotka(
                new double[]{ 1, 0.5 }, new double[]{ 0, 2 }).rExact(), 1e-12);
    }

    @Test
    @DisplayName("a schedule with no solution is reported in plain English, not answered with ±5")
    void unsolvableScheduleIsReported() {
        // All reproduction at age 0: e^(−r·0) = 1, so the sum is the constant R0 = 3 and
        // no r solves it. The old code returned 5.0 and called it exact.
        IllegalArgumentException up = assertThrows(IllegalArgumentException.class,
                () -> PopulationGenetics.eulerLotka(new double[]{ 1, 1 }, new double[]{ 3, 0 }));
        assertTrue(up.getMessage().contains("no intrinsic rate r fits this schedule"),
                "the reason must be readable: " + up.getMessage());

        // The same shape below replacement (R0 = 0.5) is equally unsolvable.
        assertThrows(IllegalArgumentException.class,
                () -> PopulationGenetics.eulerLotka(new double[]{ 1, 1 }, new double[]{ 0.5, 0 }));

        // R0 exactly 1 at age 0 IS solvable: the population is stationary, r = 0.
        assertEquals(0.0, PopulationGenetics.eulerLotka(
                new double[]{ 1, 1 }, new double[]{ 1, 0 }).rExact(), 1e-12);
    }

    @Test
    @DisplayName("from a student's protocol file: the out-of-bracket model runs and prints one r")
    void protocolFileReportsOneRate() {
        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "phase: calm uniform 200",
                "model: eulerlotka 1:0 1:250"));
        assertEquals(1, spec.models().size());
        assertTrue(spec.problems().isEmpty());
        EcologyFieldDay.Session s = assertDoesNotThrow(() -> ExperimentLab.run(spec));
        // Both columns of the report now read the same rate.
        assertTrue(s.report().contains("r≈5.5215 (ln R0/T), r=5.5215 (exact)"),
                "the report must not print two disagreeing rates:\n" + s.report());
        assertFalse(s.report().contains("r=5.0000 (exact)"));
    }

    @Test
    @DisplayName("an unsolvable schedule in a protocol file is a reported spec problem, not a crash")
    void protocolFileReportsUnsolvableSchedule() {
        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "phase: calm uniform 200",
                "model: eulerlotka 3:1 0:0"));      // all reproduction at age 0, R0 = 3
        assertEquals(0, spec.models().size(), "the unsolvable model must not be accepted");
        assertFalse(spec.problems().isEmpty(), "it must be reported as a spec problem");
        EcologyFieldDay.Session s = assertDoesNotThrow(() -> ExperimentLab.run(spec));
        assertTrue(s.report().contains("⚠ spec:"));
    }
}
