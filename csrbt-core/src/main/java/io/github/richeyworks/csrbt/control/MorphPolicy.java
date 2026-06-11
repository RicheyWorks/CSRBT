package io.github.richeyworks.csrbt.control;

import java.util.List;

/**
 * The control plane's anti-thrash gate (ADR-002 step 6, Phase C), promoted from
 * {@code GenomeDrivenTreeController.MorphPolicy} to a top-level
 * {@code core.control} unit. Morphing is O(n), so a switch is allowed only when it
 * clears all of the DESIGN §3.3 gates:
 *
 * <ul>
 *   <li><b>cooldown</b> — at least {@code cooldownOps} ops since the last morph;</li>
 *   <li><b>stability</b> — the candidate has won at least {@code stabilityWins}
 *       consecutive evaluations;</li>
 *   <li><b>minimum improvement</b> — the candidate beats the incumbent by at least
 *       {@code minImprovement} (fractional), not merely marginally.</li>
 * </ul>
 *
 * <p>Two entry points share the same {@linkplain #gatesPass three-gate core} so they can
 * never drift:</p>
 * <ul>
 *   <li>{@link #evaluate} — the design's signature: reads the {@link StrategyScorer}'s
 *       ascending-cost ranking and a {@link MorphHistory}, computing the cost-reduction
 *       improvement exactly as the DESIGN §10 worked trace does
 *       ({@code (incumbentCost − candidateCost) / incumbentCost}).</li>
 *   <li>{@link #shouldMorph} — the legacy desirability form (higher = better), preserved
 *       byte-for-byte so the existing controller and {@code MorphPolicyTest} keep their
 *       semantics during the strangler period.</li>
 * </ul>
 *
 * <p>{@code WorkloadFeatures} is accepted by {@link #evaluate} for the size-based
 * amortization gate described in DESIGN §3.3; that gate is not yet enforced (parity with
 * the legacy policy) and is a documented future addition.</p>
 */
public final class MorphPolicy {

    /** The policy's verdict for one evaluation. */
    public enum Decision { HOLD, MORPH }

    private final int    cooldownOps;
    private final double minImprovement;   // fractional, e.g. 0.20 = 20%
    private final int    stabilityWins;

    public MorphPolicy(int cooldownOps, double minImprovement, int stabilityWins) {
        this.cooldownOps    = Math.max(0, cooldownOps);
        this.minImprovement = Math.max(0.0, minImprovement);
        this.stabilityWins  = Math.max(1, stabilityWins);
    }

    /** Defaults from DESIGN §3.3: 4000-op cooldown, 20% margin, 3 stability wins. */
    public static MorphPolicy defaults() { return new MorphPolicy(4000, 0.20, 3); }

    /**
     * Decide whether to morph off {@code current}, given the scorer's ascending-cost
     * {@code ranked} list and the {@code history}. Holds when the incumbent is already the
     * cheapest, when the front-runner is not actually cheaper, or when any gate fails.
     *
     * @param current  the live strategy (may be {@code null} if unknown → treated as max cost)
     * @param ranked   scores sorted ascending by cost (cheapest first); {@code get(0)} is the candidate
     * @param features current workload (reserved for amortization; not yet gated)
     * @param history  cooldown clock + win streak; {@code null} is treated as {@link MorphHistory#initial()}
     */
    public Decision evaluate(StrategyId current, List<StrategyScorer.Score> ranked,
                             WorkloadFeatures features, MorphHistory history) {
        if (ranked == null || ranked.isEmpty()) return Decision.HOLD;

        StrategyScorer.Score best = ranked.get(0);
        if (current != null && best.strategy() == current) return Decision.HOLD; // already optimal

        double candidateCost = best.estimatedCost();
        double incumbentCost = (current == null) ? Double.POSITIVE_INFINITY : costOf(ranked, current);
        if (candidateCost >= incumbentCost) return Decision.HOLD;                // not actually cheaper

        double improvement = (incumbentCost - candidateCost) / Math.max(1e-9, Math.abs(incumbentCost));
        MorphHistory h = (history == null) ? MorphHistory.initial() : history;
        boolean pass = gatesPass(improvement, h.opsSinceLastMorph(), h.consecutiveWins(best.strategy()));
        return pass ? Decision.MORPH : Decision.HOLD;
    }

    /**
     * Legacy desirability gate (higher score = better), preserved exactly from
     * {@code GenomeDrivenTreeController.MorphPolicy} so its behaviour is identical.
     */
    public boolean shouldMorph(double currentScore, double candidateScore,
                               int opsSinceLastMorph, int consecutiveWins) {
        if (candidateScore <= currentScore) return false;                       // must be better
        double improvement = (candidateScore - currentScore) / Math.max(1e-9, Math.abs(currentScore));
        return gatesPass(improvement, opsSinceLastMorph, consecutiveWins);
    }

    /** The shared three-gate core: cooldown, then stability, then the improvement margin. */
    private boolean gatesPass(double improvementFraction, int opsSinceLastMorph, int consecutiveWins) {
        if (opsSinceLastMorph < cooldownOps)  return false;   // cooldown
        if (consecutiveWins   < stabilityWins) return false;  // stability
        return improvementFraction >= minImprovement;         // by a margin
    }

    private static double costOf(List<StrategyScorer.Score> ranked, StrategyId id) {
        for (StrategyScorer.Score s : ranked) {
            if (s.strategy() == id) return s.estimatedCost();
        }
        return Double.POSITIVE_INFINITY; // incumbent not scored → any scored candidate beats it
    }

    public int    cooldownOps()    { return cooldownOps; }
    public double minImprovement() { return minImprovement; }
    public int    stabilityWins()  { return stabilityWins; }
}
