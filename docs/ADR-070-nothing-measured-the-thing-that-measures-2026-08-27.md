# ADR-070: nothing measured the thing that measures

**Status:** Accepted and implemented — `tools/verify/verify_mutate.py` (new, 19 checks, the kit's 54th
suite), `tools/mutate.py` (an ADR-046 guard, and the three guards folded into one probe),
`tools/verify/verify_ss.py` (81 → 84).
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-040 (the finder was the defect), ADR-046, ADR-069

---

## Context

`mutate.py` is the instrument that says how much of this kit is really tested. Yesterday and today it
was caught reporting a kill for a reason that had nothing to do with the mutation — three times:

| | what the suite did | what the sweep read |
|---|---|---|
| ADR-046 | printed FAIL, exited 0 | every failure as a pass; FEK **7%** against a true 95% |
| ADR-069 | was already red on clean code | every mutant killed; **33% → 100%** in three seconds |
| ADR-069 | compared publish digests, so any edit failed it | every mutant killed; **100%** again, an hour later |

Every one was found by a person noticing a number that looked too good. Fifty-three suites test the
pages, and **nothing tested the thing that tests them** — which is ADR-040's lesson arriving one level
up: the finder was the defect, and the finder had no canary.

## Decision

`tools/verify/verify_mutate.py` builds a scratch tree with one small page and a set of deliberately
pathological suites — one honest, one always red, one that fails on any byte change, one that prints
FAIL and exits 0, and one that is silent on clean code and lies only once something is wrong — then
runs `mutate.py` against it and reads its **output**.

The suites are real files run as real subprocesses rather than mocks, because every guard here is
about exit codes and printed reasons. A mock of those would be a test of the mock.

It found the gap it was written to look for: **19 checks, and two of them failed on the first run** —
the ADR-046 shape had been fixed in the suite that had it and never in the runner, so the next suite
to exit 0 on a failure would have been believed all over again. `run_suite` now treats a printed
failure as a failure whatever the exit code, which both recovers the detection and names the offender:

```
SUITES THAT EXIT 0 ON A FAILURE -- their detections were counted, but
an exit code that lies is what made the Field Entry Kit read 7% in
ADR-046. Fix the suite: verify_fake_sneaky.py
```

Excluding such a suite would have been the wrong answer: it *did* notice. The signal is worth keeping
and the defect is worth naming, and those are two different jobs.

### One probe instead of two

ADR-069 added two passes before the mutants: green-on-clean, then green-after-a-null-edit. Writing the
fixtures made it obvious they are the same question. A comment appended to the page changes its bytes
and cannot change its behaviour, so a suite that passes **that** is green *and* is not measuring the
file. Only a suite that fails gets a second run, on the clean page, purely to say which of the two it
is. Stand Sheet is named by eight suites; the common case now costs eight runs before the first mutant
rather than sixteen.

### Canaried, all three

Each guard was removed in a scratch copy and the suite re-run: 17/19, 17/19, 15/19. Removing the
baseline is instructive — the null-edit probe catches the red suite anyway, and the suite still fails,
because it is reported under the wrong reason. A guard that fires for the wrong reason is not the same
guard.

## What the sweep found while this was being built

`stand-sheet.html`, **75% → 100%**.

The survivor was `D <= 0` → `D < 0` in the tree-height guard:

```js
var D=num("hD"), t=num("hT"), b=num("hB");
if(D===null||t===null||b===null||D<=0) return null;
return D*(Math.tan(t*R)-Math.tan(b*R));
```

A horizontal distance of zero is not a small distance, it is no distance: `D · (tan θ − tan θ)` is 0
for every pair of angles. With the guard weakened, `height()` returns 0 instead of null, and the page
answers with the **wrong diagnosis** — *"That gives 0.0 m. Check the signs — looking up is positive"* —
for a reading whose problem is not the signs at all. Zero is reachable: it is the bottom of the
distance stepper's own range.

Measured, both ways, before writing anything: at D = 0 the page says *"Enter a horizontal distance and
both angles"*; with the mutant it offers the sign advice.

The check asserts an **equivalence** rather than a string — a zero distance must be refused exactly as
a missing one is — plus that the refusal is not a sign diagnosis, plus that a real distance still
computes so the fixture cannot go vacuous. Four suites in this kit have broken on pinned prose; this
one survives a rewording.

Three of stand-sheet's four mutants were in inlined modules and were killed by `fek_emit` and
`keep_emit`, which is ADR-069's second link doing its job: the line is not that page's to change.

## Cost

`verify_mutate` 19 new, `verify_ss` 81 → 84. No page changed. **54/54 jobs green, 3894 checks.**

**Swept: 20 pages, 19 to go — 7 with code of their own, 12 the shared loader.**
