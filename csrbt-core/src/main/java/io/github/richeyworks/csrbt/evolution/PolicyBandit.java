package io.github.richeyworks.csrbt.evolution;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Objects;

/**
 * UCB1 over the discretized parameter box (ADR-011 V3) — the explore/exploit engine of
 * the evolution machine's first search loop. Arms are {@link PolicyGenome}s (value
 * identity = arm identity); rewards are {@link Fitness} costs (lower = better), so
 * selection is UCB1 mirrored for minimization: pick the arm minimizing
 * {@code meanCost − exploration·√(2·ln(totalPulls)/pulls)} — optimism under uncertainty,
 * pointed downhill. Untried arms are selected first, in arm order.
 *
 * <p><b>Deterministic and pure.</b> No RNG anywhere: tie-breaks go to the lower arm
 * index, untried arms are visited in list order, and the whole state is three numbers
 * per arm (pulls, mean cost, disqualified). Same call sequence, same decisions — the
 * property the V5 experiment's seeds depend on.</p>
 *
 * <p><b>Disqualification is death.</b> An arm whose strategy fails the health gate at
 * build-aside, or whose own invariant fails at window end (the V1 (5,3) finding, turned
 * into a live mechanism), is {@link #disqualify disqualified}: never selected again,
 * never scored again. The bandit doesn't decide this — the safety architecture does;
 * the bandit just remembers.</p>
 *
 * <p>Every {@link #select()} returns a {@link Selection} carrying the winning arm's
 * named terms — explainable from one log line, like every decision-maker in this
 * codebase. The bandit holds no reference to trees, ensembles, or monitors: it is a
 * pure scoreboard, driven entirely by its caller ({@code PolicySearchController}).</p>
 */
public final class PolicyBandit {

    /** Default exploration constant (the canonical UCB1 √2 lives inside the bonus). */
    public static final double DEFAULT_EXPLORATION = 1.0;

    /** One selection: the arm and the named terms that made it win (one-line explainable). */
    public record Selection(PolicyGenome arm, int pulls, long totalPulls,
                            double meanCost, double bonus, double value) {
        @Override
        public String toString() {
            return String.format(Locale.ROOT,
                    "select arm=%s pulls=%d/%d meanCost=%s bonus=%s value=%s",
                    arm, pulls, totalPulls, fmt(meanCost), fmt(bonus), fmt(value));
        }
        private static String fmt(double d) {
            return Double.isNaN(d) ? "untried"
                 : Double.isInfinite(d) ? "inf"
                 : String.format(Locale.ROOT, "%.4f", d);
        }
    }

    private final List<PolicyGenome> arms;
    private final double exploration;
    private final int[]      pulls;
    private final double[]   meanCost;
    private final boolean[]  disqualified;
    private final String[]   disqualifyReason;
    private long totalPulls;

    public PolicyBandit(List<PolicyGenome> arms, double exploration) {
        Objects.requireNonNull(arms, "arms cannot be null");
        if (arms.isEmpty()) throw new IllegalArgumentException("at least one arm required");
        if (arms.stream().distinct().count() != arms.size()) {
            throw new IllegalArgumentException("duplicate arms (arm identity is value identity)");
        }
        if (exploration < 0.0) throw new IllegalArgumentException("exploration must be >= 0: " + exploration);
        this.arms = List.copyOf(arms);
        this.exploration = exploration;
        this.pulls = new int[this.arms.size()];
        this.meanCost = new double[this.arms.size()];
        this.disqualified = new boolean[this.arms.size()];
        this.disqualifyReason = new String[this.arms.size()];
    }

    public PolicyBandit(List<PolicyGenome> arms) { this(arms, DEFAULT_EXPLORATION); }

    /**
     * The full discretized box as arms: every (Δ, Γ) with Δ ∈ [{@value PolicyGenome#DELTA_MIN},
     * {@value PolicyGenome#DELTA_MAX}], Γ ∈ [1, Δ) — 28 grid points, in (Δ, Γ) order, the
     * verified default (3,2) among them. In-box ≠ sound (V1's (5,3)): unsound points are
     * arms precisely so they can self-disqualify on the record.
     */
    public static List<PolicyGenome> boxGrid() {
        List<PolicyGenome> grid = new ArrayList<>();
        for (int d = PolicyGenome.DELTA_MIN; d <= PolicyGenome.DELTA_MAX; d++) {
            for (int g = 1; g < d; g++) {
                grid.add(PolicyGenome.weightBalanced(d, g));
            }
        }
        return grid;
    }

