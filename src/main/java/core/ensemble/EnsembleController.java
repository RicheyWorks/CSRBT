package core.ensemble;

import core.RedBlackTree;
import core.TreeNode1;
import core.control.CostModelStrategyScorer;
import core.control.MorphHistory;
import core.control.MorphPolicy;
import core.control.StrategyId;
import core.control.StrategyScorer;
import core.control.WorkloadFeatures;
import core.control.WorkloadMonitor;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * EnsembleController -- the measured-promotion control loop for an {@link EnsembleOrderedSet}
 * (ADR-003, step E2). It reuses the single-tree control plane <em>unchanged</em> -- snapshot the
 * {@link WorkloadMonitor}, score strategies with a {@link StrategyScorer}, gate the switch through
 * the {@link MorphPolicy} anti-thrash gates, thread a {@link MorphHistory} for cooldown/stability --
 * and differs in exactly one place: the executor. Where {@code MorphController} commits a decision
 * with {@code OrderedSet.setStrategy} (an O(n) build-aside), the ensemble already holds every
 * candidate built and kept in sync, so a commit is {@link EnsembleOrderedSet#promote} -- an
 * <b>O(1) atomic primary swap</b>, no rebuild. That swap is the whole point of paying the mirror's
 * write fan-out.
 *
 * <p>The controller is also the data-plane facade for the ensemble: callers route operations
 * through {@link #add}/{@link #remove}/{@link #contains} so each op is both applied to the ensemble
 * and folded into the monitor (the read/write mix and hot-key skew the scorer needs). Reads are
 * served by the current primary; a promotion changes which member that is, transparently.</p>
 *
 * <p>Only strategies actually present as ensemble members are promotable: the scorer's ranking is
 * filtered to available members before the policy sees it, so a strategy the ensemble does not
 * carry (e.g. a scored-but-absent Hybrid) can never win the gate, and the policy still compares
 * against the genuinely cheapest <em>available</em> candidate. Exactly one
 * {@code event=morph_eval} line is emitted per evaluation (ADR-003 E2 / DESIGN section 12), carrying
 * the workload vector, the per-member meters, and the decision.</p>
 *
 * <p>Not thread-safe beyond the ensemble's own write lock: like the rest of the engine it is
 * expected to run under a single writer (DESIGN section 4).</p>
 */
public final class EnsembleController<K> {

    private static final Logger logger = LogManager.getLogger(EnsembleController.class);

    private final EnsembleOrderedSet<K> ensemble;
    private final WorkloadMonitor       monitor;
    private final StrategyScorer        scorer;
    private final MorphPolicy           policy;

    /** StrategyId -> the member backing it, for O(1) decision -> member resolution. */
    private final Map<StrategyId, EnsembleMember<K>> byStrategy;

    private MorphHistory history = MorphHistory.initial();

    public EnsembleController(EnsembleOrderedSet<K> ensemble, WorkloadMonitor monitor,
                              StrategyScorer scorer, MorphPolicy policy) {
        this.ensemble   = Objects.requireNonNull(ensemble, "ensemble cannot be null");
        this.monitor    = Objects.requireNonNull(monitor,  "monitor cannot be null");
        this.scorer     = Objects.requireNonNull(scorer,   "scorer cannot be null");
        this.policy     = Objects.requireNonNull(policy,   "policy cannot be null");
        this.byStrategy = indexMembers(ensemble);
    }

    /** Convenience: the transparent cost-model scorer + DESIGN section 3.3 default anti-thrash policy. */
    public EnsembleController(EnsembleOrderedSet<K> ensemble, WorkloadMonitor monitor) {
        this(ensemble, monitor, new CostModelStrategyScorer(), MorphPolicy.defaults());
    }

    /** Map each member to the {@link StrategyId} whose strategy class it carries (unknown ids skipped). */
    private static <K> Map<StrategyId, EnsembleMember<K>> indexMembers(EnsembleOrderedSet<K> ens) {
        Map<StrategyId, EnsembleMember<K>> map = new EnumMap<>(StrategyId.class);
        for (EnsembleMember<K> m : ens.members()) {
            Class<?> memberStrategy = m.set().getStrategy().getClass();
            for (StrategyId id : StrategyId.values()) {
                if (id.newStrategy().getClass() == memberStrategy) {
                    map.putIfAbsent(id, m);
                    break;
                }
            }
        }
        return map;
    }

    // -- Data-plane facade: apply to the ensemble and feed the monitor --

    /** Add {@code key}; on an effective insert, record it in the monitor's op stream. */
    public boolean add(K key) {
        boolean changed = ensemble.add(key);
        if (changed) monitor.recordAdd(Objects.hashCode(key));
        return changed;
    }

    /** Remove {@code key}; on an effective delete, record it in the monitor's op stream. */
    public boolean remove(K key) {
        boolean changed = ensemble.remove(key);
        if (changed) monitor.recordRemove(Objects.hashCode(key));
        return changed;
    }

    /** Membership test served by the primary; always recorded as a read (drives skew + read mix). */
    public boolean contains(K key) {
        boolean present = ensemble.contains(key);
        monitor.recordSearch(Objects.hashCode(key), 0);
        return present;
    }

    // -- Control loop: one measured-promotion evaluation --

    /**
     * Run one evaluation, advancing the cooldown clock by {@code opsElapsed} (ops counted since
     * the previous evaluation). Snapshots the workload, scores the <em>available</em> members,
     * asks the {@link MorphPolicy} whether to switch off the incumbent, and on a promote performs
     * the O(1) primary swap. Emits exactly one {@code event=morph_eval} line and returns the
     * {@link PromotionResult}.
     */
    public PromotionResult evaluateAndMaybePromote(int opsElapsed) {
        WorkloadFeatures f = monitor.snapshot();
        StrategyId current = currentPrimaryId();

        // Restrict the ranking to strategies the ensemble can actually serve.
        List<StrategyScorer.Score> available = new ArrayList<>();
        for (StrategyScorer.Score s : scorer.score(f)) {
            if (byStrategy.containsKey(s.strategy())) available.add(s);
        }

        MorphPolicy.Decision decision = policy.evaluate(current, available, f, history);
        StrategyId top = available.isEmpty() ? current : available.get(0).strategy();

        boolean    promoted = false;
        StrategyId to       = current;
        String     reason;

        if (decision == MorphPolicy.Decision.MORPH && !available.isEmpty()) {
            StrategyId candidate = available.get(0).strategy();
            EnsembleMember<K> target = byStrategy.get(candidate);
            boolean swapped = target != null && ensemble.promote(target);
            if (swapped) {
                promoted = true;
                to       = candidate;
                history  = history.afterMorph();
                reason   = "promoted " + current + "->" + candidate + " (O(1) swap)";
            } else {
                // Winner already primary (or unmapped): a hold for cooldown/streak purposes.
                history = history.observed(top, opsElapsed);
                reason  = "no-op promote; kept " + current;
            }
        } else {
            history = history.observed(top, opsElapsed);
            reason  = (current != null && top == current)
                    ? "incumbent " + current + " already optimal"
                    : "hold; gates not cleared";
        }

        emitMorphEval(f, available, current, to, promoted);
        return new PromotionResult(promoted, current, to, reason);
    }

    /** The history this controller is carrying (cooldown clock + win streak). */
    public MorphHistory history() { return history; }

    /** The {@link StrategyId} of the member currently serving reads, or {@code null} if unmapped. */
    public StrategyId currentPrimaryId() {
        EnsembleMember<K> p = ensemble.primary();
        for (Map.Entry<StrategyId, EnsembleMember<K>> e : byStrategy.entrySet()) {
            if (e.getValue() == p) return e.getKey();
        }
        return null;
    }

    // -- Observability --

    /** One structured line per evaluation: workload vector, ranked costs, per-member meters, decision. */
    private void emitMorphEval(WorkloadFeatures f, List<StrategyScorer.Score> ranked,
                               StrategyId from, StrategyId to, boolean promoted) {
        StringBuilder scores = new StringBuilder("[");
        for (int i = 0; i < ranked.size(); i++) {
            StrategyScorer.Score s = ranked.get(i);
            if (i > 0) scores.append(", ");
            scores.append(s.strategy()).append(':').append(String.format("%.4f", s.estimatedCost()));
        }
        scores.append(']');
        logger.info("event=morph_eval {} scores={} members={} decision={} from={} to={} promoted={}",
                f, scores, meters(), promoted ? "PROMOTE" : "HOLD", from, to, promoted);
    }

    /** Per-member realized meters (ADR-003 E2): node height, size, avg insert/delete time. */
    private String meters() {
        List<EnsembleMember<K>> members = ensemble.members();
        EnsembleMember<K> prim = ensemble.primary();
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < members.size(); i++) {
            EnsembleMember<K> m = members.get(i);
            if (i > 0) sb.append(", ");
            sb.append(String.format("%s{h=%d n=%d insMs=%.4f delMs=%.4f%s}",
                    m.strategyName(), height(m), m.set().size(),
                    m.set().avgInsertTimeMs(), m.set().avgDeleteTimeMs(),
                    m == prim ? " *primary" : ""));
        }
        return sb.append(']').toString();
    }

    /** Node height of a member's tree (NIL = 0), iterative so a deep splay tree cannot overflow. */
    private int height(EnsembleMember<K> m) {
        RedBlackTree<K> engine = m.set().getEngine();
        TreeNode1<K> root = engine.getRoot();
        if (root == null || root.isNil()) return 0;
        Deque<TreeNode1<K>> nodes  = new ArrayDeque<>();
        Deque<Integer>      depths = new ArrayDeque<>();
        nodes.push(root); depths.push(1);
        int max = 0;
        while (!nodes.isEmpty()) {
            TreeNode1<K> n = nodes.pop();
            int d = depths.pop();
            if (d > max) max = d;
            TreeNode1<K> l = n.getLeft(), r = n.getRight();
            if (l != null && !l.isNil()) { nodes.push(l); depths.push(d + 1); }
            if (r != null && !r.isNil()) { nodes.push(r); depths.push(d + 1); }
        }
        return max;
    }

    /**
     * The outcome of one evaluation. {@code from} and {@code to} are equal on a hold; a
     * promotion reports {@code promoted=true} with {@code to} the newly-serving strategy.
     */
    public record PromotionResult(boolean promoted, StrategyId from, StrategyId to, String reason) { }
}
