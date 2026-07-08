package io.github.richeyworks.csrbt.ensemble;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentRankedSet;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.event.TreeEventListener;
import io.github.richeyworks.csrbt.interfaces.OrderedCollection;
import io.github.richeyworks.csrbt.interfaces.RankedSet;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Function;
import java.util.function.Supplier;

/**
 * EnsembleOrderedSet — a drop-in {@link OrderedCollection} backed by several independent strategy
 * members kept in exact sync (MIRROR mode), the foundation of the multi-tree ensemble in ADR-003.
 *
 * <p><b>Step E1 (this class):</b> every effective {@code add}/{@code remove} fans out to all active
 * members so each is an exact copy of the logical set; reads (membership, order, size, and order
 * statistics) are served by a fixed {@code primary}. Because switching the serving member will be a
 * pointer swap, adaptation can later become O(1) instead of an O(n) morph — but the controller that
 * does the swapping (E2), per-member health/quarantine/failover (E3), and read-quorum N-version
 * voting (E4) are not here yet. The primary never changes in E1.</p>
 *
 * <p>Members share no mutable state, so the write fan-out is embarrassingly parallel; E1 keeps it
 * sequential under a single writer lock (linearizable logical set) and parallelizes in E5.</p>
 *
 * <p><b>Step E5 (fan-out executor):</b> writes go through a {@link MemberExecutor} — sequential by
 * default (E1 behavior, bit-for-bit), parallel via {@link Builder#parallelFanOut()} or an injected
 * {@link Builder#executor(MemberExecutor)}. Either way the whole fan-out runs under the single
 * writer lock, so parallelism is within a write, never between writes — the logical set stays
 * linearizable. The ADR-003 write-failure rule also lands here: a member that throws is
 * {@code QUARANTINED} and the write still commits to the rest; if the <em>primary</em> throws, a
 * surviving member is promoted first (failover precedes quarantine, as in VERIFIED reads).</p>
 *
 * <p><b>Step E5 (sampled shadows):</b> in {@link EnsembleMode#SAMPLED_SHADOW} the primary receives
 * every write and stays the one exact copy; the other members receive only every
 * ceil(1/p)-th write (deterministic stride over the write counter), so they cost ~p of a mirror in
 * memory and write work. A shadow is marked {@linkplain EnsembleMember#isExact() inexact} on the
 * first write that skips it; from then on it never serves, fails over, or votes. {@link #promote}
 * on an inexact member performs the ADR's <em>sync-on-promote</em>: an O(n) rebuild from the
 * primary, then the swap — after which the deposed primary drifts into a shadow in its turn.</p>
 *
 * <p><b>ADR-004 R2 (READ_REPLICA):</b> lock-free reads via a left-right write discipline. Epoch
 * readers enter the serving member's counter, re-verify it still serves, and read a tree no
 * writer shares; the writer applies each op to the non-serving mirrors first, flips, drains the
 * old side's epoch, then updates it. Promotion and healing are epoch-aware (drain after a flip,
 * drain before a rebuild). Requires two exact ACTIVE members; degrades by failing writes loudly,
 * never by serving a mutating tree.</p>
 */
public final class EnsembleOrderedSet<K> implements OrderedCollection<K>, AutoCloseable {

    private static final Logger logger = LogManager.getLogger(EnsembleOrderedSet.class);

    /**
     * ADR-007 kill switch: when true (the default) a VERIFIED vote first makes one lock-free
     * pass and serves on unanimity; any disagreement escalates to the locked E4 vote. Set
     * false to restore pre-ADR-007 behavior wholesale (every vote under the writeLock).
     */
    public static volatile boolean OPTIMISTIC_VOTES = true;

    private final List<EnsembleMember<K>> members;
    private final Comparator<? super K> keyOrder;
    private final Object writeLock = new Object();
    private final MemberExecutor executor;
    private final int sampleEvery;            // SAMPLED_SHADOW: shadows receive every sampleEvery-th write
    private final int rebuildEvery;           // REBUILD_SHADOW: shadows rebuilt every rebuildEvery-th write
    private final long memoryCeilingBytes;    // 0 = no ceiling (ADR-003 "Revisit": memory ceilings)
    private final int verifyEvery;            // VERIFIED: every verifyEvery-th read votes (ADR-006)
    private final AtomicLong verifiedReads = new AtomicLong();   // VERIFIED read stride; outside the lock
    private long writeOps;                    // logical add/remove counter; guarded by writeLock
    private volatile boolean overCeiling;     // latched breach flag; reset when back under
    private volatile EnsembleMember<K> primary;
    private volatile EnsembleMode mode = EnsembleMode.MIRROR;

    // -- structured events (ADR-009 P3); null = unobserved, the allocation-free default --
    private volatile TreeEventListener<K> events;

    /**
     * Register a structured-event listener (ADR-009 P3); {@code null} unregisters. Ensemble
     * events mirror the {@code event=...} log lines: quarantine/heal/retire, promotion (with
     * a failover flag), Option C shadow rebuilds, and memory-ceiling transitions. Controller-
     * driven repairs flow through the same lifecycle methods, so they emit automatically.
     * See {@link TreeEventListener} for the fast/non-reentrant contract.
     */
    public void setEventListener(TreeEventListener<K> listener) { this.events = listener; }

    /**
     * Forward to the listener, swallowing anything it throws (hardening M-1, mirroring
     * {@code OrderedSet.emit}): several emit sites run inside the write lock mid-fan-out — a
     * throwing listener must not fail the write, spuriously quarantine a member, or abort a
     * promotion that already happened. Call only after a null check.
     */
    private void emit(TreeEvent<K> e) {
        try {
            events.onEvent(e);
        } catch (RuntimeException listenerFault) {
            // Observability must never break the data plane.
        }
    }

