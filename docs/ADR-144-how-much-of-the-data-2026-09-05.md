# ADR-144 — How much of the data: the fields nothing has ever filled

**Status:** accepted · **Date:** 2026-09-05 · **Twenty-one science tasks enter data on the twenty-one data-entry pages and hold each page's report to a hand-checked oracle. That answers "can the harness enter data here?" with a yes, and has never answered the question underneath: how MUCH of it. `tools/entry_reach.py` measures it — 183 of 516 fields across the kit, per page, with the un-entered ones named — and ratchets it, so a task that stops filling a field is a field nothing checks any more**

## 1. The number nobody had

The stand sheet carries 157 controls that hold a value. Its science task drives
25 steps, and every figure those 25 steps produce is checked to the last digit.
The other fields are entered by nothing at all — so a field that silently drops
what you type, or a figure that only goes wrong once the third column is
filled, is not something any suite in this kit could notice.

"21 science tasks, all green" says nothing about that difference, and the
standing goal is explicitly about it: *make sure it can enter all the data and
the reports are correct.* The second half has been measured since ADR-128. The
first half has not been measured at all.

## 2. What counts

    ENTERABLE   the controls that CARRY A VALUE -- text, fields, pickers,
                steppers, sliders, selects, checkboxes, file inputs, and the
                choice controls (dial options, chips, key options, swatches).
    NOT         Add, Save, Clear, tabs, links, and `readonly_out` -- the swarm's
                own name for "a display, not a control". Pressing those is doing
                something WITH data, not entering any.

Every kind `harness.KINDS` discovers is on one side of that line or the other,
and `verify_entry_reach` holds it to that: a kind on neither list would be
silently outside the accounting.

**A field is not a control.** Three decisions, each of which changed the number
by a lot and each of which is a fixture check:

- **A FEK widget is one field.** A stepper is a minus, a value and a plus; a
  slider is a rail and a readout. Entering the value enters the field, and
  counting the minus button as a field nobody filled counts the same field
  three times. First reading of the stand sheet before this rule: 10 of 157.
- **A group of mutually exclusive choices is one field.** A key with 34 regions
  is one question, not 34; a page whose task picks one shape of four is not
  ignoring three fields.
- **A control the entry touched and the page then REMOVED is still a field that
  was entered.** A character key deletes the option it has just answered, so
  counting only what survives said "0 of 4 entered" about a task that answers
  the whole key.

And one that had to be fixed twice: **which control a step touched is resolved
BEFORE the step runs.** Asked afterwards, a key's answered option and a
rebuilt region's controls are gone, and the eight answers the cp-characters
task gives recorded as zero.

## 3. The reading

    185 of 518 fields  (36%)  ·  27 pages with anything to enter, of 41

Per page, with the un-entered fields **named**, because the point is a worklist
and not a score:

| page | entered | fields | some of what nothing has ever filled |
|---|---:|---:|---|
| collection-sheet | 6 | 63 | `cBruise`, `cNum`, `cOdour`, `sColl`, `sDate` … |
| stand-sheet | 9 | 50 | `iA`, `iB`, `iN`, `kSearch`, the shape chips … |
| ecology-lab | 7 | 40 | `wb-ab`, `wb-area`, `wb-bb`, `wb-deckflip` … |
| deployment-log | 17 | 37 | `aFw`, `aLat`, `aLon`, `aSite`, `fDate` … |
| cell-bench | 16 | 28 | `pNo`, `pNote`, `pSplit`, `stU` … |

A reference page and a glossary have no fields and drop out of both halves on
their own; `tree-proofs` enters 3 of 3.

## 4. A ratchet, not a target

A target ("every page must reach 80%") would be a number invented here, and the
pages differ honestly: a key with 40 mutually exclusive options cannot have all
40 entered in one pass. What can be said without inventing anything is the rule
the engine ledger already uses for tests (ADR-139): **a page's coverage must not
silently go down.** A floor per page, raised deliberately with `--raise-floors`,
lowered only with a reason that goes into the ledger beside what it was lowered
from.

The ratchet fails **by default**, with no flag: `run_all` runs an audit with no
arguments, so a floor that only bit under `--check` would be a floor nothing
ever checked. `entry_reach` is registered there now, so a task that stops
filling a field fails the run that day rather than being noticed a month later.

## 5. What is now asserted

`verify_entry_reach` **26**, new, on a fixture built to have every case in it:
two steppers, two chip groups in different hosts, a key whose answered options
vanish and which *builds* two more that no state walk ever sees, three inputs,
a readonly display, an Add and a Clear, and one deliberately refused step. It
pins the control count, the field count and the entered count exactly — 18, 10,
6 — and every one of those three numbers is load-bearing: `mutate_entry` **18**,
17 killed, 0 survived, **1 recorded equivalent**.

The equivalent is honest and stays: `if ok and before` → `if before` cannot be
observed, because the page plugin refuses by **raising** — every wrong-kind
selector, every missing control, every bad value comes back as a HarnessError —
so the line after `execute()` is only ever reached with `ok` true. The guard is
defence against a future plugin that answers no without raising, which is a
shape this kit does not currently have.

## 6. And the never-exposed fault was not what it looked like

ADR-143 put the never-exposed control's NAME in `audit_contrast`'s summary
because `run_all` prints only a failing job's tail. This slice finished that for
`audit_targets` and `audit_focus` — and the very next run printed the name:

    never exposed:   collection-sheet.html   None

`None`. `UNSTAMPED_JS` reads every control's `data-audit`; a control that mounted
**after the last `MARK_JS`** has none, so it came back as `null`, counted as a
control no state exposed, and was "named" by looking up an id that does not
exist. Three of six runs' worth of never-exposed faults were that, and both
ADR-140's frame wait and ADR-143's repeated look were aimed one layer away from
it: they made a stamped control's box arrive in time, and this control had no
stamp at all.

`coverage()` now stamps immediately before it enumerates, with nothing between
the two calls, and anything still unstamped is reported as *"N control(s)
mounted after the last stamp and could not be measured"* — a sentence a reader
can act on, rather than a name nobody can look up. `verify_audit_states` **64**
(+2); `mutate_audit_states` **43** (+1), 43 killed, with the second half of the
clause recorded equivalent — once coverage stamps immediately before it
enumerates, producing a null needs a control that mounts in the microseconds
between two `evaluate` calls, and no fixture can hit that window.

## 7. Held

- **This is not a claim that an entered field is entered CORRECTLY.** That is
  the task's oracle and the task's business. Nor is an un-entered field a broken
  one. It is the worklist: these are the fields nothing has ever put a value
  into.
- **35% is the reading, not the target.** The number to watch is whether it goes
  up, and the floors are what stop it going down quietly.
- **Identity is the audit's stamp**, `tag#id.class` plus occurrence among
  identical siblings (ADR-131). Two identical controls in different hosts are
  told apart by that index, so a rebuild that reorders them can alias one to the
  other. It cost a fixture rewrite here (three key options needed ids before the
  numbers were explainable) and it is a real limit on any page whose identical
  controls have no ids.
- **A field behind a state the walk never reaches is not in the universe.** The
  walk is the audits' walk, which is thorough and not exhaustive.
- The reading costs about five minutes for the kit; it runs in `run_all` as an
  audit and its ledger is what the board reads.

## 8. First reading

    the kit             185 / 518 fields entered (36%), over 27 pages that have any
    floors              recorded per page; a drop below one fails the run
    verify_entry_reach   26 / 26  ·  mutate_entry 17 killed, 0 survived, 1 equivalent
