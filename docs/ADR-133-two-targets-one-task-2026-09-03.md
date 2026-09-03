# ADR-133 — Two targets, one task: the science engine and the page, held to each other

**Status:** accepted · **Date:** 2026-09-03 · **A task's steps may each name their own target. The first two-target task runs the shipped protocol through the science engine and holds the kit page's workbench figures to the engine's own — two independent implementations of the same statistics, agreeing across one run.**

## 1. What ADR-125 left

> Tasks are sequential and single-target. A task that needs two targets (write
> through the organism, look through a page) has no shape yet.

That is the shape of every real operator workflow, and until a task can do it
the harness cannot stand in for one. It is also the only shape in which the kit
can check the thing it most wants checked: that two instruments which compute
the same science **agree**.

## 2. The decision

### A step may name its target

A step gains an optional `target`. The runner opens each target the task
names — its own plus every step's — **once**, keeps them for the task's life,
and closes them in the reverse of the order it opened them. References resolve
across targets: `$run.output.session.entered.0.shannon` is the engine's figure,
and the step that uses it is talking to the page. A step with no target uses
the task's own, which is every task written before this one.

Two failures are the **task's**, not any target's: naming a target that does
not exist, and (for a caller that hands the runner an incomplete set of wires)
naming one nobody opened. Both are `DEFECT`, and `two-targets-canary` is
written to be one — a third kind of canary beside the two that must `FAIL`.

### `~=`, because two instruments do not print the same string

The engine reports `1.227621`. The page shows `1.23`, because that is what a
reader needs. The claim is that they **agree**, and the grammar could not say
it: `==` is false, and `contains` is a coincidence waiting to happen.

`~=` takes a `value` and a **required** `tolerance`. No default — a default
would be the task runner deciding how close two instruments have to be, which
is the task's claim and nobody else's: a page that rounds to two decimals
agrees to 0.005, and a page that rounds to a whole number does not.

### The two tasks

**`two-targets-lab-and-page`** — the science claim. Run `sample-experiment`
through the lab engine; enter *the same five species and counts* into
`ecology-lab.html`'s workbench; hold the page's `species`, `Shannon H′`,
`evenness J′` and `Chao1 est.` to the engine's `session.entered[0]`. A Java
engine and a page's JavaScript, written separately, computing the same four
statistics from the same field data. They agree — 16 expectations confirmed.

**`two-targets-isolated`** — the machinery claim. Write through the organism,
crash the fixture, then read the organism back: the write is still there, its
meters still moved, and the fixture's failure never touched them. Each target
kept its own session.

Writing them turned up two things worth naming. The workbench figure is
labelled `Chao1 est.` — **with a trailing dot** — so its path has to escape it
(`Chao1 est\.`) or it splits inside the label. And `held` was hard-coded
`False` on the path where a target cannot be opened, which made the one canary
that reaches that path unholdable; `held` is `verdict == must` everywhere now,
and every ledger entry names its transport, that path's included.

## 3. Verification

`verify_tasks` **203** (+18). The multi-target section holds the runner without
a browser or a JVM: a fake wire per target records what it was asked, so the
checks are about the *runner* — that each step went to the wire its target
names under that target's plugin id, that a reference crosses targets, that the
ledger entry names every target the task used and not just the one it declares,
that a step naming an unopened target is the task's defect, and that every wire
is closed in the reverse of the order it was opened. Then, through `run_tasks`:
an unknown target is a `DEFECT` whose message says so, and a canary written to
be one is **held** when it defects. Plus `~=`: it holds a rounded figure to a
full one, the tolerance is the claim (too tight and it is refuted), a missing
tolerance is a defect, and a value that is not a number is refuted rather than
a crash.

`mutate_tasks` **41** (+10): the step's target ignored, an unopened target
quietly answered by the task's own, the ledger naming one target, only the
declared target opened, an unknown target not a defect, the targets closed in
the wrong order, a target never closed, `~=` given a default tolerance, `~=`
asking for equality, and `held` hard-coded false.

Ledger: **53 tasks, 53 held.**

    verify_tasks 203 / 203 · mutate_tasks 41 killed, 0 survived
    kit  77 / 77 jobs, 5,562 / 5,562 checks

## 4. Held

- The two targets run in one process each, sequentially. A task that needs them
  *concurrently* — write while reading — has no shape, and probably should not.
- `~=` compares numbers. Two instruments that disagree about a *string* (a
  verdict, a name) still need `==`.
- Timing is still not an expectation (ADR-125).
