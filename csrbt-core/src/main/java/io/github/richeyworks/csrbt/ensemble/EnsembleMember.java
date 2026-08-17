package io.github.richeyworks.csrbt.ensemble;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.interfaces.RankedSet;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * One member of an {@link EnsembleOrderedSet}: a backing set over an exact copy of the logical
 * key set, plus the lifecycle state the ensemble manages (ADR-003).
 *
 * <p><b>ADR-005 P3:</b> the backing set is any {@link RankedSet} — the strategy-driven
 * {@link OrderedSet} as always, or an ENGINE-tier set such as {@code PersistentRankedSet} over
 * the weight-balanced persistent engine. The ensemble's fan-out, voting, healing, and promotion
 * speak {@code RankedSet} only; the controller's strategy-specific machinery (StrategyId
 * indexing, {@code StrategyHealthCheck}) applies only to {@linkplain #isStrategyBacked()
 * strategy-backed} members and reaches the concrete facade through {@link #orderedSet()}.</p>
 */
public final class EnsembleMember<K> {

    /** Lifecycle state. E1 only uses {@code ACTIVE}; the others are wired in E3. */
    public enum State { ACTIVE, QUARANTINED, RETIRED }

    private final RankedSet<K> set;
    /** Fixed label for an ENGINE-tier member; strategy-backed members resolve their own name. */
    private final String label;
    private volatile State state = State.ACTIVE;
    private volatile boolean exact = true;

    /**
     * Epoch reader count (ADR-004 R2, READ_REPLICA). A reader increments before verifying this
     * member is still the serving primary and reads only on success; the writer flips the
     * serving pointer away and then drains this count to zero before mutating. The invariant —
     * a member is mutated only while it is not primary AND its count is zero (modulo transient
     * holders who verified, failed, and are exiting without touching the tree) — is what makes
     * replica reads safe without the member's read lock ever being contended.
     */
    private final AtomicInteger epochReaders = new AtomicInteger();

    EnsembleMember(OrderedSet<K> set) {
        this(set, set.getStrategy().getClass().getSimpleName());
    }

    /** ADR-005 P3: any {@link RankedSet} backing, labeled (engine members have no strategy). */
    EnsembleMember(RankedSet<K> set, String label) {
        this.set = set;
        this.label = label;
    }

    /** The backing set — an exact mirror of the logical set while {@code ACTIVE}. */
    public RankedSet<K> set() { return set; }

    /** True when the backing set is a strategy-driven {@link OrderedSet} (the RB-engine family). */
    public boolean isStrategyBacked() { return set instanceof OrderedSet; }

    /**
     * The backing {@link OrderedSet} for strategy-specific machinery (engine/strategy access,
     * {@code StrategyHealthCheck}). @throws IllegalStateException for ENGINE-tier members —
     * check {@link #isStrategyBacked()} first.
     */
    public OrderedSet<K> orderedSet() {
        if (!(set instanceof OrderedSet)) {
            throw new IllegalStateException(label + " is an engine-tier member with no strategy facade");
        }
        return (OrderedSet<K>) set;
    }

    /**
     * Label for the backing structure, e.g. {@code "SplayStrategy"} or {@code "PersistentTreeEngine"}.
     *
     * <p>Resolved <em>at call time</em> from the backing set's current strategy (sixth-pass audit
     * finding 18): a member's strategy is not fixed for life — {@code OrderedSet.setStrategy} is how
     * the evolution controllers materialize candidates on a member ({@code PolicySearchController
     * .beginTrial}, {@code PolicyEvolutionController.beginGeneration}), so a name frozen at
     * construction reported the strategy a member <em>used to</em> run. ENGINE-tier members have no
     * strategy and keep their construction label.</p>
     */
    public String strategyName() {
        return (set instanceof OrderedSet<K> os) ? os.getStrategy().getClass().getSimpleName() : label;
    }

    public State state() { return state; }

    public boolean isActive() { return state == State.ACTIVE; }

    /**
     * True while this member is an exact mirror of the logical set. Always true in MIRROR/VERIFIED
     * operation; in SAMPLED_SHADOW mode (E5) a member drops to inexact the first time a sampled-out
     * write skips it — and in REBUILD_SHADOW (ADR-003 Option C) on the first write after a rebuild —
     * and only an O(n) rebuild from the primary (heal, the cadence rebuild, or the sync-on-promote
     * catch-up) restores it. An inexact member never serves, fails over, or votes.
     */
    public boolean isExact() { return exact; }

    /** Package-private: the ensemble owns lifecycle transitions (E3). */
    void setState(State s) { this.state = s; }

    /** Package-private: the ensemble owns exactness (E5 sampled shadows / Option C rebuilds). */
    void setExact(boolean exact) { this.exact = exact; }

    // -- Epoch readers (ADR-004 R2) --

    void enterRead()      { epochReaders.getAndIncrement(); }
    void exitRead()       { epochReaders.getAndDecrement(); }
    int  activeReaders()  { return epochReaders.get(); }

    // -- Per-member rotation meter (ADR-024) --

    /**
     * Minimum writes a member must have <em>actually received</em> in an evaluation window before
     * its own rotations-per-write ratio counts as an observation.
     *
     * <p>The ratio's relative standard error falls as {@code 1/sqrt(w)}, so at {@code w = 8} a
     * single rebalancing cascade (a Red-Black delete fixup performs up to three rotations) moves
     * it by well under the {@link io.github.richeyworks.csrbt.control.MorphPolicy} default
     * improvement margin, while at {@code w = 2} one cascade can double it. Below this floor the
     * member has no measurement of its own and {@link #rotationsPerWrite()} says so
     * ({@code NaN}) rather than reporting a ratio built from a handful of samples — the same
     * "no observation is not a cheap observation" discipline
     * {@link io.github.richeyworks.csrbt.evolution.Fitness#informative(long)} applies to size.</p>
     */
    public static final long MIN_METERED_WRITES = 8L;

    /**
     * The meter's three words are {@code volatile} for the same reason {@link #state} and
     * {@link #exact} are: they are written on the write path and read, unsynchronized, from the
     * controller thread.
     *
     * <p>Every mutation ({@link #markRotations}, {@link #foldRotations},
     * {@link #resetRotationMeter}) runs inside {@code EnsembleOrderedSet}'s {@code writeLock}, so
     * there is exactly one mutator at a time and no read-modify-write needs to be atomic — but the
     * public readers ({@link #meteredRotations()}, {@link #meteredWrites()},
     * {@link #rotationsPerWrite()}) take no lock at all, and JLS 17.7 permits a non-volatile
     * 64-bit write to be observed as two 32-bit halves. A torn {@code meteredWrites} can put a
     * member above or below {@link #MIN_METERED_WRITES} on a value it never held, which flips the
     * per-member/stream pricing regime; a torn {@code meteredRotations} misprices the write term
     * directly. {@code volatile} removes both, and removes the staleness — before this, a
     * controller could read a meter the write path had already reset.</p>
     *
     * <p>{@link #meterVersion} makes the numerator/denominator <em>pair</em> readable as a
     * snapshot as well — see {@link #rotationsPerWrite()}. It is odd exactly while a fold or a
     * reset is mid-update. All four fields are volatile, so the JMM's synchronization order keeps
     * the writer's stores in program order and the reader's loads in program order; that is the
     * whole proof the seqlock rests on.</p>
     *
     * <p><b>Measured cost on the write path: none detectable.</b> 400 000 mixed writes fanned to
     * three members (Red-Black / AVL / Splay), 7 timed runs after 3 warm-up runs: median
     * <b>1588.5 ms</b> with the volatile stores and the version stamp, <b>1573.3 ms</b> without —
     * 1.0 %, inside a run-to-run spread of 1552–1766 ms and 1544–1713 ms respectively, i.e. about
     * 4 ns on a ~1320 ns member-write. That is what it should be: this is two counter reads, one
     * accumulate and two version stores per recipient per write, against a full
     * {@code OrderedSet.add} (comparisons, rotations, FIFO bookkeeping) already inside the
     * ensemble's {@code writeLock} — the stores are not even the ordering fence, the
     * {@code synchronized} block's exit already is.</p>
     */
    private volatile long rotationMark = -1L;
    private volatile long meteredRotations;
    private volatile long meteredWrites;
    private volatile long meterVersion;

    /**
     * Capture this member's rotation counter before a write is applied to it. Package-private:
     * only {@link EnsembleOrderedSet}'s fan-out knows which members a write actually reaches,
     * which is exactly what makes the denominator honest for a sampled shadow.
     */
    void markRotations() {
        rotationMark = (set instanceof OrderedSet<K> os) ? os.rotationCount() : -1L;
    }

    /**
     * Fold the rotations this member performed across the write just applied to it. Clamped at
     * zero per {@link OrderedSet#rotationCount()} — a morph or self-repair swaps the engine and
     * resets the counter, which would otherwise read as a negative delta. Never called for a
     * write the member did not receive, or for one that threw (a half-applied write's churn is
     * not a measurement of the policy).
     */
    void foldRotations() {
        long before = rotationMark;
        rotationMark = -1L;
        if (before < 0L) return;                                  // engine-tier: no counter
        long after = (set instanceof OrderedSet<K> os) ? os.rotationCount() : -1L;
        if (after < 0L) return;
        long v = meterVersion;
        meterVersion = v + 1;                        // odd: the pair is mid-update
        meteredRotations += Math.max(0L, after - before);
        meteredWrites++;
        meterVersion = v + 2;                        // even: the pair is consistent again
    }

    /** Clear the meter — the evaluation window's boundary; the controllers own the cadence. */
    void resetRotationMeter() {
        long v = meterVersion;
        meterVersion = v + 1;
        rotationMark = -1L;
        meteredRotations = 0L;
        meteredWrites = 0L;
        meterVersion = v + 2;
    }

    /** Rotations this member performed across the writes it received since the last reset. */
    public long meteredRotations() { return meteredRotations; }

    /**
     * Writes this member <em>actually received</em> since the last reset — not the stream's write
     * count. In {@link EnsembleMode#SAMPLED_SHADOW} a shadow takes every {@code sampleEvery}-th
     * write, so this is the only denominator that turns its rotation count into a rate comparable
     * with a full-stream member's.
     */
    public long meteredWrites() { return meteredWrites; }

    /**
     * This member's own realized rotations per write it received, or {@code NaN} when that is not
     * an observation — fewer than {@link #MIN_METERED_WRITES} received writes, or an ENGINE-tier
     * member, which has no rotation counter at all.
     *
     * <p>ADR-024: this is the per-member refinement ADR-011 held. Rotations-per-write is an
     * <em>intensive</em> quantity — a property of the policy, not of the stream's length — so
     * normalizing a shadow's rotations by the writes it saw makes it directly comparable with the
     * primary's rate even though the two saw different numbers of writes.</p>
     *
     * <p>The numerator and denominator are two words, so a caller reading them concurrently with
     * the write path could otherwise pair one write's rotations with the previous write's count —
     * a rate for a write sequence that never happened. They are read as a snapshot instead, over
     * the even-valued {@link #meterVersion} stamp the single mutator brackets each update with.
     * The retry loop makes progress by construction: there is one mutator (every fold and reset
     * runs under {@code EnsembleOrderedSet}'s {@code writeLock}), so it re-reads at most once per
     * completed write, and on an idle meter it reads a stable pair first time.</p>
     */
    public double rotationsPerWrite() {
        while (true) {
            long v = meterVersion;
            if ((v & 1L) == 0L) {                    // even: no fold or reset is mid-update
                long rotations = meteredRotations;
                long writes    = meteredWrites;
                if (v == meterVersion) {
                    return writes >= MIN_METERED_WRITES ? (double) rotations / writes : Double.NaN;
                }
            }
            Thread.onSpinWait();
        }
    }

    /**
     * {@code stream} with this member's own realized churn substituted for the stream-wide
     * {@link WorkloadFeatures#rotationsPerWrite()}, so {@code Fitness}'s write term prices the
     * member on the rotations <em>it</em> paid. Returns {@code stream} unchanged when this member
     * has no own measurement (see {@link #rotationsPerWrite()}), which is exactly the
     * primary-metered behavior that preceded ADR-024 — the refinement can never make the signal
     * worse than the number it replaces.
     *
     * <p>Comparability is the <em>caller's</em> job: a cost priced on a member's own churn and one
     * priced on the stream's are two different measurements, so the controllers price every side
     * of a comparison per-member or none of them (ADR-024 §Decision, clause 3).</p>
     */
    public WorkloadFeatures pricedFeatures(WorkloadFeatures stream) {
        double own = rotationsPerWrite();
        if (Double.isNaN(own)) return stream;
        return new WorkloadFeatures(stream.readFraction(), stream.writeFraction(),
                stream.accessSkew(), stream.meanSearchDepth(), own, stream.size(),
                stream.growthRate());
    }

    @Override
    public String toString() {
        return "EnsembleMember[" + strategyName() + ", " + state + (exact ? "" : ", shadow")
                + ", n=" + set.size() + "]";
    }
}
