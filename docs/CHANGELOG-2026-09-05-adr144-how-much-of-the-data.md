# Changelog — 2026-09-05 — ADR-144: how much of the data

Twenty-one science tasks enter data and hold each page's report to an oracle.
Nobody had ever asked how much of the page's data they enter.

## New — `tools/entry_reach.py`

Per page: the controls that **carry a value**, how many of them the page's own
entry task actually acted on, and the ones it never touched, **named**.

```
python3 tools/entry_reach.py                 # the table and the kit total
python3 tools/entry_reach.py --page stand-sheet.html
python3 tools/entry_reach.py --raise-floors  # after a task grows
python3 tools/entry_reach.py --lower stand-sheet.html --reason "..."
```

**The reading: 185 of 518 fields (36%), across the 27 pages that have any.**
collection-sheet 6 of 63; stand-sheet 9 of 50; ecology-lab 7 of 40;
deployment-log 17 of 37; cell-bench 16 of 28; tree-proofs 3 of 3.

A *field* is not a control, and three rules make the number mean something —
each one a fixture check:

- a FEK widget (stepper, slider, picker) is **one** field, not three;
- a group of mutually exclusive choices is **one** field, not forty;
- a control the entry touched and the page then **removed** still counts as
  entered — a character key deletes the option it has answered, and counting
  only survivors said "0 of 4" about a task that answers the whole key.

**A ratchet, not a target** (the ADR-139 rule applied to data entry): a floor
per page, raised deliberately, lowered only with a reason that goes into the
ledger beside what it was lowered from. It fails **by default** with no flag,
because `run_all` runs an audit with no arguments — and `entry_reach` is
registered there now.

## `tools/audit_states.py`

- `enter()` returns **`touched`**: `{data-audit stamp: kind}` for every control
  a step successfully acted on, resolved **before** the step runs. Asked
  afterwards, a key's answered option and a rebuilt region's controls are gone,
  and the eight answers the cp-characters task gives recorded as zero.

## ...and the never-exposed fault turns out not to be what it looked like

With the name finally in the summary, this slice's next run printed it:

```
never exposed:   collection-sheet.html   None
```

`None`. `UNSTAMPED_JS` reads every control's `data-audit`, and a control that
mounted **after the last `MARK_JS`** has none — so it came back as `null`, was
counted as a control no state exposed, and was named by looking up an id that
does not exist. That is what `audit_targets`' never-exposed fault has been:
not a stamped control that never had a box, but an unstamped one that arrived in
the gap between two `evaluate` calls. ADR-140's frame wait and ADR-143's
repeated look were both aimed one layer away from it.

`coverage()` now stamps immediately before it enumerates, with nothing in
between, and reports anything still unstamped as *"N control(s) mounted after
the last stamp and could not be measured"* rather than as a nameless
never-exposed control. `verify_audit_states` **64** (+2); `mutate_audit_states`
**43** (+1), 43 killed, one clause recorded equivalent (with the fix in, a null
needs a control mounting between two `evaluate` calls — no fixture can hit it).

## ADR-143's rule, finished

This slice's own closing run lost one control to `never exposed` in
`audit_targets` — the fourth instance of that family — and the kit's report of
it was, once again, a count with the name cut off two hundred lines above.
ADR-143 put the name in `audit_contrast`'s summary; `audit_targets` and
`audit_focus` now do the same, so a truncated tail still carries the finding.

## The board — `tools/harness_board.py`

- New tile: **fields entered**, `183 / 516`, with the page count beside it.
- `mutate_entry` joins the runner table.

## Verification

- `verify_entry_reach` **26**, new. A fixture with every case in it: two
  steppers, two chip groups in different hosts, a key whose answered options
  vanish and which builds two more no state walk ever sees, three inputs, a
  readonly display, an Add and a Clear, and one deliberately refused step. The
  control count, the field count and the entered count are pinned exactly (18,
  10, 6), and the un-entered fields are asserted to be **named** by the member
  that says most — "button(−)" tells a reader nothing about which field was
  never filled.
- `mutate_entry` **18**, 17 killed, 0 survived, 1 recorded equivalent
  (`if ok and before` → `if before` is unobservable: the page plugin refuses by
  raising, so the line after `execute()` is only ever reached with `ok` true).

## Docs

`docs/ADR-144-how-much-of-the-data-2026-09-05.md`; `docs/AI_HARNESS.md`.
