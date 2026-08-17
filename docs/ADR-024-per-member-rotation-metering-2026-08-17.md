# ADR-024: Per-member rotation metering — 2026-08-17

## Status

Accepted, implemented. Trigger: ADR-011's held refinement, carried forward by sixth-pass fix
**S6-12** ("the meter is the **primary's** delta … per-member rotation meters remain the ADR's
held refinement").

## Context

`Fitness`'s write term is `writeCost = writeFraction × rotationsPerWrite`. Until S6-12 the
rotation feed was a literal `0` from every production facade, so the term was structurally
zero. S6-12 fixed the feed by metering the **serving primary's** engine counter across each
logical write, on the stated grounds that "the realized write term is the stream's, not
per-member" — defensible, because a `SAMPLED_SHADOW` sees only a thinned stream and its
rotation *count* is therefore not comparable with a full-stream member's.

The cost of that choice is that **every member is priced on the primary's churn**. The
controllers score a candidate against the incumbent using one `WorkloadFeatures` snapshot, so
both sides carry the same `rotationsPerWrite` and their write terms are *identical by
construction*. In an ensemble whose members deliberately run different policies — the entire
reason the ensemble exists — a rotation-thrashing member and a rotation-cheap one were
indistinguishable in the term that exists to price rotation churn. Measured here: over a
4 000-op write-heavy stream, a Splay member and a Red-Black member seeing the *identical*
write sequence differ by more than 3× in realized rotations per write, and the fitness write
term saw none of it.

The write term did not vanish from the comparison — a common additive constant still moves
`MorphPolicy`'s improvement *fraction*, which is what S6-12's damping test pins — but it could
only ever damp both candidates equally. It could not say which candidate was doing the
thrashing.

## Decision

**Meter each member's own rotations, over the writes that member actually received, and price
each member on its own rate — under an explicit comparability rule.**

1. **Own churn, own denominator.** `EnsembleMember` carries a rotation meter
   (`meteredRotations`, `meteredWrites`, `rotationsPerWrite()`), driven from
   `EnsembleOrderedSet`'s fan-out — the only code that knows *which* members a write reached.
   The denominator is the writes the member received, never the stream's write count.

   This is what makes the shadow case honest. Rotations-per-write is an **intensive** quantity:
   a property of the policy, not of the stream's length. A shadow that took 20 of 200 writes
   and paid 10 rotations is 0.5 rotations/write — the same unit and the same number as a
   primary that paid 100 over all 200. Dividing the shadow's rotations by the *stream's* 200
   would have made it look ten times cheaper than it is, which is the pricing error this ADR
   exists to avoid, in a new form.

2. **A rate needs samples: `MIN_METERED_WRITES = 8`.** Below eight received writes,
   `rotationsPerWrite()` is `NaN` — *no observation*, not a cheap one. The ratio's relative
   standard error falls as `1/√w`; at `w = 2` a single Red-Black delete fixup (up to three
   rotations) can double it, at `w = 8` it moves it by less than the default improvement
   margin. This is sixth-pass finding 8's discipline (`Fitness.informative`) applied to the
   write term instead of the read term. An ENGINE-tier member has no rotation counter at all
   and is likewise `NaN`.

3. **Both sides per-member, or neither.** A cost built from a member's own churn and a cost
   built from the stream's are two different measurements, and `MorphPolicy` reads their
   *ratio*. So V3 prices arm and incumbent per-member only when **both** have an own-churn
   observation, and V4 — which ranks every nursery body against every other body *and* against
   the throne in one pool — makes the choice all-or-nothing per generation. Short of evidence,
   everyone falls back to the stream's number, i.e. exactly S6-12's behavior. **The refinement
   can never make the signal worse than the number it replaces.**

The meter is **window-scoped**: `beginTrial` / `beginGeneration` reset it (after the morph, so
a body is never charged for the previous genome's churn), and `EnsembleController` resets after
each `evaluateAndMaybePromote`. That inherits the caller-cadenced measurement window every
controller here already has, instead of inventing a second decay constant next to
`RollingWorkloadMonitor`'s.

A `clear()` is not metered: it is a wholesale reset, not a keyed mutation, and folding it in as
a zero-rotation write would dilute every member's rate.

## Consequences

- The fitness write term now distinguishes policies. `EnsembleMember.pricedFeatures` substitutes
  the member's own rate into the stream vector, so `Fitness`'s arithmetic is **untouched** —
  `FitnessTest`'s pins hold, and `Fitness` stays a pure function of scalars.
- `EnsembleController`'s `event=morph_eval` meters line gains `rot/w=… over Nw` per member, so
  the thrasher is visible from one log line.
- **`CostModelStrategyScorer` is deliberately not re-priced.** It is a pure function of one
  `WorkloadFeatures` vector by construction (ADR-002 step 6) — that purity is what makes it
  unit-testable with hand-built vectors — and it ranks `StrategyId`s, not members, so it has no
  per-member term to receive. `EnsembleController` maintains and reports the meters; consuming
  them in the scorer would be an ADR-002 change and is out of scope.
- **`GenomeDrivenTreeController` is untouched.** Its literal-0 rotation feed stays pinned by
  `ControllerConvergenceTest` G5 (plan decision 12.2.2); it does not run on an ensemble and has
  no member to meter.
- Cost on the write path: two counter reads and an accumulate per recipient per write, only for
  `add`/`remove`, inside the loops the fan-out already runs. No allocation.
- **Not a breaking change.** Everything added is new public surface (`rotationsPerWrite()`,
  `meteredWrites()`, `meteredRotations()`, `pricedFeatures()`, `MIN_METERED_WRITES`,
  `EnsembleOrderedSet.resetRotationMeters()`); no signature, no record component, no existing
  behavior of a published method changed. `PolicySearchController.TrialResult` deliberately did
  **not** gain a component — adding one to a published record is a source break, and the churn
  evidence goes on the log line instead.

*Tests:* `PerMemberRotationMeterTest` (9), one per clause plus the window and the log line, each
verified red by reverting the corresponding fix in isolation.

## Held, honestly

- **Sampling still biases the shadow's key distribution.** Rate normalization makes the *unit*
  comparable; it does not make a thinned stream the same stream. A shadow taking every 50th
  write sees a sparser key set, so more of its deletes miss and its inserts are more spread —
  its rate is a rate for *its* traffic. This is a real residual, bounded by clause 2's sample
  floor and by the fact that a promoted shadow is rebuilt from the primary (sync-on-promote)
  before it serves. Probe-reads (ADR-011 §4 "Revisit") would close it properly.
- **Per-member `meanSearchDepth` is still structural.** Only the write term is per-member now;
  the read term remains `Fitness.meanDepth`'s structural estimate, unchanged, because shadows
  still do not serve reads.
- **The window is a hard reset, not a decay.** A window in which a member happens to receive
  fewer than eight writes falls back to the stream's number rather than carrying the previous
  window's rate forward. That is the conservative direction and it is pinned.

---

## Amendment, same day — clause 3 holds over the pool, not only within a window

The seventh-pass audit (item C) read clause 3 back against the code and found the rule enforced
where it was written and not where it is *used*. **Reproduced end to end**, so this is an amendment
rather than a note.

**What was wrong.** "Both sides per-member or neither" was decided per evaluation window, but
neither controller's decision reads only one window.

- **V3.** `PolicySearchController` gates on `policy.shouldMorph(-incumbentCost, -bandit.meanCost(winner), …)`.
  `meanCost` is a running mean over **every window that arm has run**, while `incumbentCost` is
  priced from the current one. A `SAMPLED_SHADOW` at `shadowSampleRate(0.1)` takes 1 write in 10,
  so a 70-op window leaves it at 7 received writes — below `MIN_METERED_WRITES` — and is
  stream-priced, while the next 3 000-op window clears the floor and was priced per-member. The
  mean then averaged the two and was compared against a single-basis incumbent.
- **V4.** `PolicyEvolutionController` ranks this generation's bodies against surviving parents
  still carrying the cost they were scored at, generations ago and possibly under the other
  regime; the (μ+λ) pool is `new LinkedHashMap<>(scored)` plus `pool.putIfAbsent(p.genome(), p.cost())`.

**Measured.** Splay incumbent, Red-Black laboratory at sample rate 0.1, `Random(11)`, one 70-op
window then one 3 000-op window:

```
window 1  lab received 7 writes   -> STREAM priced      armCost 1.3724
window 2  lab received 300 writes -> PER-MEMBER priced  armCost 0.6897   incumbent 10.4777
bandit mean fed to shouldMorph = 1.0311   (the mean of one stream price and one per-member price)

improvement fraction, mixed mean          0.9016   -> HOLD
improvement fraction, window 2's own price 0.9342  -> PROMOTE
```

At `MorphPolicy(0, 0.9179, 1)` — a margin inside that band — the live run holds and the throne
stays Splay. A genuinely cheaper policy was kept off the throne because the gate's numerator was a
blend of two different measurements. The promotion decision was being taken on incomparable numbers,
which is precisely what clause 3 exists to prevent.

**The amendment.** *Every recorded cost carries both prices, and a comparison is taken on the basis
every participant in it has.*

- `PolicyBandit` keeps two means per arm: `meanStreamCost` (always defined) and `meanOwnChurnCost`
  (defined only while **every** pull of that arm carried an own-churn price). `perMemberBasis()` is
  true only when every live scored arm has the second, and `meanCost`, `select()`, `bestArm()` and
  `statsLine()` all read the basis it names — so the whole scoreboard sits on one basis at a time.
  `recordCost(arm, cost)` keeps its published meaning and now says, honestly, "no own-churn price".
- `PolicySearchController` evaluates each window on both bases, records both, and prices the
  incumbent — and reports `TrialResult.armCost` — on the bandit's basis rather than the window's.
- `PolicyEvolutionController`'s `Scored` carries both costs; the pool's basis is per-member only
  when this generation qualifies **and** every carried-over parent has an own-churn price, and the
  throne is priced on that same basis.

Short of that evidence everything falls back to the stream's number, which is exactly S6-12's
behaviour — so clause 3's closing sentence still holds unchanged: **the refinement can never make
the signal worse than the number it replaces.** The `event=trial_eval` churn field now prints the
basis the decision used *and* the basis this window alone would have supported, so the two can be
told apart from one log line.

*Tests:* `SeventhPassClosureTest$PoolWideComparability` (6), each verified red by reverting the
corresponding fix in isolation.

## Held, honestly — added by the amendment

- **The basis is the run's, not the window's.** One live scored arm that has ever been through an
  unmeterable window puts the whole V3 scoreboard on the stream basis for the rest of the run,
  because the mean it would otherwise be ranked on has no single meaning. That is the conservative
  direction and it is pinned, but it does mean a long run with one early short window never uses
  the refinement. Re-basing would require the bandit to keep per-window costs rather than running
  means, which is a bigger change than the defect justifies; revisit if a real run is measured
  losing signal to it.
- **A carried-over parent is never re-priced.** V4 could in principle re-score a surviving parent
  on the current generation's basis, but only bodies materialized *this* generation have an engine
  to measure; a parent without a body has no own churn to read. Carrying both prices is what makes
  the pool rankable without inventing one.
