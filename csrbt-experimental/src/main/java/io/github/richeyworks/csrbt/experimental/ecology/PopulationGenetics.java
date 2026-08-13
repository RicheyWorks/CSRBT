package io.github.richeyworks.csrbt.experimental.ecology;

/**
 * Population-genetics equations for the classroom seam (ADR-019) — the Hardy–Weinberg
 * toolkit a genetics or ecology course leans on, as pure oracle-testable functions.
 *
 * <p>One locus, two alleles (A, a). Genotype counts are observed field data; the
 * equations give allele frequencies p and q, the Hardy–Weinberg expected genotype
 * distribution (p&#xB2;, 2pq, q&#xB2;), observed and expected heterozygosity, and the
 * &#x3C7;&#xB2; goodness-of-fit statistic against HW equilibrium (df = 1 for one locus, two
 * alleles: three classes, one estimated parameter). The 5% critical value
 * {@link #CHI_SQUARE_CRITICAL_DF1} is a documented constant — a &#x3C7;&#xB2; above it reads
 * "significantly out of equilibrium," below it "consistent with equilibrium."</p>
 */
public final class PopulationGenetics {

    private PopulationGenetics() {}

    /** &#x3C7;&#xB2; critical value at &#x3B1; = 0.05, df = 1 (the HW test's df). */
    public static final double CHI_SQUARE_CRITICAL_DF1 = 3.841;

    /** The full Hardy–Weinberg analysis of observed genotype counts. */
    public record HardyWeinberg(long aaHom, long het, long aHom,
                                double p, double q,
                                double expectedAA, double expectedAa, double expectedaa,
                                double observedHet, double expectedHet,
                                double chiSquare, boolean inEquilibrium) {}

    /**
     * Analyze observed genotype counts (AA, Aa, aa). Allele frequency
     * p = (2&#xB7;AA + Aa) / 2n by allele counting; expectations are p&#xB2;n, 2pqn, q&#xB2;n;
     * &#x3C7;&#xB2; = &#x3A3;(O&#x2212;E)&#xB2;/E over the three classes (classes with E = 0 contribute 0 —
     * they can only have O = 0 when p or q is 0). Throws on an empty sample.
     */
    public static HardyWeinberg hardyWeinberg(long countAA, long countAa, long countaa) {
        if (countAA < 0 || countAa < 0 || countaa < 0) {
            throw new IllegalArgumentException("genotype counts must be non-negative");
        }
        long n = countAA + countAa + countaa;
        if (n == 0) throw new IllegalArgumentException("no individuals in the sample");

        double p = (2.0 * countAA + countAa) / (2.0 * n);
        double q = 1.0 - p;
        double eAA = p * p * n, eAa = 2.0 * p * q * n, eaa = q * q * n;

        double chi = term(countAA, eAA) + term(countAa, eAa) + term(countaa, eaa);
        return new HardyWeinberg(countAA, countAa, countaa, p, q, eAA, eAa, eaa,
                (double) countAa / n, 2.0 * p * q,
                chi, chi <= CHI_SQUARE_CRITICAL_DF1);
    }

    private static double term(long observed, double expected) {
        if (expected == 0.0) return 0.0;    // p or q is 0 ⇒ observed is necessarily 0 too
        double d = observed - expected;
        return d * d / expected;
    }

    /**
     * The Euler–Lotka life-table rates (Pianka's core calculus): from an age schedule
     * of survivorship l&#x2093; and fecundity m&#x2093; (age = array index), the net reproductive
     * rate R&#x2080; = &#x3A3; l&#x2093;m&#x2093;, generation time T = &#x3A3; x&#xB7;l&#x2093;m&#x2093; / R&#x2080;, the first-order
     * intrinsic rate r &#x2248; ln R&#x2080; / T, and the exact r solving the Euler–Lotka equation
     * &#x3A3; e^(&#x2212;rx) l&#x2093;m&#x2093; = 1 by bisection (the left side is strictly decreasing in r).
     * Requires R&#x2080; &gt; 0 (some reproduction somewhere) and equal-length schedules.
     */
    public record LifeTableRates(double r0, double generationTime,
                                 double rApprox, double rExact) {}

    public static LifeTableRates eulerLotka(double[] lx, double[] mx) {
        if (lx.length != mx.length || lx.length == 0) {
            throw new IllegalArgumentException("lx and mx must be equal-length and non-empty");
        }
        double r0 = 0, weighted = 0;
        for (int x = 0; x < lx.length; x++) {
            double lm = lx[x] * mx[x];
            if (lm < 0) throw new IllegalArgumentException("lx·mx must be non-negative at age " + x);
            r0 += lm;
            weighted += x * lm;
        }
        if (r0 <= 0) throw new IllegalArgumentException("R0 must be > 0 (no reproduction in schedule)");
        double t = weighted / r0;
        double rApprox = t == 0 ? 0.0 : Math.log(r0) / t;

        // Bisection on f(r) = Σ e^(−rx) lx mx − 1, strictly decreasing in r.
        double lo = -5, hi = 5;
        for (int i = 0; i < 200; i++) {
            double mid = (lo + hi) / 2;
            if (eulerLotkaSum(lx, mx, mid) > 1.0) lo = mid;
            else hi = mid;
        }
        return new LifeTableRates(r0, t, rApprox, (lo + hi) / 2);
    }

    private static double eulerLotkaSum(double[] lx, double[] mx, double r) {
        double s = 0;
        for (int x = 0; x < lx.length; x++) s += Math.exp(-r * x) * lx[x] * mx[x];
        return s;
    }
}
