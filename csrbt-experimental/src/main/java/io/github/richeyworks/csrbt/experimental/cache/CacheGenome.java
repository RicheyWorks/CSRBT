package io.github.richeyworks.csrbt.experimental.cache;

/**
 * The second policy space (ADR-012 E6): a two-gene genome for segmented-LRU cache
 * eviction, deliberately shaped like {@link io.github.richeyworks.csrbt.evolution.PolicyGenome}'s (Δ, Γ) so the
 * transfer thesis is tested on like-for-like terms.
 *
 * <ul>
 *   <li><b>protectedTenths</b> ∈ [0, 10] — the fraction of capacity reserved for the
 *       protected (frequency-earned) segment, in tenths. 0 = pure probation LRU;
 *       10 = <em>no probation at all</em>, which is structurally in-bounds and
 *       behaviorally lethal: an admitted key has nowhere to land and is evicted on
 *       arrival. That genome is this space's WB(5,3) — the viability oracle, not the
 *       constructor, is what kills it.</li>
 *   <li><b>promoteAfter</b> ∈ [1, 4] — probation hits required before a key earns
 *       promotion to the protected segment.</li>
 * </ul>
 *
 * <p>Immutable value type; {@code of} enforces only the <em>structural</em> box (the
 * analog of {@code weightBalancedUnboxed}'s walls). Lethality inside the box is the
 * gate's job to discover — that asymmetry is the point of the experiment.</p>
 */
public record CacheGenome(int protectedTenths, int promoteAfter) {

    public static final int TENTHS_MIN = 0;
    public static final int TENTHS_MAX = 10;
    public static final int PROMOTE_MIN = 1;
    public static final int PROMOTE_MAX = 4;

    public CacheGenome {
        if (protectedTenths < TENTHS_MIN || protectedTenths > TENTHS_MAX) {
            throw new IllegalArgumentException("protectedTenths out of structural box: " + protectedTenths);
        }
        if (promoteAfter < PROMOTE_MIN || promoteAfter > PROMOTE_MAX) {
            throw new IllegalArgumentException("promoteAfter out of structural box: " + promoteAfter);
        }
    }

    public static CacheGenome of(int protectedTenths, int promoteAfter) {
        return new CacheGenome(protectedTenths, promoteAfter);
    }

    /** Reflect {@code v} into [{@code lo}, {@code hi}] — the PolicyGenome walk, verbatim shape. */
    public static int reflect(int v, int lo, int hi) {
        if (v < lo) return lo + (lo - v);
        if (v > hi) return hi - (v - hi);
        return v;
    }

    @Override
    public String toString() {
        return "SLRU(" + protectedTenths + "/10,p" + promoteAfter + ")";
    }
}
