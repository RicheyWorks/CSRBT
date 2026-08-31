# ADR-110: a control judged on an empty page was not judged

**Status:** Accepted (2026-08-31) — full suite **68 of 68 jobs, 4,591 of 4,591
checks**; Java **1,127 tests**; harness matrix **62/62**; mutation catalogue
**13 killed, 0 survived**.
**Date:** 2026-08-31
**Deciders:** Richmond
**Builds on:** ADR-109 (a detector with no alarm), ADR-108, ADR-106, ADR-105.

---

## 1. Ten of the twelve remaining "dead" controls were working

ADR-109 cleared the harness's false accusations down to twelve controls
genuinely reported as wired to nothing. Reading the list is the argument:

> Clear trial · ↩ Undo · Copy CSV (for Excel/R) · ✕ · ✕ · 🍎 fruit program ·
> New random tree · 📷 Add photos · +

Every one of the first six **operates on data**. The harness pressed them on an
empty page, they correctly did nothing, and doing nothing was filed as a defect.

Measured directly on `field-notebook`, not inferred: Undo with an empty tally
changes nothing — which is right, there is nothing to undo. Tally one card first
and it takes the tap back, page text 1223 → 1089. The control was never broken.

The multi-pass loop already knew half of this. Its own comment says *"a page that
has had a record added offers controls that were not on it when it loaded"*, and
it repeats the walk until nothing new turns up. But it only ever **drives newly
discovered** affordances. An affordance pressed in pass one is never pressed
again, however much state the rest of the walk has since built. For a kit of
data-entry pages that is the wrong half.

## 2. The second chance

Anything still dead at the end of the walk is pressed **once more**, against
state built by the page's own controls. Nothing synthetic is injected.

One refinement was forced by the first attempt failing. Retrying against
whatever state the walk happened to leave is not enough: on `field-notebook` the
walk both builds the tally history and drains it (it presses Undo on every pass),
so by the end the history is empty again and the retry is the same wrong test a
second time. So the retry is **pane-scoped and rebuilds first** — the affordances
that did leave a trace in that pane are replayed, then its dead candidates are
pressed against that fresh state.

Result across the kit: **dead 12 → 2**, and the revived controls are recorded as
having *needed prior state*, which is a fact about the control worth keeping
rather than a defect.

The accounting identity caught a bug in my own implementation while I wrote it:
the loop extended every bucket per pane and then assigned `res["dead"] = kept`
afterwards, discarding the ones that came back still dead. Two affordances
vanished and the run printed `UNACCOUNTED`. That is what the identity is for.

## 3. One of the two survivors is a real defect, found and fixed

`tree-proofs.html`'s **"New random tree"** survived the retry. Probed directly:
four presses, page text unchanged, SVG markup unchanged, DOM node count
unchanged, no errors. Then read:

```js
for(i=keys.length-1;i>0;i--){ var j=Math.floor(((i*2654435761)%2147483647)/2147483647*(i+1)); ... }
var take=13+ (RB.rot%3);
```

The shuffle is a pure function of the loop index — no seed, no state — so it
produces the identical permutation on every press. And `take` reads `RB.rot`
from a tree created one line earlier, which is always 0. **The button rebuilt the
same tree every time.**

Not wired to nothing: wired to something that could not answer, which is the
harder version of the same defect and precisely what the oracle exists to catch.

Fixed in this kit's idiom rather than with `Math.random()`: a counter advances
once per press and seeds an xorshift mixer, so **press N always yields tree N** —
reproducible, and different from press N−1. Verified: three presses give three
different trees, and the sequence is byte-identical across reloads.

The remaining survivor, `stand-sheet`'s "📷 Add photos", is accepted debt with a
name on it.

## 4. What that did to the identity of a finding

Re-running the ratchet surfaced a flaw in ADR-109's signature scheme. Two of
them, in fact.

**Generated ids leaked into labels.** A signature read
`survey-design.html | spill9px | harness-373:plot:01plot · Nort`. Those ids are
minted at run time, so every run produced new signatures, every one reading as a
regression. A ratchet that cries wolf is one nobody looks at. Generated ids and
row numbers now collapse to `#`, and the same normalisation is applied to labels
parsed out of error strings — the first version applied it only to records, which
is why every spill kept its row id.

**Counts were being compared, and counts belong to the walk.** Adding the
second-chance retry moved one signature from seven occurrences to nine without a
line of page code changing, because the retry builds more rows. A ratchet that
fires on its own maintenance is worse than none. Counts are recorded and no
longer compared; the set of distinct signatures is the evidence.

That is a partial retraction of ADR-109, which argued that collapsing duplicates
would let seven regressions hide behind one baseline entry. With normalisation
the collapse is not a loss of information but a gain in truth: `survey-design`
has **one** defect that shows on every row, not twenty-three defects. Accepted
debt fell from 32 distinct signatures to **17**, over 4 pages instead of 8, with
no defect forgiven.

## 5. The tester grew with the thing it tests

`verify_harness_matrix` gained section J — five checks on the second chance:
a state-needing control is driven and recorded as such, the run reports what it
retried and revived, a genuinely dead control stays dead, and the identity holds
with the retry in play.

Then mutation testing did its job twice more:

- **A survivor.** "The second chance does not rebuild state before retrying"
  survived J1–J3, because in that fixture the state happened to survive to the
  end of the walk. The real case does not. A new fixture (`j_drained`) puts the
  drain in a *second pane*, so the walk ends with the state empty and the
  pane-scoped replay is the only thing that can bring it back. The mutant dies.
- **A self-reference.** One mutant was "killed" by the wrong check: section I
  verifies that every catalogue anchor still matches the harness, and a mutation
  run alters the harness on purpose. A mutant killed by I2 has proved nothing
  about the clause it targets. The runner now marks mutation runs and section I
  stands aside, saying so rather than passing in silence.

I also shadowed a variable in my own test file — inserting the new fixture
between `r = run(...)` and the check that read `r`, so J4 asserted against the
wrong page. It failed, which is the correct outcome for a test file that is
wrong.

Final: **13 mutants, 13 killed, 0 survived, 0 inconclusive.**

## 6. Consequences

- The dead list is now short enough to act on and true enough to trust: two
  entries, one of them fixed in this slice.
- A finding's identity survives the next run, which is what makes the ratchet
  usable rather than noisy.
- **Third rule earned the hard way:** a defect register must be robust to changes
  in the tool that produces it, or maintaining the tool looks like regression.

## 7. Still open

- `selection-log` and `survey-design`: the `row2` flex-chain repair, unchanged
  since ADR-103 and now the great majority of the accepted debt.
- `ecology-lab`: four Workbench textarea fills time out under the walk while
  working by hand. Either the harness's fill is wrong for that control or the
  control is, and **nobody has measured which** — which is the honest state and
  the next thing worth measuring.
  → **Measured, ADR-111.** The harness's, not the page's: two visibility oracles
  inside one instrument, and the controls sit in a collapsed `<details>`.
- `stand-sheet`: "📷 Add photos", the one genuinely dead control remaining.
  (Kit-wide dead read **2** on the run this ADR was written from; the second was
  on `ecology-lab` and went away with the oracle fix in ADR-111, which is why the
  figure is **1** from that point on. "The one remaining" was written a run early
  and is recorded here rather than quietly corrected above.)
