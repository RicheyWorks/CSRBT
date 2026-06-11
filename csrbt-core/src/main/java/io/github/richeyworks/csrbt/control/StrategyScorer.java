package io.github.richeyworks.csrbt.control;

import java.util.List;

/**
 * Pure function from a {@link WorkloadFeatures} snapshot to a ranked list of candidate
 * strategies, each with an explicit estimated per-op cost and a one-line rationale
 * (DESIGN-adaptive-engine.md §3.2 / §9.2). Being a pure function over an immutable
 * feature vector is what makes the adaptation decision explainable and unit-testable
 * with hand-built inputs — the scorer never reads the tree.
 *
 * <p>Cost is <em>ascending</em>: index 0 is the cheapest (best) strategy. The
 * {@code MorphController} (Phase D) compares the incumbent's cost to the front of this
 * list, and the {@code MorphPolicy} decides whether the improvement clears the
 * anti-thrash gates.</p>
 */
public interface StrategyScorer {

    /**
     * Score every implemented strategy for the given workload.
     *
     * @return a non-empty list sorted by ascending {@link Score#estimatedCost()}
     *         (cheapest first); ties are broken deterministically.
     */
    List<Score> score(WorkloadFeatures features);

    /**
     * One strategy's estimated cost under a workload, with a human-readable reason.
     *
     * @param strategy      the candidate
     * @param estimatedCost lower is better; a transparent model output, not a measurement
     * @param rationale     the dominant factor behind the cost, for the §12 log line
     */
    record Score(StrategyId strategy, double estimatedCost, String rationale) { }
}
