# ADR-224 — thirty written judgements stood in four ledgers and nothing could say whether one of them was still about anything (ADR-218, rebuilt)

**ADR-218 was built, verified — 53 mutants, all killed, the ledger says so —
and never delivered. Its paragraph in `AI_HARNESS.md`, its row on the board, its
runner's entry in the mutant ledger and its audit's line in `run_all` reached
origin inside ADR-217's commit; `tools/exempt.py`, `tools/audit_declared.py`,
`verify_declared` and `mutate_declared` did not exist anywhere (ADR-219 §4). This
is that slice again, built from its paragraph and the names of its mutants,
which together turned out to be a specification.**

## 1. The defect, as ADR-218 stated it

Six audits let a finding be DECLARED with a reason — a figure right to stay on
the screen, a box right to say nothing about a rejected keystroke, a reading
right to differ after a reload, a control right to reach no published reader, a
bulk remover right not to ask, a button right to hand nothing over — and all six
applied the exemption by filtering the finding out of the list and writing the
FILTERED list to the ledger. The evidence was discarded at the moment the
exemption was used. A declaration is keyed by a label; delete the control and
the exemption stays; add a control that takes the same label and the exemption
is waiting for it, carrying a reason written about something else. Six audits
could add an exemption and none could remove one. Thirty stood.

## 2. What is built

- **`tools/exempt.py`** — the only place an exemption is granted, and it
  FILTERS AND RECORDS IN ONE CALL: the row gets `raw` (what was flagged before
  the exemption) and `seen` (everything the reading could have flagged) beside
  the filtered list it always had. Copies, not the audit's live list. A blank
  reason is refused here, once. An audit with two ratchets on one row keeps two
  records (`outputs`: `raw`/`seen` and `mute_raw`/`mute_seen`); the whole-page
  declaration gets the audit's own VERDICT written to the row (`trap`).
- **All six audits go through it.** `carried` records the labels it compared,
  `restored` the keys it read before the reload, `takeaway` the buttons that hand
  something over, `destructive` every control it classified, `badinput` every
  field, `outputs` every button.
- **`tools/audit_declared.py`** reads what that writes and gives every
  declaration one of four verdicts: COVERING (in raw), IDLE (in seen, not raw —
  slack that would hide the defect coming back), STALE (in neither — nothing by
  that name), UNREAD (no row, no universe, or a row older than the newest row of
  its own one-pass ledger by more than six hours: the audit did not visit that
  page on its last pass). Only covering passes. Whole-subject sources are judged
  by their recorded verdict; a page that has grown an export is STALE for its
  no-outputs declaration, not idle, because it is not the page the reason was
  about. The contention ledger is written by a sweep, not a pass, and gets no
  freshness test — stated per source, not decided in the reader. It opens no
  browser and runs last in `run_all`, so it judges this run's readings.
- **It has no `--declare`**, deliberately. It can only take a declaration away,
  and `--forget SOURCE:PAGE:KEY` prints the reason it removes; a key may contain
  a colon; the last one removed takes the empty block with it; the reading stays.
- **`verify_declared`** (48) builds ledgers in which each verdict is the right
  one, drives `--forget` through every refusal, and then checks THE LIVE
  LEDGERS: filtered within raw within seen, and raw minus filtered exactly the
  declared keys — so a recording that silently stops fails against the kit's
  own data. **`mutate_declared`** 45, all killed. The shared rule is asserted
  through each of the six audits' own suites (two or three checks each, one of
  them a direct probe that the record is a copy) and mutated through their six
  runners (four mutants each, `exempt.py` added to each SUBJECT).

## 3. What the first honest reading found

See §5 — filled in after the audits ran under the new rule.

## 4. What the rebuild found about the rebuild

The first version of `verify_declared` used `NOW` as the newest row's `at`, so a
reader that measured a reading's age against the wall clock and one that
measured it against its own ledger's newest row were indistinguishable, and the
mutant for it survived. The fixture's newest row is now a thousand seconds ago.
One mutant — "every ledger gets the freshness window, sweep or not" — was
equivalent by construction, because the window test itself asks `one_pass`
again; it is dropped rather than recorded, since a mutant that cannot be
reached is not a clause anybody could delete. Eight mutants crashed the suite
rather than failing it on the first run: the suite now reads every row with
`.get`, because a mutant runner cannot score a crash (ADR-191's lesson, again).

## 5. Findings against the live ledgers

The six audits were re-run under the new rule and `audit_declared` read what
they wrote:

    30 declaration(s): 30 covering, 0 idle, 0 stale, 0 unread

Every one of the thirty reasons is still about a finding the audit makes today
— carried 9, restored 11, destructive 1, outputs-mute 9. That is the honest
answer and it is worth having exactly because it could have been otherwise:
until this slice the number was not measurable, and the ADR-218 paragraph's
own guess ("nothing could say whether one of them was still about anything")
was true of the kit and, it turns out, false of the declarations. The first
reading before the audits re-ran was 30 UNREAD — the rows had no `raw`/`seen`
record — which is the verdict the reader gives a ledger written by an audit that
filtered quietly, and is what every ledger in origin reads today.

## 6. Held

- **A declaration's reason is not held to the thing it names**: `--forget`
  prints it; nothing reads it. A reason that quotes a control's label could be
  checked against the label. Trigger: the first STALE declaration whose reason
  would have caught it.
- **The six audits' `seen` lists are what each audit chose to compare**, not
  the page. A control the audit never classifies is invisible to IDLE/STALE.
  That is the audit's reach, measured elsewhere (entry_reach, audit_targets).
