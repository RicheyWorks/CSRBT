package core.evolution;

import core.strategy.AVLStrategy;
import core.strategy.HybridStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;
import core.strategy.WeightBalancedStrategy;

import java.util.Objects;
import java.util.Random;

/**
 * The real genome (ADR-011 V2): an immutable, bounds-checked parameter vector over the
 * policy space the evolution machine searches. Where the deprecated {@link TreeGenome}
 * was a self-interpreting trait soup, a {@code PolicyGenome} is exactly what the ADR
 * promised — "a small vector of real parameters": a {@link Family} tag plus, for the
 * parameterized family, the weight-balance dials {@code (Δ, Γ)}. Nothing in here is a
 * preference or a score; every gene is a number an executable strategy actually reads.
 *
 * <p><b>Purity.</b> {@link #perturbed(Random)} (mutation) and {@link #blended(PolicyGenome,
 * Random)} (crossover) are pure: they take the caller's seeded {@link Random} and return
 * new genomes — same seed, same offspring, every time. No static RNG, no clock, no UUID
 * (the lesson of {@code TreeGenome}). Identity is <em>value</em> identity:
 * {@link #equals(Object)} compares family and genes, which is precisely the "arm identity
 * = family + grid point" representation V3's bandit needs.</p>
 *
 * <p><b>The box.</b> Perturbation is bounds-aware: offspring stay inside
 * {@code Δ ∈ [}{@value #DELTA_MIN}{@code , }{@value #DELTA_MAX}{@code ]},
 * {@code Γ ∈ [1, Δ)} — the structural bounds from {@link WeightBalancedStrategy} with a
 * searchable ceiling on Δ (beyond ~8 the tree tolerates so much skew the family stops
 * being interesting). Being <em>inside the box</em> is necessary, not sufficient: V1's
 * first finding was that (5,3) satisfies these bounds and is still unsound under delete
 * churn. The box is where the search is allowed to look; the health gate's
 * strategy-supplied invariant decides what survives. Out-of-box exploration is V4's
 * flagged business, not this class's.</p>
 */
public final class PolicyGenome {

    /** Searchable floor for Δ (structural: weight balance needs Δ ≥ 2). */
    public static final int DELTA_MIN = 2;
    /** Searchable ceiling for Δ (beyond this, skew tolerance makes the family degenerate). */
    public static final int DELTA_MAX = 8;

    /**
     * The policy families. The four classics are points (no genes); WEIGHT_BALANCED is
     * the parameterized family ADR-011 V1 opened. Splay-p joins here when that dimension
     * lands (ADR-011 §3, "Revisit").
     */
    public enum Family {
        RED_BLACK, AVL, SPLAY, HYBRID, WEIGHT_BALANCED;

        /** True if this family carries genes a perturbation can act on. */
        public boolean parameterized() { return this == WEIGHT_BALANCED; }
    }

    private final Family family;
    private final int delta;   // 0 unless parameterized
    private final int ratio;   // 0 unless parameterized

    private PolicyGenome(Family family, int delta, int ratio) {
        this.family = family;
        this.delta = delta;
        this.ratio = ratio;
    }

    /** A fixed-family genome (one of the four classics) — no genes, nothing to perturb. */
    public static PolicyGenome of(Family family) {
        Objects.requireNonNull(family, "family cannot be null");
        if (family.parameterized()) {
            throw new IllegalArgumentException(
                    family + " is parameterized — use weightBalanced(delta, ratio)");
        }
        return new PolicyGenome(family, 0, 0);
    }

    /**
     * A weight-balanced genome at grid point {@code (delta, ratio)}, validated against
     * the box: {@code Δ ∈ [DELTA_MIN, DELTA_MAX]}, {@code Γ ∈ [1, Δ)}.
     */
    public static PolicyGenome weightBalanced(int delta, int ratio) {
        if (delta < DELTA_MIN || delta > DELTA_MAX) {
            throw new IllegalArgumentException(
                    "delta must be in [" + DELTA_MIN + ", " + DELTA_MAX + "]: " + delta);
        }
        if (ratio < 1 || ratio >= delta) {
            throw new IllegalArgumentException("ratio must be in [1, delta): " + ratio);
        }
        return new PolicyGenome(Family.WEIGHT_BALANCED, delta, ratio);
    }

    /** The literature-verified default arm, WB(3, 2) — the search's safe anchor. */
    public static PolicyGenome verifiedDefault() {
        return weightBalanced(WeightBalancedStrategy.DEFAULT_DELTA,
                              WeightBalancedStrategy.DEFAULT_RATIO);
    }

    /** Structural ceiling for unboxed exploration (V4): past this, Δ-tolerance is theater. */
    public static final int DELTA_STRUCTURAL_MAX = 32;

