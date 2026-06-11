package io.github.richeyworks.csrbt.control;

import io.github.richeyworks.csrbt.strategy.TreeStrategy;

/**
 * The executor seam the {@link MorphController} drives (ADR-002 step 6, Phase D,
 * decision §12.1 B1 of the plan). A morph target knows its current balancing strategy and
 * can attempt a health-gated swap to a new one, reporting whether the swap was published.
 *
 * <p>Implemented directly by {@code OrderedSet<K>} and by {@code TreeContext} (for
 * {@code Integer}). The controller holds the <em>target</em> — never a captured inner
 * {@code OrderedSet} — so a swap always routes to the live engine even after a snapshot
 * load reassigns the underlying set ({@code TreeContext.loadSnapshot}).</p>
 *
 * <p>The contract is exactly the existing build-aside + {@code StrategyHealthCheck} +
 * publish path: {@link #setStrategy} returns {@code true} only when the candidate validates
 * and is swapped in; a rejected (or same-class/null) candidate leaves the incumbent
 * untouched and returns {@code false}.</p>
 */
public interface StrategyMorphTarget<K> {

    /**
     * Attempt a health-gated swap to {@code newStrategy}, rebuilding from the current
     * contents and publishing only on a clean validation.
     *
     * @return {@code true} iff the candidate validated and was published.
     */
    boolean setStrategy(TreeStrategy<K> newStrategy);

    /** The currently-installed balancing strategy. */
    TreeStrategy<K> getStrategy();
}
