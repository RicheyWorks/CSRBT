# The fourth blind trial — provenance (ADR-194)

Four operators, the same four science pages as the third trial (ADR-187), the
same grader, the same floors. What changed between the two trials is the door
and the briefing: ADR-188 names, ADR-189 settling, ADR-190 the manual, ADR-191
the session and the diff, ADR-193 the brief. This is the measurement those five
slices were built to move.

Run **2026-09-12**. The traces are gzipped because every response carries a
page snapshot; `gunzip -c <file>` is the trace exactly as the server wrote it.

## The conditions

Four general-purpose subagents, fresh context each, working in
`/tmp/blind4/CSRBT` — a copy of the repository with `tools/tasks/`,
`tools/traces/`, `tools/delivery/`, `tools/push/`, every ledger, the board and
its renderer, every `mutate_*.py`, the whole of `tools/verify/` except
`_kit.py` (which the door imports), and every `docs/*.md` **removed from the
filesystem**. As in ADR-136, "the operator did not see the task" is a fact
about the disk rather than a promise about anyone's attention.

Each was handed:

- its **blind brief** — `harness_tasks.py --brief <task> --blind` (ADR-193):
  the goal in prose, every value the task supplies with the control that takes
  it, and the count of readings and claims held but not what they are;
- `OPERATOR.md`, which names the door, the moves grammar, the address forms,
  the refusal vocabulary, and the session;
- `tools/blind_console.py --session op`, which holds one door open across
  invocations (ADR-191), with `SENSITIVE_READ`, `DRAFT` and `MUTATE`.

## What it measured

| task | reached (3rd → 4th) | of | claims (3rd → 4th) | of | calls 3rd | calls 4th | attempts 3rd → 4th |
|---|---|---|---|---|---|---|---|
| page-stand-sheet-science | 30 → **42** | 57 | 88 → **107** | 125 | ~290 | **123** | 6 → **1** |
| page-collection-sheet-science | 5 → **12** | 21 | 26 → **34** | 45 | 270 | **100** | 6 → **1** |
| page-pheno-tracker-science | 8 → **9** | 12 | 21 → **25** | 32 | 207 | **87** | 5 → **1** |
| page-breeding-bench-science | 10 → **19** | 22 | 34 → **47** | 58 | 229 | **88** | 4 → **1** |
| **total** | **53 → 82** | 112 | **169 → 213** | 260 | **996** | **398** | **21 → 4** |

Outcomes reached rose by **55%**, claims confirmed by **26%**, and the whole
trial cost **40%** of the calls the third did. Every operator finished in **one
attempt**: there is no "graded attempt" column here because there was nothing
to choose between.

All four took the ~100 KB snapshot **exactly once** and never again. Each says
so in its own words, and the traces bear it out: one full `observe` at the
start, then the `diff` on every result for the rest of the run.

## What it found

**The trial harness could not grant the rung its own brief promised.** Two of
the four briefs — the stand sheet's and the breeding bench's — carry
`RUNGS: … DESTRUCTIVE` because the tasks declare it (ADR-142: *"the goal
includes undoing the last tally"*). `blind_console.py` hard-coded the
supervised three and never set `CSRBT_HARNESS_ALLOW_DESTRUCTIVE`, so both
operators were refused at the goal's last step:

> `forbidden: DESTRUCTIVE is not enabled for this session -- activate was
> raised from MUTATE to DESTRUCTIVE because action_btn:4 is the control
> 'Clear trial' in #p-tri, and its label 'Clear trial' reads as clear`

Both diagnosed it exactly — down to the line numbers in the console and the
fact that `Policy` reads the environment once when the session's door is
spawned, so no later batch could raise it — and both correctly declined to
press the row-removing `✕` instead. Neither restarted the session, as
instructed.

This is a defect in the **trial harness**, not the door, and it was only
visible because ADR-193 started printing the rungs a task declares.
`blind_console.py` takes `--rungs` now; the default is still the supervised
three. The two affected numbers above are therefore **lower bounds**: the
stand sheet's `intact` and the bench's `trial` and `g163-endintact` outcomes
were unreachable under the rungs those two sessions actually held.

## What the operators found in the pages

- **breeding bench** — `popOut` drops the citation label into the
  mating-system slot for any crop with a cited population: *"…and 100 for an
  outbreeder; this crop is **cited for this crop**."* (Bean reads *"this crop
  is inbreeder"*, ungrammatical in its own right.)
- **breeding bench** — "after 10 generations" is `10 × ΔF` under a caption
  that says *compounding*: 1.25% → 12.5% where compounding gives 11.84%. The
  third trial found this too; it is still filed, still not fixed.
- **breeding bench** — roguing's "left standing" is computed from *Plants
  grown* in the Selection card, an undeclared coupling.
- **collection sheet** — the field-sheet export pads reagent labels to a fixed
  column using entity-encoded source strings, so `KOH 3&ndas`, `&alpha;-Nano`
  and `Syringalda` lose the separator. The third trial found this too. The
  voucher label leaks `&ndash;` the same way **and** is stale: it keeps only
  the spot tests that existed when it was made.
- **stand sheet** — with no stems, the CSV and Darwin Core copy buttons answer
  `ok: true` with `changed: false` and produce no payload. A caller with no
  other instrument would read that as "copied".
- **pheno tracker** — the `.eco` export's header names a trait that scored
  nothing, implying a denominator it did not use; the CSV is honest about it.
- **pheno tracker** — plant buttons publish their address from their visible
  label, so `@#1—` becomes `@#15.00` then `@#14.45` as the dials move. The
  address is stable only for controls whose label is.

None of these is fixed here; all are filed.

## What they said about the session and the diff

Unprompted and in four different voices, the same finding:

> *"I took the ~100 KB full snapshot exactly once and mined it for the rest of
> the run… I re-observed the snapshot **zero** times after the first call,
> which is the number the diff was built to make possible."* — stand sheet

> *"An **unchanged stamp** was itself information — it told me immediately that
> those three calls were no-ops, which I would otherwise have mistaken for
> failed calls. Re-observing after each of those 87 calls would have cost on
> the order of 8 MB."* — breeding bench

> *"The diff showed `@Pinus contorta` moving from `pick_opt:69` to
> `pick_opt:68` — the host picker silently reordering itself. That was the
> advance warning that explained a refusal twenty calls later, and it is the
> sort of thing a re-observe would have buried in 125 KB."* — collection sheet

And one thing the door still does not do, reported by two of them
independently: the diff is **control-shaped**. A `read-report`'s figures and
boxes have no `since`, so an operator watching a computed figure must re-read
the whole report. The stand-sheet operator counted fourteen `read_report`
calls it would not have needed. That is the next gap, and it is filed rather
than fixed.
