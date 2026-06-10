# ADR-006: Sampled verification — tuning VERIFIED's read amplification

**Status:** Accepted (2026-06-09 — V1 landed, see CHANGELOG-2026-06-09-adr006-verified-sampling.md)
**Date:** 2026-06-09
**Deciders:** Richmond
**Builds on:** ADR-003 E4 (VERIFIED N-version read voting: majority serve + dissenter
quarantine), ADR-004 R1 (torn-read-free single-member reads), and ADR-003's explicit
"Revisit: whether VERIFIED's read amplification is acceptable for the target deployment."
**Goal:** make VERIFIED's cost a dial instead of a constant — keep the e2e guarantee
(divergent members are detected, quarantined, and never serve a winning answer they dissent
from) while letting read-heavy deployments pay K× verification on a sampled stride rather
than on every read.

---

## 1. Context

E4's VERIFIED mode executes every read on **every** active exact member and serves the
majority answer; dissenters are quarantined (the primary, if it dissents, is deposed first).
Two separate costs ride on that:

- **Amplification:** one logical read = K member reads, always. For k=3 that triples every
  `contains`/`select`/`rank` — the dominant operation in the read-heavy deployments VERIFIED
  is aimed at.
- **Serialization:** `vote()` runs under the writeLock (it can quarantine and fail over, both
  of which mutate member lifecycle), so verified reads also contend with writes — and with
  each other. That axis is deliberately **out of scope** here; it is the same single-lock
  ceiling ADR-003 names for writes, and ADR-007 owns it.

What changed since E4 makes per-read voting worth questioning. **Post-R1, the fault class
VERIFIED exists to catch is persistent, not transient.** R1 made single-member reads
torn-read-free: a healthy tree cannot return a wrong answer because of a concurrent write.
What remains is *divergent content* — a member that silently dropped a write (the
`SilentDropStrategy` fault in `EnsembleVerifiedTest`), holds a key its siblings lack, or
drifted through any out-of-band mutation. Divergence of that kind does not flicker: the
member stays wrong until the E3 health pass or a vote catches it. Against a persistent
fault, voting on every read buys detection latency measured in *reads*, while voting on a
stride of N buys the same detection within at most N verified-eligible reads — at 1/N of the
amplification.

The honest loss: between sampled votes, reads are served by the primary alone. If it is the
*primary* that diverged, up to N−1 reads can serve unverified (possibly wrong) answers before
the next vote catches and deposes it. That window is the tuning surface — N=1 is exactly E4's
per-read guarantee, and remains the default.

---

## 2. Options considered

### Option A: Deterministic stride sampling (`verifyEvery(N)`)

Count VERIFIED-mode reads; every Nth runs the full E4 vote, the rest serve from the primary
(1×, no lock). Default N=1 — existing behavior, existing tests, existing guarantee.

| Dimension | Assessment |
|---|---|
| Complexity | Low — one counter, one branch, one builder knob |
| Amplification | amortized 1 + (K−1)/N |
| Detection latency | ≤ N verified-eligible reads for any persistent divergence |
| Guarantee at N=1 | bit-identical to E4 (default) |
| Failure window | primary divergence can serve ≤ N−1 unverified reads |

**Pros:** deterministic (testable without flakiness, like E5's write stride); zero new
machinery — the vote itself, quarantine, and failover are untouched; the knob composes with
every mode feature (memory ceiling, engine members, parallel fan-out).
**Cons:** unverified reads between strides are exactly as trustworthy as MIRROR reads; a
read-rate-dependent detection latency (an idle ensemble detects nothing until read).

### Option B: Pair audit (primary + one rotating witness)

Every read executes on the primary and one round-robin witness; mismatch escalates to a full
vote for adjudication.

| Dimension | Assessment |
|---|---|
| Complexity | Medium — a second dispatch path + escalation |
| Amplification | fixed 2×, regardless of K |
| Detection latency | ≤ K−1 reads (witness rotation must reach the divergent member) |
| Failure window | none for witnessed reads, but adjudication is still the full vote |

**Pros:** every read is cross-checked; amplification independent of K.
**Cons:** 2× is the *floor*, not the dial — read-heavy deployments wanted less, not a
different constant; a primary+witness agreement is not a majority (two colluding-divergent
members serve wrong answers with no third opinion until escalation); doubles the locked
section per read rather than skipping it N−1 times in N.

### Option C: Asynchronous audit (serve 1×, verify in background)

Serve every read from the primary immediately; replay a sample of reads against the other
members on a background thread.

**Pros:** 1× read latency always.
**Cons:** abandons VERIFIED's core promise — the served answer is never the voted answer;
introduces the project's first background thread with lifecycle, ordering, and shutdown
semantics (everything so far is caller-threaded by design); detection without protection is
what the E3 health pass already provides on a cadence, making this redundant with cheaper
existing machinery.

---

## 3. Trade-off analysis

The deciding observation: **post-R1, per-read voting and sampled voting catch the same fault
class — persistent divergence — differing only in the unverified window.** Option A makes
that window an explicit, documented dial (N) whose endpoints are both honest: N=1 is E4
verbatim, large N approaches MIRROR cost with a periodic content audit. Option B replaces the
dial with a different fixed cost and a weaker quorum. Option C buys latency by giving up the
guarantee entirely.

A is also the only option that is *deletable*: at default N=1 the new code path is dead and
the diff is a counter. That matches the project's bias for additive, opt-in slices
(ADR-003 §11).

---

## 4. Decision

**Adopt Option A.** `Builder.verifyEvery(int n)` (default 1): in VERIFIED mode, every nth
read runs the E4 vote — majority serve, dissenter quarantine, primary failover — and the
other n−1 serve from the primary without taking the lock, exactly like MIRROR reads. The
read counter is an `AtomicLong` outside the lock, so unverified reads stay lock-free; the
stride is deterministic for the same interleaving (testable, like E5's write stride).
`toString()` reports the dial. The vote itself is unchanged.

---

## 5. Consequences

**Easier:** read-heavy VERIFIED deployments tune amplification continuously between 1× and
K×; unverified reads also skip the writeLock, which reduces read-write contention as a side
effect (the full fix remains ADR-007); the default preserves every existing test and caller.

**Harder:** the VERIFIED guarantee is now conditional on configuration — docs and the meters
line must say "verifies every Nth read" loudly, because a quietly-large N looks like E4 but
is not; reasoning about worst-case staleness now involves the read rate.

**Revisit:** auto-escalation (drop N to 1 for a window after any dissent) if real deployments
show divergence arriving in bursts; combining the stride with ADR-007's lock work so even
sampled votes stop contending with writes.

---

## 6. Action items

1. [x] **V1** — `verifyEvery` dial: builder knob + validation, `AtomicLong` read stride,
   primary-serve fast path, dial in `toString()`; `EnsembleVerifiedSamplingTest` (stride
   semantics, default-1 equivalence, detection-within-N, validation); benchmark row:
   per-read vote vs sampled vs MIRROR read throughput. _(Done 2026-06-09.)_
2. [ ] **V2** — (held) burst auto-escalation after dissent, if demanded by real traffic.

---

## 7. Verification & rollback

V1 is additive and opt-in: at the default N=1 the ensemble behaves (and benchmarks) exactly
as before, and the existing `EnsembleVerifiedTest` is the regression floor. Rollback is
reverting the slice. Ships green through host `ant clean test` per `CLAUDE.md`.