    // ── The decision ─────────────────────────────────────────────────────────────

    /**
     * UCB1 selection (minimizing): the first untried live arm, else the live arm with the
     * lowest {@code meanCost − exploration·√(2·ln N / nᵢ)}; ties to the lower index.
     *
     * @throws IllegalStateException when every arm is disqualified — the search has
     *         nothing left to try, and silence would hide it
     */
    public Selection select() {
        int best = -1;
        double bestValue = Double.POSITIVE_INFINITY;
        for (int i = 0; i < arms.size(); i++) {
            if (disqualified[i]) continue;
            if (pulls[i] == 0) {
                return new Selection(arms.get(i), 0, totalPulls,
                        Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY);
            }
            double bonus = exploration * Math.sqrt(2.0 * Math.log(totalPulls) / pulls[i]);
            double value = meanCost[i] - bonus;
            if (value < bestValue) {
                bestValue = value;
                best = i;
            }
        }
        if (best < 0) throw new IllegalStateException("every arm is disqualified — search space exhausted");
        double bonus = exploration * Math.sqrt(2.0 * Math.log(totalPulls) / pulls[best]);
        return new Selection(arms.get(best), pulls[best], totalPulls,
                meanCost[best], bonus, bestValue);
    }

    /** Record a realized cost for {@code arm} (running mean; one pull). */
    public void recordCost(PolicyGenome arm, double cost) {
        int i = indexOf(arm);
        if (disqualified[i]) throw new IllegalStateException("arm " + arm + " is disqualified");
        if (cost < 0.0 || Double.isNaN(cost)) {
            throw new IllegalArgumentException("cost must be a non-negative number: " + cost);
        }
        pulls[i]++;
        totalPulls++;
        meanCost[i] += (cost - meanCost[i]) / pulls[i];
    }

    /** Kill {@code arm} permanently (health gate / invariant verdicts land here). */
    public void disqualify(PolicyGenome arm, String reason) {
        int i = indexOf(arm);
        disqualified[i] = true;
        disqualifyReason[i] = Objects.requireNonNullElse(reason, "unspecified");
    }

    // ── Read model ───────────────────────────────────────────────────────────────

    /** The live arm with the lowest mean cost among scored arms; {@code null} if none scored. */
    public PolicyGenome bestArm() {
        int best = -1;
        for (int i = 0; i < arms.size(); i++) {
            if (disqualified[i] || pulls[i] == 0) continue;
            if (best < 0 || meanCost[i] < meanCost[best]) best = i;
        }
        return best < 0 ? null : arms.get(best);
    }

    public List<PolicyGenome> arms()                    { return arms; }
    public long totalPulls()                            { return totalPulls; }
    public int pulls(PolicyGenome arm)                  { return pulls[indexOf(arm)]; }
    public double meanCost(PolicyGenome arm)            { return meanCost[indexOf(arm)]; }
    public boolean isDisqualified(PolicyGenome arm)     { return disqualified[indexOf(arm)]; }
    public String disqualifyReason(PolicyGenome arm)    { return disqualifyReason[indexOf(arm)]; }

    /** One line of per-arm state, for the {@code event=trial_eval} log and post-mortems. */
    public String statsLine() {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < arms.size(); i++) {
            if (i > 0) sb.append(", ");
            sb.append(arms.get(i)).append(':');
            if (disqualified[i]) sb.append("DQ(").append(disqualifyReason[i]).append(')');
            else if (pulls[i] == 0) sb.append("untried");
            else sb.append(String.format(Locale.ROOT, "%.4f/%d", meanCost[i], pulls[i]));
        }
        return sb.append(']').toString();
    }

    private int indexOf(PolicyGenome arm) {
        int i = arms.indexOf(Objects.requireNonNull(arm, "arm cannot be null"));
        if (i < 0) throw new IllegalArgumentException("unknown arm: " + arm);
        return i;
    }
}
