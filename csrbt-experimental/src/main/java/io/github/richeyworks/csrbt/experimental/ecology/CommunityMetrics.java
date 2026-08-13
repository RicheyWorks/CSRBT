package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Within-community diversity indices, computed on a real abundance distribution
 * (per-key access counts from {@link EcologyRecorder}) rather than on stored keys —
 * which is what makes them measurements instead of the constants documented in the
 * 2026-08-09 ecology audit (EC-1).
 *
 * <p>All standard first-course community-ecology material, each formula cited at the
 * method. Every function here is pure and static — same input map, same double, bit for
 * bit — so the whole class is oracle-testable with hand-built vectors, the same
 * discipline the {@code StrategyScorer} follows.</p>
 *
 * <p>Conventions: a "species" is a key with abundance &gt; 0; entries with count
 * &#x2264; 0 are ignored. Natural log throughout (nats), matching {@code TreeEcology}.</p>
 */
public final class CommunityMetrics {

    private CommunityMetrics() {}

    // ── Richness & totals ─────────────────────────────────────────────────────

    /** Species richness S — count of keys with abundance &gt; 0 (Margalef 1958). */
    public static <T> int richness(Map<T, Long> abundance) {
        int s = 0;
        for (long c : abundance.values()) if (c > 0) s++;
        return s;
    }

    /** Total individuals N — sum of abundances. */
    public static <T> long total(Map<T, Long> abundance) {
        long n = 0;
        for (long c : abundance.values()) if (c > 0) n += c;
        return n;
    }

    // ── Shannon family (Shannon 1948; Pielou 1966) ────────────────────────────

    /** Shannon diversity H&#x2032; = &#x2212;&#x3A3; p&#x1D62; ln p&#x1D62;. Empty community &#x2192; 0. */
    public static <T> double shannon(Map<T, Long> abundance) {
        long n = total(abundance);
        if (n == 0) return 0.0;
        double h = 0.0;
        for (long c : abundance.values()) {
            if (c <= 0) continue;
            double p = (double) c / n;
            h -= p * Math.log(p);
        }
        return h;
    }

    /**
     * Pielou's evenness J&#x2032; = H&#x2032; / ln S (Pielou 1966). J&#x2032; = 1 &#x2192; perfectly even,
     * &#x2192; 0 as one species dominates. Defined here as 1.0 for S &#x2264; 1 (a one-species
     * community is trivially even).
     */
    public static <T> double pielouEvenness(Map<T, Long> abundance) {
        int s = richness(abundance);
        if (s <= 1) return 1.0;
        return shannon(abundance) / Math.log(s);
    }

    // ── Simpson family (Simpson 1949) ─────────────────────────────────────────

    /** Simpson's index D = &#x3A3; p&#x1D62;&#xB2; — probability two random draws are the same species. */
    public static <T> double simpsonIndex(Map<T, Long> abundance) {
        long n = total(abundance);
        if (n == 0) return 0.0;
        double d = 0.0;
        for (long c : abundance.values()) {
            if (c <= 0) continue;
            double p = (double) c / n;
            d += p * p;
        }
        return d;
    }

    /** Gini–Simpson diversity 1 &#x2212; D. */
    public static <T> double simpsonDiversity(Map<T, Long> abundance) {
        long n = total(abundance);
        return n == 0 ? 0.0 : 1.0 - simpsonIndex(abundance);
    }

    /** Inverse Simpson 1/D — the "effective number of dominant species". Empty &#x2192; 0. */
    public static <T> double inverseSimpson(Map<T, Long> abundance) {
        double d = simpsonIndex(abundance);
        return d == 0.0 ? 0.0 : 1.0 / d;
    }

    // ── Hill numbers (Hill 1973) ──────────────────────────────────────────────

    /**
     * Hill number &#x1D48;D = (&#x3A3; p&#x1D62;&#x1D68;)^(1/(1&#x2212;q)) — the unified "effective species count"
     * family: q = 0 &#x2192; richness, q &#x2192; 1 &#x2192; exp(H&#x2032;), q = 2 &#x2192; inverse Simpson.
     * The q = 1 limit is taken analytically (|q &#x2212; 1| &lt; 1e-9).
     */
    public static <T> double hillNumber(Map<T, Long> abundance, double q) {
        long n = total(abundance);
        if (n == 0) return 0.0;
        if (Math.abs(q - 1.0) < 1e-9) return Math.exp(shannon(abundance));
        double sum = 0.0;
        for (long c : abundance.values()) {
            if (c <= 0) continue;
            double p = (double) c / n;
            sum += Math.pow(p, q);
        }
        if (q == 0.0) return sum; // p^0 = 1 per species → richness
        return Math.pow(sum, 1.0 / (1.0 - q));
    }

