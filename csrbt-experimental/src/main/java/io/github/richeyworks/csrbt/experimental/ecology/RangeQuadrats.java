package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.List;
import java.util.function.ToDoubleFunction;

/**
 * Quadrat sampling over an engine's key space (ADR-016 §E3) — the field method applied
 * literally: lay a grid of {@code Q} equal-width quadrats over the occupied key range,
 * count individuals (stored keys) per quadrat, and compute the standard dispersion
 * statistics. Works identically over <em>any</em> engine's {@code inOrder()} output —
 * strategy-backed, ensemble, persistent, B+tree — which is the point: one spatial
 * instrument for the whole engine family. (Leaf-level occupancy inside the B+tree would
 * need a core seam; held, ADR-016 §5 — the grid does not require it, just as a field
 * grid does not follow burrow walls.)
 *
 * <p>The two classical indices, each cited, each with its textbook reading:</p>
 * <ul>
 *   <li><b>Index of dispersion</b> I = s&#xB2;/x&#x304; (variance-to-mean ratio; Fisher):
 *       &#x2248; 1 random (Poisson), &lt; 1 regular/uniform, &gt; 1 clumped.</li>
 *   <li><b>Morisita's index</b> I&#x2090; = Q &#xB7; &#x3A3;n&#x1D62;(n&#x1D62;&#x2212;1) / (N(N&#x2212;1)) (Morisita 1959):
 *       1 random, &lt; 1 regular, &gt; 1 clumped — robust to N, the reason field work
 *       prefers it.</li>
 * </ul>
 *
 * <p>All static, pure, deterministic. Counts are taken from a single in-order pass;
 * positions come from a caller-supplied mapper so generic keys work (integers get the
 * {@link #countsOfInts} convenience).</p>
 */
public final class RangeQuadrats {

    private RangeQuadrats() {}

    // ── Counting ──────────────────────────────────────────────────────────────

    /**
     * Bucket keys into {@code quadrats} equal-width bins over [min, max] of their
     * mapped positions. The top boundary is inclusive (the max key lands in the last
     * bin). Empty input &#x2192; all-zero counts; a degenerate range (all positions equal)
     * puts everything in bin 0.
     */
    public static <K> long[] counts(List<K> keys, ToDoubleFunction<K> position, int quadrats) {
        if (quadrats < 1) throw new IllegalArgumentException("quadrats must be >= 1");
        long[] out = new long[quadrats];
        if (keys.isEmpty()) return out;

        double min = Double.POSITIVE_INFINITY, max = Double.NEGATIVE_INFINITY;
        for (K k : keys) {
            double p = position.applyAsDouble(k);
            if (!Double.isFinite(p)) {
                throw new IllegalArgumentException("non-finite position for key " + k);
            }
            min = Math.min(min, p);
            max = Math.max(max, p);
        }
        double span = max - min;
        for (K k : keys) {
            double p = position.applyAsDouble(k);
            int bin = span == 0.0 ? 0
                    : (int) Math.min(quadrats - 1, (long) ((p - min) / span * quadrats));
            out[bin]++;
        }
        return out;
    }

    /** Integer-key convenience for the common engines. */
    public static long[] countsOfInts(List<Integer> keys, int quadrats) {
        return counts(keys, Integer::doubleValue, quadrats);
    }

    // ── Dispersion statistics ─────────────────────────────────────────────────

    /** Total individuals across quadrats. */
    public static long total(long[] counts) {
        long n = 0;
        for (long c : counts) n += c;
        return n;
    }

    /** Occupied quadrats / total quadrats. Zero quadrats &#x2192; 0. */
    public static double occupancy(long[] counts) {
        if (counts.length == 0) return 0.0;
        int occupied = 0;
        for (long c : counts) if (c > 0) occupied++;
        return (double) occupied / counts.length;
    }

    /**
     * Index of dispersion I = s&#xB2;/x&#x304; with the sample variance (n&#x2212;1 denominator, the
     * form the chi-square goodness-of-fit uses). Reads: &#x2248;1 random, &lt;1 regular,
     * &gt;1 clumped. Fewer than 2 quadrats or a zero mean &#x2192; 0.
     */
    public static double indexOfDispersion(long[] counts) {
        int q = counts.length;
        if (q < 2) return 0.0;
        double mean = (double) total(counts) / q;
        if (mean == 0.0) return 0.0;
        double ss = 0.0;
        for (long c : counts) {
            double d = c - mean;
            ss += d * d;
        }
        double variance = ss / (q - 1);
        return variance / mean;
    }

    /**
     * Morisita's index of dispersion I&#x2090; = Q &#xB7; &#x3A3;n&#x1D62;(n&#x1D62;&#x2212;1) / (N(N&#x2212;1))
     * (Morisita 1959): 1 random, &lt;1 regular, &gt;1 clumped. Defined as 1.0 (random)
     * when N &lt; 2 — the index needs at least two individuals to compare co-occurrence.
     */
    public static double morisita(long[] counts) {
        long n = total(counts);
        if (n < 2) return 1.0;
        double sumPairs = 0.0;
        for (long c : counts) sumPairs += (double) c * (c - 1);
        return counts.length * sumPairs / ((double) n * (n - 1));
    }

    /** One-line report over a prepared count vector, deterministic field order. */
    public static String report(long[] counts) {
        return String.format(
                "quadrats=%d N=%d occupancy=%.4f dispersionI=%.4f morisita=%.4f",
                counts.length, total(counts), occupancy(counts),
                indexOfDispersion(counts), morisita(counts));
    }
}
