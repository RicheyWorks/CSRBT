# ADR-136 — The blind trial: six operators who had never seen the tasks, and the four things they proved wrong about the instrument

**Status:** accepted · **Date:** 2026-09-03 · **The trace grader's first real customers: six subagents given a task's goal sentence and a JSON-RPC door, working in a checkout with `tools/tasks/`, `tools/traces/`, the ledger and every ADR deleted. First grading: 24 of 40 required steps. Every miss was a defect in the instrument, not in the operator. After the fixes: 30 of 30 — and the six blind traces are now a committed check, so a task that pins its author's route stops grading and the suite says so**

## 1. What ADR-126 promised and could not do

ADR-126 built the trace grader and ended by naming what it was missing:

> A blind trial: a model that did not write the tasks. The instrument is
> ready; the operator is not in this sandbox.

The six traces it shipped were produced by the session that had written the
tasks earlier the same day. Their provenance says so. They are a real test of
the *grader* — the operator planned its own calls, and its arguments differ
from the tasks' — but they are not a test of the *tasks*, because a task whose
required steps quietly encode the route its author happened to take will still
grade against a trace that author produced.

That is the whole failure mode of a verification instrument: it confirms the
thing that built it.

## 2. The trial

`tools/blind_console.py` is the operator's side of the door. It spawns
`tools/harness_mcp.py` as a child, speaks JSON-RPC over the pipe, and offers
exactly what a host offers — `tools/list`, `resources/list`, a call, a read —
and nothing else. It never reads `tools/tasks/`.

Six general-purpose subagents, a fresh context each, were given:

- the task's **`goal` sentence, verbatim**, and nothing else about the task;
- the console, with `SENSITIVE_READ`, `DRAFT` and `MUTATE` allowed and
  `DESTRUCTIVE` refused;
- a working copy of the repo at `/tmp/blind/CSRBT` with `tools/tasks/`,
  `tools/traces/`, `tools/task_ledger.json`, every `docs/ADR-1*.md`, every
  `CHANGELOG-*`, `AI_HARNESS.md`, `AUTOMATION-HARNESS.md` and `PLAN-*.md`
  **deleted** — blindness as a fact about the filesystem, not a promise about
  someone's attention.

One run was mis-conducted, by me: `organism-crash-road`'s first operator was
handed a paraphrase of the goal that dropped the clause *"see the organism
refuse the next batch while the crashed one is still applying"* — the hardest
step in the task. An operator cannot be graded on a step its goal never asked
for. That run was discarded and re-run with the goal verbatim; the trace kept
is the second one. It is in `tools/traces/blind/PROVENANCE.md`, and
`verify_tasks` requires the provenance to say so, because a trial whose
conduct is not on the record proves nothing.

## 3. Both numbers

| task | first grading | after the fixes |
|---|---|---|
| `organism-preserve-cold-scan` | PASS 6/6 | PASS 6/6 |
| `lab-run-shipped-protocol` | PASS 2/2 | PASS 2/2 |
| `organism-cold-recovery` | PASS 7/7 | PASS 7/7 |
| `page-enter-and-read-back` | 1/3 | PASS 3/3 |
| `organism-crash-road` | 2/8 | PASS 6/6 |
| `organism-replica-behind` | 2/9 | PASS 6/6 |
| **required steps met** | **24 of 40** | **30 of 30** |

Half the tasks held first time, against operators that had never seen them.
The other half did not, and every one of those misses was the instrument's.

## 4. The four findings

### An observation rides every response

`grade_trace` matched a step's `action` against the call's `action`, so an
`observe` step could only be satisfied by a bare `resources/read`. But **every
gateway response carries a `snapshot`**. An operator that reads the fleet's lag
off the `put` it just made has observed the fleet; demanding a separate read
afterwards is the instrument asking for a ceremony the goal never mentioned.
Two blind operators lost required steps to it.

`grade_trace` now lets an `observe` step be met by any call whose response
carries a snapshot. The licence is `observe`'s alone: every other step is still
met only by the action it names, and a response with no snapshot observes
nothing.

### A probe must not be required

`look` and `settle` in `organism-crash-road`, and `w2`/`w3`/`w4` in
`organism-replica-behind`, described *the author's* route to a state rather
than the state. `organism-replica-behind`'s operator wrote one 40-op batch
where the task wrote four `put`s — a better answer than the task's, graded as
three missing steps. They are probes now.

### A required step must not pin the author's constant

`page-enter-and-read-back` read back the literal `"Quercus rubra"`. The claim
is not that the page holds *that* string; it is that the page gives back what
was entered. It reads `$type.output.value`.

### A count of what the author did is not a count of what the goal says

`organism-crash-road` required exactly three records in the index because the
author's batch had three. Its goal claims the batch comes back **whole**;
`>= 3` is that claim, and the operator's larger batch satisfies it.

## 5. A claim may not rest on a probe

