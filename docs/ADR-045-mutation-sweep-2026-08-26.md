# ADR-045: Measuring whether the suites would fail, not whether they pass

**Status:** Accepted and implemented — `tools/mutate.py`, plus real picker coverage in `tools/verify/verify_fek.py` (55 → 66 checks).
**Date:** 2026-08-26
**Deciders:** Richmond
**Touches:** `tools/verify/verify_fek.py`

---

## Context

Three times in one week the same failure: a fixture that could not tell two implementations apart.

- ADR-039: two seeded faults walked through `verify_fw` because both shipped presets give identical
  answers under either implementation. Then a third escaped a *second* time because the chain fixture
  happened to be declared in an order that made a one-pass cascade look correct.
- ADR-044: a self-exclusion fault escaped twice — first because the test run was not a baseline run,
  then because the baseline run chosen sat near the mean, where excluding it barely moves anything.

Each was found by hand, on whichever page was in front of me. **Twenty-five suites have never had it
done at all.** A green run says the suites passed. It does not say they would have failed.

## Decision

`tools/mutate.py` seeds single small faults — `max` becomes `min`, `>=` becomes `>`, an `esc()` call
disappears, a trapezoid's `/2` goes away, a decimal constant moves 10% — runs the suites that name
that page, and reports the **survivors**: mutations every relevant suite passed.

It is a **finder, not a gate**. Some mutants are *equivalent* — they change the source without
changing anything a suite could observe — and there is no general way to detect that. Every survivor
is a question. It exits zero and prints a count for triage, on the same principle as `audit_claims`,
because a tool whose every row is noise teaches you to skim, and skimming is what let eight faults
through `verify_fw`.

## The first numbers, and the tool defect underneath them

The first sweep reported mutation scores of **10–20%** on pages I had never canaried, against
**100%** on `food-web.html`, which I had hand-canaried with thirteen faults last week.

Before believing that, two of the tool's own defects had to go — ADR-040's rule applied to the
instrument rather than the kit.

**1. Shared blocks were attributed to the wrong suite.** FEK, KEEP and the greenhouse engine are
inlined into pages. Mutating FEK inside `ethogram.html` and then running only `verify_etho` reported
a survivor that `verify_fek` might well have killed. A mutation in a shared block is now also run
against the module's own suite.

**2. The tool mutated the real tree, while its own docstring said it used a copy.** It edited
`docs/` in place and restored in a `finally`. A `finally` survives SIGTERM and does not survive
SIGKILL, a full disk, or a container that goes away — and the failure mode is a **mutant left in the
real tree**, which is the worst thing a tool like this could possibly do. It now copies `docs/` and
`tools/` to a scratch root and never touches the checkout. *A tool's docstring describing behaviour
it does not have is the same defect class as an audit rule that cannot see what it is named for.*

## What survived, and what one of them was

With both fixed, the FEK survivors stayed survivors — which made them findings rather than artefacts.
The worst:

```js
return !qq || (op.label+" "+(op.sub||"")).toLowerCase().indexOf(qq) >= 0;
```

Change that `>= 0` to `> 0` and **`verify_fek`'s 55 checks all pass.**

`indexOf` returns **0** when a query matches the *start* of an option — which is what happens when
anyone types the first letters of the thing they are looking for. Type `may` and "mayfly nymph"
vanishes. Type `alg` and "algae" vanishes. The picker becomes actively broken for the normal case,
and it is inlined in fifteen pages.

`verify_fek` had exactly one picker check: that `FEK.picker` was a function.

## The fix, and its fixture

`verify_fek` now drives the picker: filtering from the start of a label, from the middle, on the
sub-label, case-insensitively, the empty state and its count, selection reporting a value rather than
a label, and `set()`.

The fixture is chosen to **discriminate**, which is the whole lesson of the last three ADRs. `may`
matches "mayfly nymph" at index 0 and matches "perch" nowhere, so `>=0` and `>0` give different
answers. A query matching mid-string would pass under either and test nothing.

Five faults seeded at the new checks; four caught (the fifth's anchor did not match — already covered
by the value-not-label check). 55 checks became 66.

