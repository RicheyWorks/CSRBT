package io.github.richeyworks.csrbt.evolution;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.control.WorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.event.TreeEventListener;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Random;
import java.util.Set;

/**
 * Evolution proper (ADR-011 V4): caller-cadenced (μ+λ) selection over {@link PolicyGenome}s
 * on a live ensemble. Where V3's bandit explored a fixed grid, this controller <em>breeds</em>:
 * each generation, λ offspring are produced from the μ surviving parents (bounded mutation
 * and blend — the V2 operators, finally consumed), materialized as ensemble shadow members
 * (the <b>nursery</b>), run against the sampled live stream, scored with {@link Fitness},
 * and selected. Shadows are offspring; the health gate and the strategy's own invariant
 * are death; promotion through the {@link MorphPolicy} gates is selection; and the
 * recorder captures complete lineages ({@link TreeEvent.Lineage} births,
 * {@code Trial} CULLED/DISQUALIFIED deaths). The {@code TreeEcology} ambition, landed as
 * an instrument instead of theatrics.
 *
 * <h2>The generation</h2>
 * <ol>
 *   <li>{@link #beginGeneration()} — breed: slot 0 re-materializes the best parent (elitism,
 *       so the reigning policy is re-scored on the <em>current</em> workload and stays
 *       promotable under non-stationarity); the other slots take fresh offspring — mutation
 *       of one parent or blend of two (seeded coin), never a genome already dead. Every
 *       birth emits {@code Lineage}; every materialization passes the health gate
 *       ({@code Trial} TRIED, or DISQUALIFIED for a gate kill).</li>
 *   <li>The caller streams ops through the data-plane facade for a window.</li>
 *   <li>{@link #endGeneration(int)} — each materialized genome answers to its own invariant
 *       (DISQUALIFIED = dead permanently), survivors are scored (SCORED) and pooled with
 *       the scored parents; the best μ live on, the rest are CULLED. The pool winner, when
 *       it is materialized this generation and clears the gates against the incumbent's
 *       fitness on the same features, is promoted (SELECTED) — sync-on-promote, O(1) swap,
 *       and the deposed primary joins the nursery: selection pressure all the way up.</li>
 * </ol>
 *
 * <p><b>Out-of-box exploration, behind the flag.</b> With {@code allowOutOfBox} the mutation
 * step may carry Δ past the verified box (structural bounds still hold —
 * {@link PolicyGenome#weightBalancedUnboxed}); with it off, steps reflect at the box walls
 * exactly like {@link PolicyGenome#perturbed}. This is the one place in the codebase allowed
 * to construct an unverified genome, because it is the place where the safety architecture
 * earns its keep: an unsound candidate fails the gate or its own invariant and is discarded
 * — recorded, visible in the arena, harmless (ADR-011 §3 V4).</p>
 *
 * <p><b>Determinism.</b> All randomness flows from one constructor-seeded {@link Random};
 * the same seed and call/op sequence reproduce the same lineages, scores aside. No
 * background threads; no RNG in selection (cost order, ties to insertion order).</p>
 */
public final class PolicyEvolutionController<K> {

    private static final Logger logger = LogManager.getLogger(PolicyEvolutionController.class);
    private static final int BREED_RETRIES = 16;

    private final EnsembleOrderedSet<K> ensemble;
    private final List<EnsembleMember<K>> nursery;     // strategy-backed, non-primary
    private final WorkloadMonitor monitor;
    private final MorphPolicy policy;
    private final List<PolicyGenome> founders;
    private final int mu;
    private final boolean allowOutOfBox;
    private final Random rng;

    /** Scored parents, ascending cost; empty until the first generation completes. */
    private final List<Scored> parents = new ArrayList<>();
    private final Set<PolicyGenome> dead = new HashSet<>();
    /** Founder root per genome (ADR-012 E2): ancestry follows parentA; first root wins. */
    private final Map<PolicyGenome, PolicyGenome> roots = new LinkedHashMap<>();
    private final Map<EnsembleMember<K>, PolicyGenome> onTrial = new LinkedHashMap<>();
    private int generation;
    private boolean generationOpen;
    private int opsSinceLastPromotion;
    private PolicyGenome lastWinner;
    private int winStreak;

    private volatile TreeEventListener<K> events;

    private record Scored(PolicyGenome genome, double cost) { }

    /** One generation's verdict, explainable in one line. */
    public record GenerationResult(int generation, int evaluated, int deaths,
                                   List<PolicyGenome> survivors, double bestCost,
                                   double incumbentCost, boolean promoted, String reason) { }

