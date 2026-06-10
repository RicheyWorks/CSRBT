# ADR-007: The writer-lock ceiling — optimistic unanimous votes, and what stays serialized

**Status:** Accepted (2026-06-09 — W1 landed, see CHANGELOG-2026-06-09-adr007-optimistic-votes.md)
**Date:** 2026-06-09
**Deciders:** Richmond
**Builds on:** ADR-003 (single external-writer lock; "Revisit: the single external-writer lock
as a throughput ceiling"), ADR-004 R1 (torn-read-free member reads), ADR-006 (sampled
verification — the amplification axis of VERIFIED's cost; this ADR is the lock axis).
**Goal:** remove the writeLock from VERIFIED's healthy read path, and document honestly which
parts of the ceiling are real and which are structural — i.e., not a lock problem at all.

---

## 1. Context

Every ensemble mutation runs under one `writeLock`: the K-member fan-out, lifecycle
transitions (promote / quarantine / heal / retire), Option C rebuilds — and, until this ADR,
every VERIFIED vote, because a vote can quarantine and fail over. ADR-003 flagged the lock as
a throughput ceiling and pointed at "lock-free multi-reader on the primary via the atomic swap
already in place."

Decomposing that ceiling:

- **Write/write serialization is structural, not incidental.** Members are single-writer
  structures (`RedBlackTree` + strategies; even the persistent engine's mutators are
  monitor-serialized). The lock is not what limits write throughput — the slowest member's
  single-threaded write rate is. Parallel fan-out (E5) already parallelizes *within* a write;
  parallelizing *between* writes would require concurrent tree implementations, a rewrite of
  the entire engine family for a workload that has not asked for it.
- **Read/write contention is already solved twice, except in VERIFIED.** MIRROR reads are
  R1-optimistic on the primary (no ensemble lock); READ_REPLICA reads are wait-free epoch
  reads. VERIFIED is the straggler: even after ADR-006, every *sampled* vote still serializes
  against writes — and against other votes.

So the honest target is narrow: take the lock out of the vote's common case.

**The observation that makes it safe:** writes are serialized, so at most one logical write is
ever in flight. A lock-free pass over the voters therefore sees each member either before or
after that one write. If all answers are **equal**, the answer is correct under either
placement — a unanimous lock-free vote is a consistent cut by construction, no version stamps
or seqlocks required. If *anything* disagrees — real divergence or mere read skew — the pass
proves nothing, and the locked vote adjudicates exactly as E4 always has (under the lock no
write is concurrent, so skew is impossible there and dissent is genuine).

---

## 2. Options considered

### Option A: Optimistic unanimous fast path, locked escalation

Lock-free pass over active+exact members; unanimity serves immediately; any disagreement (or
zero eligible voters) falls into the existing locked vote.

| Dimension | Assessment |
|---|---|
| Complexity | Low — one pass + the untouched E4 vote as fallback |
| Correctness | unanimity = consistent cut (single in-flight write); dissent always re-adjudicated under the lock |
| Healthy-path cost | K member reads, zero locks; composes with ADR-006 (a sampled vote is now also lock-free) |
| Degenerate cost | skew during a write = one wasted pass + a locked vote |

**Pros:** VERIFIED's steady state becomes entirely lock-free (R1 member reads + lock-free
unanimity); quarantine/failover semantics bit-identical (they only ever happen under the
lock); deletable via a kill switch.
**Cons:** under a saturating writer, escalation frequency rises (every vote that straddles a
write commit may dissent spuriously) — bounded by falling back to exactly today's behavior.

### Option B: Seqlock/version validation around the vote

Stamp mutations with entry/exit counters; lock-free readers retry while a write is in flight.

**Pros:** also detects in-flight writes for *non-unanimous* reasoning.
**Cons:** strictly more machinery for the same outcome — Option A already gets correctness
from unanimity alone; version plumbing must touch every mutating method (six synchronized
blocks, every early return) for no additional guarantee the vote needs.

### Option C: Concurrent write fan-out (inter-write parallelism)

Multiple writer threads, flat-combining or striped member ownership.

**Pros:** attacks write throughput itself.
**Cons:** members are single-writer structures — this is a rewrite of the engine family, not
a locking change; breaks the linearizable-logical-set contract that every mode's reasoning
(exactness, voting, epochs) is built on; no workload demands it. **Rejected as out of scope;
recorded so the ceiling's *structural* half stays documented.**

---

## 3. Decision

**Adopt Option A.** `vote()` becomes: one lock-free pass over the eligible voters; serve on
unanimity; otherwise run the existing locked vote verbatim. A static kill switch
(`EnsembleOrderedSet.OPTIMISTIC_VOTES`, default true, mirroring `OrderedSet.OPTIMISTIC_READS`)
restores pre-ADR behavior wholesale for rollback and for benchmarking the delta.

Explicitly **not** adopted: any change to write/write serialization (structural, per Option
C), and any change to lifecycle operations — promote/quarantine/heal/retire stay under the
lock, where their invariants live.

---

## 4. Consequences

**Easier:** VERIFIED deployments stop paying lock contention for healthy reads — combined
with ADR-006, a read-heavy VERIFIED workload is now lock-free except at the sampled-vote-
with-dissent corner; the locked vote shrinks to an escalation path, which is also the only
path that can quarantine — so all repair decisions still happen race-free under the lock.

**Harder:** two code paths where there was one (mitigated: the locked path is the unmodified
E4 code, and the kill switch collapses back to it); spurious escalations under write pressure
make vote cost workload-dependent rather than constant.

**Revisit:** if escalation frequency under real write-heavy traffic is material, add ADR-006
V2's burst logic (escalate the *stride*, not the lock); concurrent member structures only if
a workload ever demands inter-write parallelism (it would supersede Option C's rejection).

---

## 5. Action items

1. [x] **W1** — optimistic unanimous fast path + kill switch; `EnsembleVerifiedConcurrencyTest`
   (no false quarantines under churn — the safety property; correct answers for stable keys;
   bounded threads/duration per house style); benchmark row: verified reads under a
   concurrent writer, optimistic vs locked. _(Done 2026-06-09.)_
2. [ ] **W2** — (held) stride auto-escalation under dissent bursts (shared with ADR-006 V2).

---

## 6. Verification & rollback

W1 is guarded by a default-on static flag; `OPTIMISTIC_VOTES = false` is the rollback and the
benchmark baseline. The existing `EnsembleVerifiedTest` (detection, quarantine, failover
semantics) is the regression floor — every dissent it injects escalates to the unmodified
locked vote. Ships green through host `ant clean test` per `CLAUDE.md`.