    // ── Richness estimation (Chao 1984; Hurlbert 1971) ────────────────────────

    /**
     * Chao1 estimated true richness &#x15C;: how many species the survey likely missed,
     * inferred from how many were seen exactly once (F&#x2081;) or twice (F&#x2082;).
     * Classic form &#x15C; = S + F&#x2081;&#xB2;/(2F&#x2082;) when F&#x2082; &gt; 0; the bias-corrected form
     * S + F&#x2081;(F&#x2081;&#x2212;1)/2 when F&#x2082; = 0 (Chao 1984). No singletons &#x2192; the survey is
     * complete as far as this estimator can tell (&#x15C; = S).
     */
    public static <T> double chao1(Map<T, Long> abundance) {
        int s = richness(abundance);
        long f1 = 0, f2 = 0;
        for (long c : abundance.values()) {
            if (c == 1) f1++;
            else if (c == 2) f2++;
        }
        if (f1 == 0) return s;
        if (f2 > 0) return s + (double) (f1 * f1) / (2.0 * f2);
        return s + (double) (f1 * (f1 - 1)) / 2.0;
    }

    /**
     * Rarefied richness E[S&#x2098;] (Hurlbert 1971): the expected number of species in a
     * random subsample of {@code m} individuals — the fair way to compare richness
     * across surveys of different effort. Exact hypergeometric expectation:
     * E[S&#x2098;] = &#x3A3;&#x1D62; (1 &#x2212; C(N&#x2212;N&#x1D62;, m)/C(N, m)), computed in log space.
     * m &#x2265; N returns S; m &#x2264; 0 or an empty community returns 0.
     */
    public static <T> double rarefiedRichness(Map<T, Long> abundance, long m) {
        long n = total(abundance);
        if (m <= 0 || n == 0) return 0.0;
        if (m >= n) return richness(abundance);
        double expected = 0.0;
        for (long c : abundance.values()) {
            if (c <= 0) continue;
            if (n - c < m) {          // subsample cannot avoid this species
                expected += 1.0;
                continue;
            }
            // ln[ C(n−c, m) / C(n, m) ] = Σ_{j=0}^{c−1} ln((n−m−j)/(n−j)) — the product
            // over the species' abundance (c terms), not the subsample size (m terms):
            // Σc = N, so a whole curve point costs O(N) instead of O(S·m). The hardening
            // audit measured the m-term form at 34 s for a 50k-op trace; this form is
            // milliseconds. Guard above ⇒ n−m ≥ c ⇒ every factor is positive.
            double logAbsent = 0.0;
            for (long j = 0; j < c; j++) {
                logAbsent += Math.log((double) (n - m - j) / (n - j));
            }
            expected += 1.0 - Math.exp(logAbsent);
        }
        return expected;
    }

    /**
     * A rarefaction curve: {@code points} evenly spaced subsample sizes from N/points
     * up to N, each with its E[S&#x2098;] — the classic species-vs-effort curve. Returns
     * {@code {m, E[S_m]}} pairs; empty community &#x2192; empty array.
     */
    public static <T> double[][] rarefactionCurve(Map<T, Long> abundance, int points) {
        if (points < 1) throw new IllegalArgumentException("points must be >= 1");
        long n = total(abundance);
        if (n == 0) return new double[0][];
        double[][] out = new double[points][];
        for (int i = 1; i <= points; i++) {
            long m = Math.max(1, Math.round((double) n * i / points));
            out[i - 1] = new double[]{ m, rarefiedRichness(abundance, m) };
        }
        return out;
    }

    // ── Rank–abundance (Whittaker 1965) ───────────────────────────────────────

    /** Abundances sorted descending — the Whittaker rank–abundance (dominance) curve. */
    public static <T> List<Long> rankAbundance(Map<T, Long> abundance) {
        List<Long> ranks = new ArrayList<>();
        for (long c : abundance.values()) if (c > 0) ranks.add(c);
        ranks.sort(Comparator.reverseOrder());
        return ranks;
    }

