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
     *
     * @throws IllegalArgumentException if either rate is negative (see {@link #rates})
     */
    public static double levinsEquilibrium(double c, double e) {
        rates(c, e);
        if (c <= 0) return 0.0;
        return Math.max(0.0, Math.min(1.0, 1.0 - e / c));
    }

    /**
     * Colonization and extinction are rates per survey interval — the fraction of patches that
     * gain or lose an occupant — so neither can be negative, and both models built on them reject
     * one rather than answering.
     *
     * <p>Before this, {@code e = -1} made Levins' p* = 1 &#x2212; e/c evaluate to <b>3.5</b>, which
     * the clamp then turned into a confident {@code p* = 1.0000}: "every patch occupied", printed
     * with no hint that the input was meaningless (frontend verification 2026-08-17, J5). The same
     * pair drives the island model, where a negative rate is worse still — it flips
     * e^(&#x2212;(c+e)t) from decay to growth, so the trajectory runs off the end of the number
     * line and used to write the bare token {@code Infinity} into {@code session.json}. One rule
     * for both, reported at the point the nonsense enters rather than absorbed by a clamp.</p>
     *
     * <p><b>Consumers.</b> {@code EnsembleCommunity.levinsEquilibrium()} is a different method
     * measuring an ensemble and is unaffected; the {@code .eco} path reports a negative rate as a
     * {@code ⚠ spec:} problem at parse time. The lab page mirrors this arithmetic and needs the
     * matching guard — routed separately.</p>
     */
    private static void rates(double c, double e) {
        if (!(c >= 0)) {
            throw new IllegalArgumentException("colonization rate c must be >= 0 (a rate is a "
                    + "fraction of patches per survey interval), got " + fmt(c));
        }
        if (!(e >= 0)) {
            throw new IllegalArgumentException("extinction rate e must be >= 0 (a rate is a "
                    + "fraction of patches per survey interval), got " + fmt(e));
        }
    }

    /**
     * Occupancy trajectory of dp/dt = c&#xB7;p(1&#x2212;p) &#x2212; e&#xB7;p, integrated with unit-step
     * Euler (dt = 1, the survey interval), state clamped to [0, 1] each step. Returns
     * {@code steps + 1} points including t = 0. Rates are per survey interval; keep
     * c and e modest (&#x2264; 1) for a faithful walk — the classroom regime.
     *
     * @throws IllegalArgumentException if {@code steps < 0} or either rate is negative
     *         (see {@link #rates})
     */
    public static double[][] levinsTrajectory(double c, double e, double p0, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        rates(c, e);
        double[][] out = new double[steps + 1][];
        double p = Math.max(0.0, Math.min(1.0, p0));
        for (int t = 0; t <= steps; t++) {
            out[t] = new double[]{ t, p };
            p += c * p * (1.0 - p) - e * p;
            p = Math.max(0.0, Math.min(1.0, p));
        }
        return representable("Levins occupancy", "c=" + fmt(c) + " e=" + fmt(e), out);
    }

    // ── Verhulst logistic growth (1838) ───────────────────────────────────────

    /**
     * Population trajectory N(t) = K / (1 + ((K&#x2212;N&#x2080;)/N&#x2080;)&#xB7;e^(&#x2212;rt)) — the exact
     * closed-form solution, no integration error. N&#x2080; &#x2264; 0 pins the trajectory at 0
     * (extinct populations stay extinct). Returns {@code steps + 1} points.
     *
     * <p>The carrying capacity must be positive: the logistic law divides by K, and the closed
     * form's denominator {@code 1 + (K&#x2212;N&#x2080;)/N&#x2080;} is exactly {@code K/N&#x2080;},
     * so {@code K = 0} evaluates 0/0 at t = 0 and produced a {@code NaN} as the trajectory's very
     * first point — which then reached {@code session.json} as the bare token {@code NaN}, invalid
     * JSON that the lab page cannot parse at all (edge-case pass 2026-08-17). A habitat with no
     * capacity is a question about the input, not an answer, so it is reported.</p>
     *
     * @throws IllegalArgumentException if {@code steps < 0} or {@code k <= 0}
     */
    public static double[][] logisticTrajectory(double r, double k, double n0, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        if (!(k > 0)) throw new IllegalArgumentException("carrying capacity K must be > 0");
        double[][] out = new double[steps + 1][];
        for (int t = 0; t <= steps; t++) {
            double n = n0 <= 0 ? 0.0
                    : k / (1.0 + ((k - n0) / n0) * Math.exp(-r * t));
            out[t] = new double[]{ t, n };
        }
        return representable("logistic growth", "r=" + fmt(r) + " K=" + fmt(k), out);
    }

    // ── MacArthur–Wilson island colonization (1967) ───────────────────────────

    /**
     * Equilibrium island richness S* = c/(c + e) &#xB7; pool; 0 when both rates are 0.
     */
    public static double islandEquilibrium(double c, double e, double pool) {
        rates(c, e);
        if (c + e <= 0) return 0.0;
        return c / (c + e) * pool;
    }

    /**
     * Richness trajectory of the colonization model dS/dt = c&#xB7;(P&#x2212;S) &#x2212; e&#xB7;S — exact
     * closed form S(t) = S* + (S&#x2080; &#x2212; S*)&#xB7;e^(&#x2212;(c+e)t). An empty island rises toward
     * S*, an overfull one relaxes down to it; the approach rate (c + e) is the
     * turnover the {@link CacheIsland} instrument measures. Returns {@code steps + 1}
     * points.
     *
     * @throws IllegalArgumentException if {@code steps < 0} or either rate is negative
     *         (see {@link #rates}); a negative rate turns the relaxation term into growth
     */
    public static double[][] islandTrajectory(double c, double e, double pool,
                                              double s0, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        rates(c, e);
        double sStar = islandEquilibrium(c, e, pool);
        double[][] out = new double[steps + 1][];
        for (int t = 0; t <= steps; t++) {
            out[t] = new double[]{ t, sStar + (s0 - sStar) * Math.exp(-(c + e) * t) };
        }
        // c + e < 0 turns the relaxation term e^(-(c+e)t) into growth, so an island with a
        // negative rate runs away exactly as exponential does.
        return representable("island colonization", "c=" + fmt(c) + " e=" + fmt(e), out);
    }

    // ── Exponential growth (the pre-logistic baseline) ────────────────────────

    /** N(t) = N&#x2080;&#xB7;e^(rt), exact. The curve every density-dependent model is compared against.
     *
     * <p>Exponential growth is the model that runs out of {@code double} first, and it does so from
     * an ordinary classroom line: {@code model: exponential 0.7 1 1200} — "bacteria doubling" —
     * passes 1.8e308 at step 1014 and every point after it is {@code Infinity}. That token is not
     * JSON, so the {@code session.json} it reached could not be parsed at all and the lab page
     * refused to open the whole session (frontend verification 2026-08-17, J1). Same failure the
     * K&nbsp;&#x2264;&nbsp;0 {@code NaN} produced; same answer — a run that leaves the number line
     * is a question about the input, not a trajectory, so it is
     * {@linkplain #representable reported}.</p>
     *
     * @throws IllegalArgumentException if {@code steps < 0}, or if the trajectory leaves the range
     *         of a {@code double}
     */
    public static double[][] exponentialTrajectory(double r, double n0, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        double[][] out = new double[steps + 1][];
        for (int t = 0; t <= steps; t++) {
            out[t] = new double[]{ t, n0 * Math.exp(r * t) };
        }
        return representable("exponential growth", "r=" + fmt(r) + " N0=" + fmt(n0), out);
    }

    // ── The one place a trajectory becomes an answer ──────────────────────────

    /**
     * Every point of a trajectory must be a real number, or the trajectory is not an answer.
     *
     * <p>A non-finite point is unusable in every direction at once: it cannot be plotted, it cannot
     * be compared against an equilibrium, and — the failure that made this a defect rather than a
     * curiosity — {@code ExperimentLab} writes series with {@code %.4f}, which renders it as the
     * bare token {@code Infinity} or {@code NaN}. Neither is JSON, so one out-of-range model makes
     * the entire {@code session.json} unparseable and the lab page cannot open the session at all.
     * Three models can reach it from spec-legal parameters — {@code exponential} (any r&#xB7;steps
     * past ~710), {@code island} (c&nbsp;+&nbsp;e&nbsp;&lt;&nbsp;0, where the relaxation term
     * grows instead of decaying) and {@code predation} (a negative rate turning the Euler walk
     * divergent) — which is why this is a shared gate on the model layer rather than a guard bolted
     * onto the one model that was noticed first.</p>
     *
     * <p>Reported, not clamped: pinning the curve at {@code Double.MAX_VALUE} or truncating it at
     * the last finite step would both answer a question the parameters did not ask, silently. The
     * message names the step where it happens so the student can shorten the run or lower the rate.</p>
     */
    private static double[][] representable(String model, String params, double[][] series) {
        for (double[] point : series) {
            if (!Double.isFinite(point[1])) {
                throw new IllegalArgumentException(model + " with " + params
                        + " leaves the range of a double at step " + (int) point[0] + " ("
                        + (Double.isNaN(point[1]) ? "the value there is not a number"
                                                  : "the value there is past ±1.8e308")
                        + ") — shorten the run or use gentler rates");
            }
        }
        return series;
    }

    /** {@link #representable} for the two-series models; both are one answer, so both must hold. */
    private static double[][][] representable(String model, String params, double[][][] pair) {
        representable(model, params, pair[0]);
        representable(model, params, pair[1]);
        return pair;
    }

    /** Rates read back the way a student wrote them, for the messages above. */
    private static String fmt(double v) {
        return v == Math.rint(v) && Math.abs(v) < 1e15
                ? String.valueOf((long) v)
                : String.format(java.util.Locale.ROOT, "%s", v);
    }

    // ── Lotka–Volterra competition (the biotic factor, Pianka ch. 12) ─────────

    /**
     * Two-species Lotka–Volterra competition:
     * dN&#x2081;/dt = r&#x2081;N&#x2081;(1 &#x2212; (N&#x2081; + &#x3B1;&#x2081;&#x2082;N&#x2082;)/K&#x2081;), symmetric for species 2.
     * Integrated with Euler substeps (dt = 0.1, ten per reported unit step, a
     * documented constant chosen for stability at classroom rates r &#x2264; 1).
     * Returns two trajectories: {@code [0]} = species 1, {@code [1]} = species 2,
     * each {@code {t, N}} with {@code steps + 1} points. Populations clamp at 0.
     *
     * <p>Both carrying capacities must be positive, for the reason
     * {@link #logisticTrajectory} states: the competition term divides by K, so a zero capacity
     * turned <em>every</em> point of both series into {@code NaN} and wrote invalid JSON into
     * {@code session.json} (edge-case pass 2026-08-17).</p>
     *
     * @throws IllegalArgumentException if {@code steps < 0} or either capacity is {@code <= 0}
     */
    public static double[][][] competitionTrajectories(double r1, double k1,
                                                       double r2, double k2,
                                                       double a12, double a21,
                                                       double n1, double n2, int steps) {
        if (steps < 0) throw new IllegalArgumentException("steps must be >= 0");
        if (!(k1 > 0)) throw new IllegalArgumentException("carrying capacity K1 must be > 0");
        if (!(k2 > 0)) throw new IllegalArgumentException("carrying capacity K2 must be > 0");
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
        return representable("Lotka–Volterra competition",
                "r1=" + fmt(r1) + " K1=" + fmt(k1) + " r2=" + fmt(r2) + " K2=" + fmt(k2),
                new double[][][]{ s1, s2 });
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
        return representable("Lotka–Volterra predation",
                "r=" + fmt(r) + " a=" + fmt(a) + " b=" + fmt(b) + " m=" + fmt(m),
                new double[][][]{ prey, pred });
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
