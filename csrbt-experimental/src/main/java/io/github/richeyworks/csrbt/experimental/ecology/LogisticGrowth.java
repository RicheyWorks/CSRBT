package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.List;

/**
 * Logistic (Verhulst 1838) population-growth fit over the op-indexed size series, plus
 * the deterministic replacement for {@code TreeEcology.colonizationEquilibrium} (audit
 * EC-2: the original derives rates from wall-clock ms — nondeterministic; house rule is
 * that deterministic meters decide).
 *
 * <p>The logistic model: dN/dt = rN(1 &#x2212; N/K), whose solution is
 * N(t) = K / (1 + ((K &#x2212; N&#x2080;)/N&#x2080;) e^(&#x2212;rt)). Fitting uses the standard
 * linearization: ln(N / (K &#x2212; N)) = ln(N&#x2080; / (K &#x2212; N&#x2080;)) + r&#xB7;t is linear in t, so with
 * K fixed the intrinsic rate r and N&#x2080; drop out of an ordinary least-squares line.
 * K is taken as max(N) + 0.5 — a half-count continuity nudge so the logit is finite at
 * the observed plateau; documented, fixed, deterministic.</p>
 *
 * <p>Time is the op index throughout ({@link EcologyRecorder#populationSeries()});
 * nothing here reads a clock.</p>
 */
public final class LogisticGrowth {

    private LogisticGrowth() {}

    /** Continuity nudge added to max(N) so the observed maximum has a finite logit. */
    public static final double K_NUDGE = 0.5;

    /**
     * A fitted logistic curve: intrinsic growth rate r (per op), carrying capacity K,
     * initial size n&#x2080; (at t = 0), and R&#xB2; of the linearized regression.
     */
    public record Fit(double r, double carryingCapacity, double n0, double rSquared) {

        /** N(t) under this fit. */
        public double predict(double t) {
            double k = carryingCapacity;
            if (n0 <= 0) return 0.0;
            return k / (1.0 + ((k - n0) / n0) * Math.exp(-r * t));
        }
    }

    /**
     * Fit the logistic model to a series of {@code {t, N}} samples (op index, population).
     * Samples with N &#x2264; 0 are skipped (logit undefined). Needs &#x2265; 2 usable samples with
     * distinct t; throws {@link IllegalArgumentException} otherwise.
     */
    public static Fit fit(List<long[]> series) {
        long maxN = 0;
        for (long[] s : series) maxN = Math.max(maxN, s[1]);
        double k = maxN + K_NUDGE;

        // Ordinary least squares on y = ln(N/(K−N)) against t.
        int m = 0;
        double sumT = 0, sumY = 0, sumTT = 0, sumTY = 0;
        for (long[] s : series) {
            long nVal = s[1];
            if (nVal <= 0) continue;
            double t = s[0];
            double y = Math.log(nVal / (k - nVal));
            m++;
            sumT += t;
            sumY += y;
            sumTT += t * t;
            sumTY += t * y;
        }
        if (m < 2) throw new IllegalArgumentException("need >= 2 samples with N > 0");
        double denom = m * sumTT - sumT * sumT;
        if (denom == 0.0) throw new IllegalArgumentException("need >= 2 distinct t values");

        double r = (m * sumTY - sumT * sumY) / denom;
        double a = (sumY - r * sumT) / m; // intercept = ln(n0/(K−n0))
        double n0 = k / (1.0 + Math.exp(-a));

        // R² of the linearized regression.
        double meanY = sumY / m;
        double ssTot = 0, ssRes = 0;
        for (long[] s : series) {
            long nVal = s[1];
            if (nVal <= 0) continue;
            double y = Math.log(nVal / (k - nVal));
            double yHat = a + r * s[0];
            ssTot += (y - meanY) * (y - meanY);
            ssRes += (y - yHat) * (y - yHat);
        }
        double r2 = ssTot == 0.0 ? 1.0 : 1.0 - ssRes / ssTot;
        return new Fit(r, k, n0, r2);
    }

    /**
     * MacArthur–Wilson immigration/extinction equilibrium S* = I/(I + E) &#xB7; P, with the
     * rates measured as <b>op counts</b> — inserts and removes observed — instead of the
     * wall-clock inverses the original used (EC-2). No ops observed &#x2192; 0 (no
     * colonization evidence yet).
     *
     * @param insertOps   inserts observed (immigration events)
     * @param removeOps   removes observed (extinction events)
     * @param speciesPool the mainland pool size P
     */
    public static double equilibriumSize(long insertOps, long removeOps, long speciesPool) {
        if (insertOps < 0 || removeOps < 0) throw new IllegalArgumentException("negative op count");
        long total = insertOps + removeOps;
        if (total == 0) return 0.0;
        return ((double) insertOps / total) * speciesPool;
    }
}
