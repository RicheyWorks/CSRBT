# ADR-052 — Binding the docs to the engine

**Status:** accepted · 2026-08-26

## The gap

CSRBT is a Java ordered-set engine. `docs/ecology-lab.html` is the page that
shows what it does, and its headline sentence reads:

> "80% of keys survive a generation, but only **57%** of the physical nodes —
> the gap is the price of path copying."

Neither figure is written in the prose. The page interpolates them
(`${fmt(f.meanContent * 100, 0)}%`) from a recorded session inlined at
`const SESSION = {…}`, which is a copy of `docs/ecology-lab-session.json`, which
is supposed to be the output of `EcologyFieldDay.run().json()`.

Three links, and **nothing checked any of them**:

```
engine  →  docs/ecology-lab-session.json  →  the page's inline copy  →  rendered prose
```

`EcologyFieldDayTest` asserts the JSON is byte-deterministic across two runs and
that its braces balance. Both are true of a JSON the engine has never seen. The
shipped artifact could have been hand-edited, or the engine could have moved
underneath it, and all 48 jobs would still have been green.

This is the FEK emitter problem — a generated value inlined in a page, with
nothing binding the two — one layer further down, at the boundary between the
docs and the system they describe. Every suite in this kit tests HTML. Not one
had ever run the engine.

## What was measured

The engine was compiled and run. `EcologyFieldDay.run().json()` is
**byte-for-byte identical** to `docs/ecology-lab-session.json`, and the page's
inline copy parses to the same object.

So the flagship figures are real: 0.8 and 0.575 are measured by the engine, not
asserted by a writer. `0.575` is exactly 23/40 — a shared-node count, not a
round number someone liked the look of.

That is a fact with a date on it. `tools/verify/verify_engine_sessions.py`
(11 checks, six seeded faults, all caught) is what keeps it true.

## What "unverified" means, and why it is not green

Link A needs a compiled engine. Where it cannot run — a fresh clone before
`./gradlew classes` — the suite prints an UNVERIFIED line and reports a **short
score**, `9/10` rather than `10/10`. run_all already cross-checks a suite's score
against its total and marks a shortfall as `FAIL*`, so "could not check" surfaces
instead of passing quietly. That machinery exists because eleven suites once
printed FAIL and exited 0; this is the first suite written to use it deliberately.

A check that cannot run must not be indistinguishable from a check that passed.

## A defect the last fixture caught, before shipping

The extractor that pulls the inline blob out of the page counted braces. The
final fixture — `{"a":"} not the end","b":2}` — showed it stops at the first `}`
**inside a string value**. Today's session carries no brace in any string, so the
comparison passed and would have gone on passing until one did, at which point
the page would have been compared against a truncated object.

Worse, that fixture *crashed* the suite rather than failing it. A check that
raises has told you nothing. Both are fixed: the matcher is string- and
escape-aware, and the fixtures are guarded so a bad extraction reports as a
failure with the exception as its evidence.

## What is deliberately not bound

Five recorded artifacts are named as **unbound**, and a check asserts the list is
exactly those five — so a new one cannot appear and quietly look covered:

`arena-session.json`, `arena-search-session.json`, `ecology-trace-session.json`,
`ecology-experiment-session.json`, `viability-map.json`.

None has a deterministic `run()` to call. Nothing here can say they are the
engine's output, and this ADR does not imply it.

## Still open

- The five unbound artifacts above — the largest is 551 KB and is loaded by the
  replay arena.
- 33 claims remain on the `audit_claims` worklist; several look citable rather
  than unsourced (Reineke 1933 for the 1.605 stand-density exponent, the 30–300
  plate-count window, DBH at 1.37 m).
- `collection-sheet` and `stand-sheet` still publish figures the repo
  contradicts (ADR-050), and `fungal-characters` remains blocked on the publish
  gate's duplicate branch.

## The rule this adds

> A number a page computes from a recorded artifact is only as true as the bond
> between that artifact and the system that produced it. Test the bond, or the
> figure is decoration with a decimal point.