    private EnsembleOrderedSet(List<EnsembleMember<K>> members, Comparator<? super K> keyOrder,
                               MemberExecutor executor, int sampleEvery, int rebuildEvery,
                               long memoryCeilingBytes, int verifyEvery) {
        this.members = members;
        this.keyOrder = keyOrder;
        this.executor = executor;
        this.sampleEvery = sampleEvery;
        this.rebuildEvery = rebuildEvery;
        this.memoryCeilingBytes = memoryCeilingBytes;
        this.verifyEvery = verifyEvery;
        this.primary = members.get(0);
    }

    // ── Construction ────────────────────────────────────────────────────────────

    public static <K> Builder<K> builder(Comparator<? super K> keyOrder) {
        return new Builder<>(keyOrder);
    }

    /** Fluent builder. The first member added is the initial primary. */
    public static final class Builder<K> {
        private final Comparator<? super K> keyOrder;
        private final List<Supplier<EnsembleMember<K>>> specs = new ArrayList<>();
        private EnsembleMode mode = EnsembleMode.MIRROR;
        private MemberExecutor executor;
        private boolean parallel;
        private double shadowSampleRate = 0.1;
        private int rebuildEvery = 4096;
        private long memoryCeilingBytes = 0;
        private int maxMembers = 0;
        private int verifyEvery = 1;

        private Builder(Comparator<? super K> keyOrder) {
            this.keyOrder = Objects.requireNonNull(keyOrder, "keyOrder cannot be null");
        }

        /** Add a member backed by a fresh strategy from {@code strategy}. */
        public Builder<K> member(Supplier<? extends TreeStrategy<K>> strategy) {
            Objects.requireNonNull(strategy, "strategy cannot be null");
            specs.add(() -> new EnsembleMember<>(new OrderedSet<>(strategy.get(), keyOrder)));
            return this;
        }

        /**
         * Add an ENGINE-tier member backed by the weight-balanced persistent engine
         * (ADR-005 P3). A persistent member mirrors the logical set like any other, serves,
         * votes, fails over, and heals — its reads are wait-free by construction, so promoting
         * it buys the R3 read guarantee for the whole ensemble's serving path. It carries no
         * {@code TreeStrategy}, so the controller's StrategyId-driven promotion never selects
         * it automatically; promote it explicitly, or let failover find it.
         */
        public Builder<K> persistentMember() {
            return engineMember(() -> new PersistentRankedSet<>(keyOrder), "PersistentTreeEngine");
        }

        /**
         * Add an ENGINE-tier member backed by any {@link RankedSet} (ADR-008 — the
         * generalization {@link #persistentMember()} now delegates to). The supplied set must
         * honor {@code OrderedSet}'s method-for-method semantics (the {@code RankedSet} voting
         * parity contract) and start empty. Like every engine member it serves, votes, heals,
         * and fails over, but is never promoted automatically — the cost-model scorer cannot
         * rank a member with no {@code TreeStrategy}.
         *
         * @param set   factory for the backing set (one fresh instance per build)
         * @param label member label for logs and {@code memberNamed}-style lookups,
         *              e.g. {@code "BPlusTreeEngine"}
         */
        public Builder<K> engineMember(Supplier<? extends RankedSet<K>> set, String label) {
            Objects.requireNonNull(set, "set cannot be null");
            Objects.requireNonNull(label, "label cannot be null");
            specs.add(() -> new EnsembleMember<>(set.get(), label));
            return this;
        }

        /**
         * REBUILD_SHADOW cadence (ADR-003 Option C): shadows are rebuilt from a primary snapshot
         * every {@code ops} writes (default 4096) and drift again until the next rebuild.
         */
        public Builder<K> rebuildEvery(int ops) {
            if (ops < 1) throw new IllegalArgumentException("rebuildEvery must be >= 1: " + ops);
            this.rebuildEvery = ops;
            return this;
        }

        /**
         * Soft memory ceiling in estimated bytes (ADR-003 "Revisit"; 0 = none, the default).
         * Checked on every write: a breach latches {@link EnsembleOrderedSet#isOverMemoryCeiling()}
         * and logs one loud {@code event=memory_ceiling} line (and one on recovery). The ensemble
         * never degrades itself — switching to SAMPLED_SHADOW/REBUILD_SHADOW or reducing K is the
         * operator's call, because both have semantic consequences (exactness, voting).
         */
        public Builder<K> memoryCeilingBytes(long bytes) {
            if (bytes < 0) throw new IllegalArgumentException("memoryCeilingBytes must be >= 0: " + bytes);
            this.memoryCeilingBytes = bytes;
            return this;
        }

        /** Hard cap on K (ADR-003 "Revisit"): {@code build()} rejects more members than this. */
        public Builder<K> maxMembers(int k) {
            if (k < 2) throw new IllegalArgumentException("maxMembers must be >= 2: " + k);
            this.maxMembers = k;
            return this;
        }

        /**
         * VERIFIED amplification dial (ADR-006): every {@code n}-th read runs the full E4 vote
         * (majority serve, dissenter quarantine, primary failover); the other n−1 serve from the
         * primary alone, lock-free, exactly like MIRROR reads. Default 1 — every read votes, the
         * E4 guarantee verbatim. The honest trade at n&gt;1: a <em>divergent primary</em> can
         * serve up to n−1 unverified reads before the next vote catches and deposes it; against
         * the post-R1 fault class (persistent content divergence) detection is still bounded by
         * n verified-mode reads. Ignored outside VERIFIED.
         */
        public Builder<K> verifyEvery(int n) {
            if (n < 1) throw new IllegalArgumentException("verifyEvery must be >= 1: " + n);
            this.verifyEvery = n;
            return this;
        }

        /** Read mode: MIRROR (serve from the primary) or VERIFIED (quorum vote). Default MIRROR. */
        public Builder<K> mode(EnsembleMode mode) {
            this.mode = Objects.requireNonNull(mode, "mode cannot be null");
            return this;
        }

