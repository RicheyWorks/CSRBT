# CHANGELOG 2026-06-09 -- ADR-003 E5 (final): SAMPLED_SHADOW mode

Third and final slice of E5 (`ADR-003-multi-tree-ensemble-2026-06-06.md`): the memory-lean mode
(the ADR's Option B). The primary receives every write and remains the one exact copy; the other
members become *shadows* that receive only a sampled fraction p of writes -- ~1 + p(K-1) memory
and write cost instead of Kx. A shadow is a statistical sketch: it estimates a strategy's cost on
the live workload but can never serve, fail over, or vote. **E5 is now complete** (benchmark +
parallel fan-out + SAMPLED_SHADOW).

## What changed

- **`EnsembleMode.SAMPLED_SHADOW` (new).** Selectable at build (`.mode(...)`) or runtime
  (`setMode`). Sampling is a deterministic stride, not a coin flip: shadows receive every
  ceil(1/p)-th logical write (`.shadowSampleRate(p)`, default 0.1), so memory/write cost and tests
  are exact, not statistical. `clear()` is never sampled -- a skipped clear would leave a shadow
  holding keys the logical set dropped wholesale.
- **`EnsembleMember.isExact()` (new).** True while a member is a faithful mirror. A member drops
  to inexact on the first write the stride skips; only an O(n) rebuild from the primary restores
  it (E3 `healFromPrimary`, or the sync-on-promote below). Exactness now gates everything a
  sketch must not do: VERIFIED voting (`vote` skips inexact members; `setMode(VERIFIED)` requires
  three exact ACTIVE members), write-failure failover (an inexact member can never stand in for a
  failed primary -- with no exact survivor the write fails loudly), and the E3 controller's
  failover candidate selection.
- **Sync-on-promote.** `promote` on an inexact member performs the ADR's catch-up first: an O(n)
  rebuild from the current primary (one `event=shadow_catchup` line), then the O(1) swap. In
  MIRROR operation every member is exact and `promote` stays a pure pointer swap -- the E5
  benchmark's O(1) claim is untouched. After the swap the deposed primary starts to drift and is
  lazily marked inexact on its first skipped write (so a runtime switch back to MIRROR before any
  skip keeps it exact).
- **E3 health check understands shadows.** A shadow diverges from the primary *by design*, so
  `EnsembleController.checkHealth` validates inexact members against their own contents
  (structural invariants only) instead of the primary's; divergence is no longer a fault for
  them, and a healthy shadow is left untouched.

## Tests

- `EnsembleShadowTest`:
  - *shadowsHoldSampledFraction* -- 1000 writes at p=0.1: primary holds 1000, each shadow exactly
    100 (the stride keys), marked inexact.
  - *readsServedByPrimaryOnly* -- membership, size, and order statistics all come from the
    primary; keys absent from every shadow still answer correctly.
  - *syncOnPromoteCatchesShadowUp* -- a 10% sketch is rebuilt to the full set before serving; the
    deposed primary drifts to shadow on its first skipped write.
  - *shadowsCannotVote* -- `setMode(VERIFIED)` rejected until shadows are healed back to exact
    mirrors; then a quorum forms.
  - *primaryFailureWithOnlyShadowsFailsTheWrite* -- fault tolerance "none", enforced: no exact
    survivor means the write raises instead of failing over to a sketch.
  - *healthCheckLeavesShadowsAlone* -- E3 cadence check quarantines nothing; sketches stay ACTIVE,
    inexact, and untouched.

## E5 closed

All three E5 deliverables have landed today: the adaptation benchmark
(CHANGELOG-2026-06-09-ensemble-e5-benchmark.md), the parallel write fan-out
(CHANGELOG-2026-06-09-ensemble-e5-fanout.md), and SAMPLED_SHADOW (this entry). Next: E6 --
persistence + docs, then flip ADR-003 to **Accepted**.
