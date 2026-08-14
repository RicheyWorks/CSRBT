package io.github.richeyworks.csrbt.experimental.ecology;

import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;

import java.util.IdentityHashMap;
import java.util.Map;
import java.util.TreeMap;

/**
 * Metapopulation and community structure over the ensemble (ADR-016 §E1) — the one
 * engine that literally <em>is</em> a multi-member community, so the mapping is
 * structurally faithful, per house rule: ensemble members are habitat patches, an
 * ACTIVE member is an occupied patch, quarantine/retire is a local extinction, and
 * {@code healFromPrimary} bringing a member back is recolonization from the mainland
 * (the primary — a rescue-effect topology, not island-to-island).
 *
 * <p>The instrument is caller-sampled: call {@link #sample()} on whatever cadence the
 * driver chooses (per op batch, per controller cycle). Each sample diffs member states
 * against the previous sample and accumulates colonization/extinction events. The clock
 * is the sample index; nothing here reads wall time. Zero engine changes — everything
 * observes the public {@code members()} surface.</p>
 *
 * <p>Levins (1969) metapopulation model: dp/dt = c&#xB7;p(1&#x2212;p) &#x2212; e&#xB7;p, equilibrium
 * occupancy p* = 1 &#x2212; e/c. The rate constants are estimated per unit of exposure:
 * e&#x302; = extinctions / occupied patch-samples, and c&#x302; from recolonizations per empty
 * patch-sample divided by mean occupancy (observed colonization rate per empty patch
 * is c&#xB7;p). The earlier event-total ratio (e/c &#x2248; extinctions/recolonizations) was
 * structurally degenerate: any record where every extinction is eventually healed —
 * exactly the steady-state regime the model describes — has equal totals and pinned
 * p* = 0 regardless of true occupancy, the "index that cannot vary" category error
 * ADR-015 exists to eliminate. {@link #levinsEquilibrium()} is the model's prediction
 * from the observed record, comparable against {@link #occupancy()}, the direct
 * measurement.</p>
 *
 * <p>Community structure: the "species" of a member is its strategy name (RedBlack, AVL,
 * Splay, engine labels). {@link #strategyAbundance()} is the abundance distribution of
 * <em>active</em> members by species, so the whole {@link CommunityMetrics} toolkit
 * applies — {@link #strategyDiversity()} is Shannon H&#x2032; over serving roles, and
 * {@link #functionalRedundancy()} is mean active copies per role (the insurance the
 * ensemble buys against a member's death).</p>
 */
public final class EnsembleCommunity<K> {

    private final EnsembleOrderedSet<K> ensemble;
    private final Map<EnsembleMember<K>, EnsembleMember.State> lastState =
            new IdentityHashMap<>();

    private long samples = 0;
    private long extinctions = 0;      // ACTIVE → QUARANTINED/RETIRED transitions
    private long recolonizations = 0;  // QUARANTINED/RETIRED → ACTIVE transitions
    private long occupiedPatchSamples = 0;   // exposure: patch-samples that began occupied
    private long emptyPatchSamples = 0;      // exposure: patch-samples that began empty

    /** Takes the baseline sample at construction (no events counted for it). */
    public EnsembleCommunity(EnsembleOrderedSet<K> ensemble) {
        this.ensemble = ensemble;
        for (EnsembleMember<K> m : ensemble.members()) {
            lastState.put(m, m.state());
        }
    }

    // ── Sampling ──────────────────────────────────────────────────────────────

    /**
     * Diff current member states against the previous sample; count each
     * occupied&#x2192;empty transition as an extinction and each empty&#x2192;occupied
     * transition as a recolonization. Returns the number of transitions seen.
     */
    public int sample() {
        samples++;
        int transitions = 0;
        for (EnsembleMember<K> m : ensemble.members()) {
            EnsembleMember.State now = m.state();
            EnsembleMember.State before = lastState.get(m);
            if (before == null) {
                lastState.put(m, now);   // member appeared since baseline: no event
                continue;
            }
            boolean wasOccupied = before == EnsembleMember.State.ACTIVE;
            boolean isOccupied  = now == EnsembleMember.State.ACTIVE;
            if (wasOccupied) occupiedPatchSamples++; else emptyPatchSamples++;   // exposure first
            if (wasOccupied && !isOccupied) { extinctions++; transitions++; }
            if (!wasOccupied && isOccupied) { recolonizations++; transitions++; }
            lastState.put(m, now);
        }
        return transitions;
    }

    // ── Metapopulation observables ────────────────────────────────────────────

