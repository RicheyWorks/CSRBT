package io.github.richeyworks.csrbt.experimental.cache;

import io.github.richeyworks.csrbt.control.MorphPolicy;
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
 * ADR-012 E6 — the evolve-under-viability loop, instantiated over the cache policy
 * space. This class <b>is the transfer experiment's measurement</b>: it re-states
 * {@link io.github.richeyworks.csrbt.evolution.PolicyEvolutionController}'s generation protocol — founders →
 * elitism → bounded mutation/blend past a graveyard → materialization through a
 * viability gate → live shadow evaluation → own-invariant death → (μ+λ) selection →
 * gated promotion with the deposed primary rejoining the nursery — over
 * {@link CacheGenome}/{@link SegmentedLruCache} bodies.
 *
 * <p><b>What transferred verbatim</b> (imported, not rewritten): {@link MorphPolicy}
 * (the promotion gate math — hit rate is already desirability-form, so it slots in
 * without even the tree's negation), the {@link TreeEvent} vocabulary
 * ({@code Lineage}/{@code Trial}/{@code Diversity} carry strings and numbers, nothing
 * tree-shaped), and {@link TreeEventListener} (so the existing recorder/arena consume
 * this space's history unchanged). <b>What did not:</b> the loop class itself —
 * {@code PolicyEvolutionController} names {@code PolicyGenome} and ensemble member
 * types in its signature and operators, so the protocol had to be re-typed here
 * (~150 lines). The experiment publishes that split as the verdict, either way.</p>
 *
 * <p>Determinism: one constructor-seeded {@link Random}; no clock, no threads,
 * caller-cadenced generations — house rules.</p>
 */
public final class CacheEvolutionLoop {

    private static final Logger logger = LogManager.getLogger(CacheEvolutionLoop.class);
    private static final int BREED_RETRIES = 16;

    private final int capacity;
    private final MorphPolicy policy;
    private final List<CacheGenome> founders;
    private final int mu;
    private final Random rng;

    private SegmentedLruCache primary;
    private CacheGenome primaryGenome;
    private final List<SegmentedLruCache> nursery = new ArrayList<>(); // λ shadow bodies

    private final List<Scored> parents = new ArrayList<>();
    private final Set<CacheGenome> dead = new HashSet<>();
    private final Map<CacheGenome, CacheGenome> roots = new LinkedHashMap<>();
    private final Map<SegmentedLruCache, CacheGenome> onTrial = new LinkedHashMap<>();
    private int generation;
    private boolean generationOpen;
    private int opsSinceLastPromotion;
    private CacheGenome lastWinner;
    private int winStreak;

    private volatile TreeEventListener<Integer> events;

    private record Scored(CacheGenome genome, double hitRate) { }

    /** One generation's verdict, explainable in one line — the tree loop's record, re-typed. */
    public record GenerationResult(int generation, int evaluated, int deaths,
                                   List<CacheGenome> survivors, double bestHitRate,
                                   double incumbentHitRate, boolean promoted, String reason) { }

    public CacheEvolutionLoop(int capacity, List<CacheGenome> founders, int mu, int lambda,
                              MorphPolicy policy, long seed) {
        if (capacity < 1) throw new IllegalArgumentException("capacity must be >= 1");
        if (lambda < 1) throw new IllegalArgumentException("lambda must be >= 1");
        if (mu < 1) throw new IllegalArgumentException("mu must be >= 1");
        this.capacity = capacity;
        this.policy = Objects.requireNonNull(policy, "policy cannot be null");
        this.founders = List.copyOf(Objects.requireNonNull(founders, "founders cannot be null"));
        if (this.founders.isEmpty()) throw new IllegalArgumentException("at least one founder required");
        if (this.founders.stream().distinct().count() != this.founders.size()) {
            throw new IllegalArgumentException("duplicate founders");
        }
        this.mu = mu;
        this.rng = new Random(seed);
        // The serving primary starts on the first founder that passes the gate.
        for (CacheGenome g : this.founders) {
            SegmentedLruCache body = materialize(g);
            if (body != null) { this.primary = body; this.primaryGenome = g; break; }
            kill(g, "founder failed the viability gate at materialization");
        }
        if (this.primary == null) throw new IllegalStateException("no founder is viable");
        for (int i = 0; i < lambda; i++) nursery.add(new SegmentedLruCache(capacity, primaryGenome));
    }

    /** Register a structured-event listener (Lineage + Trial + Diversity); {@code null} unregisters. */
    public void setEventListener(TreeEventListener<Integer> listener) { this.events = listener; }

    // ── Data plane: one reference stream, mirrored to every body on trial ─────────

    /** Reference {@code key}: hit or admit on the primary, mirrored to the shadows. */
    public boolean lookup(int key) {
        boolean hit = primary.get(key);
        if (!hit) primary.admit(key);
        for (SegmentedLruCache shadow : onTrial.keySet()) {
            if (!shadow.get(key)) shadow.admit(key);
        }
        return hit;
    }

    /**
     * Whether {@code key} currently resides in the serving primary (no recency bump, no
     * stats) — the residency seam an external value cache needs to trim its value map to
     * the champion's actual contents. Named by the first external consumer (Brine).
     */
    public boolean resident(int key) {
        return primary.peek(key);
    }

    /** The genome of the serving primary — the current champion policy, for the record. */
    public CacheGenome champion() {
        return primaryGenome;
    }

    // ── The generation (the tree protocol, step for step) ─────────────────────────

    public List<CacheGenome> beginGeneration() {
        if (generationOpen) throw new IllegalStateException("generation " + generation + " still open");
        generation++;
        onTrial.clear();

        for (int slot = 0; slot < nursery.size(); slot++) {
            CacheGenome g;
            String op;
            CacheGenome pa = null;
            CacheGenome pb = null;
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
                    CacheGenome blended = blend(pa, pb);
                    if (dead.contains(blended)) {
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

            roots.putIfAbsent(g, pa == null ? g : roots.getOrDefault(pa, pa));
            if (!"elite".equals(op)) {
                emit(new TreeEvent.Lineage<>(generation, g.toString(),
                        pa == null ? null : pa.toString(), pb == null ? null : pb.toString(), op));
            }

            SegmentedLruCache body = materialize(g);       // the viability gate
            if (body != null) {
                nursery.set(slot, body);
                body.resetWindow();
                onTrial.put(body, g);
                emit(new TreeEvent.Trial<>(g.toString(), "TRIED", Double.NaN, generation));
            } else {
                kill(g, "viability gate rejected at materialization");
            }
        }
        if (onTrial.isEmpty()) throw new IllegalStateException("no candidate survived materialization");
        primary.resetWindow();
        generationOpen = true;
        logger.info("event=generation_begin space=cache gen={} onTrial={} parents={} dead={}",
                generation, onTrial.values(), parents.size(), dead.size());
        return List.copyOf(onTrial.values());
    }

    public GenerationResult endGeneration(int opsElapsed) {
        if (!generationOpen) throw new IllegalStateException("no generation open");
        generationOpen = false;
        opsSinceLastPromotion += Math.max(0, opsElapsed);

        // 1. Judgment: own invariant under live traffic, then realized fitness.
        Map<CacheGenome, Double> scored = new LinkedHashMap<>();
        Map<CacheGenome, SegmentedLruCache> bodies = new LinkedHashMap<>();
        int deaths = 0;
        for (Map.Entry<SegmentedLruCache, CacheGenome> t : onTrial.entrySet()) {
            List<String> violations = t.getKey().validateInvariant();
            CacheGenome g = t.getValue();
            if (!violations.isEmpty()) {
                kill(g, "own invariant failed under live traffic: " + violations.get(0));
                deaths++;
                continue;
            }
            double rate = t.getKey().windowHitRate();
            scored.put(g, rate);
            bodies.put(g, t.getKey());
            emit(new TreeEvent.Trial<>(g.toString(), "SCORED", 1.0 - rate, generation));
        }

        // 2. (μ+λ) selection: fresh scores first, surviving parents' last scores after.
        Map<CacheGenome, Double> pool = new LinkedHashMap<>(scored);
        for (Scored p : parents) pool.putIfAbsent(p.genome(), p.hitRate());
        List<Map.Entry<CacheGenome, Double>> ranked = new ArrayList<>(pool.entrySet());
        ranked.sort((a, b) -> Double.compare(b.getValue(), a.getValue())); // hit rate: higher wins
        parents.clear();
        int culled = 0;
        for (int i = 0; i < ranked.size(); i++) {
            if (i < mu) {
                parents.add(new Scored(ranked.get(i).getKey(), ranked.get(i).getValue()));
            } else {
                culled++;
                emit(new TreeEvent.Trial<>(ranked.get(i).getKey().toString(), "CULLED",
                        1.0 - ranked.get(i).getValue(), generation));
            }
        }

        emit(new TreeEvent.Diversity<>(generation, parents.size(), survivorLineages(),
                survivorSpread(), deaths, culled));

        // 3. Promotion = selection pressure on the throne. Hit rate is desirability-form
        //    already, so MorphPolicy consumes it without the tree's negation.
        double incumbentRate = primary.windowHitRate();
        boolean promoted = false;
        String reason = "hold";
        if (!parents.isEmpty()) {
            CacheGenome winner = parents.get(0).genome();
            winStreak = winner.equals(lastWinner) ? winStreak + 1 : 1;
            lastWinner = winner;
            SegmentedLruCache body = bodies.get(winner);
            if (body != null && !winner.equals(primaryGenome)
                    && policy.shouldMorph(incumbentRate, parents.get(0).hitRate(),
                                          opsSinceLastPromotion, winStreak)) {
                int slot = nursery.indexOf(body);
                nursery.set(slot, primary);                // the deposed primary joins the nursery
                primary = body;                            // O(1) swap — promotion is a pointer
                primaryGenome = winner;
                opsSinceLastPromotion = 0;
                winStreak = 0;
                lastWinner = null;
                promoted = true;
                reason = "promoted " + winner + " (generation " + generation + ")";
                emit(new TreeEvent.Trial<>(winner.toString(), "SELECTED",
                        1.0 - pool.get(winner), generation));
            }
        }

        List<CacheGenome> survivors = parents.stream().map(Scored::genome).toList();
        double best = parents.isEmpty() ? Double.NaN : parents.get(0).hitRate();
        logger.info("event=generation_eval space=cache gen={} evaluated={} deaths={} survivors={} best={} incumbent={} decision={}",
                generation, scored.size(), deaths, survivors,
                String.format("%.4f", best), String.format("%.4f", incumbentRate),
                promoted ? "PROMOTE" : "HOLD");
        return new GenerationResult(generation, scored.size(), deaths, survivors,
                best, incumbentRate, promoted, reason);
    }

    // ── Breeding (the V2 operators, re-typed) ─────────────────────────────────────

    private CacheGenome retryMutation(CacheGenome pa) {
        CacheGenome g = pa;
        for (int i = 0; i < BREED_RETRIES; i++) {
            g = mutate(g);                                 // walk, don't re-roll
            if (!dead.contains(g)) return g;
        }
        return null;
    }

    private CacheGenome mutate(CacheGenome p) {
        int step = rng.nextBoolean() ? 1 : -1;
        if (rng.nextBoolean()) {
            return CacheGenome.of(
                    CacheGenome.reflect(p.protectedTenths() + step,
                            CacheGenome.TENTHS_MIN, CacheGenome.TENTHS_MAX),
                    p.promoteAfter());
        }
        return CacheGenome.of(p.protectedTenths(),
                CacheGenome.reflect(p.promoteAfter() + step,
                        CacheGenome.PROMOTE_MIN, CacheGenome.PROMOTE_MAX));
    }

    private CacheGenome blend(CacheGenome x, CacheGenome y) {
        return CacheGenome.of(
                x.protectedTenths() + (y.protectedTenths() - x.protectedTenths()) / 2,
                x.promoteAfter() + (y.promoteAfter() - x.promoteAfter()) / 2);
    }

    // ── Plumbing ──────────────────────────────────────────────────────────────────

    /** The viability gate: construct, check the oracle, probe admission liveness. */
    private SegmentedLruCache materialize(CacheGenome g) {
        SegmentedLruCache body = new SegmentedLruCache(capacity, g);
        if (!body.validateInvariant().isEmpty()) return null;
        body.admit(Integer.MIN_VALUE);                     // the live probe: admitted ⇒ retrievable
        boolean alive = body.peek(Integer.MIN_VALUE);
        return alive ? new SegmentedLruCache(capacity, g) : null;
    }

    private int survivorLineages() {
        Set<CacheGenome> r = new HashSet<>();
        for (Scored p : parents) r.add(roots.getOrDefault(p.genome(), p.genome()));
        return r.size();
    }

    /** Mean L1 distance over survivor pairs in (protectedTenths, promoteAfter). */
    private double survivorSpread() {
        double sum = 0;
        int pairs = 0;
        for (int i = 0; i < parents.size(); i++) {
            for (int j = i + 1; j < parents.size(); j++) {
                CacheGenome a = parents.get(i).genome();
                CacheGenome b = parents.get(j).genome();
                sum += Math.abs(a.protectedTenths() - b.protectedTenths())
                     + Math.abs(a.promoteAfter() - b.promoteAfter());
                pairs++;
            }
        }
        return pairs == 0 ? Double.NaN : sum / pairs;
    }

    private void kill(CacheGenome g, String why) {
        dead.add(g);
        logger.warn("event=lineage_death space=cache gen={} genome={} reason={}", generation, g, why);
        emit(new TreeEvent.Trial<>(g.toString(), "DISQUALIFIED", Double.NaN, generation));
    }

    public CacheGenome primaryGenome() { return primaryGenome; }

    public double primaryHitRate() { return primary.hitRate(); }

    public List<CacheGenome> parents() {
        return parents.stream().map(Scored::genome).toList();
    }

    public Set<CacheGenome> graveyard() { return Set.copyOf(dead); }

    private void emit(TreeEvent<Integer> e) {
        TreeEventListener<Integer> l = events;
        if (l != null) l.onEvent(e);
    }
}