    /**
     * @param nursery       the offspring bodies: strategy-backed, non-primary members
     *                      (λ = {@code nursery.size()})
     * @param founders      generation 0's population (≥ 1, all distinct)
     * @param mu            survivors per generation (μ ≥ 1)
     * @param allowOutOfBox the V4 flag: mutation may leave the verified box
     * @param seed          the run's single source of randomness
     */
    public PolicyEvolutionController(EnsembleOrderedSet<K> ensemble, List<EnsembleMember<K>> nursery,
                                     WorkloadMonitor monitor, MorphPolicy policy,
                                     List<PolicyGenome> founders, int mu,
                                     boolean allowOutOfBox, long seed) {
        this.ensemble = Objects.requireNonNull(ensemble, "ensemble cannot be null");
        this.nursery = new ArrayList<>(Objects.requireNonNull(nursery, "nursery cannot be null"));
        this.monitor = Objects.requireNonNull(monitor, "monitor cannot be null");
        this.policy = Objects.requireNonNull(policy, "policy cannot be null");
        this.founders = List.copyOf(Objects.requireNonNull(founders, "founders cannot be null"));
        if (this.nursery.isEmpty()) throw new IllegalArgumentException("nursery cannot be empty (λ >= 1)");
        for (EnsembleMember<K> m : this.nursery) {
            if (!m.isStrategyBacked()) throw new IllegalArgumentException("nursery member " + m + " has no strategy seam");
            if (m == ensemble.primary()) throw new IllegalArgumentException("the serving primary cannot be a nursery slot");
        }
        if (this.founders.isEmpty()) throw new IllegalArgumentException("at least one founder required");
        if (this.founders.stream().distinct().count() != this.founders.size()) {
            throw new IllegalArgumentException("duplicate founders");
        }
        if (mu < 1) throw new IllegalArgumentException("mu must be >= 1: " + mu);
        this.mu = mu;
        this.allowOutOfBox = allowOutOfBox;
        this.rng = new Random(seed);
    }

    /** Register a structured-event listener (Lineage + Trial); {@code null} unregisters. */
    public void setEventListener(TreeEventListener<K> listener) { this.events = listener; }

    // ── Data plane (the V3 facade, verbatim) ─────────────────────────────────────

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

    // ── The generation ───────────────────────────────────────────────────────────

    /**
     * Breed and materialize this generation's population onto the nursery slots.
     *
     * @return the genomes on trial, in slot order
     * @throws IllegalStateException if a generation is already open, the nursery is empty,
     *         or breeding cannot produce a single living candidate
     */
    public List<PolicyGenome> beginGeneration() {
        if (generationOpen) throw new IllegalStateException("generation " + generation + " still open");
        if (nursery.isEmpty()) throw new IllegalStateException("nursery is empty — no slot to evolve on");
        generation++;
        onTrial.clear();

        for (int slot = 0; slot < nursery.size(); slot++) {
            PolicyGenome g;
            String op;
            PolicyGenome pa = null;
            PolicyGenome pb = null;
            if (parents.isEmpty()) {                       // generation 1 (or extinction): founders first
                if (slot < founders.size() && !dead.contains(founders.get(slot))) {
                    g = founders.get(slot);
                    op = "founder";
                } else {
                    pa = founders.get(rng.nextInt(founders.size()));
                    g = retryMutation(pa);
                    op = "mutation";
                }
            } else if (slot == 0) {                        // elitism: re-score the best parent
                g = parents.get(0).genome();
                op = "elite";
            } else {
                pa = parents.get(rng.nextInt(parents.size())).genome();
                if (parents.size() > 1 && rng.nextBoolean()) {
                    do { pb = parents.get(rng.nextInt(parents.size())).genome(); } while (pb.equals(pa));
                    PolicyGenome blended = blend(pa, pb);
                    if (dead.contains(blended)) {          // dead blend: fall back to mutation
                        pb = null;
                        g = retryMutation(pa);
                        op = "mutation";
                    } else {
                        g = blended;
                        op = "blend";
                    }
                } else {
                    g = retryMutation(pa);
                    op = "mutation";
                }
            }
            if (g == null) continue;                       // breeding only found the dead: slot idles

            // ADR-012 E2: ancestry. Founders root themselves; offspring follow parentA.
            roots.putIfAbsent(g, pa == null ? g : roots.getOrDefault(pa, pa));

            if (!"elite".equals(op)) {
                emit(new TreeEvent.Lineage<>(generation, g.toString(),
                        pa == null ? null : pa.toString(), pb == null ? null : pb.toString(), op));
            }
            EnsembleMember<K> body = nursery.get(slot);
            OrderedSet<K> set = body.orderedSet();
            core.strategy.TreeStrategy<K> candidate = g.toStrategy();
            boolean accepted = candidate.samePolicyAs(set.getStrategy())
                    || set.setStrategy(candidate);         // the health gate (V1 hook included)
            if (accepted) {
                onTrial.put(body, g);
                emit(new TreeEvent.Trial<>(g.toString(), "TRIED", Double.NaN, generation));
            } else {
                kill(g, "health gate rejected at build-aside");
            }
        }
        if (onTrial.isEmpty()) throw new IllegalStateException("no candidate survived materialization");
        generationOpen = true;
        logger.info("event=generation_begin gen={} onTrial={} parents={} dead={}",
                generation, onTrial.values(), parents.size(), dead.size());
        return List.copyOf(onTrial.values());
    }

