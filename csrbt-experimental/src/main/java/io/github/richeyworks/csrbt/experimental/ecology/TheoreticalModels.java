package io.github.richeyworks.csrbt.experimental.ecology;

/**
 * The theory side of the classroom seam (ADR-019): pure trajectory generators for the
 * three population models this layer already measures against, so a student can run a
 * <em>theoretical</em> experiment — "what does the model say happens?" — and lay the
 * curve next to what the simulated habitat actually did. Every function is pure,
 * deterministic, and closed-form where the model has one; the one numerical
 * integration (Levins) is a documented unit-step Euler walk with the state clamped to
 * its meaningful range.
 *
 * <p>Trajectories return {@code {t, value}} pairs, ready for the lab page's line
 * charts and for side-by-side comparison with {@link EcologyRecorder} series.</p>
 */
public final class TheoreticalModels {

    private TheoreticalModels() {}

    // ── Levins metapopulation (1969) ──────────────────────────────────────────

    /**
     * Equilibrium patch occupancy p* = 1 &#x2212; e/c, clamped to [0, 1]; defined as 0
     * when c &#x2264; 0 (no colonization, the metapopulation empties).
     */
    public static double levinsEquilibrium(double c, double e) {
        if (c <= 0) return 0.0;
        return Math.max(0.0, Math.min(1.0, 1.0 - e / c));
    }

    /**
     * Occupancy trajectory of dp/dt = c&#xB7;p(1&#x2212;p) &#x2212; e&#xB7;p, integrated with unit-step
     * Euler (dt = 1, the survey interval), state clamped to [0, 1] each step. Returns
     * {@code steps + 1} points including t = 0. Rates are per survey interval; keep
     * c and e modest (&#x2264; 1) for a faithful walk — the classroom regime.
     */
    public static double[][] levinsTrajectory(double c, double e, double p0, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        double[][] out = new double[steps + 1][];
        double p = Math.max(0.0, Math.min(1.0, p0));
        for (int t = 0; t <= steps; t++) {
            out[t] = new double[]{ t, p };
            p += c * p * (1.0 - p) - e * p;
            p = Math.max(0.0, Math.min(1.0, p));
        }
        return out;
    }

    // ── Verhulst logistic growth (1838) ───────────────────────────────────────

    /**
     * Population trajectory N(t) = K / (1 + ((K&#x2212;N&#x2080;)/N&#x2080;)&#xB7;e^(&#x2212;rt)) — the exact
     * closed-form solution, no integration error. N&#x2080; &#x2264; 0 pins the trajectory at 0
     * (extinct populations stay extinct). Returns {@code steps + 1} points.
     */
    public static double[][] logisticTrajectory(double r, double k, double n0, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        double[][] out = new double[steps + 1][];
        for (int t = 0; t <= steps; t++) {
            double n = n0 <= 0 ? 0.0
                    : k / (1.0 + ((k - n0) / n0) * Math.exp(-r * t));
            out[t] = new double[]{ t, n };
        }
        return out;
    }

    // ── MacArthur–Wilson island colonization (1967) ───────────────────────────

    /**
     * Equilibrium island richness S* = c/(c + e) &#xB7; pool; 0 when both rates are 0.
     */
    public static double islandEquilibrium(double c, double e, double pool) {
        if (c + e <= 0) return 0.0;
        return c / (c + e) * pool;
    }

    /**
     * Richness trajectory of the colonization model dS/dt = c&#xB7;(P&#x2212;S) &#x2212; e&#xB7;S — exact
     * closed form S(t) = S* + (S&#x2080; &#x2212; S*)&#xB7;e^(&#x2212;(c+e)t). An empty island rises toward
     * S*, an overfull one relaxes down to it; the approach rate (c + e) is the
     * turnover the {@link CacheIsland} instrument measures. Returns {@code steps + 1}
     * points.
     */
    public static double[][] islandTrajectory(double c, double e, double pool,
                                              double s0, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        double sStar = islandEquilibrium(c, e, pool);
        double[][] out = new double[steps + 1][];
        for (int t = 0; t <= steps; t++) {
            out[t] = new double[]{ t, sStar + (s0 - sStar) * Math.exp(-(c + e) * t) };
        }
        return out;
    }

    // ── Exponential growth (the pre-logistic baseline) ────────────────────────

