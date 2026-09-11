# ADR-187 — Outcomes, not routes: the third blind trial, and a grader that asks what the operator reached

**Status:** accepted · **Date:** 2026-09-11 · **Four fresh operators, given one science page each and nothing but the goal sentence, drove the door as it stands and reported reaching every figure their goal names — and graded as traces all four are UNMET at step 5, 23, 8 and 16 of scripts 73 to 165 long. The failure is the question, not the operator: a science task is a script, and holding an operator to an author's route measures obedience. `--grade-trace --outcomes` asks the other question — of the readings this task holds the page to, how many did this trace reach, in any order, by any route, with partial credit per claim — and answers it with four numbers the suite now holds as floors: 30 of 57, 10 of 22, 8 of 12, 5 of 21. The misses are almost all the same thing, and it is a finding about the tasks: they hold more than their goals say. `verify_tasks` 293 → 308, `mutate_tasks` 67 → 73; the four traces and their conditions are in `tools/traces/blind3/`.**

## 1. The trial

ADR-136 ran the first blind trial on the organism, the lab and one page, and
every miss it found was a defect in the instrument. ADR-141 ran the second on
the science pages and found a door that could not press a button; its five
traces were never graded, because the door they recorded no longer exists.
Everything since has been checked by scripts. This is the third, against the
door as it stands.

Four general-purpose subagents, fresh context each, in a copy of the repo with
`tools/tasks/`, `tools/traces/`, the task ledger, `tools/delivery/`, the
delivery ledger, the board, every `docs/ADR-*.md`, every changelog and both
harness guides **removed from the filesystem**. Each was given one task's
`goal` sentence verbatim, a briefing that named the door and forbade looking
for the answer key, and `tools/blind_console.py` with `SENSITIVE_READ`,
`DRAFT` and `MUTATE` allowed and `DESTRUCTIVE` withheld — a supervised
operator. The pages: stand sheet, collection sheet, pheno tracker, breeding
bench. `tools/traces/blind3/PROVENANCE.md` carries the conditions, the
attempt counts and what each operator reported.

They reached it. Every figure in every goal sentence, quoted back from the
door: 100 stems/ha, 6.9 m²/ha, QMD 29.7, SDI 132, IV 78.6 against 21.4, EF
100.1, 134.7 m³/ha, 47 m and 5406 m of coordinate uncertainty; Chao1 6.5,
H′ 1.359, J′ 0.845, all eight reagents on RCW-2026-041; S +1.44, χ² 0.00
against 3:1, two exports and exactly one print; Nₑ 40 and 150, i 1.755,
R 6.14, LSD 1.51, 85.0% ± 3.6%. Two ran their own oracle beside the page.
Nothing in any goal was unreachable under the supervised rungs, and both
goals that end in a DESTRUCTIVE press were driven up to it and stopped —
the refusal reported as correct, no escalation. That is the answer to
ADR-141: the door can be operated.

It cost 4 to 6 attempts and 200 to 290 calls each to land 73 to 89.
Section 4 is what that bought.

## 2. Why the grade had to change

`grade_trace` matches a task's required steps in order, each by the next
unused call, and stops at the first that nothing satisfies. Against these
traces it stops almost immediately: the breeding-bench operator opened
another pane first, the collection-sheet operator typed another site name,
the pheno operator scored a different plant. Every one of those is a
different route to the same reading.

A task, written for the runner, is a script: every step required, in the
author's order, with the author's arguments. That is the right shape for
holding a page to itself — it is how 44 science tasks catch a page that
changed what it prints. It is the wrong shape for measuring an operator.
Grading a route as if it were a goal does not measure whether the goal was
achievable; it measures whether the operator guessed the author's keystrokes.

So the grader gained a second question, and the tasks did not change at all.

## 3. What `--outcomes` is

    python3 tools/harness_tasks.py --grade-trace tools/traces/blind3 --outcomes

**An outcome is a reading with a claim.** `outcomes_of(task)` keeps every step
whose action reads — `read-report`, `read-control`, `read-page`,
`read-dialogs`, `collect-output`, `observe` — and which claims something
beyond `ok` about what it read. Entry steps are dropped: *type 30 into the
DBH box* is a route. A bare `read-page` asserting only `ok` is dropped: it
claims nothing. What survives is the part of the script that is the goal —
what the page must be read to say.

**Order-free, with partial credit.** Each outcome is offered every call of its
action, in any order, each call considered whole and on its own; the call that
confirms the most of its claims is the one recorded. An outcome is REACHED
when one call confirms all of its claims, and the best count is kept either
way — a readout where the operator got nine figures of ten is not scored as
if it had reached none. A claim that refers to another step's answer
(`$step.path`) has no step to refer to here and counts unreachable rather
than confirmed; that is honest, and it is why the fixture in `verify_tasks`
carries one.