    /**
     * Close the generation after {@code opsElapsed} streamed ops: invariant-check, score,
     * select μ survivors, cull the rest, and consider promoting the pool winner. Exactly
     * one {@code event=generation_eval} line.
     */
    public GenerationResult endGeneration(int opsElapsed) {
        if (!generationOpen) throw new IllegalStateException("no generation open");
        generationOpen = false;
        opsSinceLastPromotion += Math.max(0, opsElapsed);
        WorkloadFeatures f = monitor.snapshot();

        // 1. Judgment: each materialized genome against its own invariant, then the scorer.
        Map<PolicyGenome, Double> scored = new LinkedHashMap<>();
        Map<PolicyGenome, EnsembleMember<K>> bodies = new LinkedHashMap<>();
        int deaths = 0;
        for (Map.Entry<EnsembleMember<K>, PolicyGenome> t : onTrial.entrySet()) {
            OrderedSet<K> set = t.getKey().orderedSet();
            PolicyGenome g = t.getValue();
            List<String> violations = set.getStrategy().validateInvariant(set.getEngine());
            if (!violations.isEmpty()) {
                kill(g, "own invariant failed under live churn: " + violations.get(0));
                deaths++;
                continue;
            }
            double cost = Fitness.evaluate(f, Fitness.meanDepth(set.getEngine()), set.size()).cost();
            scored.put(g, cost);
            bodies.put(g, t.getKey());
            emit(new TreeEvent.Trial<>(g.toString(), "SCORED", cost, generation));
        }

        // 2. (μ+λ) selection: fresh offspring scores first, surviving parents' last scores after.
        Map<PolicyGenome, Double> pool = new LinkedHashMap<>(scored);
        for (Scored p : parents) pool.putIfAbsent(p.genome(), p.cost());
        List<Map.Entry<PolicyGenome, Double>> ranked = new ArrayList<>(pool.entrySet());
        ranked.sort(Map.Entry.comparingByValue());
        parents.clear();
        int culled = 0;
        for (int i = 0; i < ranked.size(); i++) {
            if (i < mu) {
                parents.add(new Scored(ranked.get(i).getKey(), ranked.get(i).getValue()));
            } else {
                culled++;
                emit(new TreeEvent.Trial<>(ranked.get(i).getKey().toString(), "CULLED",
                        ranked.get(i).getValue(), generation));
            }
        }

        // ADR-012 E2: diversity as a first-class output — measured over the survivors,
        // emitted once per generation, read back into nothing (mechanisms are E4's).
        emit(new TreeEvent.Diversity<>(generation, parents.size(), survivorLineages(),
                survivorSpread(), deaths, culled));

        // 3. Promotion = selection pressure on the throne (the V3 gate math, verbatim).
        double incumbentCost = incumbentCost(f);
        boolean promoted = false;
        String reason = "hold";
        if (!parents.isEmpty()) {
            PolicyGenome winner = parents.get(0).genome();
            winStreak = winner.equals(lastWinner) ? winStreak + 1 : 1;
            lastWinner = winner;
            EnsembleMember<K> body = bodies.get(winner);
            if (body != null && policy.shouldMorph(-incumbentCost, -parents.get(0).cost(),
                                                   opsSinceLastPromotion, winStreak)) {
                EnsembleMember<K> deposed = ensemble.primary();
                promoted = ensemble.promote(body);
                if (promoted) {
                    nursery.remove(body);
                    if (deposed.isStrategyBacked() && deposed.isActive()) nursery.add(deposed);
                    opsSinceLastPromotion = 0;
                    winStreak = 0;
                    lastWinner = null;
                    reason = "promoted " + winner + " (generation " + generation + ")";
                    emit(new TreeEvent.Trial<>(winner.toString(), "SELECTED",
                            pool.get(winner), generation));
                } else {
                    reason = "promote refused by ensemble";
                }
            }
        }

        List<PolicyGenome> survivors = parents.stream().map(Scored::genome).toList();
        double bestCost = parents.isEmpty() ? Double.NaN : parents.get(0).cost();
        logger.info("event=generation_eval gen={} evaluated={} deaths={} survivors={} best={} incumbent={} decision={} lineages={} spread={}",
                generation, scored.size(), deaths, survivors,
                String.format("%.4f", bestCost), String.format("%.4f", incumbentCost),
                promoted ? "PROMOTE" : "HOLD",
                survivorLineages(), String.format("%.2f", survivorSpread()));
        return new GenerationResult(generation, scored.size(), deaths, survivors,
                bestCost, incumbentCost, promoted, reason);
    }

