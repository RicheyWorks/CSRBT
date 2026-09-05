# ADR-142 — Supervised, and it still enters the data: the rungs a task declares

**Status:** accepted · **Date:** 2026-09-05 · **ADR-141 made `activate` raisable so a supervised session could press a button. It did not answer the question underneath: the task runner opened all four rungs for every task, so every "the harness can enter this data" in this kit had been measured with the wipe-the-store rung held throughout. The default is now the supervised set, a task that needs `DESTRUCTIVE` declares it with a reason and the step ids that need it, and the runner grants exactly that. Run supervised, 13 of 54 tasks failed. One was the classifier's first false positive — a data-entry page's primary tally button — and twelve were real**

## 1. The question ADR-141 left open

ADR-141's headline was that a supervised session could fill a page and commit
nothing, and it fixed the door. But `harness_walk._spawn` had written all four
rungs into every child's environment since ADR-114:

```python
env.update({..., "CSRBT_HARNESS_ALLOW_MUTATE": "true",
                 "CSRBT_HARNESS_ALLOW_DESTRUCTIVE": "true"})
```

So the 54 tasks — including the 21 science tasks that are this kit's evidence
that the harness can enter data on a data-entry page — had never been run at
the rungs an actual supervised operator holds. "The harness can enter this
data" was true of a session that could also wipe the store, and nobody could
say which of the two facts was doing the work.

## 2. Two named sets, and no leak

    WALK_RUNGS        SENSITIVE_READ, DRAFT, MUTATE, DESTRUCTIVE
    SUPERVISED_RUNGS  SENSITIVE_READ, DRAFT, MUTATE

A walk still opens everything, because a walk's job is to drive every tool a
target publishes and a walk that could not reach half of them would report a
green kit it had never touched. A **task** now runs supervised unless its own
file says otherwise.

`_spawn` also **clears** every `CSRBT_HARNESS_ALLOW_*` it inherits before
setting the ones it was given. A rung left open in the parent's environment is
a rung nobody in this process decided to open, and "supervised" cannot mean
anything if the parent's shell can widen it. That is asserted directly:
`verify_walk` opens a supervised wire with `CSRBT_HARNESS_ALLOW_DESTRUCTIVE=true`
set in its own environment and requires the child to refuse.

## 3. Run supervised: 13 of 54 failed

Every one failed on exactly one step, and the step ids say what they are:
`tclear`, `reset` ×3, `undo` ×3, `refuseWipe`, `rm`, `rebuild`, `wipe`, `a0`.

Twelve are genuine: the goal itself includes removing something — the
greenhouse's *Clear all runs* (the goal is that wiping the runs makes
`runChart` disappear from the report), the food web's *Undo*, the character
keys' *Start over*, the tree visualizer's *Clear*. Those twelve now declare it:

```json
"policy": {"allow": ["SENSITIVE_READ", "DRAFT", "MUTATE", "DESTRUCTIVE"],
           "needs": ["refuseWipe"],
           "why": "the goal is that wiping the runs REMOVES runChart from the report: runWipe is 'Clear all runs'"}
```

`needs` names step ids, and they are checked against the task's own steps: a
reason with no step named is a sentence, and a step id is a thing a reader can
go and look at — one that rots visibly when the step is renamed.

**42 of 54 tasks enter their data with no destructive rung at all**, and the
board carries that number beside "tasks held".

## 4. The thirteenth: the classifier's first false positive

`page-field-notebook-science` failed at `a0`, activating `specGrid#0`. That
control is the field notebook's **tally chip**, and it is one button:

```js
b.innerHTML = '<span class="x" data-x="'+idx+'">✕</span>'
            + '<div class="name">'+esc(it.name)+'</div>'
            + '<div class="count">'+it.n+'</div>';
b.addEventListener("click", function(ev){
  if (ev.target && ev.target.dataset && ev.target.dataset.x !== undefined) { …delete…; return; }
  it.n++;  …
});
```

Clicking the button increments the tally. Clicking the little ✕ *inside* it
deletes the row. ADR-141's label read the whole button — `✕ clover 3` — saw a
removal mark at the start, and raised the **primary data-entry control of a
data-entry page** to `DESTRUCTIVE`. Exactly the failure mode ADR-141 said it was
accepting in the safe direction, found on the first page that used the pattern.

The rule that fixes it is the one already there for `<small>` and `<kbd>`: the
name of a control is not the name of a smaller control living inside it.
`LABEL_FN` now strips `[data-x]` and `.x` children, and the button reads
`clover 3`.

Re-measured across all 41 routed pages, with the same tool that produced
ADR-141's figures:

| | ADR-141 | now |
|---|---:|---:|
| activatable controls | 1,453 | 1,453 |
| raised to `DESTRUCTIVE` | 110 | **99** |
| distinct raised labels | 34 | **23** |

The eleven that left were all tally chips (`✕honeybee0`, `✕forage0`, …) on the
three pages that use the pattern. Every one of the 23 that remain names a
removal.

## 5. What is now asserted

`verify_tasks` **282** (+48): the supervised default; a declared policy granted
exactly and in ladder order; `DESTRUCTIVE` refused without a reason, refused
without `needs`, refused when `needs` names a step that does not exist; a rung
outside the ladder refused; an empty allow list refused; the ledger recording
the rungs per task, and the reason wherever the fourth is open.

The check that matters most is the one that runs something: a task that never
declared the fourth rung and reaches for it is **refused by the door**. Without
it, a runner that read the declaration and then ignored it would have passed
every other check in this section — which is precisely the mutant that now dies.

`verify_walk` **126** (+5): the two named sets, the supervised wire, the
environment that does not leak into it, the withheld tool, and the refusal.

`mutate_tasks` **62** (+7), 62 killed, 0 survived. `verify_report` **79**,
`mutate_report` 50 killed — the label change is covered by the fixture that
already carried a chip.

## 6. Held

- **Supervised is not sandboxed.** `MUTATE` still writes: a supervised session
  can enter wrong data, overwrite a field, or fill a sheet with nonsense. What
  it cannot do is press the buttons this kit's pages use to destroy work.
- **The twelve declarations are self-reported.** A task could open the rung it
  does not need and the reason would still read plausibly. What stops that is
  cheap and partial: `needs` must name a real step, and the ledger prints the
  reason beside the task, so an unearned declaration is visible rather than
  hidden in a runner's environment.
- **The classifier still reads names.** It has been wrong once, in the
  direction it was designed to be wrong in, and one page pattern was enough to
  find it. A second pattern would find a second one.
- **The walk still opens everything**, so a walk is not evidence about
  supervision — only the tasks are.
- Two contention flakes named in ADR-141 (`verify_organism`'s two physicals,
  `audit_targets`' never-measured control) are **not** addressed here; they
  remain the next slice, and a tool to measure flake rate under named load is
  drafted.

## 7. First reading

    default             a task runs supervised: SENSITIVE_READ, DRAFT, MUTATE
    declared            12 of 54 tasks open DESTRUCTIVE, each with a reason and its steps
    supervised          42 of 54 enter their data with no destructive rung
    classifier          99 of 1,453 activatable controls raise (was 110); 23 distinct labels
    verify_tasks        282 / 282  ·  mutate_tasks 62 killed, 0 survived
    verify_walk         126 / 126
