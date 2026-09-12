# ADR-194 — The fourth blind trial: what the five slices were for

**Status:** accepted · **Date:** 2026-09-12 · **The last of the seven slices of `docs/PLAN-operator-api-2026-09-11.md`. The same four science pages, the same four goals, the same grader, the same floors — through the door ADR-188 to ADR-193 built, with a brief instead of a sentence. Outcomes reached rose from **53 to 82** of 112. Claims confirmed rose from **169 to 213** of 260. The whole trial cost **398 calls against 996**, and every operator finished in **one attempt** where the third took four to six. Four traces kept in `tools/traces/blind4/`. The trial also found a defect in itself: the console could not grant the rung two of its own briefs promised.**

## 1. The measurement

|  | third trial (ADR-187) | fourth trial | |
|---|---|---|---|
| outcomes reached | 53 / 112 | **82 / 112** | +55% |
| claims confirmed | 169 / 260 | **213 / 260** | +26% |
| calls, whole trial | 996 | **398** | −60% |
| attempts, whole trial | 21 | **4** | one each |

Per page, graded by `grade_outcomes` against the floors ADR-187 wrote down:

| task | reached | of | claims | of | calls | attempts |
|---|---|---|---|---|---|---|
| page-stand-sheet-science | 30 → **42** | 57 | 88 → **107** | 125 | ~290 → **123** | 6 → **1** |
| page-collection-sheet-science | 5 → **12** | 21 | 26 → **34** | 45 | 270 → **100** | 6 → **1** |
| page-pheno-tracker-science | 8 → **9** | 12 | 21 → **25** | 32 | 207 → **87** | 5 → **1** |
| page-breeding-bench-science | 10 → **19** | 22 | 34 → **47** | 58 | 229 → **88** | 4 → **1** |

Nothing about the grader, the tasks or the pages changed between the two
trials. Not one goal sentence was rewritten. The difference is the door and
the briefing, which is the only claim worth making about an API: not that it
is better designed, but that a stranger got further with it.

`verify_tasks` section F4 holds every one of these numbers, and holds them as
**floors** — the third trial's, which the fourth had to clear, and the
fourth's, which the next door has to.

## 2. What the operators actually did differently

All four took the ~100 KB snapshot **exactly once** and never again. In four
independent voices, unprompted:

> *"I re-observed the snapshot **zero** times after the first call, which is
> the number the diff was built to make possible."*

> *"An **unchanged stamp** was itself information — it told me immediately
> that those three calls were no-ops, which I would otherwise have mistaken
> for failed calls. Re-observing after each of those 87 calls would have cost
> on the order of 8 MB."*

> *"The diff showed `@Pinus contorta` moving from `pick_opt:69` to
> `pick_opt:68` — the host picker silently reordering itself. That was the
> advance warning that explained a refusal twenty calls later, and it is the
> sort of thing a re-observe would have buried in 125 KB."*

And on the session (ADR-191):

> *"The trial's headline claims are mostly claims about intermediate states,
> and only a session can show them."*

That last sentence is the whole of ADR-191 said better than ADR-191 said it. A
science task walks one control through several values — kept 10 → 50 → 200 →
10, tested 100 → 20, radius 11.28 → 5.64 → 11.28 — and every reading between
is a *transient*. With a fresh page per batch they are not merely expensive to
reach; they are unreachable.

## 3. What the trial found in itself

Two of the four briefs carry `RUNGS: … DESTRUCTIVE`, because their tasks
declare it (ADR-142: *"the goal includes undoing the last tally"*).
`blind_console.py` hard-coded the supervised three. Both operators were refused
at the goal's last step:

    forbidden: DESTRUCTIVE is not enabled for this session -- activate was
    raised from MUTATE to DESTRUCTIVE because action_btn:4 is the control
    'Clear trial' in #p-tri, and its label 'Clear trial' reads as clear

Both diagnosed it exactly — down to the lines in the console and the fact that
`Policy` reads the environment once when the session's door is spawned, so no
later batch could raise it. Both declined to press the row-removing `✕`
instead, on the reasoning that it would be raised the same way and they could
not undo it. Neither restarted the session.

This is a defect in the **trial harness**, not the door, and it was invisible
until ADR-193 started printing the rungs a task declares. `blind_console.py`
takes `--rungs` now; the default is still the supervised three, because an
operator that can wipe the store is not being supervised but trusted.

The two affected numbers in §1 are therefore **lower bounds**.

## 4. What they found in the pages

Filed, not fixed. The two the third trial already found are still open, and
both were found again independently:

- **breeding bench** — "after 10 generations" is `10 × ΔF` under a caption
  that says *compounding* (12.5% where compounding gives 11.84%).
- **collection sheet** — the field-sheet export pads reagent labels using
  entity-encoded source strings: `KOH 3&ndas`, `&alpha;-Nano`, `Syringalda`.

New this time:

- **breeding bench** — `popOut` drops the citation label into the
  mating-system slot: *"this crop is cited for this crop"*.
- **breeding bench** — roguing's "left standing" is computed from *Plants
  grown* in the Selection card, an undeclared coupling.
- **collection sheet** — the voucher label leaks `&ndash;` and is **stale**:
  it keeps only the spot tests that existed when it was made.
- **stand sheet** — with no stems, the CSV and Darwin Core copy buttons answer
  `ok: true`, `changed: false`, and produce no payload. A caller with no other
  instrument reads that as "copied".
- **pheno tracker** — the `.eco` export names a trait that scored nothing,
  implying a denominator it did not use.
- **pheno tracker** — plant buttons publish their address from their visible
  label, so `@#1—` becomes `@#15.00` then `@#14.45` as the dials move. An
  address is stable only for a control whose label is.

## 5. The gap the trial leaves open

Two operators reported it independently, and it is the honest answer to "is the
door finished":

> *"The diff is control-shaped. A `read-report`'s figures and boxes have no
> `since`, so an operator watching a computed figure must re-read the whole
> report."*

The stand-sheet operator counted fourteen `read_report` calls it would not have
needed. ADR-191 gave the *controls* a diff; the *report* has none. That is the
next slice, and it is filed rather than pretended away.

## What moved

    verify_tasks       308 → 331      mutate_contract   56 → 60 / 60
    verify_mcp          89 →  93
    blind traces        12 →  16

    outcomes reached    53 → 82 of 112        calls   996 → 398
    claims confirmed   169 → 213 of 260       attempts  21 → 4

## Held

- The fourth trial's numbers are floors in `verify_tasks`, beside the third's.
  A change to the door or the grader that lowers one is a regression with a
  name.
- Graded as a **route**, all four traces are still FAIL. A better door does not
  make a stranger take the author's steps in the author's order, which is
  ADR-187's finding standing rather than an oversight.
- The console's default is still the supervised three; the fourth rung is
  named on the command line or not granted.
- The traces are kept exactly as the server wrote them. Neither the blocked
  sessions nor their scores were re-run after the console was fixed: the
  numbers above are what the trial measured, and the fix is dated after it.
