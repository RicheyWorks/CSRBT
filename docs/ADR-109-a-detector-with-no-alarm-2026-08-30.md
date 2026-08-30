# ADR-109: a detector with no alarm

**Status:** Accepted (2026-08-30) — landed and green: full suite **68 of 68 jobs,
4,584 of 4,584 checks**; Java **1,127 tests**; harness matrix **56/56**; mutation
catalogue **10 killed, 0 survived**.
**Date:** 2026-08-30
**Deciders:** Richmond
**Builds on:** ADR-108 (the harness had no map), ADR-106, ADR-105, ADR-104.

---

## 1. The harness was finding real defects and nothing failed

Measured before any change: **21 dead controls, 4 actions that raise, 62 broken
invariants** across 41 pages. Every suite green, for weeks.

The harness had a genuinely good property — the accounting identity, `discovered
== driven + dead + hidden + failed + excluded` — and it answered the wrong
question. It proved the harness had not *lost* anything. It said nothing about
whether anyone acted on what it found. It was a detector wired to no alarm, and a
finding nobody's build reads is indistinguishable from a finding nobody made.

That is the fourth appearance of one family in this kit: ADR-104's ledger nothing
consumed, ADR-106's audits examining nothing, ADR-108's coverage of a page never
opened, and now a defect list nothing enforced. **A tool that produces truth into
a vacuum.**

## 2. Two of the findings were the instrument describing itself

Before building the alarm, the list had to be true. Two parts of it were not.

**Ten of the twenty-one dead controls — 48% — were the harness's own sequencing.**
To press a selected option fairly the walk first clicks a sibling to move the
group off it; on the kit's real pages that click re-renders the row, so the
control the walk was about to press no longer exists. It was filed as "wired to
nothing": an accusation against working code, caused entirely by the order the
harness chose to act in. They now go to a sixth bucket, `sequenced`, still
counted and still visible, and never mixed with real ones.

**Both "junk rendered" findings were false.** field-notebook renders *"No
recaptures yet — the estimate is undefined (R must be ≥ 1)"*, because
Lincoln–Petersen is M×C/R and genuinely has no value at zero recaptures. The
detector matched the word `undefined` and reported the kit's own carefulness as a
value leak. The existing mitigation — compare the token against what was present
at load — could never have worked, because that text only renders after an
interaction.

The fix is not a cleverer regex. **An element may declare that it renders one of
these words as prose**, with a reason, via `data-junk-ok`, exactly as suites
declare `MUTATE_ROLE` and the harness declares its excluded kinds. The
declaration excuses the word `undefined` only: `NaN` and `[object Object]` are
never English and no marker can hide them, or the escape hatch becomes the way
the next real leak goes unreported. All three cases are canaried.

That is this kit's recurring defect for the fifth time — *right about what it
matched, wrong about what the match meant* (ADR-040, ADR-105, ADR-106).

## 3. The alarm

`tools/findings.py` signs a finding by what a person would recognise it by:

```
page | category | label
```

Not by the harness's own ids, which renumber the moment a page changes.
Duplicates are kept and counted, because eight identical `remove` buttons each
spilling nine pixels is a different fact from one, and collapsing them would let
seven regressions hide behind a single baseline entry.

`tools/harness_baseline.json` records the accepted debt — **32 distinct findings,
76 occurrences, across 8 pages**, each page carrying a reason. Adding to that file
is accepting a defect, deliberately, with a name on it.

`tools/verify/verify_findings.py` fails in **both** directions:

- **NEW** — a finding not in the baseline. A regression breaks the build.
- **FIXED** — a baseline entry that no longer occurs. Debt paid and not written
  off makes the register longer than the kit's real problem, which is how a
  defect list stops being read.

A ratchet that only tightens becomes a list nobody believes; one that only
loosens is not a ratchet.

## 4. The harness now gates the build, so it is tested like something that does

`verify_findings` makes a harness bug consequential in a way it never was: either
a build breaks over nothing, or — worse — a real defect stops being reported and
nobody notices, because the thing that would have noticed is the thing that
broke.

`tools/verify/verify_harness_matrix.py` walks the contract clause by clause,
**56 checks in nine sections**: every one of the 20 kinds it claims to discover;
every one of the 6 buckets it sorts into; every trace it accepts as evidence an
action worked (text, class, form value, `localStorage`, print, alert); every
invariant it claims to catch (NaN, `[object Object]`, two panes, spill, console
error); pages that fight it (no controls, throws on load, a control that removes
itself, `confirm`/`prompt`, a slow handler); determinism across identical runs;
unique addressability; and the ledger's merge arithmetic.

## 5. And the tester is tested by breaking the harness on purpose

It passed 52 of 52 the run it was written, which in this kit is a reason for
suspicion. `tools/mutate_harness.py` breaks the harness ten ways **on a copy**
and requires the matrix to notice each. Every mutant names the check that must
kill it.

The first run returned two non-kills, and they were different things:

- One was **my** mistake, not the tester's: a mis-typed anchor that never
  applied. The runner now verifies every mutant actually changed the file before
  believing its result, and reports `BAD MUTANT` rather than a pass — a mutation
  that did not happen produces a green that means nothing.
- One was **real**. "Sequencing artifacts folded back into dead" survived,
  because the check only asserted that the `sequenced` bucket *existed*, not that
  anything landed in it. A bucket exists whether or not it is used. That check now
  asserts placement in both directions, and the mutant dies.

Final: **10 killed, 0 survived, 0 inconclusive.** The matrix asserts that the
catalogue stays live — every anchor must still match the harness exactly once,
because an anchor that stops matching is a mutant that silently stops testing.

## 6. Consequences

- A control that stops working now breaks the build. That was not true this
  morning.
- The defect register is honest: 12 real dead controls, not 21; 60 invariant
  breaks, not 62.
- `docs/AI_HARNESS.md` documents the six buckets, the declaration, the ratchet
  and the mutation catalogue.
- The pattern is named for the fourth time. **Any tool in this kit that produces
  a report nothing consumes should be assumed wrong**, and the cheapest way to
  find out is to give it a reader.

## 7. Still open

- The accepted debt itself: `selection-log.html` at 38 findings and
  `survey-design.html` at 23 are the `row2` flex-chain repair ADR-103 named,
  now with a worst case of 37px measured. Paying it down is the next slice, and
  the ratchet will notice when it is paid.
- `ecology-lab.html`'s two Workbench textareas time out under the walk while
  working by hand — either the harness's fill is wrong for that control or the
  control is, and nobody has measured which.
