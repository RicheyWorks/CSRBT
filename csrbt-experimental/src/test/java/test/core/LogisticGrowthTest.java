package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.LogisticGrowth;
import io.github.richeyworks.csrbt.experimental.ecology.LogisticGrowth.Fit;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Logistic growth over op time — parameter recovery on an exactly-generated curve,
 * the audit EC-2 replacement (op-count equilibrium, no wall clock), and determinism.
 */
@DisplayName("LogisticGrowth — Verhulst fit and op-count equilibrium")
class LogisticGrowthTest {

    private static final double EPS = 1e-9;

    /** Exact logistic series N(t) = K / (1 + ((K−n0)/n0)e^(−rt)), rounded to counts. */
    private static List<long[]> logisticSeries(double k, double r, double n0,
                                               long tMax, long step) {
        List<long[]> series = new ArrayList<>();
        for (long t = 0; t <= tMax; t += step) {
            double n = k / (1.0 + ((k - n0) / n0) * Math.exp(-r * t));
            series.add(new long[]{ t, Math.round(n) });
        }
        return series;
    }

    @Test
    @DisplayName("parameter recovery: r within 5% and K within 1% on a clean curve")
    void parameterRecovery() {
        double trueK = 1000, trueR = 0.01, trueN0 = 10;
        Fit fit = LogisticGrowth.fit(logisticSeries(trueK, trueR, trueN0, 1200, 60));

        assertEquals(trueR, fit.r(), trueR * 0.05);
        assertEquals(trueK, fit.carryingCapacity(), trueK * 0.01);
        assertTrue(fit.rSquared() > 0.99, "linearized fit should be near-perfect, R²=" + fit.rSquared());
        // The fitted curve reproduces the observations to within rounding + regression slack.
        for (long[] s : logisticSeries(trueK, trueR, trueN0, 1200, 60)) {
            assertEquals(s[1], fit.predict(s[0]), trueK * 0.03);
        }
    }

    @Test
    @DisplayName("growth-phase oracle: predict() is monotone and bounded by K")
    void predictionShape() {
        Fit fit = LogisticGrowth.fit(logisticSeries(500, 0.02, 5, 600, 30));
        double prev = 0;
        for (long t = 0; t <= 600; t += 30) {
            double n = fit.predict(t);
            assertTrue(n >= prev, "logistic prediction must be non-decreasing");
            assertTrue(n <= fit.carryingCapacity() + EPS, "prediction exceeded K");
            prev = n;
        }
    }

    @Test
    @DisplayName("fit contract: too few usable samples or a single t value throws")
    void fitContract() {
        assertThrows(IllegalArgumentException.class,
                () -> LogisticGrowth.fit(List.of(new long[]{ 0, 10 })));
        assertThrows(IllegalArgumentException.class,
                () -> LogisticGrowth.fit(List.of(new long[]{ 0, 0 }, new long[]{ 10, 0 })));
        assertThrows(IllegalArgumentException.class,
                () -> LogisticGrowth.fit(List.of(new long[]{ 5, 10 }, new long[]{ 5, 20 })));
    }

    // ── EC-2 replacement: deterministic equilibrium ───────────────────────────

    @Test
    @DisplayName("MacArthur–Wilson equilibrium on op counts: I=E → P/2, E=0 → P, I=0 → 0")
    void equilibriumOracles() {
        assertEquals(50.0,  LogisticGrowth.equilibriumSize(700, 700, 100), EPS);
        assertEquals(100.0, LogisticGrowth.equilibriumSize(300, 0, 100), EPS);
        assertEquals(0.0,   LogisticGrowth.equilibriumSize(0, 300, 100), EPS);
        assertEquals(0.0,   LogisticGrowth.equilibriumSize(0, 0, 100), EPS);
        assertEquals(75.0,  LogisticGrowth.equilibriumSize(300, 100, 100), EPS);
        assertThrows(IllegalArgumentException.class,
                () -> LogisticGrowth.equilibriumSize(-1, 5, 100));
    }

    @Test
    @DisplayName("determinism: identical series give bitwise-identical fits")
    void determinism() {
        List<long[]> series = logisticSeries(800, 0.015, 8, 900, 45);
        Fit a = LogisticGrowth.fit(series);
        Fit b = LogisticGrowth.fit(series);
        assertEquals(a.r(), b.r());
        assertEquals(a.carryingCapacity(), b.carryingCapacity());
        assertEquals(a.n0(), b.n0());
        assertEquals(a.rSquared(), b.rSquared());
    }
}