        /**
         * Fan writes out to members in parallel (ADR-003 E5): one logical write is applied to all
         * K members concurrently on a daemon pool sized min(K-1, cores) — one member always runs
         * on the writer's own thread. Mutually exclusive with {@link #executor(MemberExecutor)}.
         */
        public Builder<K> parallelFanOut() {
            this.parallel = true;
            return this;
        }

        /** Inject a custom fan-out executor (tests, alternative pools). Overrides the default. */
        public Builder<K> executor(MemberExecutor executor) {
            this.executor = Objects.requireNonNull(executor, "executor cannot be null");
            return this;
        }

        /**
         * Fraction p of writes a shadow receives in {@link EnsembleMode#SAMPLED_SHADOW} (default
         * 0.1). Realized as a deterministic stride: shadows receive every ceil(1/p)-th write.
         * Ignored in MIRROR/VERIFIED, where every member receives every write.
         */
        public Builder<K> shadowSampleRate(double p) {
            if (!(p > 0.0 && p <= 1.0)) {
                throw new IllegalArgumentException("shadowSampleRate must be in (0, 1]: " + p);
            }
            this.shadowSampleRate = p;
            return this;
        }

        public EnsembleOrderedSet<K> build() {
            if (specs.size() < 2) {
                throw new IllegalArgumentException("an ensemble needs at least two members");
            }
            if (maxMembers > 0 && specs.size() > maxMembers) {
                throw new IllegalArgumentException("ensemble capped at K=" + maxMembers
                        + " members; " + specs.size() + " specified (memory ceiling, ADR-003)");
            }
            if (mode == EnsembleMode.VERIFIED && specs.size() < 3) {
                throw new IllegalArgumentException("VERIFIED mode needs at least three members to form a majority");
            }
            if (parallel && executor != null) {
                throw new IllegalArgumentException("choose parallelFanOut() or executor(...), not both");
            }
            List<EnsembleMember<K>> ms = new ArrayList<>(specs.size());
            for (Supplier<EnsembleMember<K>> s : specs) {
                ms.add(s.get());
            }
            MemberExecutor exec = executor != null ? executor
                    : parallel ? new ParallelMemberExecutor(
                            Math.max(1, Math.min(specs.size() - 1, Runtime.getRuntime().availableProcessors())))
                    : MemberExecutor.sequential();
            int sampleEvery = Math.max(1, (int) Math.round(1.0 / shadowSampleRate));
            EnsembleOrderedSet<K> ens = new EnsembleOrderedSet<>(ms, keyOrder, exec, sampleEvery,
                    rebuildEvery, memoryCeilingBytes, verifyEvery);
            ens.mode = mode;
            return ens;
        }
    }

    // ── Writes: fan out to every active member via the MemberExecutor (E1 seq / E5 parallel) ──

    @Override
    public boolean add(K value) {
        return write("add", true, s -> s.add(value));
    }

    @Override
    public boolean remove(K value) {
        return write("remove", true, s -> s.remove(value));
    }

    @Override
    public void clear() {
        // Never sampled: a skipped clear would leave a shadow holding keys the logical set dropped
        // wholesale. (An emptied shadow that was already inexact stays inexact -- harmless.)
        write("clear", false, s -> { s.clear(); return true; });
    }

    /**
     * Bulk-build every member from one ASCENDING, DISTINCT run, fanned out across members through the
     * {@link MemberExecutor} (parallel when {@code parallelFanOut()}). Strategy-backed members use
     * {@link io.github.richeyworks.csrbt.OrderedSet#buildFromSorted} (O(n)); any engine-tier member
     * without that fast path falls back to element-wise {@code add}. Every member ends an exact mirror.
     *
     * <p>Additive and gated: requires an <em>empty</em> ensemble in {@link EnsembleMode#MIRROR} or
     * {@link EnsembleMode#VERIFIED} (the modes where every member is an exact copy). It deliberately
     * bypasses the per-write cadence/events of the {@code add} path -- it is a one-shot initial load,
     * not a logical write stream. Runs under the writer lock, so it is linearizable against writes.</p>
     *
     * @throws IllegalStateException if the ensemble is non-empty, not in an all-exact mode, or a member build fails
     */
    public void buildAllFromSorted(List<K> ascendingDistinct) {
        synchronized (writeLock) {
            if (mode != EnsembleMode.MIRROR && mode != EnsembleMode.VERIFIED) {
                throw new IllegalStateException("buildAllFromSorted requires MIRROR or VERIFIED mode; was " + mode);
            }
            if (!isEmpty()) {
                throw new IllegalStateException("buildAllFromSorted requires an empty ensemble");
            }
            List<EnsembleMember<K>> recipients = new ArrayList<>();
            for (EnsembleMember<K> m : members) {
                if (m.isActive()) recipients.add(m);
            }
            List<MemberExecutor.Outcome> outcomes = executor.apply(recipients, m -> {
                if (m.isStrategyBacked()) {
                    m.orderedSet().buildFromSorted(ascendingDistinct);
                } else {
                    for (K k : ascendingDistinct) m.set().add(k);
                }
                return true;
            });
            for (int i = 0; i < recipients.size(); i++) {
                if (outcomes.get(i).failed()) {
                    throw new IllegalStateException("buildAllFromSorted: a member build failed", outcomes.get(i).cause());
                }
                recipients.get(i).setExact(true);
            }
        }
    }

    /** Dispatch a write: READ_REPLICA uses the left-right two-phase protocol (ADR-004 R2). */
    private boolean write(String op, boolean sampleable, Function<RankedSet<K>, Boolean> fn) {
        return (mode == EnsembleMode.READ_REPLICA)
                ? replicaWrite(op, fn)
                : fanOutWrite(op, sampleable, fn);
    }

