package io.github.richeyworks.csrbt.evolution;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.control.WorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.event.TreeEventListener;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.List;
import java.util.Objects;

/**
 * The search loop (ADR-011 V3): a caller-cadenced controller that lets a {@link PolicyBandit}
 * try parameterized policies as live <em>trials</em> on one designated shadow member of a
 * {@link EnsembleOrderedSet}, score them with {@link Fitness}, and promote a proven winner
 * through the {@link MorphPolicy} anti-thrash gates. No background threads — the caller
 * decides when a window begins ({@link #beginTrial()}) and ends ({@link #endTrial(int)}),
 * like every controller in this codebase.
 *
 * <h2>The loop</h2>
 * <ol>
 *   <li>{@code beginTrial()} — the bandit selects an arm (UCB1); the trial member's set is
 *       morphed to that arm's strategy via {@code OrderedSet.setStrategy} — i.e. through the
 *       <b>health gate</b>, including the strategy-supplied invariant hook (ADR-011 V1). A
 *       candidate the gate rejects is disqualified on the spot and the next arm is tried.</li>
 *   <li>The caller streams ops through {@link #add}/{@link #remove}/{@link #contains} for a
 *       window: the ensemble fans writes out (the trial shadow sees the sampled stream), the
 *       {@link WorkloadMonitor} accumulates the realized meters.</li>
 *   <li>{@code endTrial(opsElapsed)} — first the arm's own invariant is re-checked on the
 *       trial tree: a parameterization that survived build-aside but degraded under live
 *       churn (the (5,3) class) is caught <em>here</em> and disqualified — V1's finding,
 *       running as a mechanism. A sound arm is scored ({@link Fitness}) and rewarded; then
 *       promotion is considered: the bandit's best arm must currently be on trial, and must
 *       clear the {@code MorphPolicy} gates (cooldown / stability / margin) against the
 *       incumbent primary's fitness on the same features. A promote is the ensemble's
 *       sync-on-promote (O(n) rebuild, then the O(1) swap) — and the deposed primary becomes
 *       the new trial slot: the throne and the laboratory trade places.</li>
 * </ol>
 *
 * <p><b>Gate reuse, exactly.</b> The policy's legacy desirability form is fed
 * {@code score = −cost}: its improvement fraction {@code (cand−cur)/|cur|} then equals the
 * cost reduction {@code (incumbentCost−armCost)/incumbentCost} — the same number
 * {@code MorphPolicy.evaluate} computes for the fixed strategies, so V3 promotion discipline
 * is bit-identical to ADR-002's, not a parallel re-implementation. Win-streak bookkeeping is
 * arm-keyed here (the {@code StrategyId}-keyed {@link io.github.richeyworks.csrbt.control.MorphHistory} cannot name
 * a grid point — the parameterized-identity consequence ADR-011 §4 predicted).</p>
 *
 * <p><b>Comparable fitness.</b> Trial and incumbent are scored against the <em>same</em>
 * {@link WorkloadFeatures} snapshot; only the structural term ({@link Fitness#meanDepth})
 * and size differ. The realized write term is the stream's, not per-member — honest, since
 * shadows see a sampled stream; per-member rotation meters are a held refinement.</p>
 *
 * <p>{@link TreeEvent.Trial} events (TRIED / SCORED / DISQUALIFIED / SELECTED) are emitted
 * to a registered listener, so a {@code TreeSessionRecorder} can replay the search in the
 * arena. Allocation-free when unobserved, like every event source here.</p>
 */
public final class PolicySearchController<K> {

    private static final Logger logger = LogManager.getLogger(PolicySearchController.class);

    private final EnsembleOrderedSet<K> ensemble;
    private final WorkloadMonitor monitor;
    private final PolicyBandit bandit;
    private final MorphPolicy policy;

    private EnsembleMember<K> trialMember;
    private PolicyGenome currentArm;          // non-null while a trial window is open
    private int opsSinceLastPromotion;
    private PolicyGenome lastWinner;
    private int winStreak;

    private volatile TreeEventListener<K> events;

    /** The verdict of one {@link #endTrial(int)} evaluation, explainable in one line. */
    public record TrialResult(PolicyGenome arm, boolean scored, double armCost,
                              double incumbentCost, boolean promoted, String reason) { }