    // ── Breeding (the V2 operators, with the V4 flag) ─────────────────────────────

    /** Repeated mutation pressure past dead genomes; {@code null} when hopeless. */
    private PolicyGenome retryMutation(PolicyGenome pa) {
        PolicyGenome g = pa;
        for (int i = 0; i < BREED_RETRIES; i++) {
            g = mutate(g);                                 // walk, don't re-roll: escapes dead pockets
            if (!dead.contains(g)) return g;
        }
        return null;
    }

    /** A ±1 single-gene step; reflects at the verified box, or — flagged — the structural walls. */
    private PolicyGenome mutate(PolicyGenome p) {
        if (!p.family().parameterized()) return p;         // classics are points
        int step = rng.nextBoolean() ? 1 : -1;
        int d = p.delta();
        int g = p.ratio();
        if (rng.nextBoolean()) {
            int hi = allowOutOfBox ? PolicyGenome.DELTA_STRUCTURAL_MAX : PolicyGenome.DELTA_MAX;
            d = PolicyGenome.reflect(d + step, PolicyGenome.DELTA_MIN, hi);
            g = Math.min(g, d - 1);
        } else {
            g = PolicyGenome.reflect(g + step, 1, d - 1);
        }
        return make(d, g);
    }

    /** Integer-midpoint blend (the V2 shape), built through the flag-appropriate factory. */
    private PolicyGenome blend(PolicyGenome x, PolicyGenome y) {
        PolicyGenome.Family f = rng.nextBoolean() ? x.family() : y.family();
        if (!f.parameterized()) return PolicyGenome.of(f);
        int d;
        int g;
        if (x.family().parameterized() && y.family().parameterized()) {
            d = x.delta() + (y.delta() - x.delta()) / 2;
            g = x.ratio() + (y.ratio() - x.ratio()) / 2;
        } else if (x.family().parameterized()) { d = x.delta(); g = x.ratio(); }
        else                                   { d = y.delta(); g = y.ratio(); }
        return make(d, Math.max(1, Math.min(g, d - 1)));
    }

    private PolicyGenome make(int d, int g) {
        return allowOutOfBox ? PolicyGenome.weightBalancedUnboxed(d, g)
                             : PolicyGenome.weightBalanced(d, g);
    }

    // ── Plumbing ─────────────────────────────────────────────────────────────────

    /** Distinct founder roots among the surviving parents (≥ 1 once any parent exists). */
    private int survivorLineages() {
        Set<PolicyGenome> r = new HashSet<>();
        for (Scored p : parents) r.add(roots.getOrDefault(p.genome(), p.genome()));
        return r.size();
    }

    /**
     * Mean L1 distance in (Δ, Γ) over survivor pairs of the same parameterized family;
     * {@code NaN} when no such pair exists (fewer than two parameterized survivors).
     */
    private double survivorSpread() {
        double sum = 0;
        int pairs = 0;
        for (int i = 0; i < parents.size(); i++) {
            PolicyGenome a = parents.get(i).genome();
            if (!a.family().parameterized()) continue;
            for (int j = i + 1; j < parents.size(); j++) {
                PolicyGenome b = parents.get(j).genome();
                if (b.family() != a.family()) continue;
                sum += Math.abs(a.delta() - b.delta()) + Math.abs(a.ratio() - b.ratio());
                pairs++;
            }
        }
        return pairs == 0 ? Double.NaN : sum / pairs;
    }

    private void kill(PolicyGenome g, String why) {
        dead.add(g);
        logger.warn("event=lineage_death gen={} genome={} reason={}", generation, g, why);
        emit(new TreeEvent.Trial<>(g.toString(), "DISQUALIFIED", Double.NaN, generation));
    }

    private double incumbentCost(WorkloadFeatures f) {
        if (!ensemble.primary().isStrategyBacked()) return Double.POSITIVE_INFINITY;
        OrderedSet<K> p = ensemble.primary().orderedSet();
        return Fitness.evaluate(f, Fitness.meanDepth(p.getEngine()), p.size()).cost();
    }

    /** The current scored parents, ascending cost (empty before generation 1 completes). */
    public List<PolicyGenome> parents() {
        return parents.stream().map(Scored::genome).toList();
    }

    /** Genomes killed by the gate or their own invariant — permanently unbreedable. */
    public Set<PolicyGenome> graveyard() { return Set.copyOf(dead); }

    /** The nursery as it stands (promotion rotates the deposed primary in). */
    public List<EnsembleMember<K>> nursery() { return List.copyOf(nursery); }

    private void emit(TreeEvent<K> e) {
        TreeEventListener<K> l = events;
        if (l != null) l.onEvent(e);
    }
}