    /**
     * One logical write: under the writer lock, apply {@code op} to the recipient members through
     * the {@link MemberExecutor}, then enforce the ADR-003 write-failure rule — a member that
     * throws is {@code QUARANTINED} while the write commits to the rest; if the serving primary
     * threw, a surviving <em>exact</em> member is promoted first (failover precedes quarantine,
     * mirroring VERIFIED reads). Returns the serving (possibly just-promoted) primary's
     * effective-change result.
     *
     * <p>Recipients are all ACTIVE members — except in {@link EnsembleMode#SAMPLED_SHADOW} (when
     * {@code sampleable}), where non-primary members receive only every {@code sampleEvery}-th
     * write; a skipped member is marked inexact on its first miss and is a shadow from then on.</p>
     *
     * @throws IllegalStateException if every recipient failed, or the primary failed with no exact
     *                               survivor (shadows cannot fail over) — the write did not commit
     */
    private boolean fanOutWrite(String op, boolean sampleable, Function<RankedSet<K>, Boolean> fn) {
        synchronized (writeLock) {
            EnsembleMember<K> servingPrimary = primary;
            boolean sampling   = sampleable && mode == EnsembleMode.SAMPLED_SHADOW;
            boolean rebuilding = sampleable && mode == EnsembleMode.REBUILD_SHADOW;
            long op0 = (sampling || rebuilding) ? ++writeOps : 0;
            // SAMPLED_SHADOW: shadows take every sampleEvery-th write. REBUILD_SHADOW (Option C):
            // shadows take no live writes at all — they are refreshed wholesale by the cadence
            // rebuild below, which runs after this write commits so the rebuilt copy includes it.
            boolean shadowsReceive = !(sampling || rebuilding) || (sampling && op0 % sampleEvery == 0);

            List<EnsembleMember<K>> recipients = new ArrayList<>();
            for (EnsembleMember<K> m : members) {
                if (!m.isActive()) continue;
                if (m == servingPrimary || shadowsReceive) {
                    recipients.add(m);
                } else if (m.isExact()) {
                    m.setExact(false);            // first skipped write: an exact mirror becomes a shadow
                }
            }
            List<MemberExecutor.Outcome> outcomes = executor.apply(recipients, m -> fn.apply(m.set()));

            boolean primaryChanged = false, primaryFailed = false;
            int failures = 0;
            for (int i = 0; i < recipients.size(); i++) {
                MemberExecutor.Outcome o = outcomes.get(i);
                if (o.failed()) {
                    failures++;
                    if (recipients.get(i) == servingPrimary) primaryFailed = true;
                } else if (recipients.get(i) == servingPrimary) {
                    primaryChanged = o.changed();
                }
            }
            if (failures == 0) {                                          // the common, healthy case
                if (rebuilding && op0 % rebuildEvery == 0) rebuildShadows();
                checkMemoryCeiling();
                return primaryChanged;
            }

            if (failures == recipients.size()) {
                Throwable cause = outcomes.isEmpty() ? null : outcomes.get(0).cause();
                throw new IllegalStateException(op + " failed on every recipient member; write did not commit", cause);
            }

            if (primaryFailed) {
                // Failover before quarantine: promote the first EXACT member whose write committed
                // (a sampled shadow is not a faithful copy and can never stand in for the primary).
                EnsembleMember<K> replacement = null;
                for (int i = 0; i < recipients.size(); i++) {
                    if (!outcomes.get(i).failed() && recipients.get(i).isExact()) {
                        replacement = recipients.get(i);
                        primaryChanged = outcomes.get(i).changed();
                        break;
                    }
                }
                if (replacement == null) {
                    Throwable cause = null;
                    for (int i = 0; i < recipients.size(); i++) {
                        if (recipients.get(i) == servingPrimary) { cause = outcomes.get(i).cause(); break; }
                    }
                    throw new IllegalStateException(
                            op + " failed on the primary and no exact member can fail over; write did not commit", cause);
                }
                this.primary = replacement;                               // volatile publish under the lock
                if (events != null) {
                    emit(new TreeEvent.Promote<>(servingPrimary.strategyName(),
                            replacement.strategyName(), true));
                }
            }
            StringBuilder q = new StringBuilder("[");
            for (int i = 0; i < recipients.size(); i++) {
                if (!outcomes.get(i).failed()) continue;
                EnsembleMember<K> failed = recipients.get(i);
                if (failed.state() != EnsembleMember.State.RETIRED) {
                    failed.setState(EnsembleMember.State.QUARANTINED);    // half-applied write -> heal later (E3)
                    if (events != null) emit(new TreeEvent.Quarantine<>(failed.strategyName()));
                }
                if (q.length() > 1) q.append(", ");
                q.append(failed.strategyName());
            }
            q.append(']');
            logger.warn("event=write_member_failure op={} quarantined={} failedOver={} survivors={}",
                    op, q, primaryFailed, recipients.size() - failures);
            if (rebuilding && op0 % rebuildEvery == 0) rebuildShadows();
            checkMemoryCeiling();
            return primaryChanged;
        }
    }

    // ── REBUILD_SHADOW: the Option C cadence rebuild (ADR-003 §3C) ────────────────

    /**
     * Rebuild every ACTIVE non-primary member from the primary's contents (Option C's amortized
     * O(n) cost), making each an exact, <em>warm</em> promotion target until the next live write
     * marks it inexact again. Runs under the write lock, after the triggering write committed, so
     * the rebuilt copies include it. The realized meters a rebuild leaves behind (height, build
     * time per insert) are the mode's promotion signal — Option C trades the mirror's continuous
     * signal and redundancy for 1× steady-state writes, exactly as the ADR's cost table says.
     */
    private void rebuildShadows() {
        List<K> truth = primary.set().inOrder();
        int rebuilt = 0;
        for (EnsembleMember<K> m : members) {
            if (m == primary || !m.isActive()) continue;
            RankedSet<K> s = m.set();
            s.clear();
            for (K k : truth) s.add(k);
            m.setExact(true);
            rebuilt++;
        }
        logger.info("event=shadow_rebuild op={} n={} rebuilt={}", writeOps, truth.size(), rebuilt);
        if (events != null) emit(new TreeEvent.ShadowRebuild<>(rebuilt, truth.size()));
    }

