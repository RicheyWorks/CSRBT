package io.github.richeyworks.csrbt.ensemble;

/**
 * Read mode for an {@link EnsembleOrderedSet} (ADR-003).
 *
 * <ul>
 *   <li>{@link #MIRROR} (default) -- reads are served by the primary alone (1x read cost). Members
 *       are kept in exact sync; promotion (E2) and the cadence health check (E3) provide adaptation
 *       and fault recovery.</li>
 *   <li>{@link #VERIFIED} -- every read is fanned out to a quorum of ACTIVE members, the
 *       strict-majority answer is served, and a dissenting member is quarantined (E4). This is
 *       N-version programming applied to the data structure: it catches a strategy bug or memory
 *       corruption that is internally self-consistent and so escapes the per-member health check
 *       (including a wrong primary). It costs a quorum-many reads and needs at least three members
 *       to adjudicate.</li>
 *   <li>{@link #READ_REPLICA} -- the lock-free read mode (ADR-004 R2): MIRROR semantics with a
 *       left-right write discipline. Readers enter an epoch on the serving member (one atomic
 *       increment, an identity re-check, one decrement -- no lock, no retry loop beyond a raced
 *       flip) and read a tree <em>no writer touches during that epoch</em>. The writer applies
 *       each op to the non-serving mirrors first, flips the serving pointer to one of them,
 *       drains the old side's epoch readers, and only then applies the op to the old side.
 *       Costs the writer a second sequential apply plus the drain wait; requires at least two
 *       exact ACTIVE members, and fails writes loudly when it degrades below that (a sampled
 *       shadow can never serve, so it can never take the flip).</li>
 *   <li>{@link #SAMPLED_SHADOW} -- the memory-lean mode (E5, ADR-003 Option B): the primary
 *       receives every write and remains the one exact copy; the other members are <em>shadows</em>
 *       that receive only a sampled fraction of writes (~1 + p&middot;(K-1) memory and write cost
 *       instead of K&times;). A shadow is a statistical sketch -- it estimates a strategy's cost on
 *       the live workload but can never serve, fail over, or vote. Promoting a shadow therefore
 *       costs an O(n) catch-up sync from the primary first (the ADR's "sync-on-promote"), after
 *       which the deposed primary becomes a shadow and starts to drift in its turn.</li>
 *   <li>{@link #REBUILD_SHADOW} -- the write-lean mode (ADR-003 Option C): the primary receives
 *       every write; shadows receive <em>none</em> and are instead rebuilt wholesale from a
 *       primary snapshot every {@code rebuildEvery} writes (1&times; steady-state write cost plus
 *       an amortized O(n) rebuild). A freshly rebuilt shadow is exact and <em>warm</em> -- an O(1)
 *       promotion target -- until the next write marks it stale again; between rebuilds it can no
 *       more serve, fail over, or vote than a sampled shadow can, and its promotion signal (the
 *       realized height and build cost each rebuild leaves behind) lags the workload by up to one
 *       cadence. The honest trade per the ADR's cost table: cheap steady-state writes, weak
 *       continuous redundancy.</li>
 * </ul>
 */
public enum EnsembleMode {
    MIRROR,
    VERIFIED,
    READ_REPLICA,
    SAMPLED_SHADOW,
    REBUILD_SHADOW
}
