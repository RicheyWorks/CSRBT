# CHANGELOG 2026-06-09 -- ADR-004 R2: READ_REPLICA — lock-free epoch reads over ensemble mirrors

Second phase of ADR-004 (`ADR-004-lock-free-reads-2026-06-09.md`): the *lock-free* deliverable.
R1 made concurrent reads safe everywhere; R2 makes them free of contention where the ensemble's
2x memory is already being paid, via the left-right pattern realized over ADR-003's exact
mirrors. Only R3 (the balanced persistent engine) remains, held as the horizon.

## What changed

- **`EnsembleMode.READ_REPLICA` (new).** MIRROR semantics with a left-right write discipline:
  - *Readers* enter an epoch on the serving member (one atomic increment), **re-verify** the
    member is still serving, read, and exit (one decrement). The re-check closes the flip race:
    once the count is held and the member was observed as primary, a writer must flip away and
    drain -- and the drain waits on that very count -- before it may mutate. A reader that loses
    the race exits without dereferencing the tree and retries on the new side. No locks, no
    seqlock retries; combined with R1, the serving member's optimistic reads always validate
    (no writer ever shares it), so the epoch path runs at uncontended-read speed.
  - *The writer* (still one at a time, under the ensemble's write lock) applies each op to every
    ACTIVE **non-serving** member first (through the MemberExecutor, so the fan-out may be
    parallel), flips the serving pointer to an exact member whose write committed, **drains**
    the old side's epoch readers, then applies the op to the old side. Cost: a second
    sequential apply plus the drain wait, exactly as the ADR priced it.
  - *Failure rule:* failed non-serving members are quarantined as in MIRROR; a post-drain
    failure of the old serving member quarantines it too (the write already committed -- the
    member is no longer primary). If **no** exact member can take the flip, the write throws:
    READ_REPLICA degrades loudly, never by mutating the tree readers are on.
- **Epoch-aware lifecycle.** `promote` drains the deposed member after the swap in READ_REPLICA
  (readers may still be inside its epoch); `healFromPrimary` drains defensively before its
  rebuild. `setMode(READ_REPLICA)` requires two exact ACTIVE members (a sampled shadow can
  never take a flip). One `event=replica_drain_slow` WARN line if a drain spins abnormally;
  `event=replica_old_side_failure` on a post-drain apply failure.
- **`EnsembleMember.epochReaders`** -- the per-member reader count behind package-private
  `enterRead`/`exitRead`/`activeReaders`.

## Tests

- `EnsembleReplicaTest`:
  - *twoPhaseWritesStayExact* -- 3000 mixed ops vs a `TreeSet` oracle; every member remains an
    exact mirror under the two-phase discipline (the flip rotates which member serves).
  - *epochReadersSurviveChurn* -- 1 writer (with mid-stream promotions) vs 3 epoch readers;
    every snapshot strictly ascending and duplicate-free, no stray exceptions, no wedged
    drains; all members converge at quiescence.
  - *degradedReplicaFailsWritesLoudly* -- quarantine the only flip target: writes throw, reads
    keep serving, heal restores write service.
  - *modeRequiresTwoExactMembers* -- a drifted shadow blocks the mode; healing it unblocks.
  - *referenceThroughput* -- printed reads-per-250ms, MIRROR vs READ_REPLICA under identical
    churn; no timing assertion (CI stability), progress-only check.

## Still open in ADR-004

- **R3** -- (held) balanced persistent engine, when snapshot iteration or wait-free reads
  without an ensemble are demanded.
