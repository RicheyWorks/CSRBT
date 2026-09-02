# ADR-126 — The first trace

**Status:** accepted · **Date:** 2026-09-02 · **A model plugged in over MCP, given the goal and not the steps, and graded by the same expectations — the program's stated end, reached once**

## 1. The customer the grader was built for

ADR-125's tasks grade an operator who is handed the steps. The operator the
program was always for — "later robots, AI etc. can be plugged into the
harness" — is handed the *goal*. It plans; it looks around; it takes a
different key, a different lag, one more `observe` than the task's author
did; and whether it accomplished the goal is the question. ADR-125 §5 held
that as the next customer. This ADR is that customer's first visit, with the
two instruments it needed and what it found in them.

## 2. The decision

**The trace.** `harness_mcp.py --trace FILE` (or `CSRBT_HARNESS_TRACE`)
appends one JSON line per `tools/call` — the action, the arguments, the
gateway's whole response, refusals included — and per `resources/read` (an
`observe` entry with the snapshot). It is what the operator did, in the
operator's order, on the record.

**The trace grader.** `harness_tasks.py --grade-trace FILE | all` holds a
trace to a task: the **required** steps in order, each satisfied by the
next unused call with its action whose expectations all CONFIRM (references
resolve against the calls that satisfied earlier steps; `"$.path"` is the
response's own); then the **optional** probes — a `not_found` sent on
purpose, a link expected to refuse — anywhere in what is left. A step no
call satisfies is UNMET and fails; a probe no call satisfies is SKIPPED. One
call satisfies one step. Calls the task did not ask for are allowed and
counted: an operator may look around, and its economy is beside its
verdict. A step whose action is `observe` is an operator's move too, in
tasks and in traces. Grades land in the ledger as `<task>@trace`.

**The visit.** For each of the six real tasks the assistant of this session
was given the goal sentence and `tools/list`, planned its own calls, and
drove the door with the trace on. `tools/traces/PROVENANCE.md` says exactly
what it was and was not given.

## 3. What the first grading found

**Two of six.** Every miss was the *instrument's*, and each one is now a
rule:

- **`snapshot.chaosCrashes` on a `pulse` step** — the author's way of
  checking the crash counter. The operator checked it by reading the
  snapshot resource, which was not a call and not in the trace. Observations
  are recorded now, and a task step may be `observe`.
- **`replicaLagMs == 200`** when the goal says "hold the replica behind".
  The operator chose 150. Over-specified: `> 0` now. Likewise `entries ==
  5` where the goal says "every key back" and the operator wrote eight —
  the step now says `entries == $.snapshot.size`, a relation the author
  does not have to know a number for; `first == 10`, `last == 90` became
  probes.
- **The task's own probes stealing the operator's calls.** The page task's
  optional look-around (`read-page`) matched the operator's only
  `read-page`, and the required "invariants intact" step after it had none
  left. Required steps are matched first now; probes take only what is
  left; and one call satisfies one step (before that, the optional
  wire-count matched the same call as the direct count).

Then **six of six**, with the operator's economy on the record: the crash
road in 8 calls for 8 required steps, the preserve road in 7 for 6, the
cold recovery in 13 for 7 (it read `first`, `last` and `recovery`
separately; engine 2 chose `network.oddeven` for eight keys), the page in 3
for 3.

## 4. What it means, and does not

It means the pipeline is closed: a goal in a file, a door a model speaks,
a trace of what it did, a grader that says whether the goal was met and how
much it cost, a ledger that keeps the answer. It does not mean a blind
trial: the same session wrote the tasks that morning. The traces say so in
their provenance, and the grader does not care who made them — a trace from
a different model tomorrow is graded by the same file.

## 5. Numbers

`verify_tasks` 48 → **70** (section F: the grader on a synthetic trace —
order, one call per step, probes after required steps, self-references, a
failure never satisfying a step that did not ask for one; the MCP server
recording calls, refusals and observations in-process; the canary graded
FAIL from a trace and held; the six committed traces PASS with arguments
that differ from the tasks'; the ledger's `@trace` entries). `mutate_tasks`
10 → **16 killed, 0 survived** (expectations unread, order ignored, one
call for two steps, an unasked failure satisfying, UNMET not failing, the
recorder silenced). Ledger: 8 runs + 6 traces, all held.

## 6. Held

- A blind trial: a model that did not write the tasks. The instrument is
  ready; the operator is not in this sandbox.
- A trace records what the gateway answered, not what the model *said* —
  its reasoning, its retries at the JSON-RPC layer, its tool-list reads. A
  host's own transcript is the other half; this file is the half the
  harness can vouch for.