    /** N(t) = N&#x2080;&#xB7;e^(rt), exact. The curve every density-dependent model is compared against. */
    public static double[][] exponentialTrajectory(double r, double n0, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        double[][] out = new double[steps + 1][];
        for (int t = 0; t <= steps; t++) {
            out[t] = new double[]{ t, n0 * Math.exp(r * t) };
        }
        return out;
    }

    // ── Lotka–Volterra competition (the biotic factor, Pianka ch. 12) ─────────

    /**
     * Two-species Lotka–Volterra competition:
     * dN&#x2081;/dt = r&#x2081;N&#x2081;(1 &#x2212; (N&#x2081; + &#x3B1;&#x2081;&#x2082;N&#x2082;)/K&#x2081;), symmetric for species 2.
     * Integrated with Euler substeps (dt = 0.1, ten per reported unit step, a
     * documented constant chosen for stability at classroom rates r &#x2264; 1).
     * Returns two trajectories: {@code [0]} = species 1, {@code [1]} = species 2,
     * each {@code {t, N}} with {@code steps + 1} points. Populations clamp at 0.
     */
    public static double[][][] competitionTrajectories(double r1, double k1,
                                                       double r2, double k2,
                                                       double a12, double a21,
                                                       double n1, double n2, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        double[][] s1 = new double[steps + 1][], s2 = new double[steps + 1][];
        double x = Math.max(0, n1), y = Math.max(0, n2);
        for (int t = 0; t <= steps; t++) {
            s1[t] = new double[]{ t, x };
            s2[t] = new double[]{ t, y };
            for (int sub = 0; sub < 10; sub++) {
                double dx = r1 * x * (1 - (x + a12 * y) / k1) * 0.1;
                double dy = r2 * y * (1 - (y + a21 * x) / k2) * 0.1;
                x = Math.max(0, x + dx);
                y = Math.max(0, y + dy);
            }
        }
        return new double[][][]{ s1, s2 };
    }

    // ── Lotka–Volterra predation ──────────────────────────────────────────────

    /**
     * Predator–prey: dN/dt = rN &#x2212; aNP, dP/dt = baNP &#x2212; mP. Integrated with Euler
     * substeps (dt = 0.01, one hundred per reported unit step — the classic cycles
     * are stiff and coarse Euler spirals them; this resolution keeps classroom
     * parameter ranges faithful). Returns {@code [0]} = prey, {@code [1]} = predator.
     */
    public static double[][][] predationTrajectories(double r, double a, double b,
                                                     double m, double n0, double p0,
                                                     int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        double[][] prey = new double[steps + 1][], pred = new double[steps + 1][];
        double n = Math.max(0, n0), p = Math.max(0, p0);
        for (int t = 0; t <= steps; t++) {
            prey[t] = new double[]{ t, n };
            pred[t] = new double[]{ t, p };
            for (int sub = 0; sub < 100; sub++) {
                double dn = (r * n - a * n * p) * 0.01;
                double dp = (b * a * n * p - m * p) * 0.01;
                n = Math.max(0, n + dn);
                p = Math.max(0, p + dp);
            }
        }
        return new double[][][]{ prey, pred };
    }

    // ── Abiotic environment (the MacArthur habitat knobs) ─────────────────────

    /**
     * Abiotic factors for an experiment, with documented multiplicative conventions
     * (see the method docs): <b>area</b> (habitat/pond size, default 1), <b>temperature</b>
     * (rate multiplier, default 1), <b>wind</b> (dispersal multiplier, default 1),
     * and <b>distance</b> (isolation, default 0 — no decay).
     */
    public record Environment(double area, double temperature, double wind, double distance) {
        public static final Environment NEUTRAL = new Environment(1, 1, 1, 0);
        public Environment {
            if (area <= 0) throw new IllegalArgumentException("area must be > 0");
            if (temperature < 0 || wind < 0 || distance < 0) {
                throw new IllegalArgumentException("temperature, wind, distance must be >= 0");
            }
        }
        /** Colonization/immigration under this environment: c&#xB7;wind&#xB7;temperature&#xB7;e^(&#x2212;distance). */
        public double colonization(double c) {
            return c * wind * temperature * Math.exp(-distance);
        }
        /** Extinction under this environment: e / area — bigger habitats buffer loss. */
        public double extinction(double e) {
            return e / area;
        }
        /** Growth rate under this environment: r&#xB7;temperature. */
        public double growth(double r) {
            return r * temperature;
        }
        /** Carrying capacity under this environment: K&#xB7;area — a small pond holds less. */
        public double capacity(double k) {
            return k * area;
        }
    }
}
