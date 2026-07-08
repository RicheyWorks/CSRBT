package benchmarks;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.infra.Blackhole;

import java.util.Comparator;
import java.util.Random;
import java.util.concurrent.TimeUnit;

/**
 * The 2026-07 measuring reads: {@code searchDepth} vs {@code contains}, single set and ensemble.
 * The design claim was "one walk answers containment AND depth, so the measured read should cost
 * the same as the plain one" — this row makes that claim falsifiable. Uniform probes over a
 * shuffled-insert RB set (50% hit rate), and a two-member RB+AVL MIRROR ensemble in front of the
 * same shape (its read is one indirection over the primary's walk).
 */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@State(Scope.Thread)
public class SearchDepthBenchmark {

    private static final int PROBE_MASK = (1 << 17) - 1;   // 131072 probes, power of two

    @Param({"100000"})
    public int n;

    private OrderedSet<Integer> set;
    private EnsembleOrderedSet<Integer> ensemble;
    private int[] probes;
    private int idx;

    @Setup(Level.Trial)
    public void setup() {
        Random rnd = new Random(7);
        int[] insertOrder = new int[n];
        for (int i = 0; i < n; i++) {
            insertOrder[i] = i * 2;                          // evens present, odds absent (50% hits)
        }
        for (int i = n - 1; i > 0; i--) {                    // Fisher-Yates shuffle
            int j = rnd.nextInt(i + 1);
            int t = insertOrder[i]; insertOrder[i] = insertOrder[j]; insertOrder[j] = t;
        }

        set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        ensemble = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .build();
        for (int v : insertOrder) {
            set.add(v);
            ensemble.add(v);
        }

        probes = new int[PROBE_MASK + 1];
        for (int i = 0; i < probes.length; i++) {
            probes[i] = rnd.nextInt(2 * n);                  // uniform over present + absent
        }
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        ensemble.close();
    }

    private int nextProbe() {
        return probes[idx++ & PROBE_MASK];
    }

    @Benchmark
    public void setContains(Blackhole bh) {
        bh.consume(set.contains(nextProbe()));
    }

    @Benchmark
    public void setSearchDepth(Blackhole bh) {
        bh.consume(set.searchDepth(nextProbe()));
    }

    @Benchmark
    public void ensembleContains(Blackhole bh) {
        bh.consume(ensemble.contains(nextProbe()));
    }

    @Benchmark
    public void ensembleSearchDepth(Blackhole bh) {
        bh.consume(ensemble.searchDepth(nextProbe()));
    }
}