    // ── Memory ceiling (ADR-003 "Revisit") ────────────────────────────────────────

    /**
     * Compare the estimated footprint against the configured ceiling (no-op when none). The check
     * is O(K) arithmetic over {@code size()}, so it runs on every write; breach and recovery each
     * log exactly once (latched), and the state is queryable via {@link #isOverMemoryCeiling()}.
     */
    private void checkMemoryCeiling() {
        if (memoryCeilingBytes <= 0) return;
        long estimate = estimatedMemoryBytes();
        if (estimate > memoryCeilingBytes) {
            if (!overCeiling) {
                overCeiling = true;
                logger.warn("event=memory_ceiling state=BREACHED estimateBytes={} ceilingBytes={} members={} "
                        + "hint=\"switch to SAMPLED_SHADOW/REBUILD_SHADOW or reduce K\"",
                        estimate, memoryCeilingBytes, members.size());
                if (events != null) {
                    emit(new TreeEvent.MemoryCeiling<>(true, estimate, memoryCeilingBytes));
                }
            }
        } else if (overCeiling) {
            overCeiling = false;
            logger.info("event=memory_ceiling state=RECOVERED estimateBytes={} ceilingBytes={}",
                    estimate, memoryCeilingBytes);
            if (events != null) {
                emit(new TreeEvent.MemoryCeiling<>(false, estimate, memoryCeilingBytes));
            }
        }
    }

    // ── READ_REPLICA: left-right two-phase writes + epoch reads (ADR-004 R2) ──────

    /**
     * One logical write under the left-right discipline: apply {@code op} to every ACTIVE
     * non-serving member (through the {@link MemberExecutor}, so the fan-out may be parallel),
     * flip the serving pointer to an exact member whose write committed, <b>drain</b> the old
     * side's epoch readers, then apply the op to the old side. A reader therefore never shares a
     * tree with a writer: the serving member is mutated only after it stopped serving and its
     * last reader left. Failed non-serving members are quarantined as in MIRROR; if the old
     * serving member fails its (post-drain) apply it is quarantined too — it is no longer
     * primary, so the write has already committed to the logical set.
     *
     * @throws IllegalStateException if no exact ACTIVE non-serving member committed the write —
     *                               READ_REPLICA cannot flip, so the write must fail loudly
     */
    private boolean replicaWrite(String op, Function<RankedSet<K>, Boolean> fn) {
        synchronized (writeLock) {
            EnsembleMember<K> serving = primary;
            List<EnsembleMember<K>> others = new ArrayList<>();
            for (EnsembleMember<K> m : members) {
                if (m.isActive() && m != serving) others.add(m);
            }
            if (others.isEmpty()) {
                throw new IllegalStateException(
                        op + ": READ_REPLICA needs a second ACTIVE member to flip to; write did not commit");
            }
            List<MemberExecutor.Outcome> outcomes = executor.apply(others, m -> fn.apply(m.set()));

            EnsembleMember<K> newServing = null;
            boolean changed = false;
            int failures = 0;
            for (int i = 0; i < others.size(); i++) {
                if (outcomes.get(i).failed()) {
                    failures++;
                } else if (newServing == null && others.get(i).isExact()) {
                    newServing = others.get(i);
                    changed = outcomes.get(i).changed();
                }
            }
            StringBuilder q = failures == 0 ? null : new StringBuilder("[");
            for (int i = 0; i < others.size(); i++) {
                if (!outcomes.get(i).failed()) continue;
                EnsembleMember<K> failed = others.get(i);
                if (failed.state() != EnsembleMember.State.RETIRED) {
                    failed.setState(EnsembleMember.State.QUARANTINED);
                }
                if (q.length() > 1) q.append(", ");
                q.append(failed.strategyName());
            }
            if (newServing == null) {
                Throwable cause = outcomes.isEmpty() ? null : outcomes.get(0).cause();
                throw new IllegalStateException(
                        op + ": no exact member committed the write; READ_REPLICA cannot flip", cause);
            }

            this.primary = newServing;     // flip: new readers go to the freshly written side
            drainReaders(serving);         // wait out readers still inside the old side's epoch
            try {
                fn.apply(serving.set());   // bring the old side up to date — no reader can see this
            } catch (Throwable t) {
                if (serving.state() != EnsembleMember.State.RETIRED) {
                    serving.setState(EnsembleMember.State.QUARANTINED);
                }
                logger.warn("event=replica_old_side_failure op={} member={} quarantined=true",
                        op, serving.strategyName(), t);
            }
            if (q != null) {
                q.append(']');
                logger.warn("event=write_member_failure op={} quarantined={} failedOver=false survivors={}",
                        op, q, others.size() - failures + 1);
            }
            checkMemoryCeiling();
            return changed;
        }
    }

    /**
     * Epoch read (ADR-004 R2): enter the serving member's epoch, re-verify it is still serving,
     * and only then dereference its tree. The re-check closes the flip race: once the count is
     * held and the member is observed as primary, a writer must flip away and drain — and the
     * drain waits on this very count — before it may mutate. A reader that loses the race exits
     * without touching the tree and retries on the new serving member.
     */
    private <R> R replicaRead(Function<RankedSet<K>, R> fn) {
        for (;;) {
            EnsembleMember<K> p = primary;
            p.enterRead();
            try {
                if (p == primary) {
                    return fn.apply(p.set());
                }
            } finally {
                p.exitRead();
            }
            // raced a flip between the volatile load and the epoch entry — retry on the new side
        }
    }

