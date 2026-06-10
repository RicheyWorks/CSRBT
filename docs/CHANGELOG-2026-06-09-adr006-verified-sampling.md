# CHANGELOG 2026-06-09 — ADR-006 V1: sampled verification (`verifyEvery`)

Closes ADR-003's "Revisit: whether VERIFIED's read amplification is acceptable" — by making it
a dial. See `ADR-006-verified-read-sampling-2026-06-09.md` (Accepted; options: stride sampling
vs pair-audit vs async audit; the deciding observation is that post-R1 the fault class is
*persistent* divergence, so per-read and sampled voting catch the same faults, differing only
in the unverified window).

## The dial (`EnsembleOrderedSet`)

- **`Builder.verifyEvery(int n)`** (default 1): in VERIFIED mode every nth read runs the full
  E4 vote — majority serve, dissenter quarantine, primary failover, all unchanged — and the
  other n−1 serve from the primary alone, lock-free, exactly like MIRROR reads.
- The stride counter is an `AtomicLong` outside the writeLock; at the default n=1 it is never
  touched (the fast path short-circuits), so existing VERIFIED behavior is bit-identical.
- `verifyEvery()` accessor; `toString()` shouts a non-default dial
  (`mode=VERIFIED, verifyEvery=16`) because a quietly-large n looks like E4 but is not.
- Amortized amplification: 1 + (K−1)/n. Detection: ≤ n verified-mode reads for persistent
  divergence. The honest window: a divergent *primary* can serve up to n−1 unverified answers
  before the next vote deposes it — documented on the knob, asserted in the tests.

## Tests (`EnsembleVerifiedSamplingTest`, 5 tests; suite 448, green)

- Stride determinism: a divergent member survives exactly n−1 reads, caught on the nth.
- The window, made visible: a divergent primary serves n−1 *wrong* answers, then the vote
  serves the majority answer, deposes, and quarantines it.
- Default n=1 is E4 verbatim (immediate detection); dial validation (`>= 1`) and loud toString.
- Benchmark row (sandbox, k=3, 10k keys, 60k reads): per-read vote **1089 ms** vs
  verifyEvery=16 **72 ms** — 15.2×. The win is amplification *and* the skipped lock; the lock
  axis proper is ADR-007.

## Held

- V2 (burst auto-escalation: drop n to 1 for a window after any dissent) — if real traffic
  shows divergence arriving in bursts.