Demoting four steps to probes exposed the trap on the other side, and
`load_task` now refuses it: **a required step may not read a probe's
response.** `"$look.output.n"` in a required step is a claim that cannot be
graded whenever the probe was skipped — the reference raises, the step is a
DEFECT, and the task blames the operator for not taking a detour the goal never
asked for. Three of the six blind operators skipped a probe; this is not
hypothetical. The rule is one-way: a probe may read a required step.

## 6. Verification — the trial is now a check, not an anecdote

`verify_tasks` gained **25** checks (**234**, of which 180 run in QUICK):

- the grader's observe rule, three ways: met by the snapshot on any response;
  not met by a response carrying no snapshot; and the licence is `observe`'s
  alone;
- the load-time probe rule, both directions, on a fixture and on every
  committed task;
- and section **F2**, the blind block: the six traces exist, name real tasks
  across all three real targets, are not the tasks' own steps replayed, and
  **each grades PASS and held with every required step met**; at least one
  meets an `observe` step by a call that is not an observe; blind operators
  skipped at least three probes; the provenance states the conditions and owns
  the mis-conducted run; and `--grade-trace all` reaches both directories, the
  ledger carrying each blind grade as `<id>@blind` beside the sighted
  `<id>@trace`.

F2 is the only empirical check in the file. There is no rule in it that says
"do not pin a constant" — there are six operators who did not know what the
constant was. A task that re-acquires its author's route stops grading against
them, and the suite fails.

`mutate_tasks` gained **11** mutants (**55**), and to carry four of them the
runner now mutates **task files** as well as the harness: put `"Quercus rubra"`
back, make `look` required again, ask for `== 3`, require the fourth write.
Each of those still grades PASS against the sighted trace its author wrote.
Only the blind operators refuse them. **55 killed, 0 survived.**

One more hardening the mutants forced: a committed task that will not load is
now a failing check rather than a traceback. A suite that falls over has not
noticed anything.

## 6a. A phantom the full run turned up: the page may still be building

The kit run that closed this slice failed `audit_focus` on **deployment-log**
with one fault — *"never exposed, so never measured: None x1"* — and passed the
same page on the next two runs. A fault that names `None` is the worst kind,
because the stamp it would be named by is the stamp it never got.

The cause is structural, not a race in the page. Every state stamps its
controls before it probes, and `coverage()` counts after the walk — so a
control the page mounts **after the last stamp** (a region rendered on a timer,
a chart that builds its own buttons) carries no stamp at all, and coverage
reports it, correctly by its own rule and falsely in fact, as a control no
state exposed.

`each_state` now settles once more at the end and, only if the page did grow a
control since the last stamp, stamps and **measures** it in a final `settled`
state. `verify_audit_states` mounts a control from the last state's probe and
requires exactly that: the extra state appears, and only then; the late control
is measured rather than counted as never measured; and no control is left
carrying no stamp. **55** checks (+3), and three more mutants — the settle
removed, the settle unconditional, the late control stamped but not measured —
**37 killed, 0 survived**.

The reproducible instance is gone; the next kit run showed the same total once
more and then, on the run after it, none. One fault that appears in a parallel
run and in neither of two solo runs is not something to declare fixed, so the
honest record is: the cause named above was real and is fixed, and if a
phantom returns it will now say what it is. `run_all.py` was printing a failing
job's **name and nothing else** whenever its output had no line beginning
`FAIL` — which is every audit, because an audit reports a fault table and a
total. It now falls back to the last twelve lines of what the job printed. A
run that says `audit_focus` and stops has told the operator to go and reproduce
it by hand.

## 6b. The board

`harness_board.py` counted a task's trace and stopped there — the six blind
grades sat in the ledger and appeared nowhere. The Tasks and traces table now
carries a **blind trace** column beside the sighted one, and the note under it
says what blind means; the headline counts twelve traces, not six.
`verify_board` requires both (**45** checks, +2), because a board that quietly
drops half a ledger is the readout ADR-127 was written against.

## 7. Held

- **Six tasks of fifty-four.** The organism, the lab and one page. The 44
  science tasks — where the reports and the oracles are — have never been put
  to a blind operator. Next: a blind trial on a data-entry page, where the
  operator must find the controls by the page's own names and reach the
  figure.
- **The operator is a subagent of this session.** It is blind by the
  filesystem, not by provenance; a genuinely foreign model is a stronger test
  and not one this sandbox can run.
- `blind_console.py` drives one target at a time; `two-targets-*` cannot be
  put to it yet.

## 8. First reading

    blind traces        6 / 6 PASS, held, 30 of 30 required steps
    sighted traces      6 / 6 PASS, held
    verify_tasks        234 (180 quick) · mutate_tasks 55 killed, 0 survived
    verify_audit_states 55 · mutate_audit_states 37 killed, 0 survived
    kit  77 / 77 jobs, 5,615 / 5,615 checks
    board 54 / 54 tasks, 12 / 12 traces (6 blind), 215 / 215 mutants
