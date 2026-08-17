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
 * ADR-023's cost model, as a rig the next person can re-run instead of re-deriving.
 *
 * <p>Rotations carry the cached height to every ancestor with a fixed-point climb
 * ({@code TreeNode1.refreshHeightUpward}). The climb's length is a property of the WORKLOAD
 * SHAPE, not of the tree size, which is why the three shapes below are the parameter and why a
 * single "insert throughput" number would hide the whole effect:</p>
 *
 * <ul>
 *   <li>{@code SORTED} — monotone inserts. Every BST link pushes +1 up the whole spine and the
 *       rebalancing rotation takes it straight back off, so the climb runs the full height:
 *       ADR-023 measured 22.7 levels per rotation on RedBlack. This is the expensive cell.</li>
 *   <li>{@code RANDOM} — uniform inserts. 1.2 levels per operation; the climb exits almost
 *       immediately.</li>
 *   <li>{@code MIXED} — 65/35 add/remove. 0.8 levels per operation.</li>
 * </ul>
 *
 * <p>{@code AVL}, {@code HYBRID} and {@code SPLAY} are included as controls: they call the
 * {@code rotate*Local} primitives because their own passes already refresh heights to the root,
 * so they should show no climb cost at all in any shape. If a future change makes them move,
 * something has broken the reasoning in {@code TreeStrategy}'s rotation notes.</p>
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
