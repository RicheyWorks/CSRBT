# ADR-186 — The charts, read (4): the terrarium's seeded stream and the theory bench's model are held to ports of the page that draws them

**Status:** accepted · **Date:** 2026-09-10 · **The lab's terrarium — two charts drawn from a seeded stream in the page's own JavaScript — and its theory bench — one curve, or two, that the page computes from a model — were the last of the lab's drawings under the reader's cap that no task held. ADR-183 said the terrarium could not be fed from the session, and it cannot; but the stream is mulberry32, the generator `tools/mulberry32.py` already ports bit for bit for the determinism shim, so `runMeadow` and `runIsland` are ported over it and the tiles, the readings and every bar have an oracle that never read the page. The theory bench's port is the model: six kinds, closed form or Euler, exactly as the page states them. `verify_eco` 165 → 194 holds the live page at every slider setting and every model the task visits, and the lab task's literals — the terrarium's charts at four steps, the theory chart at three, the tiles that were transcribed when the task was written — to the same ports; `page-ecology-lab-science` 263 → 337.**

## What was left

The terrarium's numbers have been in the task since it was written: J′ 0.73,
29.2 effective species, Chao1 100, 616 immigrations and 604 extinctions at
boot; 0.43 at a 95% hot share; 0.88 with a hot set of 20; 342 and 310 at
capacity 32. Every one was read off the page and typed in. That holds the
page to itself: a page whose stream drifted in step with a re-transcription
would pass. The two charts beneath the tiles were held by nothing. The
theory bench was held to a chip — `habitat: area 2.5 · temp 1.4 · wind 0.6 ·
distance 3` — and to the absence of "cannot be drawn"; the curve itself, and
the effective r and K the page prints above it, were not.

## What is held

**The terrarium.** `tools/verify/_lab_models.py` ports `runMeadow` and
`runIsland` over `Mulberry32(42)` and `Mulberry32(7)`: four thousand touches
over a hundred keys, a hot share of them over the hot set, the rank list of
the forty busiest; eight hundred admissions to an LRU of `cap`, an
immigration for every unseen key, an extinction for every eviction, a
turnover point every eighty operations. Shannon, Chao1 and the evenness
sentence are ported beside them. `verify_eco` drives the sliders as the task
does — 60%/5/12 at boot, 95%, 20, 32 — and holds, at each setting, the tiles
to the port's strings (`fmt` as the page formats, "16 ops" of mean residence
included), the reading sentence, and both charts through `_lab_charts`'s
`bar_chart` at 480 × 150: every bar's box, the ticks, the marks, the path
count.

**The theory bench.** `theory(kind, p, area, temp, wind, dist)` is
`runTheory` without the DOM: `steps` rounded and clamped to [1, 2000];
logistic and island in closed form, exponential likewise, Levins iterated
and clamped to [0, 1], competition by Euler in ten substeps of 0.1,
predation in a hundred of 0.01, colonisation scaled by wind × temperature ×
e^−distance and extinction by 1/area as the page scales them. `theory_note`
is the reading above the chart. The suite drives seven cases — the defaults;
the task's `logistic-again` (r 0.25, N₀ 10, thirty steps, the typed
habitat); competition and predation with two curves; Levins, island,
exponential — and holds the page's path boxes, ticks, marks and longest to
`line_chart` at 980 × 190, and the reading to the note.

**The task.** `boot` holds `t-meadow-chart` (forty bars, `at.0`, `at.1`)
and `t-island-chart` (ten bars, all ten centres); `uneven` and `even` hold
the meadow again at 95% and at a hot set of 20; `island` holds the island at
32 — and the tiles at every one of those steps, mean residence and
residents/capacity now included, are written by the port, not read from the
page. `logistic-again` holds `wb-theory-out`: thirty-one points to K 300,
ticks to 324, and the box now must contain `effective r=0.35, K=300` before
the habitat chip. `competition` holds two curves of eighty-one under ticks to
270 and the note `effective K₁=250, K₂=200`. `still`, at the end, holds the
sixty-one-point default curve to K 120 — the import of `imported pond`
restored the neutral habitat, which is the fact the earlier probe had read
as a discrepancy. The suite holds every one of those literals to the port,
so a literal drifting from the page fails twice: once in the runner, once
here.

**Moving a thing.** Twenty-one hand mutants, each named to the check that
must fail: the meadow's seed 42 → 43, the island's 7 → 8, the interval 80 →
100, the rank list one shorter, the hot share read against 1000, logistic at
half the decay, extinction scaled *with* area, competition on five substeps,
predation's prey term without the predator, the effective K left unprinted,
the theory chart 180 tall; the port's seed, its 799 admissions, a Chao1
without f2, K without area, a 0.2 substep, a mean residence that is a sum;
the task's 342 → 343, a reading without its full stop, a tick 129 → 130, a
note K₂ 200 → 201. All killed at the named check — the Chao1 mutant at the 95% setting, the first where the stream leaves a singleton; at boot every key is touched and Chao1 is S.

## What moved

    page-ecology-lab-science      263 → 337
    verify_eco                    165 → 194
    tools/verify/_lab_models.py   new (imported, not run)

One port, one suite, one task. No page was edited.

## Held

- `spans` is a box. A curve with the right extent and the wrong middle
  passes, as ADR-140 said of paths and ADR-182 of boxes; the competition
  curves are held by their two boxes and eighty-one points each, not by
  shape. `longest` and the ticks catch a substep or a rate that moves the
  ceiling; a mutation that keeps the extremes is the standing gap.
- The tiles are held as strings through `fmt`, the page's `toLocaleString`
  half-up; a stream whose Chao1 changed by less than the formatted digit
  would pass the tile and fail the bars.
- The theory bench's refusals (K 0, steps −1, distance below zero) were held
  already and are not re-held; the port is of the curves, and it raises on a
  kind it does not know rather than drawing something.
- What still draws unasserted: the tree visualizer's tree, the character
  keys' static figures, and the lab's charts past the reader's sixteen.
