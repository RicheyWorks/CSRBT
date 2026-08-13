package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Cohort life table and survivorship classification (Deevey 1947) over key lifespans,
 * with age measured in <b>ops</b> — the deterministic clock — not wall time.
 *
 * <p>A key is "born" at the op that inserts it and "dies" at the op that removes it;
 * {@link EcologyRecorder} collects these {@link Lifespan}s from the live op stream.
 * The table is the standard cohort form: equal-width age classes, and per class x:
 * deaths d&#x2093;, survivors entering n&#x2093;, survivorship l&#x2093; = n&#x2093;/N, and per-capita
 * mortality q&#x2093; = d&#x2093;/n&#x2093;.</p>
 *
 * <p><b>Survivorship classification.</b> Deevey's three curves differ in where deaths
 * concentrate: Type I — late (die of old age), Type II — constant per-capita rate
 * (exponential decay of l&#x2093;), Type III — early (heavy juvenile mortality). On a
 * <em>complete</em> cohort the terminal age class always shows q = 1, so per-class
 * mortality comparisons degenerate; instead this classifier uses the concentration
 * diagnostic &#x3C1; = mean/median age at death. The exponential (pure Type II) benchmark
 * is &#x3C1; = 1/ln 2 &#x2248; 1.44: deaths clustered late pull the median up to the mean
 * (&#x3C1; &#x2192; 1, Type I); deaths clustered early leave a tiny median under a long-tail mean
 * (&#x3C1; large, Type III). Thresholds are fixed constants ({@link #TYPE_I_MAX_RATIO},
 * {@link #TYPE_III_MIN_RATIO}) bracketing the benchmark — deterministic verdicts.</p>
 */
public final class LifeTable {

    /** One key's completed lifespan: born at {@code birthOp}, died at {@code deathOp}. */
    public record Lifespan(int key, long birthOp, long deathOp) {
        public Lifespan {
            if (deathOp < birthOp) throw new IllegalArgumentException("deathOp < birthOp");
        }
        /** Age at death, in ops. */
        public long age() {
            return deathOp - birthOp;
        }
    }

    /** Deevey survivorship curve types. */
    public enum SurvivorshipType { TYPE_I, TYPE_II, TYPE_III }

    /** &#x3C1; = mean/median below this &#x2192; deaths concentrate late &#x2192; Type I. */
    public static final double TYPE_I_MAX_RATIO = 1.2;
    /** &#x3C1; = mean/median above this &#x2192; deaths concentrate early &#x2192; Type III. */
    public static final double TYPE_III_MIN_RATIO = 1.8;

    private final int cohortSize;
    private final long classWidth;
    private final long[] deaths;         // d_x
    private final long[] entering;       // n_x
    private final double[] survivorship; // l_x
    private final double[] mortality;    // q_x
    private final double meanAge;
    private final double medianAge;

    private LifeTable(int cohortSize, long classWidth, long[] deaths, long[] entering,
                      double[] survivorship, double[] mortality,
                      double meanAge, double medianAge) {
        this.cohortSize   = cohortSize;
        this.classWidth   = classWidth;
        this.deaths       = deaths;
        this.entering     = entering;
        this.survivorship = survivorship;
        this.mortality    = mortality;
        this.meanAge      = meanAge;
        this.medianAge    = medianAge;
    }

    /**
     * Build a cohort life table from completed lifespans.
     *
     * @param lifespans  completed lifespans (right-censored still-alive keys are simply
     *                   not in this list; the standard cohort simplification)
     * @param ageClasses number of equal-width age classes, &#x2265; 1
     */
    public static LifeTable fromLifespans(List<Lifespan> lifespans, int ageClasses) {
        if (ageClasses < 1) throw new IllegalArgumentException("ageClasses must be >= 1");
        int n = lifespans.size();

        List<Long> ages = new ArrayList<>(n);
        long maxAge = 0;
        double ageSum = 0.0;
        for (Lifespan ls : lifespans) {
            long age = ls.age();
            ages.add(age);
            maxAge = Math.max(maxAge, age);
            ageSum += age;
        }
        Collections.sort(ages);

        // Width covers [0, maxAge] inclusive; minimum 1 op per class.
        long width = Math.max(1, (maxAge / ageClasses) + 1);

        long[] d = new long[ageClasses];
        for (long age : ages) {
            int idx = (int) Math.min(ageClasses - 1, age / width);
            d[idx]++;
        }

        long[] nx = new long[ageClasses];
        double[] lx = new double[ageClasses];
        double[] qx = new double[ageClasses];
        long alive = n;
        for (int x = 0; x < ageClasses; x++) {
            nx[x] = alive;
            lx[x] = n == 0 ? 0.0 : (double) alive / n;
            qx[x] = alive == 0 ? 0.0 : (double) d[x] / alive;
            alive -= d[x];
        }

        double mean = n == 0 ? 0.0 : ageSum / n;
        double median;
        if (n == 0) {
            median = 0.0;
        } else if (n % 2 == 1) {
            median = ages.get(n / 2);
        } else {
            median = (ages.get(n / 2 - 1) + ages.get(n / 2)) / 2.0;
        }
        return new LifeTable(n, width, d, nx, lx, qx, mean, median);
    }

    // ── Table accessors ───────────────────────────────────────────────────────

    public int cohortSize()          { return cohortSize; }
    public long classWidth()         { return classWidth; }
    public int ageClasses()          { return deaths.length; }
    /** Deaths in age class x (d&#x2093;). */
    public long deathsAt(int x)      { return deaths[x]; }
    /** Survivors entering age class x (n&#x2093;). */
    public long enteringAt(int x)    { return entering[x]; }
    /** Survivorship l&#x2093; = n&#x2093;/N, monotone non-increasing, l&#x2080; = 1 for a non-empty cohort. */
    public double survivorshipAt(int x) { return survivorship[x]; }
    /** Per-capita mortality q&#x2093; = d&#x2093;/n&#x2093;. */
    public double mortalityAt(int x) { return mortality[x]; }
    /** Mean age at death (life expectancy at birth, in ops). */
    public double lifeExpectancy()   { return meanAge; }
    /** Median age at death, in ops. */
    public double medianAge()        { return medianAge; }

    /**
     * The concentration diagnostic &#x3C1; = mean/median age at death. Exponential benchmark
     * &#x2248; 1.44 (1/ln 2). Defined as 1.0 when the median is 0 but so is the mean; a zero
     * median under a positive mean returns {@link Double#POSITIVE_INFINITY} (extreme
     * early-death concentration).
     */
    public double concentrationRatio() {
        if (medianAge == 0.0) {
            return meanAge == 0.0 ? 1.0 : Double.POSITIVE_INFINITY;
        }
        return meanAge / medianAge;
    }

    /**
     * Deevey type from {@link #concentrationRatio()}: &#x3C1; &lt; {@value #TYPE_I_MAX_RATIO}
     * &#x2192; TYPE_I, &#x3C1; &gt; {@value #TYPE_III_MIN_RATIO} &#x2192; TYPE_III, otherwise TYPE_II.
     * Cohorts of fewer than 2 members default to TYPE_II (no shape to classify).
     */
    public SurvivorshipType survivorshipType() {
        if (cohortSize < 2) return SurvivorshipType.TYPE_II;
        double rho = concentrationRatio();
        if (rho < TYPE_I_MAX_RATIO)   return SurvivorshipType.TYPE_I;
        if (rho > TYPE_III_MIN_RATIO) return SurvivorshipType.TYPE_III;
        return SurvivorshipType.TYPE_II;
    }
}
