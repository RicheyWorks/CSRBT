# ADR-237 — a perfect fit is not an unstable one

**Date:** 2026-09-22 · **Status:** accepted · **Chain:** ADR-236 → this ·
**Protocol:** 1.11 (unchanged)

## Why

The goal requires every report to be correct. The eighth blind trial (ADR-230)
filed three things the ordination page said that were not so. All three were
still live:

1. **At stress 0.000 the starts verdict called the fit unstable.** On four
   and on five sites the page said *"1 of 12 starts converged to the same
   configuration. **That is not a stable solution.** Fewer than half the starts
   agreed, which means the stress surface has many basins"*. The stress tile
   beside it read 0.000. That verdict is false. At stress zero the rank order
   of the dissimilarities is reproduced exactly, and with a handful of sites
   more than one arrangement does that. Nine or ten of the twelve starts had
   reached a perfect fit. They disagreed about positions because every one of
   those positions is exact, not because the fit is shaky. The operator read
   the verdict and the tile as a contradiction, and it was one.
2. **"1 value could not be read as a number and were taken as zero."**
3. **The toast kept its words after it slid away.** The demo's *"Simulated:
   the same sites and species, no gradient at all"* was still the page's toast
   after the reader had pasted their own data, and a reader of the page
   (`read-report`, and so the blind operator) read it as current.

The task held none of the three. It checked *"Stress 0.000"* on the four-site
fit and *"could not be read as a number"* on the bad value, and nothing about
the starts verdict or the toast.

## Decision

- **The starts verdict at stress zero** now says how many starts reached a
  perfect fit, how many of them are this configuration, and what that means.
  For example: *"10 of 12 starts reached a perfect fit (stress 0.000), and 1
  of them is this configuration. At stress zero the rank order of the
  dissimilarities is reproduced exactly, and with 4 sites more than one
  arrangement does that — so starts that disagree here are not a sign of an
  unstable fit. The picture is one of several exact ones: read its rank order,
  which all of them share, and not its distances."* The starts that missed are
  accounted for: *"The other 2 starts stopped in local minima, the worst at
  stress 0.169."* `nmds()` records `perfect`, the number of starts under
  stress 1e-4. A fit with real stress keeps the verdict it always had.
- **The copied coordinates** carry it too: *"; 1 of 12 random starts agree,
  10 of 12 reach stress 0 -- one of several exact arrangements"*, and only at
  stress zero.
- **One value "was" taken as zero, and two values "could not be read as
  numbers and were".**
- **A toast that has gone says nothing.** Its text is cleared once it has
  slid away.

**Found while fixing:** the page seeds its NMDS starts from the clock
(`Date.now()`), so how many of the twelve reach zero varies from run to run.
The first draft of the task held *"9 of 12"*, which the probe had read, and
the task run read *"10 of 12"*. So the task holds the sentence's structure
and the site count, never the counts. The suite checks the counts against
each other.

**Found in its own close:** the first draft made the change to `nmds()`
directly in `docs/ordination.html`. That block is emitted from
`tools/ord.py`, and the full run caught it: `verify_emitters` 169/173, with
*"ord_emit.py --check is clean on a clean tree"* failing and 436 bytes
differing. The change now lives in the source, and the engine is **Ordination
1.1.0**. Re-emitting it produced exactly the page as fixed by hand, plus the
banner, so both pages are republished.

## Held by

- **The task** (`page-ordination-science`), 89 → 100 confirmed. On four and
  five sites the start verdict must say *perfect fit* with the site count and
  never *not a stable solution*. One unreadable value must say *was*, a new
  pair of steps with two unreadable values must say *were … numbers*, the
  copied coordinates must carry the stress-0 clause, and the goal says so.
- **`verify_ord`** 114 → **129**. On four and five sites: the verdict's form,
  its counts consistent with each other and with the tile (agreeing ≤ perfect
  ≤ starts), the verb agreeing with the count, the site count named, the rest
  accounted for exactly when some start missed, and the coordinates' clause.
  **The claim itself, independently:** from the page's own four-site
  configuration, Python moves every point, keeps the rank order of the six
  distances, and computes Kruskal's stress-1 with its own isotonic fit (pool
  adjacent violators). The result has stress 0 and is not the page's
  configuration up to rotation, reflection and scale. So *"one of several
  exact ones"* is true, and *"not a stable solution"* was false. The
  twenty-site demo, with real stress, keeps the convergence verdict, and its
  coordinates say nothing about stress 0. The suite also checks one value and
  two values, and that the toast says what it did while it shows and nothing
  after, including after the reader's own data is in.
- **New runner `tools/mutate_ord.py`**, on the board, **8/8 killed**. It
  covers the instability verdict restored, *perfect* at any stress under 1,
  the site count typed, the coordinates' clause dropped or always present,
  *were* for one value, *a number* for two, and a toast that keeps its words.
  Mutants whose kill would depend on the page's clock-seeded starts are left
  out on purpose: a kill that depends on the time of day is not a kill.

## Numbers

| | before | after |
|---|---|---|
| page-ordination-science | 89 confirmed | **100** |
| verify_ord | 114 | **129** |
| mutate_ord | — | **8**, all killed |

## Held

- **The page's starts are seeded from the clock.** That makes the counts
  unreproducible without `set-clock`. Trigger: a claim that needs the counts
  exactly.
- **The remaining pages' filed defects:** selection log, field notebook,
  ethogram, relevé, pheno tracker, stand sheet and ecology lab, one page per
  slice, oracle first.

## Lessons

- A verdict written for one regime can be false at the edge of another.
  *"Fewer than half agreed"* means instability only when the fit is imperfect.
  At stress zero the same count means the solution is not unique.
- A count that depends on a clock-seeded generator belongs in a suite's
  consistency checks, not in a task's expectations.
