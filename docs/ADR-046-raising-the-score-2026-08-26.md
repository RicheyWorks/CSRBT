# ADR-046: FEK from 7% to 95%, and two more places the sweep was measuring nothing

**Status:** Accepted and implemented — `tools/verify/verify_fek.py` (66 → 101 checks), `tools/fek_harness.py` (three new fixtures), `tools/verify/verify_gh.py` (131 → 141), `tools/mutate.py` (emitter step in `--module`).
**Date:** 2026-08-26
**Deciders:** Richmond
**Supersedes:** nothing. **Follows:** ADR-045

---

## Context

ADR-045 built the sweep and it immediately found something bigger than itself: eleven suites that
could not fail the run. That got fixed. What it left behind was the actual number — **FEK scored 7%**,
and FEK is inlined in fifteen pages. One weak spot there is a weak spot everywhere.

## Three measurements, and what moved between them

| | FEK | why it changed |
|---|---|---|
| ADR-045, before the exit fix | **7%** | `verify_fek` printed FAIL and exited 0, so the sweep read every failure as a pass |
| after the exit fix, nothing else | **62%** | the suite could finally fail; most of it had been working all along |
| after this slice's coverage | **95%** | the survivors that were left were real |

The jump from 7 to 62 is worth staring at. **Nothing about the component changed and nothing about
the tests changed** — only whether a failing suite could say so. Fifty-five points of that first
number were an artefact of the reporting, which is a useful reminder that a bad measurement is not a
conservative one; it is just wrong, in whichever direction.

The jump from 62 to 95 is the real work.

## What was actually untested

**The field registry — completely.** `reg()` and `setField()` are FEK v1.3.0's whole point: a saved
value goes back *through* the widget's own `set()` rather than only into a hidden input, so a restored
session shows the right thing instead of stale dials over correct data. That is what KEEP's restore
path depends on. **The harness had no component declaring a `field` at all**, so nothing in 66 checks
ever touched it. It now has two, and the suite checks registration, that components *without* a field
stay out (the feature is additive), that `setField` redraws the widget rather than only moving the
value, that an unknown id reports failure rather than pretending, and that a restore does **not** fire
`onchange` — because a restore is not the user acting.

**`field()`'s clamping.** The control for a number you read off an instrument had no test that it
respects its own min and max, or that a non-number becomes null rather than zero.

**The dial's tap-to-clear**, `clearable:false`, the unit box, the nullable slider's "not recorded"
state, and `field()`'s blur formatting — each found by a mutation, each now driven.

## The fixture that could not tell, again

The default colour ramp is `min(5, round(i*5/(n-1)))`. I wrote four properties for it: starts at 0,
ends at 5, never exceeds 5, never goes backwards.

Mutating the divisor's guard produces `0,5,5,5,5` — which satisfies **all four**. The mutant survived.

That is the fourth time in a week. The fix is the one ADR-041 already named: stop asserting properties
and **recompute the sequence from the same formula**, then compare it whole. The check now also
asserts that the expected sequence has distinct values, so it fails loudly if someone ever picks a
fixture that could not discriminate.

## Two more places the sweep itself was measuring nothing

**`--module gh` scored four survivors that a hand test killed instantly.** `verify_fek` builds its
harness from `tools/fek.py` at run time, so mutating that file reaches the suite. `verify_gh` does
not — it opens `docs/greenhouse.html`, a **built** artefact with the engine already inlined. Mutating
`tools/gh.py` never reached it. The sweep now runs the module's emitter inside the scratch tree before
each suite run, and GH went from 60% to **100%**.

That is the second time this tool assumed a suite could see a mutation it structurally could not; the
first was running `verify_fek` against a page's inlined copy. Both share one shape: **a module's
source and the code a suite actually executes are two different things unless something regenerates
one from the other.** Where an emitter does that, the emitter has to run.

**`inBand()` was never called.** Three separate mutations of it survived `verify_gh`'s 131 checks,
because the page only uses it to pick a tile colour. A boundary function tested through a colour is
not tested. Six boundary cases now, including both inclusive edges and a zero that must read as
outside rather than as a falsy free pass.

## Two of my own checks were wrong, and the suite said so

Written and immediately failing against working code:

- `querySelector('.u')` for the unit box also matches the unit span inside the **label**. Scoped to
  `.fek-field .u`.
- The nullable-slider assertion read the harness's shared slider *after earlier checks had dragged
  it*. It now builds a fresh one. **Asserting on a shared mutable fixture after other tests have used
  it tests the test order, not the component.**

## Consequences

FEK **95%**, GH **100%**, at the sample sizes recorded above. One FEK survivor remains and is left
standing: it is a plausible equivalent mutant, and manufacturing a check to kill it would be scoring
the metric rather than testing the component.

**The rule this leaves behind:** a mutation score is a measurement, and like every other measurement
in this kit it needs its own instrument checked first. Twice now the sweep reported survivors that
were artefacts of the sweep. Both times the tell was the same — a result that disagreed with a
thirty-second hand check.