    public PolicySearchController(EnsembleOrderedSet<K> ensemble, EnsembleMember<K> trialMember,
                                  WorkloadMonitor monitor, PolicyBandit bandit, MorphPolicy policy) {
        this.ensemble = Objects.requireNonNull(ensemble, "ensemble cannot be null");
        this.trialMember = Objects.requireNonNull(trialMember, "trialMember cannot be null");
        this.monitor = Objects.requireNonNull(monitor, "monitor cannot be null");
        this.bandit = Objects.requireNonNull(bandit, "bandit cannot be null");
        this.policy = Objects.requireNonNull(policy, "policy cannot be null");
        if (!trialMember.isStrategyBacked()) {
            throw new IllegalArgumentException("trial member must be strategy-backed (engine members have no strategy seam)");
        }
        if (trialMember == ensemble.primary()) {
            throw new IllegalArgumentException("trial member must not be the serving primary");
        }
    }

    /** Register a structured-event listener for Trial events; {@code null} unregisters. */
    public void setEventListener(TreeEventListener<K> listener) { this.events = listener; }

    // ── Data plane (mirrors EnsembleController: apply + feed the monitor) ──────────

    public boolean add(K key) {
        boolean changed = ensemble.add(key);
        if (changed) monitor.recordAdd(Objects.hashCode(key));
        return changed;
    }

    public boolean remove(K key) {
        boolean changed = ensemble.remove(key);
        if (changed) monitor.recordRemove(Objects.hashCode(key));
        return changed;
    }

    public boolean contains(K key) {
        boolean present = ensemble.contains(key);
        monitor.recordSearch(Objects.hashCode(key), 0);
        return present;
    }

    // ── The search loop ─────────────────────────────────────────────────────────

    /**
     * Open a trial window: UCB1-select an arm and morph the trial member to it through the
     * health gate. Gate-rejected arms are disqualified (DISQUALIFIED event) and selection
     * moves on; bounded by the arm count.
     *
     * @return the arm now on trial
     * @throws IllegalStateException if a window is already open, or every arm is disqualified
     */
    public PolicyGenome beginTrial() {
        if (currentArm != null) {
            throw new IllegalStateException("trial window already open on arm " + currentArm);
        }
        if (trialMember == null) {
            throw new IllegalStateException("no strategy-backed trial slot left after promotion");
        }
        OrderedSet<K> trialSet = trialMember.orderedSet();
        for (int attempts = bandit.arms().size(); attempts > 0; attempts--) {
            PolicyBandit.Selection sel = bandit.select();           // throws when exhausted
            PolicyGenome arm = sel.arm();
            TreeStrategy<K> candidate = arm.toStrategy();
            boolean accepted = arm.equals(armOf(trialSet.getStrategy()))
                    || trialSet.setStrategy(candidate);             // health gate, V1 hook included
            if (accepted) {
                currentArm = arm;
                logger.info("event=trial_begin {} arms={}", sel, bandit.statsLine());
                emit(new TreeEvent.Trial<>(arm.toString(), "TRIED", Double.NaN, sel.pulls()));
                return arm;
            }
            bandit.disqualify(arm, "health gate rejected candidate at build-aside");
            logger.warn("event=trial_disqualified arm={} reason=health-gate", arm);
            emit(new TreeEvent.Trial<>(arm.toString(), "DISQUALIFIED", Double.NaN, sel.pulls()));
        }
        throw new IllegalStateException("no arm passed the health gate — search space exhausted");
    }

