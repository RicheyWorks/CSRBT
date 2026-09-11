# The third blind trial — provenance (ADR-187)

The six traces in `tools/traces/blind/` were the first blind trial (ADR-136);
the five in `blind2/` the second (ADR-141), which found a door that could not
press a button and was not graded. These four are the third, run
**2026-09-10** against the door as it stands (protocol 1.5, ADR-141's fixes
in), and they ARE graded — by outcomes, which is the instrument this trial
added. The files are gzipped because every response carries a page snapshot;
`gunzip -c <file>` is the trace exactly as the server wrote it.

## The conditions

Four general-purpose subagents, fresh context each, working in
`/tmp/blind3/CSRBT` — a copy of the repo with `tools/tasks/`, `tools/traces/`,
`tools/task_ledger.json`, `tools/delivery/`, the delivery ledger, the board,
every `docs/ADR-*.md`, every `CHANGELOG-*`, `AI_HARNESS.md`,
`AUTOMATION-HARNESS.md` and `PLAN-*.md` **removed from the filesystem**. Each
was given one task's `goal` sentence verbatim and a briefing
(`/tmp/blind3/OPERATOR.md`, reproduced in ADR-187) that named the door —
`tools/blind_console.py --target page --page <page> --moves <file> --trace
<file>` — and the rungs: `SENSITIVE_READ`, `DRAFT`, `MUTATE` allowed,
`DESTRUCTIVE` withheld, a supervised operator. Each run of the console is a
fresh page, so an operator plans a whole moves file, runs it, reads every
answer and runs again under the next attempt number; the trace file appends,
so every attempt has its own. **The trace kept here is each operator's last
attempt**; the earlier ones are the operator's discovery and are not the
subject.

| task | attempts | calls in the graded attempt | read the page source? |
|---|---|---|---|
| page-stand-sheet-science | 6 (≈290 calls in all) | 89 | no |
| page-collection-sheet-science | 6 (270 in all) | 74 | no |
| page-pheno-tracker-science | 5 (207 in all) | 73 | no |
| page-breeding-bench-science | 4 (229 in all) | 86 | no |

## What the operators reported

All four reported reaching **every figure the goal sentence names**, and
quoted the door's values for them: stems/ha 100, BA 6.9, QMD 29.7, SDI 132,
IV 78.6/21.4, EF 100.1, 134.7 m³/ha, 47 m and 5406 m; Chao1 6.5, H′ 1.359,
J′ 0.845, 0.50 per 100 m², 3.3 per hour, all eight reagents on RCW-2026-041;
S +1.44, χ² 0.00 against 3:1, two exports and exactly one print; Nₑ 40 and
150, i 1.755, R 6.14, 85 rogued, LSD 1.51, 85.0% ± 3.6%. Two of them ran
their own oracle beside the page and one found a page defect by it: the
breeding bench prints "after 10 generations" as 10 × ΔF (12.5%) under a
caption that says *compounding* (11.8%). The collection-sheet operator found
the field-sheet export truncating reagent labels to ten characters before
decoding entities (`KOH 3&ndas`). Neither is fixed here; both are filed.

Nothing was unreachable under the supervised rungs. The two goals that end in
a DESTRUCTIVE press (Undo on the stand sheet, Clear trial on the bench) were
reached up to that press; the operators reported the refusal as correct and
did not escalate.

## Why they are graded by outcomes

`--grade-trace` holds a trace to a task's steps: every step required, in
order, the author's arguments. Graded that way the four are UNMET at steps 5, 23, 8 and 16 of scripts 73 to
165 long, because the operator opened another pane first, typed another site
name, or scored a different plant. So `harness_tasks.py --grade-trace tools/traces/blind3 --outcomes`
asks the other question — of the readings the task holds (every step that
reads the page and claims something), how many did this trace reach, in any
order, by any route — and gives partial credit per claim:

    page-breeding-bench-science          PARTIAL  outcomes reached 10 of 22, claims 34 of 58, by 86 call(s)
    page-collection-sheet-science        PARTIAL  outcomes reached  5 of 21, claims 26 of 45, by 74 call(s)
    page-pheno-tracker-science           PARTIAL  outcomes reached  8 of 12, claims 21 of 32, by 73 call(s)
    page-stand-sheet-science             PARTIAL  outcomes reached 30 of 57, claims 88 of 125, by 89 call(s)

The misses are not the operators'. Reading them one by one: the collection
sheet's task holds a 32 mm rain event, a 36 m GPS uncertainty, a site named
Bear Creek and a note "Cap viscid when wet" — none of which the goal
sentence mentions. The tasks hold more than their goals state, and an
operator given the goal cannot reach what it was never told. The outcome
grade therefore measures the distance between a task and its goal sentence
as much as it measures the operator, and the four numbers above are floors
the suite holds: a goal widened to say what its task holds should raise them.

## What the door made hard, converging across four operators

1. **Selectors still renumber, silently.** `action_btn:N` is a flat index
   over the page; a filtered species list, a loaded pack, every tallied stem,
   every added chip shifts everything after it. All four re-observed after
   each structural change and computed offsets by hand; two pressed the wrong
   button once each on the way (ADR-141's raise caught the destructive ones).
   Every operator noticed that stable ids exist (`tAdd`, `iAdd`, `pSave`,
   `traitAdd`) and that **no tool accepts them**. `@control:<name>` is
   resolved by the task runner, not by the door.
2. **A fresh page has no controls until something has looked at it.** A first
   move of `pick` or `activate` was refused as "no such control at all", and
   once escalated to DESTRUCTIVE because the selector named nothing; a leading
   `observe` fixed it. The door should settle the page before its first
   action, and an unresolvable selector is a `not_found`, not a rung.
3. **Pools undersell.** The snapshot lists six picker options of twenty-eight
   and `pick` accepts the rest.
4. **Controls without names.** Eight reagent fields with `id: null` and a
   placeholder for a label, distinguishable only by DOM order; twenty dial
   buttons labelled 1–5 whose trait is only inferable from grouping.
5. **Box text is concatenated without separators** (`bean, common20you plan
   to keep20`); the `figures` and `by` maps are the only clean read.
6. **The scoring rules are not stated anywhere the door shows** (weighted mean
   over the sum of weights; keepers' mean minus run mean) — the pheno
   operator recovered them by experiment.
