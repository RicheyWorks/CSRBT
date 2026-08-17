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
 *
 * <h2>Two bases, never mixed (ADR-024 clause 3, pool form)</h2>
 *
 * <p>A cost priced on a member's own realized churn and one priced on the stream's are two
 * different measurements. The bandit's means run over <em>windows</em>, and whether a window
 * could be priced per-member is a property of that window — a {@code SAMPLED_SHADOW} at a low
 * sample rate falls below {@code EnsembleMember.MIN_METERED_WRITES} in a short window and clears
 * it in a long one — so a single running mean silently averaged the two. Every arm therefore
 * carries <em>both</em> means: {@link #meanStreamCost} (always defined, the pre-ADR-024 number)
 * and {@link #meanOwnChurnCost} (defined only while <em>every</em> pull of that arm carried an
 * own-churn price). {@link #perMemberBasis()} is true only when every live scored arm has the
 * second, and {@link #meanCost}, {@link #select()}, {@link #bestArm()} and {@link #statsLine()}
 * all read the basis it names — so the whole scoreboard is on one basis at a time, and short of
 * evidence it is the stream's, which is exactly the number the refinement replaced.</p>
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
    /** Mean cost priced on the stream's churn — always defined once an arm has been pulled. */
    private final double[]   meanStreamCost;
    /** Mean cost priced on the member's own churn; meaningful only while {@link #ownComplete}. */
    private final double[]   meanOwnCost;
    /** False once any pull of this arm had no own-churn price — the mean is then not a mean. */
    private final boolean[]  ownComplete;
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
        this.meanStreamCost = new double[this.arms.size()];
        this.meanOwnCost = new double[this.arms.size()];
        this.ownComplete = new boolean[this.arms.size()];
        java.util.Arrays.fill(this.ownComplete, true);   // vacuously true until the first pull
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
        boolean basis = perMemberBasis();
        int best = -1;
        double bestValue = Double.POSITIVE_INFINITY;
        for (int i = 0; i < arms.size(); i++) {
            if (disqualified[i]) continue;
            if (pulls[i] == 0) {
                return new Selection(arms.get(i), 0, totalPulls,
                        Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY);
            }
            double bonus = exploration * Math.sqrt(2.0 * Math.log(totalPulls) / pulls[i]);
            double value = mean(i, basis) - bonus;
            if (value < bestValue) {
                bestValue = value;
                best = i;
            }
        }
        if (best < 0) throw new IllegalStateException("every arm is disqualified — search space exhausted");
        double bonus = exploration * Math.sqrt(2.0 * Math.log(totalPulls) / pulls[best]);
        return new Selection(arms.get(best), pulls[best], totalPulls,
                mean(best, basis), bonus, bestValue);
    }

    /**
     * Record a realized cost for {@code arm} (running mean; one pull), with no own-churn price —
     * equivalent to {@link #recordCost(PolicyGenome, double, double)} with {@code NaN}, and
     * therefore enough on its own to put this arm (and the scoreboard) permanently on the stream
     * basis. This is the published 0.2.0 form and its behavior is unchanged.
     */
    public void recordCost(PolicyGenome arm, double cost) {
        recordCost(arm, cost, Double.NaN);
    }

    /**
     * Record one window's realized cost for {@code arm} on <em>both</em> bases (ADR-024).
     *
     * <p>{@code streamCost} is the cost priced on the stream's rotations-per-write and is always
     * required. {@code ownChurnCost} is the same window priced on the member's own realized churn,
     * or {@code NaN} when that window had no own-churn observation on both sides of the
     * comparison — in which case this arm's own-churn mean stops being a mean and the scoreboard
     * falls back to the stream basis for good. Recording both is what lets the promotion gate
     * compare a mean over windows against a single window's incumbent cost without blending two
     * different measurements.</p>
     *
     * @throws IllegalArgumentException if {@code streamCost} is negative or NaN, or if
     *         {@code ownChurnCost} is negative
     * @throws IllegalStateException if the arm is disqualified
     */
    public void recordCost(PolicyGenome arm, double streamCost, double ownChurnCost) {
        int i = indexOf(arm);
        if (disqualified[i]) throw new IllegalStateException("arm " + arm + " is disqualified");
        if (streamCost < 0.0 || Double.isNaN(streamCost)) {
            throw new IllegalArgumentException("cost must be a non-negative number: " + streamCost);
        }
        if (ownChurnCost < 0.0) {
            throw new IllegalArgumentException(
                    "own-churn cost must be non-negative or NaN: " + ownChurnCost);
        }
        pulls[i]++;
        totalPulls++;
        meanStreamCost[i] += (streamCost - meanStreamCost[i]) / pulls[i];
        if (Double.isNaN(ownChurnCost)) {
            ownComplete[i] = false;
        } else if (ownComplete[i]) {
            meanOwnCost[i] += (ownChurnCost - meanOwnCost[i]) / pulls[i];
        }
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
        boolean basis = perMemberBasis();
        int best = -1;
        for (int i = 0; i < arms.size(); i++) {
            if (disqualified[i] || pulls[i] == 0) continue;
            if (best < 0 || mean(i, basis) < mean(best, basis)) best = i;
        }
        return best < 0 ? null : arms.get(best);
    }

    public List<PolicyGenome> arms()                    { return arms; }
    public long totalPulls()                            { return totalPulls; }
    public int pulls(PolicyGenome arm)                  { return pulls[indexOf(arm)]; }
    public boolean isDisqualified(PolicyGenome arm)     { return disqualified[indexOf(arm)]; }
    public String disqualifyReason(PolicyGenome arm)    { return disqualifyReason[indexOf(arm)]; }

    /**
     * The arm's mean cost <em>on the basis the scoreboard is currently comparing on</em>
     * ({@link #perMemberBasis()}) — the number to feed a promotion gate, paired with an
     * incumbent priced on that same basis.
     */
    public double meanCost(PolicyGenome arm)            { return mean(indexOf(arm), perMemberBasis()); }

    /** The arm's mean cost priced on the stream's churn — defined for every pulled arm. */
    public double meanStreamCost(PolicyGenome arm)      { return meanStreamCost[indexOf(arm)]; }

    /**
     * The arm's mean cost priced on the member's own realized churn, or {@code NaN} when any of
     * its pulls had no own-churn price — a mean over a mixture is not a mean of either.
     */
    public double meanOwnChurnCost(PolicyGenome arm) {
        int i = indexOf(arm);
        return (ownComplete[i] && pulls[i] > 0) ? meanOwnCost[i] : Double.NaN;
    }

    /**
     * True when every live scored arm has an own-churn mean, i.e. when the per-member basis ranks
     * the whole scoreboard comparably (ADR-024 clause 3 over the pool the decision reads, not just
     * within one window). False — the conservative direction — whenever any live scored arm has
     * ever been through a window that could not be priced per-member, and false before anything
     * has been scored.
     */
    public boolean perMemberBasis() {
        boolean anyScored = false;
        for (int i = 0; i < arms.size(); i++) {
            if (disqualified[i] || pulls[i] == 0) continue;
            if (!ownComplete[i]) return false;
            anyScored = true;
        }
        return anyScored;
    }

    private double mean(int i, boolean perMemberBasis) {
        return (perMemberBasis && ownComplete[i]) ? meanOwnCost[i] : meanStreamCost[i];
    }

    /** One line of per-arm state, for the {@code event=trial_eval} log and post-mortems. */
    public String statsLine() {
        boolean basis = perMemberBasis();
        StringBuilder sb = new StringBuilder(basis ? "per-member[" : "stream[");
        for (int i = 0; i < arms.size(); i++) {
            if (i > 0) sb.append(", ");
            sb.append(arms.get(i)).append(':');
            if (disqualified[i]) sb.append("DQ(").append(disqualifyReason[i]).append(')');
            else if (pulls[i] == 0) sb.append("untried");
            else sb.append(String.format(Locale.ROOT, "%.4f/%d", mean(i, basis), pulls[i]));
        }
        return sb.append(']').toString();
    }

    private int indexOf(PolicyGenome arm) {
        int i = arms.indexOf(Objects.requireNonNull(arm, "arm cannot be null"));
        if (i < 0) throw new IllegalArgumentException("unknown arm: " + arm);
        return i;
    }
}