    /** Spin until {@code m} has no epoch readers (writer-side, under the write lock). */
    private void drainReaders(EnsembleMember<K> m) {
        int spins = 0;
        while (m.activeReaders() != 0) {
            spins++;
            if (spins < 1024) {
                Thread.onSpinWait();
            } else {
                Thread.yield();
                if ((spins & 0xFFFF) == 0) {
                    logger.warn("event=replica_drain_slow member={} readers={}",
                            m.strategyName(), m.activeReaders());
                }
            }
        }
    }

    // ── Reads: served by the primary ──────────────────────────────────────────────

    @Override public boolean contains(K value) { return read(s -> s.contains(value)); }
    @Override public int size()                { return read(s -> s.size()); }
    @Override public List<K> inOrder()         { return read(s -> s.inOrder()); }
    @Override public boolean isEmpty()         { return read(s -> s.isEmpty()); }

    // ── Order statistics (drop-in parity with OrderedSet), served by the primary ──

    public K select(int rank)             { return read(s -> s.select(rank)); }
    public int rank(K value)              { return read(s -> s.rank(value)); }
    public K successor(K value)           { return read(s -> s.successor(value)); }
    public K predecessor(K value)         { return read(s -> s.predecessor(value)); }
    public K minimum()                    { return read(s -> s.minimum()); }
    public K maximum()                    { return read(s -> s.maximum()); }
    public K median()                     { return read(s -> s.median()); }
    public K percentile(int pct)          { return read(s -> s.percentile(pct)); }
    public int countInRange(K lo, K hi)   { return read(s -> s.countInRange(lo, hi)); }
    public List<K> rangeQuery(K lo, K hi) { return read(s -> s.rangeQuery(lo, hi)); }

    // ── Promotion: the O(1) atomic primary swap (ADR-003 E2) ─────────────────────

    /**
     * Promote {@code member} to primary — make it the member that serves reads and order
     * statistics. Because every member already mirrors the logical set, this is a single
     * {@code volatile} pointer publish: <b>O(1)</b>, with no tree rebuild, no traversal, and
     * no copy. It is the payoff ADR-003 trades the mirror's write fan-out for — adaptation
     * becomes a pointer swap instead of {@code OrderedSet.setStrategy}'s O(n) build-aside.
     *
     * <p>Serialized on the same write lock as the fan-out, so a swap never interleaves with a
     * mutation. The incoming member must be a live ({@code ACTIVE}) member of this ensemble —
     * serving reads from a quarantined member (E3) would read from a set that is no longer a
     * faithful mirror.</p>
     *
     * <p><b>Sampled shadows (E5):</b> an {@linkplain EnsembleMember#isExact() inexact} member is
     * first caught up by an O(n) rebuild from the current primary — the ADR's
     * <em>sync-on-promote</em> — and only then swapped in. In MIRROR operation every member is
     * exact and the swap stays O(1); the cost table's "O(n) sync-on-promote" applies exactly when
     * SAMPLED_SHADOW chose to skimp on the standing fan-out.</p>
     *
     * @param member the member to serve reads from; must belong to this ensemble and be {@code ACTIVE}
     * @return {@code true} if the primary changed; {@code false} if {@code member} was already primary
     * @throws IllegalArgumentException if {@code member} is not part of this ensemble
     * @throws IllegalStateException    if {@code member} is not {@code ACTIVE}
     */
    public boolean promote(EnsembleMember<K> member) {
        Objects.requireNonNull(member, "member cannot be null");
        synchronized (writeLock) {
            if (!members.contains(member)) {
                throw new IllegalArgumentException("member is not part of this ensemble: " + member);
            }
            if (!member.isActive()) {
                throw new IllegalStateException("cannot promote a non-active member: " + member);
            }
            if (member == primary) return false;
            if (!member.isExact()) {
                // Sync-on-promote: rebuild the shadow from the one exact copy, then it may serve.
                List<K> truth = primary.set().inOrder();
                RankedSet<K> set = member.set();
                set.clear();
                for (K k : truth) set.add(k);
                member.setExact(true);
                logger.info("event=shadow_catchup member={} n={}", member.strategyName(), truth.size());
            }
            EnsembleMember<K> deposed = primary;
            this.primary = member;   // volatile publish — readers observe the swap atomically
            if (events != null) {
                emit(new TreeEvent.Promote<>(deposed.strategyName(), member.strategyName(), false));
            }
            if (mode == EnsembleMode.READ_REPLICA) {
                // Epoch-aware promotion (ADR-004 R2): readers may still be inside the deposed
                // member's epoch. Drain before returning so any later mutation of it is safe.
                drainReaders(deposed);
            }
            return true;
        }
    }

    // ── Introspection ────────────────────────────────────────────────────────────

    /** The member currently serving reads. */
    public EnsembleMember<K> primary() { return primary; }

    /** All members, in insertion order, unmodifiable. */
    public List<EnsembleMember<K>> members() { return Collections.unmodifiableList(members); }

    public Comparator<? super K> comparator() { return keyOrder; }

    /** The fan-out executor in use (sequential unless configured otherwise). */
    public MemberExecutor fanOutExecutor() { return executor; }

    // ── Memory metrics (ADR-003 "Revisit": memory ceilings / cap-K) ──────────────

    /**
     * Estimated live footprint of all non-retired members, in bytes — a coarse node-count model
     * (see {@link RankedSet#estimatedMemoryBytes()}), for trend and ceiling checks, not accounting.
     */
    public long estimatedMemoryBytes() {
        long sum = 0;
        for (EnsembleMember<K> m : members) {
            if (m.state() != EnsembleMember.State.RETIRED) sum += m.set().estimatedMemoryBytes();
        }
        return sum;
    }

