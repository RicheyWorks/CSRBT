package io.github.richeyworks.csrbt.experimental.ecology;

import io.github.richeyworks.csrbt.PersistentTreeEngine;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Descent bookkeeping over the persistent engine's snapshots (ADR-016 §E2) — the
 * path-copying engine is the one place the codebase already produces an honest
 * generational record: every O(1) snapshot is a preserved past state, so a sequence of
 * snapshots is a fossil record in op time, and the standard descent-with-modification
 * observables apply to it directly.
 *
 * <p>Register each generation with {@link #capture} (or {@link #register} for an
 * existing snapshot). Between consecutive generations the instrument reports:
 * <b>inherited fraction</b> — the share of the parent generation's keys still present in
 * the child (retention across one generation); <b>gains/losses</b> — keys added and
 * removed; <b>divergence</b> — Jaccard distance between any two retained generations;
 * and <b>turnover per generation</b> — the mean consecutive divergence, a uniform-rate
 * summary of how fast content drifts (useful the same way a constant-rate drift model
 * is: as the null to compare bursts against).</p>
 *
 * <p>Two inheritance measures, distinct on purpose (ADR-017 — the seam ADR-016 §5
 * held is now open): <b>content</b> inheritance ({@link #inheritedFraction}) asks how
 * many of the parent's <em>keys</em> survive; <b>structural</b> inheritance
 * ({@link #structuralInheritance}) asks how many of its <em>nodes</em> physically
 * survive ({@code Snapshot.sharedNodeCount}, reference identity). The gap between them
 * is the price of path copying — ancestors of every edit are rewritten even though
 * their keys persist. Retention is bounded ({@code maxGenerations}, oldest evicted —
 * note retained snapshots pin their versions' nodes, the usual persistent-structure
 * cost); generation numbering stays absolute. Deterministic throughout — the clock is
 * the generation index.</p>
 *
 * <p><b>Key-identity caveat</b> (bug audit 2026-08-09, B-4): generation sets compare
 * keys by {@code equals}/{@code hashCode}, while the engine deduplicates by its
 * comparator. For a key type whose comparator is inconsistent with equals, cross-
 * generation comparisons can report turnover the engine never performed. All current
 * key types (Integer, String) are consistent; if a custom-comparator key type arrives,
 * thread the comparator through this class first (the ADR-002 seam discipline).</p>
 */
public final class SnapshotLineage<K> {

    /** Default cap on retained generations. */
    public static final int DEFAULT_MAX_GENERATIONS = 64;

    /** One retained generation: its absolute index, key set, and the snapshot itself. */
    public record Generation<K>(long index, Set<K> keys,
                                PersistentTreeEngine.Snapshot<K> snapshot) {
        public int size() { return keys.size(); }
    }

    private final int maxGenerations;
    private final Deque<Generation<K>> retained = new ArrayDeque<>();
    private long nextIndex = 0;

    public SnapshotLineage() {
        this(DEFAULT_MAX_GENERATIONS);
    }

    public SnapshotLineage(int maxGenerations) {
        if (maxGenerations < 2) throw new IllegalArgumentException("maxGenerations must be >= 2");
        this.maxGenerations = maxGenerations;
    }

    // ── Registration ──────────────────────────────────────────────────────────

    /** Snapshot the engine now and register it as the next generation. */
    public long capture(PersistentTreeEngine<K> engine) {
        return register(engine.snapshot());
    }

    /** Register an existing snapshot as the next generation; returns its index. */
    public long register(PersistentTreeEngine.Snapshot<K> snapshot) {
        Set<K> keys = new HashSet<>(snapshot.inOrder());
        long index = nextIndex++;
        retained.addLast(new Generation<>(index, keys, snapshot));
        if (retained.size() > maxGenerations) retained.removeFirst();
        return index;
    }

    // ── Record accessors ──────────────────────────────────────────────────────

    /** Total generations ever registered. */
    public long generations() { return nextIndex; }

    /** Retained generations, oldest &#x2192; newest. */
    public List<Generation<K>> retained() { return new ArrayList<>(retained); }

    private Generation<K> find(long index) {
        for (Generation<K> g : retained) {
            if (g.index() == index) return g;
        }
        throw new IllegalArgumentException(
                "generation " + index + " is not retained (window " + maxGenerations + ")");
    }

    // ── Descent observables ───────────────────────────────────────────────────

    /**
     * Fraction of generation {@code parent}'s keys still present in generation
     * {@code parent + 1} — retention across one generation. Empty parent &#x2192; 1.0
     * (nothing to lose).
     */
    public double inheritedFraction(long parent) {
        Generation<K> p = find(parent);
        Generation<K> c = find(parent + 1);
        if (p.keys().isEmpty()) return 1.0;
        int kept = 0;
        for (K k : p.keys()) if (c.keys().contains(k)) kept++;
        return (double) kept / p.keys().size();
    }

    /** Keys present in generation {@code parent + 1} but not in {@code parent}. */
    public int gains(long parent) {
        Generation<K> p = find(parent);
        Generation<K> c = find(parent + 1);
        int gained = 0;
        for (K k : c.keys()) if (!p.keys().contains(k)) gained++;
        return gained;
    }

    /** Keys present in generation {@code parent} but not in {@code parent + 1}. */
    public int losses(long parent) {
        Generation<K> p = find(parent);
        Generation<K> c = find(parent + 1);
        int lost = 0;
        for (K k : p.keys()) if (!c.keys().contains(k)) lost++;
        return lost;
    }

    /**
     * Structural inheritance across one generation: the fraction of generation
     * {@code parent}'s <em>nodes</em> physically shared with {@code parent + 1}
     * (reference identity under path copying). Empty parent &#x2192; 1.0. Always
     * &#x2264; {@link #inheritedFraction} up to rounding: a key can be inherited while its
     * node is rewritten, never the reverse.
     */
    public double structuralInheritance(long parent) {
        Generation<K> p = find(parent);
        Generation<K> c = find(parent + 1);
        int parentNodes = p.snapshot().size();
        if (parentNodes == 0) return 1.0;
        return (double) p.snapshot().sharedNodeCount(c.snapshot()) / parentNodes;
    }

    /** Mean {@link #inheritedFraction} over retained consecutive pairs; 1.0 if fewer than two. */
    public double meanContentInheritance() {
        List<Generation<K>> gens = retained();
        if (gens.size() < 2) return 1.0;
        double sum = 0.0;
        for (int i = 0; i + 1 < gens.size(); i++) sum += inheritedFraction(gens.get(i).index());
        return sum / (gens.size() - 1);
    }

    /** Mean {@link #structuralInheritance} over retained consecutive pairs; 1.0 if fewer than two. */
    public double meanStructuralInheritance() {
        List<Generation<K>> gens = retained();
        if (gens.size() < 2) return 1.0;
        double sum = 0.0;
        for (int i = 0; i + 1 < gens.size(); i++) sum += structuralInheritance(gens.get(i).index());
        return sum / (gens.size() - 1);
    }

    /** Jaccard distance 1 &#x2212; J between any two retained generations. */
    public double divergence(long a, long b) {
        return 1.0 - BetaDiversity.jaccard(find(a).keys(), find(b).keys());
    }

    /**
     * Mean consecutive-generation Jaccard distance across the retained window — the
     * uniform-rate drift summary. Fewer than two retained generations &#x2192; 0.
     */
    public double turnoverPerGeneration() {
        List<Generation<K>> gens = retained();
        if (gens.size() < 2) return 0.0;
        double sum = 0.0;
        for (int i = 0; i + 1 < gens.size(); i++) {
            sum += 1.0 - BetaDiversity.jaccard(gens.get(i).keys(), gens.get(i + 1).keys());
        }
        return sum / (gens.size() - 1);
    }
}
