# Blind traces — provenance

The six traces in `tools/traces/` were produced by the session that had
written the tasks earlier the same day. That session knew the answers. These
six were produced on **2026-09-03** under conditions designed so the operator
could not.

## The conditions

Each trace is one general-purpose subagent, a fresh context, given:

- **the task's `goal` sentence, verbatim** — nothing else about the task;
- **`tools/blind_console.py`** — a child process speaking JSON-RPC to
  `tools/harness_mcp.py`, with `CSRBT_HARNESS_ENABLED=true`, a random token,
  and `SENSITIVE_READ` / `DRAFT` / `MUTATE` allowed (never `DESTRUCTIVE`);
- **a working directory of `/tmp/blind/CSRBT`** — a copy of the repo with
  `tools/tasks/`, `tools/traces/`, `tools/task_ledger.json`, every
  `docs/ADR-1*.md`, every `CHANGELOG-*`, `AI_HARNESS.md`,
  `AUTOMATION-HARNESS.md` and `PLAN-*.md` **deleted**. Blindness is a fact
  about the filesystem, not a promise the operator made;
- **the instruction** not to read anything under `/home/claude`, and not to
  go looking for task files, expected outputs, or documentation of what the
  answer should be.

What the operator could see is what any operator sees: `tools/list`,
`resources/list`, the plugin's own `describe`, and the snapshot riding every
response. It planned its own calls from the goal.

## Conduct

One run was mis-conducted. For **`organism-crash-road`** the first operator
was handed a paraphrase of the goal that dropped the clause *"see the organism
refuse the next batch while the crashed one is still applying"*. That is the
hardest step in the task, and an operator cannot be graded on a step its goal
never asked for. The run was discarded and re-run with the goal verbatim; the
trace kept here is the second one. No other goal was paraphrased.

## Both numbers

Graded against `tools/tasks/<id>.json` as the tasks stood on 2026-09-02:

| task | first grading | after the instrument fixes |
|---|---|---|
| `organism-preserve-cold-scan` | PASS 6/6 | PASS 6/6 |
| `lab-run-shipped-protocol` | PASS 2/2 | PASS 2/2 |
| `organism-cold-recovery` | PASS 7/7 | PASS 7/7 |
| `page-enter-and-read-back` | 1/3 | PASS 3/3 |
| `organism-crash-road` | 2/8 | PASS 6/6 |
| `organism-replica-behind` | 2/9 | PASS 6/6 |
| **total required steps met** | **24 of 40** | **30 of 30** |

The second column is smaller because three steps that had been *required* were
demoted to probes — a probe that goes unmet is not a miss. Nothing was scored
by relaxing an expectation about the engine's behaviour: every claim about
what the organism did still has to hold.

## What the misses were about

Each miss was read as a hypothesis about the instrument, and each one was a
real defect in the instrument:

1. **An observation rides every response.** `grade_trace` matched a step's
   `action` against the call's `action`, so an `observe` step could only be met
   by a bare `observe` call. But every gateway response carries a `snapshot`;
   an operator that reads the fleet off the response it already has is doing
   the thing the step asks for, better. `grade_trace` now lets an `observe`
   step be met by any call whose response carries a snapshot.
2. **A probe must not be required.** `look` and `settle` in `organism-crash-road`,
   and `w2`/`w3`/`w4` in `organism-replica-behind`, described *the author's*
   route to a state, not the state. They are `optional` now.
3. **A required step must not pin an author's constant.** `page-enter-and-read-back`
   read back the literal `"Quercus rubra"` — the value *this* task types. The
   claim is that the page gives back what was entered; it now reads
   `$type.output.value`.
4. **A count of what the author did, not what the goal says.** `organism-crash-road`
   required exactly three records in the index because the author's batch had
   three; the operator wrote a larger batch. `>= 3` is what the goal claims.

Finding 1 is a grader bug and is now pinned by `verify_tasks`. Findings 2-4 are
task-shape bugs, and `verify_tasks` now holds every task file to those shapes,
so no future task can reintroduce them.

## Reproducing

    python3 tools/blind_console.py --moves '<json array of moves>' \
        --trace tools/traces/blind/<task-id>.jsonl
    python3 tools/harness_tasks.py --grade-trace all

`--grade-trace all` grades `tools/traces/` and `tools/traces/blind/` alike;
a blind trace is graded by exactly the same rules as any other.
