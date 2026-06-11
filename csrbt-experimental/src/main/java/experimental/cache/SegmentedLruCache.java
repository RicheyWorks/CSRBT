package experimental.cache;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The body a {@link CacheGenome} materializes into (ADR-012 E6): a fixed-capacity
 * segmented LRU over integer keys. Probation is insertion-ordered (scan-resistant: one
 * pass through cold keys cannot flush the protected segment); a key that takes
 * {@code promoteAfter} probation hits is promoted to the access-ordered protected
 * segment, whose overflow demotes its LRU entry back to probation.
 *
 * <p><b>The viability oracle</b> is {@link #validateInvariant()} — the structural truths
 * every genome must keep under live traffic: segments disjoint, each within its
 * capacity, hit bookkeeping only for probation residents, and <em>admission
 * liveness</em> (a cache with capacity must be able to hold an admitted key; the
 * {@code protectedTenths = 10} genome violates exactly this). Deterministic, no clock,
 * no RNG — same discipline as the tree strategies' {@code validateInvariant}.</p>
 *
 * <p>Fitness is realized hit rate over a generation window ({@link #resetWindow()} /
 * {@link #windowHitRate()}), the cache space's analog of comparisons/op: measured at the
 * seam, not modelled.</p>
 */
public final class SegmentedLruCache {

    private final CacheGenome genome;
    private final int capacity;
    private final int protectedCap;
    private final int probationCap;

    /** Insertion-ordered: eldest = first admitted, evicted first. */
    private final LinkedHashMap<Integer, Boolean> probation = new LinkedHashMap<>();
    /** Access-ordered: eldest = least recently touched, demoted first. */
    private final LinkedHashMap<Integer, Boolean> shielded =
            new LinkedHashMap<>(16, 0.75f, true);
    /** Probation hit counts; an entry exists iff the key is a probation resident. */
    private final Map<Integer, Integer> probationHits = new HashMap<>();

    private long lookups;
    private long hits;
    private long windowLookups;
    private long windowHits;

    public SegmentedLruCache(int capacity, CacheGenome genome) {
        if (capacity < 1) throw new IllegalArgumentException("capacity must be >= 1: " + capacity);
        this.capacity = capacity;
        this.genome = genome;
        this.protectedCap = capacity * genome.protectedTenths() / 10;
        this.probationCap = capacity - protectedCap;
    }

    public CacheGenome genome() { return genome; }

    /** A reference: hit bumps recency/earns promotion; miss returns false (caller admits). */
    public boolean get(int key) {
        lookups++;
        windowLookups++;
        if (shielded.get(key) != null) {           // access-order bump is the LRU touch
            hits++;
            windowHits++;
            return true;
        }
        if (probation.containsKey(key)) {
            hits++;
            windowHits++;
            int seen = probationHits.merge(key, 1, Integer::sum);
            if (seen >= genome.promoteAfter() && protectedCap > 0) promote(key);
            return true;
        }
        return false;
    }

    /** Admit a missed key into probation MRU, evicting the probation LRU on overflow. */
    public void admit(int key) {
        if (probation.containsKey(key) || shielded.containsKey(key)) return;
        probation.put(key, Boolean.TRUE);
        probationHits.put(key, 0);
        evictProbationOverflow();
    }

    private void promote(int key) {
        probation.remove(key);
        probationHits.remove(key);
        shielded.put(key, Boolean.TRUE);
        while (shielded.size() > protectedCap) {   // demote the protected LRU to probation MRU
            Iterator<Integer> it = shielded.keySet().iterator();
            int demoted = it.next();
            it.remove();
            probation.put(demoted, Boolean.TRUE);
            probationHits.put(demoted, 0);
        }
        evictProbationOverflow();
    }

    private void evictProbationOverflow() {
        while (probation.size() > probationCap) {
            Iterator<Integer> it = probation.keySet().iterator();
            int evicted = it.next();
            it.remove();
            probationHits.remove(evicted);
        }
    }

    /** Non-mutating membership peek (no recency bump, no stats). */
    public boolean peek(int key) {
        return shielded.containsKey(key) || probation.containsKey(key);
    }

    public int size() { return probation.size() + shielded.size(); }

    public double hitRate() { return lookups == 0 ? 0.0 : hits / (double) lookups; }

    public void resetWindow() { windowLookups = 0; windowHits = 0; }

    public double windowHitRate() {
        return windowLookups == 0 ? 0.0 : windowHits / (double) windowLookups;
    }

    /**
     * The viability oracle: structural truths under any traffic, or the reasons they
     * fail. Empty = viable.
     */
    public List<String> validateInvariant() {
        List<String> failures = new ArrayList<>();
        if (capacity >= 1 && probationCap < 1) {
            failures.add("admission liveness violated: probation capacity is 0 ("
                    + genome + " cannot hold an admitted key)");
        }
        if (probation.size() > probationCap) {
            failures.add("probation over capacity: " + probation.size() + " > " + probationCap);
        }
        if (shielded.size() > protectedCap) {
            failures.add("protected over capacity: " + shielded.size() + " > " + protectedCap);
        }
        if (size() > capacity) {
            failures.add("total over capacity: " + size() + " > " + capacity);
        }
        for (Integer k : probation.keySet()) {
            if (shielded.containsKey(k)) {
                failures.add("segments not disjoint at key " + k);
                break;
            }
        }
        if (!probationHits.keySet().equals(probation.keySet())) {
            failures.add("hit bookkeeping diverged from probation residency");
        }
        return failures;
    }
}