## The thing the sweep was actually for

Chasing one FEK survivor into the module produced the finding this whole slice justifies.

`mutate.py --module fek` scored **7%**: thirteen of fourteen seeded faults survived, including the
picker break I had *just written a check for*. The check worked when run by hand. It did not work
through the sweep.

The reason:

```
FAIL: a query matching the START of a label still finds it
PASS 64
64/66
rc: 0
```

**`verify_fek` prints its failures and exits zero.** Eleven suites in this kit have no exit statement
at all. For every one of them, `run_all`'s per-job "ok" has meant *the process did not crash* — and
the headline **"45 of 45 jobs green" was counting eleven jobs that could not have said otherwise.**

The check-count line was load-bearing and the job line was not, which is a bad way for a report to be
half right.

### The fix is not eleven edits

Eleven exit statements were added, and they are hygiene. The durable fix is one change in `run_all`:
**stop treating the exit code as the only evidence.** The score is already parsed on every job. When
it shows a shortfall — or the output carries a `FAIL` line — that is a failure whatever the process
claimed on the way out. Such rows are marked `FAIL*` and listed under a heading that says what they
are.

That covers every suite written from here on without anyone remembering to add an exit line, which is
the failure mode that produced eleven of them.

Seven classifier cases canaried, all correct: clean green stays green; a worded audit score
(`37/37 pages clear`) and a `99 passed, 0 failed` tail stay green; a shortfall in either format is
flagged; a `FAIL` line with a clean score is flagged; and a job that already exited nonzero is left
alone.

## The tool damaged the repository, one run before the fix landed

This has to be written down, because it is the worst thing that happened and the reason the scratch
tree exists.

An early in-place run was killed mid-mutant. Its `finally` did not run, and it left this in
`food-web.html`:

```js
function s{ return s.replace(/[&<>"']/g, ...
```

Two faults compounded. The `drop-esc` operator matched the escaper's own **definition** —
`esc(s)` inside `function esc(s){` — turning it into a syntax error rather than a mutant. And the
tool was editing the real tree while its docstring said it used a copy.

It surfaced in the next full regression as three HIGH `js-error` findings on food-web. The page was
restored byte-for-byte from the last delivered package and re-verified.

Three changes came out of it:

- **`drop-esc` now refuses to match a definition** (`(?<!function )`).
- **Every mutant is checked for viability** with `node --check` before it is run. A page that will
  not parse is killed by every suite for free, which inflates the score while measuring nothing;
  unviable mutants are counted separately and excluded from the ratio. Had this existed, the bad
  mutant would never have been written to disk at all.
- The scratch tree, which was already the documented behaviour and is now the actual one.

*A tool that seeds faults is a tool that can leave one behind. It gets the same suspicion as
everything else here, and it earned it.*

## The new rule's own first false positive

The cross-check's debut run flagged `audit_contrast`. It was wrong.

That audit prints a table whose column header reads `PAGE      AA FAILURES`, and the rule was
`"FAIL" in out`. One false positive out of forty-five jobs, on the rule's first outing — **the exact
defect ADR-040 is about, inside the fix for a different one.** A row that is right about what it
matched and wrong about what the match means.

Now anchored: `^[ \t]*FAIL\b`. A result line starts with FAIL; a table header saying FAILURES does
not, and `\b` refuses the longer word anyway. Six cases canaried, all correct — including
`FAILURES: 0` at line start, which must stay quiet, and an indented `FAIL`, which must not.

## Consequences

The mutation score is now a number this kit can watch. `food-web.html` scores 100% because it was
canaried by hand; the pages that were not score far lower, and the gap between those two numbers is
the honest measure of how much of this kit's green is load-bearing.

`--all` exists and is bounded by `--limit`, because an unbounded sweep across 39 pages would run for
hours and therefore never be run.

**The rule this leaves behind:** a suite that has never failed on purpose has never been tested. The
question is not whether your tests pass — you can see that. It is whether they would fail, and the
only way to find out is to break the thing and watch.
