# 2026-09-07 — ADR-154: the ethogram, recorded whole

**No task had ever started a session on the one page whose product is a
measurement of time. Driven against a clock the harness steps, every duration is
exact — and the exact numbers found two defects.**

## New

- **`tools/tasks/page-ethogram-science.json`** — 64 steps, 68 confirmed
  expectations. Declares the design (focal animal, continuous, scan interval,
  session length, observer, date, site, species, conditions), adds a subject and
  a behaviour with its definition, then records a focal session against a frozen
  clock stepped press by press, reads the time budget, event rates and
  transition matrix, holds all five exports, and computes Cohen's κ.

## Changed — `docs/ethogram.html`

- **The elapsed tile was not elapsed.** It showed `observed + out of sight` —
  the time that is *in a state*. The session ran 06:20 and the tile said 06:00.
  It now shows the elapsed time and names the difference in a line of its own:
  *"00:20 of the session is in no state."*
- **A transition is adjacency, not order.** Dropping out-of-sight segments
  closed the gap they left, so the state before a disappearance and the state
  after it were counted as one following the other. This session reported four
  transitions where three were observed. Non-adjacent pairs are no longer
  counted, and the page says how many it dropped and why.

## Numbers

    ethogram.html   5 -> 16 of 16 fields entered  (100%)
                    3 unread + 2 silent -> 5 of 5 outputs held
    the kit         405 -> 416 of 520 fields      (78% -> 80%)
                    42 -> 39 unread, 21 -> 26 held, 19 -> 17 silent (of 65)

Every figure in the task comes from a Python oracle mirroring the page's own
budget, rate and transition arithmetic; none was typed by hand.

## Held

- The stepped clock reproduces exact durations and nothing about an observer's
  reaction time or the scan timer, which under a frozen clock never fires — so
  instantaneous and one-zero recording are still driven only by their design
  chips.
- The "in no state" line is a report, not a correction: the page does not guess
  what the animal was doing before the first tap.
- 39 outputs on 15 pages are still unread; 17 buttons still silent.
