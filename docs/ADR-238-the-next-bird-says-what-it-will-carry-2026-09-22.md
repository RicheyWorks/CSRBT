# ADR-238 — the next bird says what it will carry

**Date:** 2026-09-22 · **Status:** accepted · **Chain:** ADR-237 → this ·
**Protocol:** 1.11 (unchanged)

## Why

The eighth blind trial (ADR-230) filed one defect on the selection log, and
it cost most of that page's miss. The operator pressed **adult** for the
third bird while *adult* was still selected from the second. The press
**cleared** the dial, and A3 was logged with no age. Nothing on the page said
so. Nothing supervised could undo it either, because the row's ✕ and Undo are
destructive.

Both behaviours involved are right on their own:

- **The dials carry forward** from one individual to the next, because a
  morning of adults is a morning of adults.
- **A dial pressed while it is already selected clears itself**, which is how
  a mistaken press is taken back. This is the kit-wide FEK dial (`clearable`).

Put together, they made a trap nobody could see. The fix is not to take away
either behaviour. It is to make the page say what the next individual will be
logged as.

The task held none of it. It pressed M and adult once, added six birds, and
never read what a seventh press would do.

## Decision

- **`indNote`**, a live line under the sex and age dials, reads *"The next
  individual will be logged as: sex M · age class adult."* It is shown from
  the first paint and after every press, add and restore. An unset field reads
  **not recorded**, which is not the same as *unknown*. The page already made
  that distinction in its help text, and now it makes it in the state too.
- **A press that clears a dial says so in words:** *"You cleared age class by
  tapping adult while it was selected, so the next individual will be logged
  with no age class. Tap a value to record one."* Switching from one value to
  another is a change, not a clear, and is not reported as one. The warning
  goes away once an individual has been added.
- **The add confirmation names what the record is missing:** *"Added A2 — no
  age class recorded"* or *"Added A3 — no sex or age class recorded"*. When
  nothing is missing it reads plain *"Added A1"*.
- **A restored sheet** shows what its restored dials will carry, and never
  reports a clear it did not witness.
- **The fix is in the page, not in FEK.** Every FEK dial clears on a re-press,
  on 27 pages. A kit-wide *"you cleared it"* would mean re-emitting and
  republishing all of them, for a behaviour only this page's carry-forward
  made dangerous. It is held on a trigger, below.

`indNote` matches the reader's `*Note` box convention, so `read-report` serves
it. The first name tried, `indNext`, matched no convention, and the task's
first run read it as `None`.

## Held by

- **The task** (`page-selection-log-science`) goes from 133 to 138 confirmed.
  After M and adult it holds the next-individual line. It then presses adult
  again and holds the *cleared* sentence word for word, then presses it once
  more and holds the restored line. The six birds and everything downstream
  are unchanged. The goal says so.
- **`verify_sel`** goes from 83 to **95**, run in a fresh context. It checks
  the empty sheet, set values, a plain confirmation that carries forward, and
  the trap said word for word. A2's confirmation must name its missing age.
  **The record KEEP's snapshot holds must really have A1 adult and A2 with no
  age**, so the sentence is checked against the data, not just beside it. The
  suite also checks that the warning goes after an add, that a switch is not
  a clear, that a sex clear names *sex*, that both missing fields are named
  together, and that a restored sheet shows its restored dials.
- **New runner `tools/mutate_sel.py`**, on the board, has 8 mutants. They
  cover a clear never noticed, a switch called a clear, the held value never
  remembered, the confirmation naming nothing, a missing sex not counted, the
  warning outliving the add, the field names swapped, and a restore left at
  boot state. **All 8 killed.**

## Numbers

| | before | after |
|---|---|---|
| page-selection-log-science | 133 confirmed | **138** |
| verify_sel | 83 | **95** |
| mutate_sel | — | **8**, all killed |

## Held

- **A kit-wide "you cleared it" in the FEK dial.** Trigger: a second page
  where a re-press on a carried-forward dial costs a record. Price: re-emitting
  and republishing 27 pages.
- **The selection log's toast keeps its words after it fades**, as the
  ordination page's did (ADR-237). It is not filed against this page. Trigger:
  an operator misled by it.
- **The remaining pages' filed defects:** field notebook, ethogram, relevé,
  pheno tracker, stand sheet and ecology lab.

## Lessons

- Two right behaviours can make a wrong one between them. Here the fix was to
  make the interaction visible, not to remove either behaviour.
- A box a reader cannot see is a box no task can hold. Name it by the kit's
  convention, or the oracle reads `None` and the check is never written.