    /** The configured soft ceiling in bytes (0 = none). */
    public long memoryCeilingBytes() { return memoryCeilingBytes; }

    /** True while the estimated footprint exceeds the configured ceiling (latched per breach). */
    public boolean isOverMemoryCeiling() { return overCeiling; }

    /** REBUILD_SHADOW cadence in writes (Option C; meaningful only in that mode). */
    public int rebuildEvery() { return rebuildEvery; }

    /** VERIFIED vote stride in reads (ADR-006; 1 = every read votes, the E4 default). */
    public int verifyEvery() { return verifyEvery; }

    /**
     * Release the fan-out executor's threads (E5). Safe to skip — the parallel pool uses daemon
     * threads — and a no-op for the sequential default. The ensemble must not be written after close.
     */
    @Override
    public void close() { executor.shutdown(); }

    @Override
    public String toString() {
        return "EnsembleOrderedSet[primary=" + primary.strategyName()
                + ", members=" + members.size() + ", n=" + size() + ", mode=" + mode
                + (mode == EnsembleMode.VERIFIED && verifyEvery > 1
                        ? ", verifyEvery=" + verifyEvery : "")
                + "]";
    }

    // -- Health lifecycle: quarantine / heal / retire (ADR-003 E3) --

    /**
     * Drop {@code member} from serving and write fan-out by marking it {@code QUARANTINED}
     * (E1's fan-out already skips non-{@code ACTIVE} members). The serving primary cannot be
     * quarantined directly -- {@link #promote} a healthy member first (failover), then quarantine
     * the deposed one. Serialized on the write lock.
     *
     * @return {@code true} if the member moved to {@code QUARANTINED}; {@code false} if already retired
     * @throws IllegalStateException if {@code member} is the serving primary
     */
    public boolean quarantine(EnsembleMember<K> member) {
        Objects.requireNonNull(member, "member cannot be null");
        synchronized (writeLock) {
            if (!members.contains(member)) {
                throw new IllegalArgumentException("member is not part of this ensemble: " + member);
            }
            if (member == primary) {
                throw new IllegalStateException("cannot quarantine the serving primary; fail over first");
            }
            if (member.state() == EnsembleMember.State.RETIRED) return false;
            member.setState(EnsembleMember.State.QUARANTINED);
            if (events != null) emit(new TreeEvent.Quarantine<>(member.strategyName()));
            return true;
        }
    }

    /**
     * Heal {@code member} by rebuilding its backing set from the <em>current primary</em>'s
     * contents and returning it to {@code ACTIVE} -- the recover step after a quarantine
     * (ADR-003 E3). The primary is the source of truth, so the healed member becomes an exact
     * mirror again under its own strategy. O(n) in the live size; {@code member} must not be the
     * primary. Serialized on the write lock.
     *
     * @return {@code true} if the member was rebuilt and reactivated; {@code false} if retired
     * @throws IllegalStateException if {@code member} is the serving primary
     */
    public boolean healFromPrimary(EnsembleMember<K> member) {
        Objects.requireNonNull(member, "member cannot be null");
        synchronized (writeLock) {
            if (!members.contains(member)) {
                throw new IllegalArgumentException("member is not part of this ensemble: " + member);
            }
            if (member == primary) {
                throw new IllegalStateException("cannot heal the primary from itself");
            }
            if (member.state() == EnsembleMember.State.RETIRED) return false;
            drainReaders(member);                      // defensive (R2): never rebuild under a reader
            List<K> truth = primary.set().inOrder();   // source of truth
            RankedSet<K> set = member.set();
            set.clear();
            for (K k : truth) set.add(k);
            member.setState(EnsembleMember.State.ACTIVE);
            member.setExact(true);                     // a full rebuild is an exact mirror (until sampled again)
            if (events != null) emit(new TreeEvent.Heal<>(member.strategyName(), true));
            return true;
        }
    }

    /**
     * Permanently remove {@code member} from service ({@code RETIRED}) -- used when a heal still
     * fails its health check. A retired member is never served, fanned to, or promoted. The
     * primary cannot be retired directly. Serialized on the write lock.
     *
     * @throws IllegalStateException if {@code member} is the serving primary
     */
    public boolean retire(EnsembleMember<K> member) {
        Objects.requireNonNull(member, "member cannot be null");
        synchronized (writeLock) {
            if (!members.contains(member)) {
                throw new IllegalArgumentException("member is not part of this ensemble: " + member);
            }
            if (member == primary) {
                throw new IllegalStateException("cannot retire the serving primary; fail over first");
            }
            member.setState(EnsembleMember.State.RETIRED);
            if (events != null) emit(new TreeEvent.Retire<>(member.strategyName()));
            return true;
        }
    }

    // -- VERIFIED mode: quorum read voting (ADR-003 E4) --

    /** Current read mode (MIRROR serves the primary; VERIFIED quorum-votes). */
    public EnsembleMode mode() { return mode; }

    /**
     * Switch read mode at runtime. VERIFIED needs at least three <em>exact</em> ACTIVE members to
     * adjudicate a majority — sampled shadows cannot vote, so an ensemble that has been running
     * SAMPLED_SHADOW must heal its shadows back to exact mirrors before it can verify.
     */
    public void setMode(EnsembleMode newMode) {
        Objects.requireNonNull(newMode, "mode cannot be null");
        if (newMode == EnsembleMode.VERIFIED || newMode == EnsembleMode.READ_REPLICA) {
            int exactActive = 0;
            for (EnsembleMember<K> m : members) {
                if (m.isActive() && m.isExact()) exactActive++;
            }
            if (newMode == EnsembleMode.VERIFIED && exactActive < 3) {
                throw new IllegalStateException(
                        "VERIFIED mode needs at least three exact ACTIVE members to form a majority; have " + exactActive);
            }
            if (newMode == EnsembleMode.READ_REPLICA && exactActive < 2) {
                throw new IllegalStateException(
                        "READ_REPLICA mode needs at least two exact ACTIVE members to flip between; have " + exactActive);
            }
        }
        this.mode = newMode;
    }

