package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.Locale;

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
     * &#x3A3; e^(&#x2212;rx) l&#x2093;m&#x2093; = 1 by bisection (the left side is non-increasing in r).
     * Requires R&#x2080; &gt; 0 (some reproduction somewhere) and equal-length schedules.
     * Schedules for which no r solves the equation are reported, never approximated —
     * see {@link #eulerLotka(double[], double[])}.
     */
    public record LifeTableRates(double r0, double generationTime,
                                 double rApprox, double rExact) {}

    /**
     * Widest |r| the bracket search will consider. Past this the exponential
     * e^(&#x2212;rx) has left the double range entirely (e^700 &#x2248; 1e304), so a root beyond
     * it cannot be located at all — and no life table a course hands out comes close:
     * r = &#xB1;700 per age class is R&#x2080; of 1e304 or 1e&#x2212;304 in one generation.
     */
    public static final double R_BRACKET_CAP = 700.0;

    /**
     * @throws IllegalArgumentException if the schedules disagree in length, are empty,
     *         carry a negative l&#x2093;m&#x2093;, have R&#x2080; = 0, or admit no intrinsic rate at all
     *         (all reproduction at age 0 with R&#x2080; &#x2260; 1 — that term is never discounted
     *         by r, so &#x3A3; e^(&#x2212;rx) l&#x2093;m&#x2093; can never reach 1)
     */
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

        // Σ e^(−rx) lx mx at r = 0 IS R0, so an exactly-replacing schedule solves the
        // equation at r = 0 — exactly, and without a search that would have to bisect
        // a flat function when all the reproduction sits at age 0.
        double rExact = r0 == 1.0 ? 0.0 : solveEulerLotka(lx, mx);
        return new LifeTableRates(r0, t, rApprox, rExact);
    }

    /**
     * Bisection on f(r) = &#x3A3; e^(&#x2212;rx) l&#x2093;m&#x2093; &#x2212; 1, non-increasing in r, over a bracket
     * expanded until it actually contains the root.
     *
     * <p>The bracket used to be a hardcoded [&#x2212;5, +5] with no containment check, so any
     * schedule whose root lay outside it got the nearest endpoint back, labelled "exact"
     * (audit 2026-08-17 #16: l&#x2093; = {1,1}, m&#x2093; = {0,250} has r = ln 250 = 5.5215 and the
     * bisection reported 5.0000, side by side with a correct r &#x2248; 5.5215). A schedule with
     * no root at all — all reproduction at age 0, where e^(&#x2212;r&#xB7;0) = 1 leaves the term
     * untouched by r — now says so instead of returning a bracket end.</p>
     */
    private static double solveEulerLotka(double[] lx, double[] mx) {
        double lo = -5, hi = 5;
        while (eulerLotkaSum(lx, mx, hi) > 1.0 && hi < R_BRACKET_CAP) {
            hi = Math.min(hi * 2, R_BRACKET_CAP);
        }
        while (eulerLotkaSum(lx, mx, lo) < 1.0 && lo > -R_BRACKET_CAP) {
            lo = Math.max(lo * 2, -R_BRACKET_CAP);
        }
        boolean high = eulerLotkaSum(lx, mx, hi) > 1.0;
        if (high || eulerLotkaSum(lx, mx, lo) < 1.0) {
            throw new IllegalArgumentException(String.format(Locale.ROOT,
                    "no intrinsic rate r fits this schedule: Σ e^(−rx)·lx·mx is still %s 1 "
                    + "at r = %+.0f, so it never crosses 1. This happens when the reproduction "
                    + "sits at age 0, which r cannot discount (e^0 = 1) — such a schedule has "
                    + "a solution only when R0 is exactly 1.",
                    high ? "above" : "below", high ? R_BRACKET_CAP : -R_BRACKET_CAP));
        }
        for (int i = 0; i < 200; i++) {
            double mid = (lo + hi) / 2;
            if (eulerLotkaSum(lx, mx, mid) > 1.0) lo = mid;
            else hi = mid;
        }
        return (lo + hi) / 2;
    }

    private static double eulerLotkaSum(double[] lx, double[] mx, double r) {
        double s = 0;
        for (int x = 0; x < lx.length; x++) s += Math.exp(-r * x) * lx[x] * mx[x];
        return s;
    }
}
