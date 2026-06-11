package test.core;

import core.OrderedSet;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;
import core.strategy.WeightBalancedStrategy;

import net.jqwik.api.Arbitraries;
import net.jqwik.api.Arbitrary;
import net.jqwik.api.Combinators;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import net.jqwik.api.Provide;
import net.jqwik.api.Tuple;
import net.jqwik.api.Tuple.Tuple2;

import java.util.List;
import java.util.TreeSet;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * ADR-013 action item 6 — the G2 down payment. The oracle-churn pattern the suite
 * already uses (seeded op sequences vs {@link TreeSet}), now with jqwik's generated
 * sequences and shrinking: when an invariant breaks, jqwik reduces the failing
 * sequence to a minimal counterexample instead of handing us a 10k-op haystack.
 *
 * <p>Generators stay modest (sequences ≤ 200 ops, keys in a tight range to force
 * add/remove collisions) so the property runs inside the suite's 15 s timeout
 * budget across all four strategies.</p>
 */
class OrderedSetPropertyTest {

    @Provide
    Arbitrary<Tuple2<Integer, List<Integer>>> opsAndStrategy() {
        Arbitrary<Integer> strategyIdx = Arbitraries.integers().between(0, 3);
        Arbitrary<List<Integer>> ops = Arbitraries.integers().between(-32, 32) // tight range: collisions on purpose
                .list().ofMinSize(0).ofMaxSize(200);
        return Combinators.combine(strategyIdx, ops).as(Tuple::of);
    }

    private static final List<Supplier<TreeStrategy<Integer>>> STRATEGIES = List.of(
            RedBlackStrategy::new,
            AVLStrategy::new,
            SplayStrategy::new,
            WeightBalancedStrategy::new);

    @Property(tries = 250)
    void behavesLikeTreeSetUnderMixedAddRemove(@ForAll("opsAndStrategy") Tuple2<Integer, List<Integer>> input) {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(STRATEGIES.get(input.get1()).get());
        TreeSet<Integer> oracle = new TreeSet<>();

        for (int op : input.get2()) {
            // sign chooses the operation, magnitude the key — one generator, full op mix
            if (op >= 0) {
                assertEquals(oracle.add(op), set.add(op));
            } else {
                assertEquals(oracle.remove(-op), set.remove(-op));
            }
            assertEquals(oracle.size(), set.size());
        }
        for (int k = -32; k <= 32; k++) {
            assertEquals(oracle.contains(k), set.contains(k), "contains(" + k + ")");
        }
    }
}
