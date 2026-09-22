# 2026-09-22 — ADR-237: a perfect fit is not an unstable one

## Fixed (ordination, all three filed by the eighth blind trial)

- **At stress 0.000 the starts verdict no longer calls the fit unstable.** It
  says how many starts reached a perfect fit, how many of them are this
  configuration, that with this few sites more than one arrangement is exact,
  and to read the rank order rather than the distances. It also accounts for
  starts that stopped in local minima. The copied coordinates carry *"P of N
  reach stress 0 -- one of several exact arrangements"*, and only at stress
  zero.
- **"1 value … was taken as zero"**, and **"2 values could not be read as
  numbers and were"**.
- **A toast that has gone is cleared**, so the demo's *"Simulated: …"* is not
  still the page's toast after the reader's data is in.

## Checked

Task 89 → 100 confirmed. verify_ord 114 → 129, including an independent
construction of a second stress-0 arrangement of the four sites (Python's own
isotonic stress-1). New runner `tools/mutate_ord.py`, 8/8 killed.

## Found

The first draft edited the emitted engine in the page rather than its source,
`tools/ord.py`. `verify_emitters` caught it (169/173). The change is now in the source,
and the engine is Ordination 1.1.0.


The page seeds its NMDS starts from the clock, so the counts vary run to run.
The task holds the sentence's structure and the suite holds the counts'
consistency.
