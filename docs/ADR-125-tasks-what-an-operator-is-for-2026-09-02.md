# ADR-125 — Tasks: what an operator is for

**Status:** accepted · **Date:** 2026-09-02 · **Gives the harness a way to ask whether a goal was accomplished, not only whether every button works — the thing a robot or a model plugged into it will be measured by**

## 1. A walk has no goal

The robot proves a target is operable: every tool driven from its
manifest, every refusal counted, nothing broken. That is the floor an
operator stands on. It is not what an operator is *for*. "Preserve the
store and read the generation back cold." "Arm a crash, let a batch fail,
restart, find the batch whole." "Hold the replica behind, wait, find the
write on it." Whether those were **done** is a different question from
whether the buttons work, and since ADR-097 nothing in the harness could
ask it — the per-target suites ask it in Python, from inside the kit, with
knowledge the manifest does not give.

The program's stated end is "robots, AI etc. plugged into the harness".
A thing plugged in needs something to be *asked to do*, and a grader that
can say it was not done.

## 2. The decision

A **task** is a JSON file under `tools/tasks/`: a target, a goal in words,
and the steps that accomplish it — each an action with arguments and, where
it matters, **expectations** about the response, graded the way the science
engine grades an `.eco` protocol's hypotheses: `CONFIRMED` or `REFUTED`,
never "passed" because a step ran.

- **References.** `"$<step>.<dotted.path>"` anywhere in arguments or
  expectations reads an earlier step's response — its output, its snapshot,
  its code. `cold-scan` is given `"$gen.output.generation"`; a fixture
  action is given the slot the previous snapshot published. A key holding a
  dot is escaped (`argumentPools.pooled\.slot.0`).
- **Expectations.** A path equals a literal or a reference, or takes an
  operator: `==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `contains`, `exists`.
  A refusal, a decline and a failure are results a task can expect
  (`"code": "conflict"`); a failure nobody expected is the target's and ends
  the task.
- **Verdicts.** `PASS` — every expectation confirmed, no step failed.
  `FAIL` — a refutation or an unexpected failure. `DEFECT` — the task
  itself could not be run: a reference to a step that has not run or a path
  that is not there, a target that went away. A defect is the task's fault
  and never a finding about the target. A task may declare `"must":
  "FAIL"`: the **canary**, a task written to be refuted so the grader is
  known to be able to say no.

`tools/harness_tasks.py` runs every task on a fresh target of its own,
through the real transport (stdio or MCP), and keeps `tools/task_ledger.json`
merged per task: `held` when the verdict is the one the task was written
for.

## 3. The tasks

Eight, over every target:

| task | target | what it proves |
|---|---|---|
| `organism-preserve-cold-scan` | organism | three writes, preserve, a later write, cold-scan the generation: `records == size at preserve`, the archive verifies, a generation never cured is `not_found` |
| `organism-crash-road` | organism | `once:2`, a three-op batch `failed` naming the Crash, `chaosCrashes 1`, the next batch `conflict`, restart clean with a journal replay, count 3 direct and over the wire, the fold rebuilt |
| `organism-replica-behind` | organism | a 200 ms lag, four writes, the fleet `lag > 0` and not gapped, a quiesce, lag 0, the last key on the replica |
| `organism-cold-recovery` | organism | five keys in shuffled order, a cold restart: `sorted`, five entries, no hint, a named strategy, inversions > 0; first 10, last 90; a clean restart warm again |
| `lab-run-shipped-protocol` | lab | `sample-experiment` listed, run and graded, run again to the same verdicts, a `dwc:` protocol refused |
| `page-enter-and-read-back` | page | collection-sheet: one pane open, no junk; enter "Quercus rubra", read it back; no errors; a nav link refused with "use open" |
| `fixture-buckets` | fixture | a refusal, a decline and a failure by expectation; a pool read into the next call; an argument set taken whole |
| `fixture-canary` | fixture | **must FAIL**: `ok` expected to decline — REFUTED at step two, held |

First run: **five held, three not** — every one of the three the task's
fault, which is the grader working: a refused response carries no snapshot
(so `snapshot.chaosCrashes` was read on the wrong step), the first
generation is 0 (the task said `>= 1`), and read-page's `junk` is `null`
when there is none. Second run: **8 of 8 held**, over stdio and over MCP,
expectation for expectation.

## 4. The suite and the runner's mutants

`verify_tasks` (**48 checks**): the grammar (paths, escapes, every
operator, references that resolve or are defects); the files (named by
their file, targets the builder stands up, references only to earlier
steps, one canary, an unknown operator refused at load); the grader on the
fixture (the canary refuted and held, the buckets task passed step for
step, a bad reference a DEFECT, an unexpected failure ending the task, a
target that dies a DEFECT, MCP reaching the same verdicts); every real
target's tasks through the gateway; the committed ledger. `mutate_tasks`
breaks the runner ten ways — every expectation confirmed, a refutation not
failing the task, a bad reference resolving to None, `must` ignored, a
missing path present, escapes dropped, a dead target a failed step, a
refusal filed as driven … — **10 killed, 0 survived**.

## 5. What this is for

A task file is the first artifact in the kit that an operator *other than
the kit* can be handed: a goal, the steps a competent operator would take,
and a grader. The next operator is a model given the goal and the manifest
and not the steps — its trace graded by the same expectations. That is the
consumer this ADR builds the instrument for, and it is held (ADR-121) until
a model can be run unattended here.

## 6. Held

- Tasks are sequential and single-target. A task that needs two targets
  (write through the organism, look through a page) has no shape yet.
- Timing is not an expectation. `quiesce`'s `quiet` is; how long it took
  is on the response (`ms`) and not graded.