    /**
     * Broken-stick expected abundance at each rank (MacArthur 1957):
     * E[a&#x1D62;] = (N/S) &#xB7; &#x3A3;&#x2096;&#x208C;&#x1D62;&#x02E2; 1/k for rank i = 1..S. The expectations sum to N.
     */
    public static double[] brokenStickExpected(int s, long n) {
        if (s <= 0) return new double[0];
        double[] out = new double[s];
        double tail = 0.0;
        for (int i = s; i >= 1; i--) {
            tail += 1.0 / i;
            out[i - 1] = ((double) n / s) * tail;
        }
        return out;
    }

    /**
     * Geometric-series expected abundance at each rank (Motomura 1932; Whittaker 1965):
     * E[a&#x1D62;] = N &#xB7; k(1&#x2212;k)^(i&#x2212;1) / (1 &#x2212; (1&#x2212;k)^S), the niche-preemption model with
     * preemption fraction k &#x2208; (0, 1).
     */
    public static double[] geometricExpected(int s, long n, double k) {
        if (s <= 0) return new double[0];
        if (k <= 0.0 || k >= 1.0) throw new IllegalArgumentException("k must be in (0,1)");
        double norm = 1.0 - Math.pow(1.0 - k, s);
        double[] out = new double[s];
        for (int i = 1; i <= s; i++) {
            out[i - 1] = n * k * Math.pow(1.0 - k, i - 1) / norm;
        }
        return out;
    }

    /**
     * Estimate the geometric preemption fraction k from an observed descending
     * rank–abundance list, via the mean successive ratio a&#x1D62;&#x208A;&#x2081;/a&#x1D62; = (1&#x2212;k).
     * Clamped to [0.001, 0.999]; a single-species list yields 0.999 (total preemption).
     */
    public static double fitGeometricK(List<Long> ranksDescending) {
        if (ranksDescending.size() < 2) return 0.999;
        double ratioSum = 0.0;
        int pairs = 0;
        for (int i = 0; i + 1 < ranksDescending.size(); i++) {
            long a = ranksDescending.get(i);
            long b = ranksDescending.get(i + 1);
            if (a > 0) {
                ratioSum += (double) b / a;
                pairs++;
            }
        }
        if (pairs == 0) return 0.999;
        double k = 1.0 - (ratioSum / pairs);
        return Math.min(0.999, Math.max(0.001, k));
    }

    /** The three rank–abundance models this layer compares. */
    public enum AbundanceModel { GEOMETRIC, BROKEN_STICK, UNIFORM }

    /**
     * Verdict of {@link #bestFit}: the winning model and the per-model sum of squared
     * errors on ln-abundance (the standard axis for rank–abundance comparison —
     * Whittaker plots are log-scaled).
     */
    public record ModelFit(AbundanceModel best, Map<AbundanceModel, Double> sse) {}

    /**
     * Fit the observed rank–abundance curve against the geometric series (fitted k),
     * the broken stick, and a uniform null, by SSE on ln-abundance; smallest SSE wins.
     * Ties break in enum order (GEOMETRIC, BROKEN_STICK, UNIFORM) — deterministic.
     */
    public static <T> ModelFit bestFit(Map<T, Long> abundance) {
        List<Long> ranks = rankAbundance(abundance);
        int s = ranks.size();
        long n = total(abundance);
        Map<AbundanceModel, Double> sse = new LinkedHashMap<>();
        if (s == 0) {
            for (AbundanceModel m : AbundanceModel.values()) sse.put(m, 0.0);
            return new ModelFit(AbundanceModel.UNIFORM, sse);
        }

        double[] geo   = geometricExpected(s, n, fitGeometricK(ranks));
        double[] stick = brokenStickExpected(s, n);
        double[] flat  = new double[s];
        java.util.Arrays.fill(flat, (double) n / s);

        sse.put(AbundanceModel.GEOMETRIC,    logSse(ranks, geo));
        sse.put(AbundanceModel.BROKEN_STICK, logSse(ranks, stick));
        sse.put(AbundanceModel.UNIFORM,      logSse(ranks, flat));

        AbundanceModel best = AbundanceModel.GEOMETRIC;
        for (AbundanceModel m : AbundanceModel.values()) {
            if (sse.get(m) < sse.get(best)) best = m;
        }
        return new ModelFit(best, sse);
    }

    private static double logSse(List<Long> observed, double[] expected) {
        double sse = 0.0;
        for (int i = 0; i < observed.size(); i++) {
            double o = Math.log(observed.get(i));
            double e = Math.log(Math.max(expected[i], 1e-12));
            double d = o - e;
            sse += d * d;
        }
        return sse;
    }
}