    /** Dispatch a read: MIRROR serves the primary; VERIFIED votes; READ_REPLICA reads in an epoch. */
    private <R> R read(Function<RankedSet<K>, R> fn) {
        EnsembleMode m = mode;
        if (m == EnsembleMode.VERIFIED) {
            // ADR-006: every verifyEvery-th read votes; the others serve from the primary,
            // lock-free. At the default (1) the stride counter is never touched.
            if (verifyEvery == 1 || verifiedReads.incrementAndGet() % verifyEvery == 0) {
                return vote(fn);
            }
            return fn.apply(primary.set());
        }
        if (m == EnsembleMode.READ_REPLICA) return replicaRead(fn);
        return fn.apply(primary.set());
    }

    /**
     * VERIFIED read (ADR-003 E4): poll every ACTIVE member, serve the strict-majority answer, and
     * quarantine any dissenter -- failing over first if the dissenter is the serving primary, so a
     * wrong primary can never decide the result. With no clear majority (a tie, or no answer holding
     * more than half the votes) the read falls back to the primary and quarantines no one, since the
     * fault cannot be adjudicated. Runs under the write lock because a dissent mutates membership.
     */
    /**
     * VERIFIED read (E4 + ADR-007). Writes are serialized, so at most one is ever in flight:
     * a lock-free pass that comes back <em>unanimous</em> is a consistent cut — every member
     * answered either before or after that one write, and unanimity means the answer is the
     * same under both placements — and is served with no lock at all. Any disagreement,
     * genuine divergence or mere read skew across a write commit, proves nothing and
     * escalates to {@link #voteLocked}, where no write can be concurrent, skew is therefore
     * impossible, and dissent is genuine. All quarantine/failover decisions live only there.
     */
    private <R> R vote(Function<RankedSet<K>, R> fn) {
        if (OPTIMISTIC_VOTES) {
            R first = null;
            int voters = 0;
            boolean unanimous = true;
            for (EnsembleMember<K> m : members) {
                if (!m.isActive() || !m.isExact()) continue;   // volatile reads; a stale view only causes escalation
                R a = fn.apply(m.set());
                if (voters++ == 0) first = a;
                else if (!Objects.equals(first, a)) { unanimous = false; break; }
            }
            if (unanimous && voters > 0) return first;   // the common, healthy case — lock-free
        }
        return voteLocked(fn);
    }

    private <R> R voteLocked(Function<RankedSet<K>, R> fn) {
        synchronized (writeLock) {
            List<EnsembleMember<K>> voters = new ArrayList<>();
            List<R> answers = new ArrayList<>();
            for (EnsembleMember<K> m : members) {
                if (!m.isActive() || !m.isExact()) continue;   // a sampled shadow can never vote (E5)
                voters.add(m);
                answers.add(fn.apply(m.set()));
            }
            if (voters.isEmpty()) return fn.apply(primary.set());

            // Tally distinct answers (equals-based; answers may be null, e.g. minimum() on empty).
            List<R> distinct = new ArrayList<>();
            List<Integer> counts = new ArrayList<>();
            for (R a : answers) {
                int idx = -1;
                for (int j = 0; j < distinct.size(); j++) {
                    if (Objects.equals(distinct.get(j), a)) { idx = j; break; }
                }
                if (idx < 0) { distinct.add(a); counts.add(1); }
                else counts.set(idx, counts.get(idx) + 1);
            }
            int topCount = -1, topIdx = -1;
            boolean unique = true;
            for (int j = 0; j < counts.size(); j++) {
                int c = counts.get(j);
                if (c > topCount) { topCount = c; topIdx = j; unique = true; }
                else if (c == topCount) { unique = false; }
            }
            boolean decisive = unique && topCount * 2 > voters.size();
            if (!decisive) {
                return fn.apply(primary.set());   // no majority -> cannot adjudicate; serve the primary
            }
            R winner = distinct.get(topIdx);

            // Identify dissenters; fail over first if the primary itself dissents.
            List<EnsembleMember<K>> dissenters = new ArrayList<>();
            boolean primaryDissents = false;
            for (int i = 0; i < voters.size(); i++) {
                if (!Objects.equals(answers.get(i), winner)) {
                    dissenters.add(voters.get(i));
                    if (voters.get(i) == primary) primaryDissents = true;
                }
            }
            if (dissenters.isEmpty()) return winner;   // unanimous -- the common, healthy case

            if (primaryDissents) {
                for (int i = 0; i < voters.size(); i++) {
                    if (Objects.equals(answers.get(i), winner) && voters.get(i) != primary) {
                        EnsembleMember<K> deposed = primary;
                        this.primary = voters.get(i);   // failover: volatile publish under the lock
                        if (events != null) {
                            emit(new TreeEvent.Promote<>(deposed.strategyName(),
                                    voters.get(i).strategyName(), true));
                        }
                        break;
                    }
                }
            }
            StringBuilder q = new StringBuilder("[");
            for (EnsembleMember<K> d : dissenters) {
                if (d == primary) continue;             // never quarantine the (new) serving primary
                if (d.state() != EnsembleMember.State.RETIRED) {
                    d.setState(EnsembleMember.State.QUARANTINED);
                    if (events != null) emit(new TreeEvent.Quarantine<>(d.strategyName()));
                }
                if (q.length() > 1) q.append(", ");
                q.append(d.strategyName());
            }
            q.append(']');
            logger.warn("event=verified_dissent winnerVotes={} of {} quarantined={} failedOver={}",
                    topCount, voters.size(), q, primaryDissents);
            return winner;
        }
    }
}
