package io.github.richeyworks.csrbt.experimental.ecology;

import io.github.richeyworks.csrbt.experimental.cache.SegmentedLruCache;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Island observables over the segmented-LRU cache (ADR-016 §E4) — the cache is a
 * bounded habitat by construction: fixed carrying capacity, keys immigrate on
 * {@code admit}, and eviction is local extinction. That is the MacArthur–Wilson (1967)
 * setting taken literally, and its signature prediction is directly checkable here:
 * <b>at equilibrium, richness holds steady while composition keeps turning over</b> —
 * immigration and extinction balance at a nonzero rate. A saturated cache under a
 * drifting workload is exactly that regime.
 *
 * <p>The instrument wraps the cache's public API: route lookups through {@link #get}
 * and admissions through {@link #admit} (both forward to the cache), and call
 * {@link #sample()} on the driver's cadence. Evictions are not announced by the cache,
 * so each sample sweeps the tracked-resident set with the non-mutating {@code peek};
 * a key found missing is recorded dead <em>at the sweep's op clock</em> — dating
 * resolution equals the sampling cadence, a documented approximation (the same way a
 * fossil's date resolves to its stratum, no finer). Op-clocked, deterministic, zero
 * cache changes.</p>
 *
 * <p>Cross-layer reuse: closed residencies are {@link LifeTable.Lifespan}s, so
 * {@link #residenceLifeTable} hands the eviction record straight to the demography
 * layer — residence-time survivorship is the cache's churn profile.</p>
 */
public final class CacheIsland {

    private final SegmentedLruCache cache;
    private final int capacity;

    private long opClock = 0;
    private long immigrations = 0;
    private long extinctions = 0;
    private long samples = 0;
    private long lastSampleImmigrations = 0;
    private long lastSampleExtinctions = 0;
    private double lastTurnover = 0.0;

    /** Tracked residents: key &#x2192; admission op. Insertion-ordered for deterministic sweeps. */
    private final Map<Integer, Long> residentSince = new LinkedHashMap<>();
    private final List<LifeTable.Lifespan> residencies = new ArrayList<>();

    /**
     * @param cache    the island
     * @param capacity the cache's build-time capacity (not exposed by the cache API;
     *                 the caller built the cache, so the caller knows it)
     */
    public CacheIsland(SegmentedLruCache cache, int capacity) {
        if (capacity < 1) throw new IllegalArgumentException("capacity must be >= 1");
        this.cache = cache;
        this.capacity = capacity;
    }

    // ── Forwarding surface ────────────────────────────────────────────────────

    /**
     * Forward a lookup; one op tick. A <em>miss</em> on a tracked resident proves an
     * eviction happened since the last sweep: the residency closes here, dated at the
     * miss (better resolution than waiting for the next sweep).
     */
    public boolean get(int key) {
        opClock++;
        boolean hit = cache.get(key);
        if (!hit) closeStaleResidency(key);
        return hit;
    }

    /**
     * Forward an admission; one op tick. A key not already resident is an immigration
     * and starts a residency at this op. If the key is absent but still <em>tracked</em>,
     * it was evicted between sweeps and is now returning: the first residency closes at
     * this op before the new one opens — re-immigration is a new residency, never a
     * silent extension of the old one, and the books stay balanced
     * (immigrations &#x2212; extinctions = current residents).
     */
    public void admit(int key) {
        opClock++;
        boolean already = cache.peek(key);
        cache.admit(key);
        if (!already) {
            closeStaleResidency(key);   // evicted-and-returning: close the first life
            immigrations++;
            residentSince.put(key, opClock);
        }
    }

    /** Close a tracked residency whose key is observed absent; dated at the current op. */
    private void closeStaleResidency(int key) {
        Long birth = residentSince.remove(key);
        if (birth != null) {
            residencies.add(new LifeTable.Lifespan(key, birth, opClock));
            extinctions++;
        }
    }

    // ── Sampling ──────────────────────────────────────────────────────────────

    /**
     * Sweep tracked residents with the non-mutating {@code peek}; each key found
     * missing is an extinction dated at the current op clock. Also fixes this
     * interval's turnover rate: (immigrations + extinctions this interval) / 2, the
     * MacArthur–Wilson turnover convention. Returns extinctions found this sweep.
     */
    public int sample() {
        samples++;
        int found = 0;
        List<Integer> gone = new ArrayList<>();
        for (Map.Entry<Integer, Long> e : residentSince.entrySet()) {
            if (!cache.peek(e.getKey())) {
                residencies.add(new LifeTable.Lifespan(e.getKey(), e.getValue(), opClock));
                gone.add(e.getKey());
                found++;
            }
        }
        for (int key : gone) residentSince.remove(key);
        extinctions += found;

        long di = immigrations - lastSampleImmigrations;
        long de = extinctions - lastSampleExtinctions;
        lastTurnover = (di + de) / 2.0;
        lastSampleImmigrations = immigrations;
        lastSampleExtinctions = extinctions;
        return found;
    }

    // ── Island observables ────────────────────────────────────────────────────

    /** Op ticks routed through this instrument (the deterministic clock). */
    public long opCount() { return opClock; }

    /** Samples taken. */
    public long samples() { return samples; }

    /** Species richness S — current residents, as the cache reports it. */
    public int richness() { return cache.size(); }

    /** The island's area: build-time capacity. */
    public int capacity() { return capacity; }

    /** Richness / capacity — how full the island is. */
    public double saturation() { return (double) richness() / capacity; }

    /** Cumulative immigrations (first-time and re-admissions after eviction). */
    public long immigrations() { return immigrations; }

    /** Cumulative extinctions (evictions observed by sweeps). */
    public long extinctions() { return extinctions; }

    /**
     * Turnover of the latest sampled interval: (immigrations + extinctions)/2 — the
     * MacArthur–Wilson equilibrium signature is this staying &gt; 0 while
     * {@link #richness()} holds flat at saturation.
     */
    public double lastIntervalTurnover() { return lastTurnover; }

    /** Completed residencies (admission &#x2192; observed eviction), in discovery order. */
    public List<LifeTable.Lifespan> residencies() {
        return Collections.unmodifiableList(residencies);
    }

    /** Residence-time life table — the demography layer over the eviction record. */
    public LifeTable residenceLifeTable(int ageClasses) {
        return LifeTable.fromLifespans(residencies, ageClasses);
    }

    @Override
    public String toString() {
        return String.format(
                "S=%d/%d saturation=%.4f immigrations=%d extinctions=%d turnover=%.2f ops=%d",
                richness(), capacity, saturation(), immigrations, extinctions,
                lastTurnover, opClock);
    }
}
