# CHANGELOG 2026-06-09 — ADR-007 W1: optimistic unanimous votes (the writer-lock ceiling, decomposed)

Closes ADR-003's "Revisit: the single external-writer lock as a throughput ceiling." The ADR
(`ADR-007-optimistic-votes-2026-06-09.md`, Accepted) decomposes the ceiling honestly: the
write/write half is **structural** (members are single-writer trees; the lock is not what
limits write throughput, the slowest member is) and stays; the read/write half — VERIFIED
votes serializing against writes — is real and is what this slice removes.

## The fast path (`EnsembleOrderedSet.vote`)

- **The argument:** writes are serialized, so at most one is ever in flight. A lock-free pass
  over the voters sees each member before or after that one write; if all answers are
  *equal*, the answer is identical under either placement — unanimity is a consistent cut by
  construction. No seqlock, no version stamps (Option B rejected as machinery for nothing).
- **The code:** `vote()` makes one lock-free pass over active+exact members and serves on
  unanimity; *any* disagreement — genuine divergence or read skew across a commit — escalates
  to `voteLocked()`, the unmodified E4 vote, where no write can be concurrent, skew is
  impossible, and dissent is genuine. Quarantine and failover therefore still happen only
  under the lock, race-free.
- **Kill switch:** `EnsembleOrderedSet.OPTIMISTIC_VOTES` (static, default true, mirroring
  `OrderedSet.OPTIMISTIC_READS`) — rollback and benchmark baseline in one.
- **Composition:** with ADR-006, a healthy VERIFIED steady state is now lock-free end to end:
  n−1 reads serve the primary, the nth votes without a lock, and the writeLock appears only
  on writes, lifecycle ops, and dissent adjudication.

## Tests (`EnsembleVerifiedConcurrencyTest`, 3 tests; suite 451, green)

- **Safety under churn:** 4 verified-reader threads × 20k reads against a saturating writer;
  stable keys never lie, never-added keys never appear, and — the property the ADR exists
  for — **no member is ever quarantined by skew** (escalations adjudicate clean under the
  lock). Bounded threads/iterations, hard timeout, per house style.
- **Equivalence:** genuine divergence (out-of-band key drop) is detected, majority-served,
  and quarantined identically with the fast path on and off.
- **Benchmark row** (sandbox, k=3, 30k reads vs a saturating writer): optimistic **11.8 ms**
  vs locked **31.3 ms** — 2.7×; the locked path's cost is contention, which is why the gap
  appears only under write pressure.

## Held

- W2 — stride auto-escalation under dissent bursts (shared with ADR-006 V2).
- Inter-write parallelism (Option C) — rejected as structural; recorded in the ADR so the
  decision survives.
