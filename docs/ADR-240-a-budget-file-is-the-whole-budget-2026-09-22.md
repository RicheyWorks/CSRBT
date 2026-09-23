# ADR-240 — A budget file is the whole budget

**Date:** 2026-09-22 · **Status:** accepted · **Chain:** ADR-239 → this ·
**Protocol:** 1.11 (unchanged)

## Why

The seventh blind trial (ADR-229) filed three things on the ethogram, and the
task certified all three.

**The budget note called the wrong number "elapsed".** ADR-154 fixed the tile
and added the *"00:20 of the session is in no state"* note. The sentence one
paragraph below still read *"percentages are of 05:30 observed, not 06:00
elapsed"*. But 06:00 is the time in a state (observed plus out of sight), and
the session ran 06:20. The tile and the sentence disagreed on what elapsed
means, and both were on the same screen.

**The budget CSV carried the state rows and nothing else.** The 00:30 that was
taken out of the denominator was in no row, so the denominator could not be
checked from the file. The event rates the page shows beside the budget were
in no export at all; the log CSV has the taps, not the rates.

**The sheet said "1 bouts".** And the task held it to that, byte for byte.

## Decision

- **The note names all three numbers:** *"percentages are of 05:30 observed,
  not the 06:00 in a state (observed plus out of sight), and not the 06:20 the
  session ran."* The third clause appears only when there is a gap, which is
  when there are three different numbers.
- **The session sheet** says *bout* of one and *bouts* of more. It names the
  out-of-sight time it excluded and the in-no-state time, so its lines add up
  to the clock.
- **The budget CSV** gains an `out of sight` row (`seconds_excluded`, with the
  in-a-state total as its denominator) and one row per event
  (`per_observed_min`, with count and observed minutes as its denominator). In
  point mode the dropped points are a row too (`points_excluded`, over the
  points taken).

## Held by

- **The task** (`page-ethogram-science`): 67 → **77** confirmed. It holds the
  note word for word, the sheet's `1 bout` and its two new lines, and the four
  CSV rows (forage's percentage over 330.0 s observed, the 30.0 s excluded
  over 360.0 s in a state, and the two rates over 5.5 min observed). The goal
  says so. Run against the page as it was, it is **refuted at the note**.
- **`verify_etho`**: 71 → **86**. A new section drives the same session
  through the door against a stepped clock, so every duration is exact. It
  states the durations itself (observed 330, out of sight 30, gap 20, two
  alarms, one aggress) and holds the note, the sheet and the CSV to arithmetic
  on them, not to the page's words. It also holds the CSV's rate to the rate
  the page shows, and the point-mode row. One existing check was rewritten:
  *oos not a budget row* had sliced the box text at the last word "elapsed",
  which the fixed note no longer says. It now reads the table's rows.
- **New runner `tools/mutate_etho.py`**, 11 mutants: the old word back in the
  note, the wrong third number, `1 bouts` back, every bout count as one, the
  out-of-sight line dropped, the gap computed without out of sight, the CSV
  without its out-of-sight row, rates per elapsed minute, no event rows, no
  point-mode row, a rate at two decimals. **11/11 killed.**

## Numbers

| | before | after |
|---|---|---|
| page-ethogram-science | 67 confirmed | **77** |
| verify_etho | 71 | **86** |
| mutate_etho | — | **11**, all killed |

## Held

- **The relevé, pheno tracker, stand sheet and ecology lab** filed defects.
- The ethogram's other pages' toasts keep their words after fading (ADR-237's
  shape, unfiled here). Trigger: an operator misled by it.

## Lessons

- A fix that changes a tile and leaves the sentence beside it is half a fix,
  and the half that was left is the one a reader quotes.
- The oracle certified `1 bouts`. A task literal transcribed from the page
  holds the page to itself, which is the defect ADR-173's suite exists to
  catch, and it is why the new checks state the durations rather than read
  them.
