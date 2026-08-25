# ADR-039: Closing the food web's verification gap — and thirteen canaries to prove it closed

**Status:** Accepted and implemented — `tools/verify/verify_fw.py` (54 checks), `docs/food-web.html` (public `FW` seam, four defect fixes, one duplication collapsed).
**Date:** 2026-08-25
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** `docs/food-web.html`, `tools/verify/verify_fw.py`, `tools/verify/run_all.py`

---

## Context

ADR-038's coverage sweep named exactly one instrument in the kit with no verification suite at all:
**Food Web Builder**. Every other page had a suite naming it. This one had none.

The reason turned out to be structural rather than an oversight. FEK, DWC, ORD and KEEP are each a
**named object with a public surface**. The food web's graph algorithms — trophic level, connectance,
cascade, cycle detection — were sealed inside the page's closure. There was nothing to call. A suite
could screenshot the page, but it could not ask the page a question.

## Decision

**Give the page a public seam, `window.FW`, on the same pattern as every other computational module in
the kit**, and write an independent Python reimplementation of each measure to check it against.

`FW` exposes `version`, `levels`, `cascade`, `connectance`, `longestChain`, `species`, `links`, `load`
and `knockout`. The seam is not a test hook bolted on the side: `connectance` and `longestChain` *are*
the functions the page's own tiles call (see the duplication finding below), and `knockout` is the
verdict renderer, otherwise reachable only by a 550 ms long-press.

## What the suite found in the page

Four real defects, none of them cosmetic.

**1. A mutual-predation pair was told it had "no arrows coming in" — while each had one.**
The old loop detector inferred a cycle from a trophic level growing past the species count. That only
ever happens to a cycle a producer feeds. An **unfed** cycle (A eats B, B eats A, nobody eats a plant)
never grows at all, so it went undetected *and* was then reported with a message that was flatly false
about the web on screen. Replaced with a real depth-first back-edge search over prey → predator.

**2. Two different faults shared one wrong message.** A consumer with no incoming link at all, and a
consumer that eats something which never traces back to a producer, are different mistakes with
different fixes. They now have separate diagnoses: `unfed()` and `rootless()`.

**3. The page claimed "the standard definitions" — plural, unnamed.** There are two standard trophic
level definitions in the literature, longest-chain and prey-averaged, and they give different numbers
for the same web. The page now says which one it uses and that a level of 4 here is not comparable to a
prey-averaged 4 in a paper. This is the honesty gate's first branch: ship, with the definition stated.

**4. Connectance and longest chain each had three implementations.** The tile, the notes export, and
the public seam. Three copies of one formula are three chances to disagree. Collapsed to one definition
with three callers — and the canary below is what proved this mattered.

## What the canaries found in the suite

The suite reported **39 passed, 0 failed** on the real page. Seeding deliberate faults is the only way
to learn whether that number means anything. It did not.

Of the first four seeded faults, **two passed a fully green suite**:

- *trophic level uses mean instead of max* — passed, because both shipped presets happen to give
  identical answers under either definition.
- *cascade stops after one round* — passed, because no shipped preset cascades past one round.

Fixtures were added. Two more rounds of seeding found **four more escapes**:

- *connectance denominator changed on the seam* — passed, because the suite read only the tile, which
  was a **separate copy of the formula**. The canary did not merely fail to catch a bug; it discovered
  the duplication that made the bug uncatchable. This is finding 4 above.
- *the whole `unfed()` filter blanked, every orphan warning gone* — passed, because the only orphan
  check in the suite was a **negative**: that a mutual-predation pair is *not* called unfed. A
  diagnosis tested only for staying quiet is not tested at all.
- *`esc()` dropped from the unfed and rootless warnings* — passed, because the escaping fixture was one
  producer, one consumer, one link, which lights exactly one of `esc()`'s seven call sites.
- *`esc()` dropped from the apex line* — passed even after the fixture above was fixed, because the
  apex line renders inside `if(!orphans.length && !L.loop && links_n)` and the new fixture had orphans.
  A **clean** web was needed to reach that branch.

Also fixed on the way: *cascade stops after one round* escaped a second time even with a three-link
chain fixture, because with the species declared `p, A, B, C` a single forward pass happens to sweep
the whole chain. Declared **backwards** — `p, C, B, A` — one pass reaches C before B has starved, and
only a loop running to a fixed point gets the right answer. **The fixture's declaration order was
load-bearing and nothing said so.**

Final state: **54 checks, and all thirteen seeded faults caught.**

| seed | caught by |
|---|---|
| connectance denominator | 4 checks |
| trophic level max → mean | 3 |
| cascade one round | 1 |
| cycle detector blinded | 1 |
| longest chain max → count | 4 |
| `unfed()` blanked | 5 |
| `rootless()` blanked | 2 |
| `esc()` dropped, unfed warning | 3 |
| `esc()` dropped, rootless warning | 2 |
| `esc()` dropped, knockout verdict | 1 |
| `esc()` dropped, node label | 3 |
| `esc()` dropped, apex line | 1 |
| `esc()` dropped, cascade names | 1 |

## Consequences

**The lesson, stated so the next suite inherits it:** *fixtures that cannot tell two implementations
apart are not tests of the difference.* A suite built from the shipped presets tests that the page
still does what it does. It does not test that what it does is right. Every measure now has at least
one fixture chosen specifically because the two candidate implementations disagree on it.

**The second lesson:** *a rendering path that no fixture reaches is unescaped as far as the suite
knows.* Seven `esc()` call sites needed three different webs to exercise — orphan-bearing, clean, and
a knockout verdict — because the page's own branch conditions are mutually exclusive.

**Cost.** The page grew a public seam it did not have. That is a surface, and surfaces are commitments.
It is the same commitment FEK, DWC, ORD and KEEP already carry, and the alternative was the one
instrument in the kit whose arithmetic nobody could check.

This also clears `food-web.html` from the ten-pages-behind list in ADR-038.

---

## Addendum: two defects in the harness, found by reading its own report

The regression that verified this slice printed, on a row marked `ok`:

```
ok     audit_offline    asyncio.exceptions.CancelledError   works with no signal…
```

An exception name, in the column where the score goes, on a green row. Chasing it turned up three
things, none of which were about the food web.

**1. A job can exit 0 while printing a traceback, and `run_all` had no opinion about that.** When a
job's output has no parseable count, the report printed its *last line*. Under `-j 4` a Playwright
teardown race appended a `CancelledError` after the real summary, so the last line was the traceback.
`run_all` now refuses to print a traceback where a score belongs, marks such rows `ok?`, and lists them
under a heading that says what they are: *an exception nobody raised is still an exception*.

**2. The teardown race itself.** `audit_offline` simulates one bar of signal by intercepting two font
requests and never answering them. It called `unroute()` before closing — but `unroute` removes the
*handler*, not the already-intercepted requests, which stay unanswered and surface as a cancelled task
at teardown. The route objects are now held and aborted explicitly before the page closes.

**3. The headline check count was short by six suites, silently.** `score()` matched only `N/M` at
end-of-line. The six newest suites — `verify_dwc`, `verify_ord`, `verify_keep`, `verify_dep`,
`verify_sd`, `verify_fw` — report `N passed, M failed`, and **none of their checks were reaching the
kit-wide total**. Audits ending `37/37 pages clear` were dropped too, for having words after the
count. The reported "1880 of 1880 checks passing" was true of the suites it could parse and silent
about the ones it could not.

*A total that silently omits a suite is worse than no total*, because it looks like coverage. Both
formats are parsed now, and the real number is in the run below this ADR's date.