    /**
     * The V4 escape hatch — a weight-balanced genome validated against <em>structural</em>
     * bounds only ({@code Δ ∈ [DELTA_MIN, DELTA_STRUCTURAL_MAX]}, {@code Γ ∈ [1, Δ)}),
     * permitted to leave the verified box. Exists exclusively behind the population
     * search's out-of-box flag (ADR-011 V4): an out-of-box genome is an <em>experiment</em>
     * whose soundness nothing guarantees — which is safe here and only here, because the
     * health gate and the strategy's own invariant kill the unsound ones on the record.
     */
    public static PolicyGenome weightBalancedUnboxed(int delta, int ratio) {
        if (delta < DELTA_MIN || delta > DELTA_STRUCTURAL_MAX) {
            throw new IllegalArgumentException("delta must be in ["
                    + DELTA_MIN + ", " + DELTA_STRUCTURAL_MAX + "] even unboxed: " + delta);
        }
        if (ratio < 1 || ratio >= delta) {
            throw new IllegalArgumentException("ratio must be in [1, delta): " + ratio);
        }
        return new PolicyGenome(Family.WEIGHT_BALANCED, delta, ratio);
    }

    /** True when this genome lies inside the verified searchable box (V3's grid). */
    public boolean inVerifiedBox() {
        return !family.parameterized() || delta <= DELTA_MAX;
    }

    public Family family() { return family; }

    /** @throws IllegalStateException if this family carries no genes */
    public int delta() { return requireParameterized(delta); }

    /** @throws IllegalStateException if this family carries no genes */
    public int ratio() { return requireParameterized(ratio); }

    private int requireParameterized(int gene) {
        if (!family.parameterized()) {
            throw new IllegalStateException(family + " carries no (Δ, Γ) genes");
        }
        return gene;
    }

    // ── Mutation ─────────────────────────────────────────────────────────────────

    /**
     * Bounded perturbation: nudge exactly one gene by ±1, clamped to the box (a nudge
     * that would leave the box reflects back inside it; Γ re-clamps to {@code [1, Δ)}
     * if Δ shrank). A fixed-family genome has no genes, so its perturbation is itself —
     * the classics are points, not regions. Pure: consumes only the caller's {@code rng}.
     */
    public PolicyGenome perturbed(Random rng) {
        Objects.requireNonNull(rng, "rng cannot be null");
        if (!family.parameterized()) return this;

        int step = rng.nextBoolean() ? 1 : -1;
        int newDelta = delta;
        int newRatio = ratio;
        if (rng.nextBoolean()) {
            newDelta = reflect(delta + step, DELTA_MIN, DELTA_MAX);
            newRatio = Math.min(newRatio, newDelta - 1);   // keep Γ < Δ if Δ shrank
        } else {
            newRatio = reflect(ratio + step, 1, newDelta - 1);
        }
        return weightBalanced(newDelta, newRatio);
    }

    /** Clamp-by-reflection: a step past a wall lands one inside it (a step is bounded). */
    static int reflect(int v, int lo, int hi) {
        if (v < lo) return Math.min(hi, lo + (lo - v));
        if (v > hi) return Math.max(lo, hi - (v - hi));
        return v;
    }

    // ── Crossover ────────────────────────────────────────────────────────────────

    /**
     * Blend with {@code other}: the child takes one parent's family (fair coin); if that
     * family is parameterized, its genes are the integer midpoint of the parents' genes
     * when both parents carry genes (rounding toward the first parent), else the genes of
     * the parent that has them. The result is re-validated against the box, so a blend
     * can never construct an out-of-bounds genome. Pure and deterministic per seed.
     */
    public PolicyGenome blended(PolicyGenome other, Random rng) {
        Objects.requireNonNull(other, "other cannot be null");
        Objects.requireNonNull(rng, "rng cannot be null");

        Family childFamily = rng.nextBoolean() ? this.family : other.family;
        if (!childFamily.parameterized()) return of(childFamily);

        int d;
        int g;
        if (this.family.parameterized() && other.family.parameterized()) {
            d = midpointTowardFirst(this.delta, other.delta);
            g = midpointTowardFirst(this.ratio, other.ratio);
        } else if (this.family.parameterized()) {
            d = this.delta;
            g = this.ratio;
        } else {
            d = other.delta;
            g = other.ratio;
        }
        g = Math.min(g, d - 1);                            // Γ < Δ after blending
        return weightBalanced(d, g);
    }

    /** Integer midpoint; on a half, round toward {@code a} (deterministic, no rng). */
    private static int midpointTowardFirst(int a, int b) {
        return a + (b - a) / 2;                            // truncation biases toward a
    }

    // ── Execution ────────────────────────────────────────────────────────────────

    /** The executable strategy this genome encodes — the genotype→phenotype map. */
    public <K> TreeStrategy<K> toStrategy() {
        switch (family) {
            case RED_BLACK:       return new RedBlackStrategy<>();
            case AVL:             return new AVLStrategy<>();
            case SPLAY:           return new SplayStrategy<>();
            case HYBRID:          return new HybridStrategy<>();
            case WEIGHT_BALANCED: return new WeightBalancedStrategy<>(delta, ratio);
            default:              throw new AssertionError("unhandled family: " + family);
        }
    }

    // ── Value identity (V3's arm identity: family + grid point) ─────────────────

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (!(obj instanceof PolicyGenome other)) return false;
        return family == other.family && delta == other.delta && ratio == other.ratio;
    }

    @Override
    public int hashCode() {
        return Objects.hash(family, delta, ratio);
    }

    @Override
    public String toString() {
        return family.parameterized()
                ? "WB(Δ=" + delta + ",Γ=" + ratio + ")"
                : family.name();
    }
}