**It writes nothing.** No ledger entry, no board row. An operator's score is
not the page's, and a number that moves when a stranger drives badly does not
belong in the ledger the board renders. The command exits non-zero while any
trace is short of PASS, so it can gate without recording.

The four traces:

    page-breeding-bench-science    PARTIAL  outcomes reached 10 of 22, claims 34 of 58, by 86 call(s)
    page-collection-sheet-science  PARTIAL  outcomes reached  5 of 21, claims 26 of 45, by 74 call(s)
    page-pheno-tracker-science     PARTIAL  outcomes reached  8 of 12, claims 21 of 32, by 73 call(s)
    page-stand-sheet-science       PARTIAL  outcomes reached 30 of 57, claims 88 of 125, by 89 call(s)

## 4. What the numbers say, and it is not about the operators

Read the collection sheet's sixteen misses one at a time and they are one
thing: a 32 mm rain event, a 36 m and a 5395 m GPS uncertainty, a site called
Bear Creek, a habitat string naming four conifers, a note reading "Cap viscid
when wet", a print note containing "white". **None of those appears in the
goal sentence.** The task holds them because its author drove the page and
wrote down what it said. The operator was told to record a search, five
collections and eight reagents, and did exactly that.

So the outcome grade measures two distances at once: how well an operator can
drive the door, and how far a task's claims exceed the sentence that is
supposed to describe them. The four numbers are floors in `verify_tasks`
precisely so that closing the second gap shows up as a rise. A goal widened
to say what its task holds should raise them; a grader change that lowers one
is a regression. That work is ADR-193 in
`docs/PLAN-operator-api-2026-09-11.md`.

## 5. What the operators found about the door

Converging, without seeing each other's work — the same shape as ADR-141,
which is what makes it evidence:

1. **Selectors renumber, silently.** `action_btn:N` indexes the whole page: a
   filtered species list, a loaded pack, each tallied stem, each added chip
   shifts everything after it. All four re-observed after every structural
   change and computed offsets by hand; two pressed a wrong button on the way.
   Every one of them noticed that stable ids exist — `tAdd`, `iAdd`, `pSave`,
   `traitAdd`, published in the snapshot as `id` — and that **no tool accepts
   them**. `@control:<name>` is resolved by the task runner, on the far side of
   the door the operator is speaking through.
2. **A fresh page has no controls until something looks at it.** A first move
   of `pick` or `activate` is refused "no such control at all" — and once,
   escalated to DESTRUCTIVE because the selector named nothing, which turns a
   staleness error into a permissions error. A leading `observe` fixes it,
   and should not be needed.
3. **Pools undersell.** Six picker options published of twenty-eight, and
   `pick` accepts the rest.
4. **Controls without names.** Eight reagent fields with `id: null` and a
   placeholder for a label, told apart only by DOM order; twenty dial buttons
   labelled 1–5 whose trait is inferable only from grouping.
5. **Box text is concatenated without separators** (`bean, common20you plan to
   keep20`), so `figures` and `by` are the only clean read.
6. **The page's own rules are not at the door.** The pheno tracker prints its
   scoring formula on the page; the operator recovered it by experiment.

Each is a line in the plan: ADR-188 addresses 1, ADR-189 addresses 2,
ADR-190 addresses 3–6.

## 6. Two page defects, filed not fixed

The breeding bench prints "after 10 generations" as ten times ΔF (12.5% for
the bean) under a caption that says *compounding* (11.8%); the corn hides it
because 3.3% is the same either way. The collection sheet's field-sheet export
truncates reagent labels to ten characters before decoding entities, so KOH
prints as `KOH 3&ndas`. Both were found by operators running their own
arithmetic beside the page, which is what a blind trial is for. Neither is
this slice: a page edit needs its own republish, and mixing one into the
slice that measured it would make the measurement unreproducible.

## What moved

    verify_tasks                 293 → 308      mutate_tasks   67 → 73 / 73
    tools/traces/blind3/         4 traces + PROVENANCE (new)
    harness_tasks.py             outcomes_of, grade_outcomes, --outcomes, .gz traces

One grader, one suite, one runner, four traces, one plan. No page and no task
was edited.

## Held

- The outcome grade is a measurement of an operator, not of the kit. It is not
  in the ledger, not on the board, and `verify_tasks` holds it only as floors
  and as the grader's own behaviour on a fixture.
- Partial credit is per claim, not per figure: a step claiming one thing is
  worth as much as a step claiming ten. The claim counts are printed beside
  the outcome counts so the shape is visible.
- An outcome reached by a call that also failed other steps' claims still
  counts: calls are not consumed. Two outcomes may be met by the same
  `read-report`, which is right — one look can confirm two readings — and it
  means the count is of readings reached, not of work done.
- The traces are each operator's LAST attempt. The earlier attempts are
  discovery and are not kept; the attempt counts are in the provenance, and
  they are the honest cost.
- This trial was four pages of forty-four. The other forty science tasks have
  still never faced an operator.
