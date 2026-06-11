package io.github.richeyworks.csrbt.control;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.List;

/**
 * Orchestrates one adaptation evaluation (ADR-002 step 6, Phase D / D1): snapshot the
 * workload, score the strategies, ask the {@link MorphPolicy} whether to switch, and on
 * {@link MorphPolicy.Decision#MORPH} drive the health-gated executor — emitting exactly one
 * {@code event=morph_eval} line per call (DESIGN §12) and returning a {@link MorphResult}.
 *
 * <p>Pipeline: {@code monitor.snapshot() -> scorer.score() -> policy.evaluate() ->
 * (MORPH) target.setStrategy(candidate.newStrategy())}. The executor is reached through the
 * {@link StrategyMorphTarget} seam (plan decision §12.1 B1), so the controller never captures
 * an inner {@code OrderedSet} reference a snapshot load could leave stale; every swap routes
 * to the live engine. The seam's boolean return <em>is</em> the health-gate verdict
 * (build-aside + {@code StrategyHealthCheck} + publish), so a rejected candidate leaves the
 * incumbent live and is treated as a hold (DESIGN §3.4) — reused, not rebuilt.</p>
 *
 * <p>The controller owns the {@link MorphHistory} (cooldown clock + win streak), advancing it
 * with {@link MorphHistory#observed} on a hold (or a rejected morph) and resetting it with
 * {@link MorphHistory#afterMorph} on a committed morph. Not thread-safe: like the rest of the
 * engine it is expected to run under the facade's single write lock (DESIGN §4).</p>
 */
public final class MorphController<K> {

    private static final Logger logger = LogManager.getLogger(MorphController.class);

    private final StrategyMorphTarget<K> target;
    private final WorkloadMonitor        monitor;
    private final StrategyScorer         scorer;
    private final MorphPolicy            policy;

    private MorphHistory history = MorphHistory.initial();

    public MorphController(StrategyMorphTarget<K> target, WorkloadMonitor monitor,
                           StrategyScorer scorer, MorphPolicy policy) {
        if (target  == null) throw new IllegalArgumentException("target cannot be null");
        if (monitor == null) throw new IllegalArgumentException("monitor cannot be null");
        if (scorer  == null) throw new IllegalArgumentException("scorer cannot be null");
        if (policy  == null) throw new IllegalArgumentException("policy cannot be null");
        this.target  = target;
        this.monitor = monitor;
        this.scorer  = scorer;
        this.policy  = policy;
    }

    /**
     * Run one evaluation against incumbent {@code current}, advancing the cooldown clock by
     * {@code opsElapsed} (ops counted since the previous evaluation). Emits one
     * {@code event=morph_eval} line and returns the {@link MorphResult}.
     */
    public MorphResult evaluateAndMaybeMorph(StrategyId current, int opsElapsed) {
        WorkloadFeatures f = monitor.snapshot();
        List<StrategyScorer.Score> ranked = scorer.score(f);
        MorphPolicy.Decision decision = policy.evaluate(current, ranked, f, history);

        StrategyId topCandidate = ranked.isEmpty() ? current : ranked.get(0).strategy();

        boolean    morphed      = false;
        boolean    healthPassed = false;
        long       buildNanos   = 0L;
        StrategyId to           = current;
        String     reason;

        if (decision == MorphPolicy.Decision.MORPH && !ranked.isEmpty()) {
            StrategyId candidate = ranked.get(0).strategy();
            long t0 = System.nanoTime();
            boolean ok = target.setStrategy(candidate.<K>newStrategy());
            buildNanos = System.nanoTime() - t0;
            if (ok) {
                morphed      = true;
                healthPassed = true;
                to           = candidate;
                history      = history.afterMorph();
                reason       = "morphed " + current + "->" + candidate;
            } else {
                // Health gate rejected the candidate: keep the incumbent and treat this
                // evaluation as a hold for cooldown / streak purposes (plan §12.3 F3/F7).
                healthPassed = false;
                to           = current;
                history      = history.observed(candidate, opsElapsed);
                reason       = "health-rejected " + candidate + "; kept " + current;
            }
        } else {
            history = history.observed(topCandidate, opsElapsed);
            reason  = (current != null && topCandidate == current)
                    ? "incumbent " + current + " already optimal"
                    : "hold; gates not cleared";
        }

        emitMorphEval(f, ranked, decision, current, to, morphed, healthPassed, buildNanos);
        return new MorphResult(morphed, current, to, healthPassed, buildNanos, reason);
    }

    /** The history this controller is carrying (cooldown clock + win streak). */
    public MorphHistory history() { return history; }

    /** One structured line per evaluation (DESIGN §12): features, ranked scores, decision. */
    private void emitMorphEval(WorkloadFeatures f, List<StrategyScorer.Score> ranked,
                               MorphPolicy.Decision decision, StrategyId from, StrategyId to,
                               boolean morphed, boolean healthPassed, long buildNanos) {
        StringBuilder scores = new StringBuilder("[");
        for (int i = 0; i < ranked.size(); i++) {
            StrategyScorer.Score s = ranked.get(i);
            if (i > 0) scores.append(", ");
            scores.append(s.strategy()).append(':').append(String.format("%.4f", s.estimatedCost()));
        }
        scores.append(']');
        logger.info("event=morph_eval {} scores={} decision={} from={} to={} morphed={} healthPassed={} buildNanos={}",
                f, scores, decision, from, to, morphed, healthPassed, buildNanos);
    }

    /**
     * The outcome of one evaluation. {@code from} and {@code to} are equal on a hold or a
     * health-rejected morph; {@code healthPassed} / {@code buildNanos} are meaningful only when
     * a morph was attempted (a plain hold reports {@code false} / {@code 0}).
     */
    public record MorphResult(boolean morphed, StrategyId from, StrategyId to,
                              boolean healthPassed, long buildNanos, String reason) { }
}
