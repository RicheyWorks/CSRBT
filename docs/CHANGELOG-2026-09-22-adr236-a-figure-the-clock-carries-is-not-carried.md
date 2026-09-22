# 2026-09-22 — ADR-236: a figure the clock carries is not carried

## Changed

- **`audit_carried` measures each page under two clocks**: the real one, and
  one shifted by 405 d 7 h 23 m 31.457 s, so every field of a timestamp
  differs. A figure is carried only if both readings carry it.
  `performance.now()` is untouched, so durations are unaffected, and a task
  that pins the clock stays pinned. Each measured page reports `clocks: 2` and
  `clock_only`. The relevé's *taxa in pack* read IDLE in ADR-234's run because
  of a timestamp's 49, and that cannot happen now.

## Checked

verify_carried 47 → 55 (a fixture whose figure only its export's timestamp
carries: lost, and named clock-only); mutate_carried 29 → 36. The kit under
two clocks reads what it read under one: 317 figures, 0 lost, every list
identical, 30/30 declarations covering.
