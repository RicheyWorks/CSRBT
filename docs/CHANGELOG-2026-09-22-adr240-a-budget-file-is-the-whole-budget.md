# 2026-09-22 — ADR-240: a budget file is the whole budget

## Fixed (ethogram, filed by the seventh blind trial)

- **The budget note** no longer calls the time in a state "elapsed". It reads
  *"percentages are of 05:30 observed, not the 06:00 in a state (observed plus
  out of sight), and not the 06:20 the session ran."*
- **The session sheet** says *1 bout*, and names the out-of-sight time it
  excluded and the in-no-state time.
- **The budget CSV** carries an `out of sight` row (seconds excluded, over the
  time in a state), one `per_observed_min` row per event (count and observed
  minutes as the denominator), and in point mode a `points_excluded` row.

## Checked

Task 67 → 77 confirmed (refuted on the old page). verify_etho 71 → 86, a
door-driven section against a stepped clock with the durations stated in the
suite. New runner `tools/mutate_etho.py`, 11/11 killed.