    /**
     * Close the trial window after {@code opsElapsed} streamed ops: invariant-check the arm
     * on its own tree, score and reward it (or disqualify it), and consider promotion
     * through the {@link MorphPolicy} gates. Exactly one {@code event=trial_eval} line.
     */
    public TrialResult endTrial(int opsElapsed) {
        if (currentArm == null) throw new IllegalStateException("no trial window open");
        PolicyGenome arm = currentArm;
        currentArm = null;
        opsSinceLastPromotion += Math.max(0, opsElapsed);

        OrderedSet<K> trialSet = trialMember.orderedSet();
        WorkloadFeatures f = monitor.snapshot();

        // 1. The arm answers to its own invariant first (the live (5,3) mechanism).
        List<String> violations = trialSet.getStrategy().validateInvariant(trialSet.getEngine());
        if (!violations.isEmpty()) {
            bandit.disqualify(arm, "own invariant failed under live churn: " + violations.get(0));
            logger.warn("event=trial_eval arm={} verdict=DISQUALIFIED violations={} arms={}",
                    arm, violations.size(), bandit.statsLine());
            emit(new TreeEvent.Trial<>(arm.toString(), "DISQUALIFIED", Double.NaN, bandit.pulls(arm)));
            return new TrialResult(arm, false, Double.NaN, Double.NaN, false,
                    "disqualified: " + violations.get(0));
        }

        // 2. Score the arm and the incumbent on the same features; reward the bandit.
        Fitness.Evaluation armEval = Fitness.evaluate(
                f, Fitness.meanDepth(trialSet.getEngine()), trialSet.size());
        OrderedSet<K> primarySet = ensemble.primary().isStrategyBacked()
                ? ensemble.primary().orderedSet() : null;
        double incumbentCost = (primarySet == null) ? Double.POSITIVE_INFINITY
                : Fitness.evaluate(f, Fitness.meanDepth(primarySet.getEngine()), primarySet.size()).cost();
        bandit.recordCost(arm, armEval.cost());
        emit(new TreeEvent.Trial<>(arm.toString(), "SCORED", armEval.cost(), bandit.pulls(arm)));

        // 3. Win-streak bookkeeping (arm-keyed; MorphHistory can't name a grid point).
        PolicyGenome winner = bandit.bestArm();
        winStreak = winner != null && winner.equals(lastWinner) ? winStreak + 1 : 1;
        lastWinner = winner;

        // 4. Promotion: best arm must be the one on trial, and −cost desirability must clear
        //    the MorphPolicy gates (improvement = exact cost-reduction fraction; see class doc).
        boolean promoted = false;
        String reason = "hold";
        if (winner != null && winner.equals(arm)
                && policy.shouldMorph(-incumbentCost, -bandit.meanCost(winner),
                                      opsSinceLastPromotion, winStreak)) {
            EnsembleMember<K> deposed = ensemble.primary();
            promoted = ensemble.promote(trialMember);               // sync-on-promote + O(1) swap
            if (promoted) {
                trialMember = pickTrialSlot(deposed);               // the lab moves to the old throne
                opsSinceLastPromotion = 0;
                winStreak = 0;
                lastWinner = null;
                reason = "promoted " + arm + " (sync-on-promote)";
                emit(new TreeEvent.Trial<>(arm.toString(), "SELECTED", armEval.cost(), bandit.pulls(arm)));
            } else {
                reason = "promote refused by ensemble";
            }
        }

        logger.info("event=trial_eval arm={} cost={} incumbent={} streak={} ops={} decision={} arms={}",
                arm, String.format("%.4f", armEval.cost()), String.format("%.4f", incumbentCost),
                winStreak, opsSinceLastPromotion, promoted ? "PROMOTE" : "HOLD", bandit.statsLine());
        return new TrialResult(arm, true, armEval.cost(), incumbentCost, promoted, reason);
    }

    /** The member currently serving as the trial slot (changes on promotion). */
    public EnsembleMember<K> trialMember() { return trialMember; }

    /**
     * The trial slot after a promotion: the deposed primary when it has a strategy seam,
     * else the first other strategy-backed, active non-primary — or {@code null}, in which
     * case the next {@link #beginTrial()} fails loudly rather than morphing nothing.
     */
    private EnsembleMember<K> pickTrialSlot(EnsembleMember<K> deposed) {
        if (deposed.isStrategyBacked() && deposed.isActive()) return deposed;
        for (EnsembleMember<K> m : ensemble.members()) {
            if (m != ensemble.primary() && m.isStrategyBacked() && m.isActive()) return m;
        }
        return null;
    }

    /** The arm whose strategy the trial member is currently running, or {@code null}. */
    private PolicyGenome armOf(TreeStrategy<K> strategy) {
        for (PolicyGenome g : bandit.arms()) {
            if (g.toStrategy().getClass() == strategy.getClass()) {
                if (!(strategy instanceof core.strategy.WeightBalancedStrategy<K> ws)) return g;
                if (g.family().parameterized()
                        && g.delta() == ws.delta() && g.ratio() == ws.ratio()) return g;
            }
        }
        return null;
    }

    private void emit(TreeEvent<K> e) {
        TreeEventListener<K> l = events;
        if (l != null) l.onEvent(e);
    }
}
