package benchmarks;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.infra.Blackhole;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.TimeUnit;

/**
 * The ADR-023 / ADR-028 cost model, as a rig the next person can re-run instead of re-deriving.
 *
 * <p>Keeping {@code TreeNode1.getHeight()} exact costs a walk, and the walk's length is a
 * property of the WORKLOAD SHAPE, not of the tree size — which is why the three shapes below are
 * the parameter and why a single "insert throughput" number would hide the whole effect. Extra
 * height recomputes per operation, RedBlack at n = 100k, measured with a counter in
 * {@code TreeNode1} (ADR-028's table has all five strategies):</p>
 *
 * <ul>
 *   <li>{@code SORTED} — monotone inserts, the expensive cell. Under ADR-023 the BST link pushed
 *       +1 up the whole spine (27.7 levels) and the rebalancing rotation's climb took it straight
 *       back off (22.7), i.e. height was maintained twice per write in opposite directions, for
 *       +22% of write time. ADR-028 maintains it once — 6.0 levels — and the cell is back at its
 *       pre-ADR-023 wall clock.</li>
 *   <li>{@code RANDOM} — uniform inserts. 14.9 levels under ADR-023, 3.6 under ADR-028; the
 *       difference was never measurable end to end in either direction.</li>
 *   <li>{@code MIXED} — 65/35 add/remove. 16.2 levels, then 3.6.</li>
 * </ul>
 *
 * <p>{@code AVL}, {@code HYBRID} and {@code SPLAY} are included as controls: their own passes
 * already recompute every height from the modification point to the root, so they neither climb
 * after a rotation (ADR-023) nor repair after a write (ADR-028), and they should not move in any
 * shape. If a future change makes them move, something has broken the reasoning in
 * {@code TreeStrategy}'s rotation and linking notes.</p>
 *
 * <p><b>What this rig cannot do by itself.</b> A JMH run measures one library version. The A/B
 * numbers in ADR-023 and ADR-028 come from loading two or three versions behind isolated class
 * loaders and interleaving their passes inside one JVM, so drift, GC and frequency scaling hit
 * every arm equally; this benchmark is the workload definition that harness drives, and the
 * absolute per-shape figure to compare a candidate against.</p>
 *
 * <p>Whole-workload timing on purpose (one {@code @Benchmark} call = one full build), because
 * the quantity of interest is amortized write cost over a shape, not a single insert.</p>
 */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@State(Scope.Thread)
public class RotationHeightPropagationBenchmark {

    @Param({"RED_BLACK", "WEIGHT_BALANCED", "AVL", "HYBRID", "SPLAY"})
    public String strategy;

    @Param({"SORTED", "RANDOM", "MIXED"})
    public String shape;

    @Param({"100000"})
    public int n;

    /** Positive = add, negative = remove that key. */
    private int[] ops;

    private TreeStrategy<Integer> newStrategy() {
        switch (strategy) {
            case "RED_BLACK":       return new RedBlackStrategy<>();
            case "AVL":             return new AVLStrategy<>();
            case "SPLAY":           return new SplayStrategy<>();
            case "HYBRID":          return new HybridStrategy<>();
            case "WEIGHT_BALANCED": return new WeightBalancedStrategy<>(); // WB(3, ·), the literature point
            default: throw new AssertionError(strategy);
        }
    }

    @Setup(Level.Trial)
    public void setup() {
        Random rnd = new Random(7); // deterministic, house style
        ops = new int[n];
        switch (shape) {
            case "SORTED":
                for (int i = 0; i < n; i++) ops[i] = i + 1;
                break;
            case "RANDOM":
                for (int i = 0; i < n; i++) ops[i] = 1 + rnd.nextInt(n * 4);
                break;
            case "MIXED": {
                List<Integer> live = new ArrayList<>();
                for (int i = 0; i < n; i++) {
                    if (!live.isEmpty() && rnd.nextInt(100) < 35) {
                        ops[i] = -live.remove(rnd.nextInt(live.size()));
                    } else {
                        int key = 1 + rnd.nextInt(n * 4);
                        live.add(key);
                        ops[i] = key;
                    }
                }
                break;
            }
            default: throw new AssertionError(shape);
        }
    }

    /**
     * Splay degenerates to an O(n) chain on monotone inserts — the run would be quadratic and
     * would say nothing about the climb. Skipped by consuming the shape and returning early.
     */
    private boolean skip() {
        return "SPLAY".equals(strategy) && "SORTED".equals(shape);
    }

    @Benchmark
    public void writeWorkload(Blackhole bh) {
        if (skip()) { bh.consume(strategy); return; }
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(newStrategy());
        for (int op : ops) {
            if (op > 0) bh.consume(set.add(op));
            else        bh.consume(set.remove(-op));
        }
        bh.consume(set.size());
        bh.consume(set.getEngine().getRoot().getHeight());   // the value ADR-023 made exact
    }
}
