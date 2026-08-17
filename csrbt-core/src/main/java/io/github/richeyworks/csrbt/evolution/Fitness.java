package io.github.richeyworks.csrbt.evolution;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Locale;

/**
 * The explainable fitness function (ADR-011 V2) — the reward signal V3's bandit pays
 * arms with and V4's selection breeds on. Deterministic and pure: a function of the
 * realized meters in {@link WorkloadFeatures} plus one structural measurement, with
 * <b>no</b> randomness, clock, or hidden state. Same inputs, same number, every time —
 * the property every downstream consumer (bandit regret, lineage comparison, the V5
 * experiment) silently depends on.
 *
 * <h2>The v1 model (cost, lower = better)</h2>
 * <pre>
 *   writeCost = writeFraction × rotationsPerWrite          (realized: the meters exist)
 *   readCost  = readFraction  × meanDepth / log₂(n + 1)    (structural estimate)
 *   cost      = writeCost + readCost
 * </pre>
 *
 * <p>The write term is fully <em>realized</em> — rotations actually incurred per mutating
 * op, workload-weighted. The read term is <em>estimated structurally</em>, because
 * ensemble shadows don't serve reads (ADR-011 §3 V2): {@code meanDepth} is the average
 * nodes-on-path over the candidate's current tree, normalized by the balanced-tree depth
 * bound {@code log₂(n+1)}, so ≈1 means "as deep as balanced allows", and a degenerating
 * shape grows without bound. Probe-reads replacing the estimate is the ADR's held
 * refinement, with its trigger ("when structural estimates prove misleading") documented
 * there.</p>
 *
 * <p>Every evaluation is an {@link Evaluation} value carrying its named inputs and both
 * partial costs — explainable from one log line, like the {@code StrategyScorer} it
 * generalizes. The structural measurement is {@link #meanDepth(MutableTree)}, split out
 * so the cost arithmetic in {@link #evaluate} stays a pure function of scalars that tests
 * can hit with hand-built vectors.</p>
 */
public final class Fitness {

    private Fitness() { }   // static utility; not instantiable

    /**
     * Smallest element count at which a tree has a <em>shape</em> — the minimum size for which
     * {@link #evaluate} produces a number that means anything.
     *
     * <p>For {@code n ≤ 1} every arrangement of the keys is the same arrangement, so the read term
     * is structure-free and {@link #evaluate} zeroes it (and {@code meanDepth} of an empty tree is
     * 0 anyway). That is honest arithmetic and a trap for the caller: a cost of exactly 0.0 beats
     * every possible incumbent.</p>
     */
    public static final long MIN_INFORMATIVE_SIZE = 2L;

    /**
     * Whether a candidate of {@code size} elements produced an <b>observation</b> — a cost that may
     * be recorded against an arm and compared with an incumbent (sixth-pass audit finding 8).
     *
     * <p>The ADR-011 controllers score a trial shadow against the serving primary. On the documented
     * {@link io.github.richeyworks.csrbt.ensemble.EnsembleMode#SAMPLED_SHADOW} path the shadow is
     * legitimately tiny — at {@code shadowSampleRate(0.02)} against a 40-key primary it is
     * <em>empty</em> — and an empty tree costs exactly 0.0. That number used to be treated as a
     * measurement: it beat the incumbent's 0.5497 on the very first trial, and because the bandit
     * kept {@code meanCost = 0.0} for that arm it stayed {@code bestArm()} forever, so no other arm
     * could ever win. The cure is not to clamp the number — a trial that saw no data must record
     * <em>no observation at all</em>, leaving the arm untried and the incumbent unchallenged until
     * there is something real to compare.</p>
     *
     * @param size the candidate's element count
     * @return {@code true} when the cost from a tree this size is comparable
     */
    public static boolean informative(long size) {
        return size >= MIN_INFORMATIVE_SIZE;
    }

    /**
     * One fitness evaluation: the named inputs it was computed from, the two partial
     * costs, and the total. Lower cost = fitter. A value, not a process — store it,
     * log it, compare it.
     */
    public record Evaluation(
            double readFraction,
            double writeFraction,
            double rotationsPerWrite,
            double meanDepth,
            double balancedDepthBound,
            double writeCost,
            double readCost,
            double cost
    ) {
        /** The one-log-line rendering (house observability style). */
        @Override
        public String toString() {
            return String.format(Locale.ROOT,
                    "fitness cost=%.4f writeCost=%.4f readCost=%.4f "
                    + "(read=%.2f write=%.2f rotPerWrite=%.4f depth=%.2f bound=%.2f)",
                    cost, writeCost, readCost,
                    readFraction, writeFraction, rotationsPerWrite,
                    meanDepth, balancedDepthBound);
        }
    }

    /**
     * Evaluate fitness from the realized meters and a structural depth measurement.
     *
     * <p>The number returned is only an <em>observation</em> when {@link #informative(long)} accepts
     * {@code size}; below that the read term is structure-free and the total collapses toward 0,
     * which is the absence of a tree, not the measurement of a good one. Callers that compare or
     * record costs must gate on {@code informative} first.</p>
     *
     * @param features  the live workload snapshot (read/write mix, realized rotations)
     * @param meanDepth average nodes-on-path of the candidate's tree, typically from
     *                  {@link #meanDepth(MutableTree)}
     * @param size      the candidate's element count ({@code n} in the depth bound)
     */
    public static Evaluation evaluate(WorkloadFeatures features, double meanDepth, long size) {
        if (features == null) throw new IllegalArgumentException("features cannot be null");
        if (meanDepth < 0.0)  throw new IllegalArgumentException("meanDepth cannot be negative: " + meanDepth);
        if (size < 0L)        throw new IllegalArgumentException("size cannot be negative: " + size);

        double writeCost = features.writeFraction() * features.rotationsPerWrite();

        // log₂(n+1): the depth bound of a perfectly balanced tree of n nodes. For n ≤ 1
        // every shape is the same shape — the read term is structure-free, so it is 0.
        double bound = log2(size + 1.0);
        double readCost = (size <= 1L) ? 0.0
                : features.readFraction() * (meanDepth / bound);

        return new Evaluation(
                features.readFraction(), features.writeFraction(),
                features.rotationsPerWrite(), meanDepth, bound,
                writeCost, readCost, writeCost + readCost);
    }

    /**
     * The structural measurement: average nodes-on-path (root = 1) over every node of
     * {@code tree} — the internal path length normalized by n, the same "nodes touched
     * per lookup" unit as the monitor's realized {@code meanSearchDepth}. Iterative
     * (a degenerated candidate may be deep); O(n), intended at evaluation-window cadence,
     * never per-op. Empty tree: 0.
     */
    public static <K> double meanDepth(MutableTree<K> tree) {
        if (tree == null) throw new IllegalArgumentException("tree cannot be null");
        TreeNode1<K> root = tree.getRoot();
        if (root == null || root.isNil()) return 0.0;

        long pathSum = 0L;
        long count = 0L;
        Deque<TreeNode1<K>> nodes = new ArrayDeque<>();
        Deque<Long> depths = new ArrayDeque<>();
        nodes.push(root);
        depths.push(1L);
        while (!nodes.isEmpty()) {
            TreeNode1<K> n = nodes.pop();
            long d = depths.pop();
            pathSum += d;
            count++;
            if (!n.getLeft().isNil())  { nodes.push(n.getLeft());  depths.push(d + 1); }
            if (!n.getRight().isNil()) { nodes.push(n.getRight()); depths.push(d + 1); }
        }
        return (double) pathSum / count;
    }

    private static double log2(double x) {
        return Math.log(x) / Math.log(2.0);
    }
}
