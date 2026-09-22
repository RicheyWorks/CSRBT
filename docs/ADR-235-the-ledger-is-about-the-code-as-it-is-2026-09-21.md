# ADR-235 — the mutant ledger is about the code as it is

**Date:** 2026-09-21 · **Status:** accepted · **Chain:** ADR-234 → this ·
**Protocol:** 1.11 (unchanged)

## Why

The board's gate *"no mutant survived"* reads `tools/mutant_ledger.json`. Each
runner writes its entry when it runs, and nothing reads the runner again until
someone runs it. A mutant is an exact string, its anchor, replaced in its
subject. When the subject is edited, the anchor can stop matching, and the
kill it recorded stays on the board.

ADR-234 found this by accident. Two of `mutate_brief`'s fourteen anchors had
stopped landing, one of them since ADR-196, nine slices earlier, when a
comment split a two-line anchor. The ledger said 14 of 14 killed the whole
time. That was true of the code as it stood at the last run, and nothing on
the board said so.

## Decision

**`tools/audit_anchors.py`** reads every runner's catalogue without running
any of them, in about a second. It measures two things:

- **Stale.** A mutant whose anchor is found nowhere in the code it could
  break. That code is the tools, pages, task files, CI definition and Gradle
  files, plus the sibling engine (WholeHog), where the organism and lab
  consoles live, found the way the organism plugin finds it. The runners
  themselves are left out, because every anchor is written in its own runner.
  A stale mutant cannot apply, and it counts as killed until its runner runs
  again.
- **Drifted.** A runner whose catalogue (its mutant names and count) is not
  the one its ledger entry recorded. After a mutant is added, removed or
  renamed, the ledger's count is about a different list.

Both need to know each catalogue's shape, and the kit uses four. This audit
states all four and reports any other shape rather than guessing past it.
*Found nowhere* is the honest limit of a static check. An anchor that lands
in the wrong file, or twice, is caught by the runner itself at run time,
because it refuses an anchor that does not match exactly once. The audit
catches the anchor that cannot land at all.

**`verify_anchors`** holds it: **23 checks.** It builds a scratch kit with one
runner of every shape and one of every failure: an anchor landing in a tool,
a page, a task file or the engine; a reworded anchor; an anchor found only in
its own runner; a renamed mutant, an added one, a runner that does not
import, one with no catalogue, one of unknown shape, one never run; and
`tools/mutate.py`, which is the sweep, not a runner. The engine is looked for
where the plugin looks for it. It then holds the real kit as a gate: every
runner read, no stale mutant, no drifted runner, every runner in the ledger
and the ledger's mutant count equal to the catalogues'. On a machine without
the engine checked out, the console anchors are reported NOT VERIFIED rather
than stale. It is on the board as a harness suite.

**`tools/mutate_anchors.py`**, on the board, has 12 mutants, all killed. Each
breaks the audit the way it would plausibly go wrong: runners counted as a
place an anchor can land, the engine never read, pages or task files dropped
from the corpus, either shape rule dropped, an anchor never looked for, drift
judged by the count alone, a runner that does not import skipped silently,
the sweep read as a runner, drift not treated as a problem, and an entry of
unknown shape passed over.

## What it found

**Run against ADR-233's tree** (`0969ff9`, before ADR-234 touched anything),
the audit reports exactly what ADR-234 found by hand: `mutate_brief`, 1
stale. It also finds something ADR-234 missed:

**`mutate_entry` had drifted since ADR-170.** ADR-170 renamed two of its
mutants and reworded the check one of them expects. The runner last ran on
2026-09-05, before that, and its entry still recorded 17 of 17 killed under
the old names. Re-run on the current catalogue, it gave **16 killed and 1
inconclusive**. The mutant *"a reading below the floor is not one"* was
killed by the wrong check, because ADR-170 changed the suite's sentence from
*"makes --check refuse"* to *"makes the run REFUSE"* (a plain run refuses
now, with no flag). The runner's expectation was corrected and the runner
run again: **17 of 17**. For thirteen days the board had shown a result the
current catalogue could not reproduce.

Among the 1,185 anchors of 33 runners there are now **0 stale and 0
drifted**.

## Numbers

| | before | after |
|---|---|---|
| verify_anchors | — | **23** |
| mutate_anchors | — | **12**, all killed |
| mutate_entry | 17 recorded under the old catalogue | **17 / 17** on the current one |
| runners audited | — | 33 (1,185 mutants) |

## Held

- **Anchors that land exactly once in the file their runner mutates.** That
  needs every runner to declare its subject in one form. Price: touching all
  33. Trigger: a mutant that lands in the wrong file and survives.
- **`audit_carried` under a frozen clock** (ADR-234). Still filed.
- **The other pages' filed defects**, one page per slice, oracle first.

## Lessons

- A ledger holds a measurement, and like any measurement it has a date. An
  entry about a runner is only as current as the catalogue it recorded, and
  that can be checked without running anything.
- Mutant runners are code about code. When the code they break is edited,
  they go stale in the same slice. A second-long static check is what keeps
  that visible between runs.
