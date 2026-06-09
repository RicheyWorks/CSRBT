# CHANGELOG 2026-06-09 -- ADR-003 E5 (partial): parallel write fan-out

Second slice of E5 (`ADR-003-multi-tree-ensemble-2026-06-06.md`): the `MemberExecutor` seam the ADR
names, with a parallel implementation. One logical write is now applied to all K members
concurrently -- members share no mutable state, so the fan-out is embarrassingly parallel -- while
the whole fan-out still runs under the single writer lock. Parallelism is *within* a write, never
*between* writes: the logical set stays linearizable. SAMPLED_SHADOW remains open.

## What changed

- **`MemberExecutor` (new interface).** The fan-out seam: apply one write op to every member,
  report a per-member `Outcome` (effective-change flag or captured throwable, never propagated).
  `SequentialMemberExecutor` preserves E1's in-thread loop bit-for-bit and stays the default;
  `ParallelMemberExecutor` runs member 0 on the writer's thread and the rest on a fixed daemon
  pool, with `Future.get` providing the happens-before edge back to the caller. The writer lock's
  acquire/release orders one write's mutations before the next, so a member mutated by pool thread
  A this write is safely mutated by pool thread B the next -- no member-level locking added.
- **`EnsembleOrderedSet` writes go through the seam.** `add`/`remove`/`clear` collapse into one
  `fanOutWrite` path. Builder gains `parallelFanOut()` (pool sized min(K-1, cores)) and
  `executor(MemberExecutor)` for injection; the facade is now `AutoCloseable` (`close()` releases
  the pool -- optional, the threads are daemons).
- **ADR-003's write-failure rule, now enforced.** Previously a throwing member aborted the whole
  fan-out mid-loop (members written before it kept the write, those after never saw it). Now a
  member that throws is `QUARANTINED` while the write commits to the rest; if the *primary* threw,
  a surviving member is promoted first (failover precedes quarantine, mirroring VERIFIED reads),
  and the new primary's effective-change result is returned. Only if *every* active member fails
  does the write raise (`IllegalStateException`) -- the write did not commit. One
  `event=write_member_failure` WARN line per incident. A quarantined (possibly half-mutated)
  member heals through the existing E3 `healFromPrimary` rebuild.

## Tests

- `EnsembleFanOutTest`:
  - *parallelMatchesOracleAndSequential* -- the parallel path is behavior-transparent: op-for-op
    effective-change parity with a `TreeSet` oracle and with the sequential fan-out; every member
    an exact mirror.
  - *throwingMemberIsQuarantinedWriteCommits* -- injected write fault: thrower quarantined, write
    committed to survivors, no fan-out to a quarantined member, E3 heal restores the mirror.
  - *throwingPrimaryFailsOverThenQuarantines* -- a primary that throws mid-write: failover to a
    survivor first, deposed primary quarantined, write visible through the new primary.
  - *concurrentWritersStayLinearizable* -- 4 writer threads through the facade; final state is the
    exact oracle set in every member.

## Still open in E5

- **SAMPLED_SHADOW mode:** ~~memory-lean shadows that receive a sampled fraction of writes~~
  _(landed later the same day -- see CHANGELOG-2026-06-09-ensemble-e5-shadow.md. E5 is complete.)_