    /** Direct measurement: occupied (ACTIVE) patches / total patches. Empty ensemble &#x2192; 0. */
    public double occupancy() {
        int total = ensemble.members().size();
        if (total == 0) return 0.0;
        int active = 0;
        for (EnsembleMember<K> m : ensemble.members()) {
            if (m.isActive()) active++;
        }
        return (double) active / total;
    }

    /** Samples taken (the deterministic clock of this instrument). */
    public long samples() { return samples; }

    /** Cumulative occupied&#x2192;empty transitions observed. */
    public long extinctions() { return extinctions; }

    /** Cumulative empty&#x2192;occupied transitions observed. */
    public long recolonizations() { return recolonizations; }

    /**
     * Levins equilibrium occupancy p* = 1 &#x2212; e&#x302;/c&#x302; with rates estimated per unit of
     * exposure from the sampled record:
     * e&#x302; = extinctions / occupied patch-samples (extinction probability per occupied
     * patch per sample), and c&#x302; = (recolonizations / empty patch-samples) / p&#x304;, since
     * the observed colonization rate per empty patch is c&#xB7;p (p&#x304; = mean occupancy over
     * the record). No extinctions observed &#x2192; 1 (no observed extinction pressure); no
     * recolonizations observed &#x2192; 0 (a metapopulation with extinction and no
     * colonization empties). Clamped to [0, 1].
     *
     * <p>Before 2026-08-14 this used the cumulative event-total ratio
     * (1 &#x2212; extinctions/recolonizations), which pins p* = 0 on any record where
     * every extinction is eventually healed — the steady-state regime itself — while
     * observed occupancy sits near 1: an index that cannot vary (ADR-015 EC-1 class).</p>
     */
    public double levinsEquilibrium() {
        if (extinctions == 0) return 1.0;
        if (recolonizations == 0) return 0.0;
        // Both events observed ⇒ both exposure counters are positive (an extinction
        // requires an occupied before-state, a recolonization an empty one).
        double eHat = (double) extinctions / occupiedPatchSamples;
        double meanOccupancy = (double) occupiedPatchSamples
                / (occupiedPatchSamples + emptyPatchSamples);
        double cHat = ((double) recolonizations / emptyPatchSamples) / meanOccupancy;
        double p = 1.0 - eHat / cHat;
        return Math.max(0.0, Math.min(1.0, p));
    }

    // ── Community observables ─────────────────────────────────────────────────

    /**
     * Abundance of active members by strategy name — the community's species-abundance
     * distribution. Sorted map, so iteration (and every metric downstream) is
     * deterministic regardless of member order.
     */
    public Map<String, Long> strategyAbundance() {
        Map<String, Long> counts = new TreeMap<>();
        for (EnsembleMember<K> m : ensemble.members()) {
            if (m.isActive()) counts.merge(m.strategyName(), 1L, Long::sum);
        }
        return counts;
    }

    /** Distinct strategies among active members (species richness of the community). */
    public int strategyRichness() {
        return CommunityMetrics.richness(strategyAbundance());
    }

    /** Shannon H&#x2032; over active members' strategies. */
    public double strategyDiversity() {
        return CommunityMetrics.shannon(strategyAbundance());
    }

    /** Pielou J&#x2032; over active members' strategies. */
    public double strategyEvenness() {
        return CommunityMetrics.pielouEvenness(strategyAbundance());
    }

    /**
     * Mean active members per distinct strategy — functional redundancy, the insurance
     * against losing any single member (1.0 = no redundancy; higher = spare copies).
     * No active members &#x2192; 0.
     */
    public double functionalRedundancy() {
        Map<String, Long> counts = strategyAbundance();
        if (counts.isEmpty()) return 0.0;
        long active = 0;
        for (long c : counts.values()) active += c;
        return (double) active / counts.size();
    }

    /** One-line state summary, deterministic field order. */
    @Override
    public String toString() {
        Map<String, Long> byRole = strategyAbundance();
        StringBuilder roleStr = new StringBuilder();
        for (Map.Entry<String, Long> e : byRole.entrySet()) {
            if (roleStr.length() > 0) roleStr.append(',');
            roleStr.append(e.getKey()).append('x').append(e.getValue());
        }
        return String.format(
                "occupancy=%.4f levinsP*=%.4f extinctions=%d recolonizations=%d "
                        + "richness=%d H'=%.4f redundancy=%.4f roles=[%s]",
                occupancy(), levinsEquilibrium(), extinctions, recolonizations,
                strategyRichness(), strategyDiversity(), functionalRedundancy(), roleStr);
    }
}
