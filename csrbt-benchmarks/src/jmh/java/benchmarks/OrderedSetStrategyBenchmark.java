package benchmarks;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
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

import java.util.Random;
import java.util.concurrent.TimeUnit;

/**
 * ADR-013 seed benchmark: the four fixed strategies (the V5 baseline) under
 * shuffled insert and uniform-random lookup. Ports the headline numbers the
 * in-suite printed rows (E5/V5) reported informally — same shapes, now with
 * forking, warmup discipline, and statistical output.
 *
 * <p>The in-suite rows stay until this rig reproduces their ordering; then they
 * go (ADR-013 §4, "to revisit").</p>
 */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@State(Scope.Thread)
public class OrderedSetStrategyBenchmark {

    @Param({"RED_BLACK", "AVL", "SPLAY", "WEIGHT_BALANCED"})
    public String strategy;

    @Param({"100000"})
    public int n;

    private int[] insertOrder;
    private int[] probes;
    private OrderedSet<Integer> warm;

    private TreeStrategy<Integer> newStrategy() {
        switch (strategy) {
            case "RED_BLACK":       return new RedBlackStrategy<>();
            case "AVL":             return new AVLStrategy<>();
            case "SPLAY":           return new SplayStrategy<>();
            case "WEIGHT_BALANCED": return new WeightBalancedStrategy<>(); // WB(3, ·), the literature point
            default: throw new AssertionError(strategy);
        }
    }

    @Setup(Level.Trial)
    public void setup() {
        Random rnd = new Random(42); // deterministic, house style
        insertOrder = rnd.ints().distinct().limit(n).toArray(); // unbounded stream, so distinct().limit(n) always fills n
        probes = new int[n];
        for (int i = 0; i < n; i++) probes[i] = insertOrder[rnd.nextInt(insertOrder.length)];

        warm = OrderedSet.withNaturalOrder(newStrategy());
        for (int k : insertOrder) warm.add(k);
    }

    /** Build cost: n shuffled inserts into a fresh tree. */
    @Benchmark
    public OrderedSet<Integer> insertShuffled() {
        OrderedSet<Integer> s = OrderedSet.withNaturalOrder(newStrategy());
        for (int k : insertOrder) s.add(k);
        return s;
    }

    /** Steady-state read cost: n uniform-random hits against a warm tree. */
    @Benchmark
    public void lookupUniform(Blackhole bh) {
        for (int k : probes) bh.consume(warm.contains(k));
    }
}
