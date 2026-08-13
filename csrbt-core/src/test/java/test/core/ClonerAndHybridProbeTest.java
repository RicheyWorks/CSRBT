package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.augment.GenericIntervalAugmentor;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.util.TreeCloner;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probes (bug audit 2026-08-12, deep sweep) for three seam defects:
 *
 * <p>C-1: {@code TreeCloner.snapshot()} built the clone around the ORIGINAL strategy
 * instance, so a stateful strategy (Hybrid's counters) was mutated by operations on
 * the clone — against the class's "no references are shared" contract. C-2:
 * {@code HybridStrategy} is parameterized ({@code depthThreshold}) but did not
 * override {@code samePolicyAs}, so a real re-parameterizing morph was refused as a
 * same-policy no-op — the exact trap {@code TreeStrategy.samePolicyAs}'s javadoc
 * names. C-3: {@code OrderedSet.buildFromSorted} rebuilt every node with the default
 * augmentor and never reapplied a pre-installed custom one (unlike setStrategy and
 * selfRepair), so interval queries silently returned empty forever after.</p>
 */
@DisplayName("Cloner isolation, Hybrid policy identity, buildFromSorted augmentor")
class ClonerAndHybridProbeTest {

    @Test
    @DisplayName("C-1: operations on a clone do not mutate the original's strategy state")
    void cloneDoesNotShareStrategyState() {
        HybridStrategy<Integer> strategy = new HybridStrategy<>();
        TreeContext ctx = new TreeContext(strategy);
        for (int k = 0; k < 50; k++) ctx.add(k);
        int insertsBefore = strategy.getInsertCount();

        TreeContext clone = new TreeCloner(ctx).snapshot();
        for (int k = 100; k < 200; k++) clone.add(k);

        assertEquals(insertsBefore, strategy.getInsertCount(),
                "inserting into the clone mutated the ORIGINAL's strategy counters — "
                + "the strategy instance is shared, violating the deep-copy contract");
        assertEquals(50, ctx.getSize(), "original contents untouched");
        assertEquals(150, clone.getSize(), "clone got the new keys");
    }

    @Test
    @DisplayName("C-2: Hybrid(4) → Hybrid(64) is a real morph, not a same-policy no-op")
    void hybridReparameterizationIsARealMorph() {
        assertFalse(new HybridStrategy<Integer>(4).samePolicyAs(new HybridStrategy<Integer>(64)),
                "different depth thresholds are different policies");
        assertTrue(new HybridStrategy<Integer>(4).samePolicyAs(new HybridStrategy<Integer>(4)),
                "same threshold is the same policy");

        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new HybridStrategy<Integer>(4));
        for (int k = 0; k < 32; k++) set.add(k);
        assertTrue(set.setStrategy(new HybridStrategy<>(64)),
                "setStrategy must perform the re-parameterizing morph, not refuse it");
    }

    @Test
    @DisplayName("C-3: a custom augmentor survives buildFromSorted — interval queries keep working")
    void buildFromSortedKeepsCustomAugmentor() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        GenericIntervalAugmentor<Integer> iv = GenericIntervalAugmentor.natural();
        set.setAugmentor(iv);

        List<Integer> keys = new ArrayList<>();
        for (int k = 1; k <= 7; k++) keys.add(k);
        set.buildFromSorted(keys);

        iv.insertInterval(set, 2, 100);
        assertFalse(iv.stabQuery(set, 50).isEmpty(),
                "interval [2,100] covers 50 — an empty stab result means the bulk build "
                + "silently discarded the installed augmentor's per-node maintenance");
    }
}
