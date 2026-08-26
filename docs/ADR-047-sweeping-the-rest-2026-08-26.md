# ADR-047: KEEP, ORD, and learning to tell a gap from an equivalent mutant

**Status:** Accepted and implemented — `tools/verify/verify_keep.py` (91 → 107), `tools/verify/verify_ord.py` (89 → 101), two operator fixes and an adaptive timeout in `tools/mutate.py`.
**Date:** 2026-08-26
**Deciders:** Richmond
**Follows:** ADR-045, ADR-046

---

## Context

ADR-046 took FEK from 7% to 95% and GH to 100%. Three modules had never been swept: **KEEP**, which
holds people's field data, **ORD**, which is the ordination mathematics, and DWC.

KEEP first, because a defect there loses work rather than displaying it wrongly.

## KEEP: 71%, and four real gaps

| survivor | what it guards |
|---|---|
| `e && e.name === "QuotaExceededError"` | telling a **full** store from a **refused** write — different problems, different actions |
| `esc(noun)` on the restored-from banner | escaping on the restore path |
| `esc(lastErr)` on the failure banner | escaping on the failure path |
| `typeof FEK !== "undefined" && FEK.setField` | not throwing on a page that has no FEK |

Three are covered now. The fourth is not, and that is the interesting one — see below.

**Two of the checks I wrote to close these were themselves wrong**, and writing them carefully is
most of the value:

- The quota check first **reimplemented the classifier in the test** and compared it against itself.
  A tautology no mutation of `keep.py` could ever fail. It now drives KEEP's own write path: wire the
  store, then replace `localStorage.setItem` with one that throws a named error, then read the banner.
- Order matters there, and getting it wrong is instructive. **KEEP probes storage at wire time**, so
  breaking `setItem` first makes the probe fail and the banner reads *"this browser is not keeping
  anything"* — correct behaviour, different message, and a check that would have passed for the wrong
  reason. The classifier only runs on a write that fails after a store that worked.
- The FEK-bridge check was `KEEP.formRestore ? KEEP.formRestore(...) : null` — a no-op that passes if
  the function is not exported. It now asserts the export first, then checks both halves: the input is
  restored when FEK is absent, and the value goes **through** `FEK.setField` when it is present.

The escaping probe also needed two setups, not one. `noun` is rendered by three different `esc()`
calls on three mutually exclusive branches, and the first probe only reached *"autosave is on"*.
Reaching *"restored from"* means seeding `localStorage` first, or `restore` is never called and the
branch never renders.

## ORD: 50%, four real gaps and two that are not gaps at all

Covered: the Jaccard presence counters (`a` = shared, `b` = in either — a fixture sharing **one of
three** species, because a pair sharing everything or nothing gives the same answer whichever counter
is broken); Jacobi's eigenvalues against trace and determinant; Procrustes agreement under rotation,
under rescaling, and on a degenerate all-zero configuration.

**And one of my own assertions was simply wrong.** I wrote that the determinant of
`[[4,1,0],[1,3,1],[0,1,2]]` was 16. It is 18. Jacobi had it right to fourteen digits and the test was
wrong — the ordinary way round, worth not pretending otherwise. Both trace and determinant are now
recomputed from the fixture rather than written in by hand, so editing the matrix cannot silently
invalidate them.

## The part worth keeping: two survivors left standing on purpose

`theta >= 0 ? 1 : -1` in the Jacobi rotation, and `if(!(s>0)) return Y` in `normScale`.

Both survived. Neither is a gap:

- With equal diagonals theta is exactly zero, and the two branches give rotations of +45° and −45°.
  **Both diagonalise the matrix.** They differ in which eigenvector pairs with which eigenvalue, and
  in convergence rate on ill-conditioned input. The `>=` is there for numerical stability, not
  correctness.
- `normScale` is internal to NMDS and not exported, and the adaptive step size added after the
  convergence bug absorbs a badly scaled configuration — the final stress matches sklearn's SMACOF
  either way.

Killing them would mean asserting a convergence count or reaching into a private function: measuring
the implementation instead of the result. The same call was made for KEEP's `esc(lastErr)`, where
`lastErr` is one of two string literals KEEP itself assigns and can never carry input.

**A mutation score is not a target.** Three survivors in this slice are documented as examined and
left, with the reasoning written where the next person reading a survivor list will find it. The
failure mode of a coverage metric is writing checks that raise the number without testing anything,
and the defence is saying out loud which survivors you decided not to kill and why.

## Two more defects in the sweep itself

**`>=` matched inside `>>>=`.** The ordination sweep reported a survivor sitting in a PRNG's
`s >>>= 0` — mutating a shift-assign into a comparison, which is nonsense. Nonsense mutants always
survive, and *a survivor list padded with garbage is a worklist nobody finishes*. Both operators now
carry lookbehinds.

**A hanging mutant cost 420 seconds.** One KEEP mutation makes `read()` always return null, so the
suite waits for a restore that never comes. A timeout is a correct kill — it just should not cost
seven minutes and make the sweep look stalled. The budget is now measured from the suite's own clean
run and set to four times it.

## Consequences

KEEP 91 → **107** checks, ORD 89 → **101**. DWC is not swept yet and is named here rather than left
implied.

**The rule this leaves behind:** a survivor is a question with three possible answers — a real gap, a
test that cannot reach it, or a mutation that changes nothing observable. All three came up in this
slice. Only the first one is work.
