# ADR-043: The greenhouse monitor — four engines, five ways in, and one number that is two numbers

**Status:** Accepted and implemented — `tools/gh.py` v1.0.0, `tools/gh_emit.py`, `docs/greenhouse.html`, `tools/verify/verify_gh.py` (99 checks).
**Date:** 2026-08-26
**Deciders:** Richmond
**Touches:** `tools/nav.py`, `tools/verify/verify_emitters.py`, `tools/artifact_map.json`

---

## Context

Requested: track every greenhouse variable, control and trend it, compute VPD, grams per watt, and
the ratio of plant growth to electricity spent — with real-time sensor data, calculus, and graphs
that are easy to read.

Four of those are the same request wearing different clothes. VPD is an equation, DLI is an integral,
kWh is an integral, and grams-per-watt is a ratio between the last two and a weight. They read from
one log, so they are one engine.

The fifth — "real-time from sensors" — is the one that needed a decision rather than an
implementation.

## Decision 1: a plugin registry, not a protocol

Asked how sensors should connect, the answer was *"we never know the user's set up, so make it very
flexible with plugins."* That is the right call and it has a sharp edge: a page that offers five
paths and silently fails on four is worse than a page that offers one.

So every source answers the **same two questions before it is offered**: can it run *here* — this
browser, this page, right now — and if not, *why not*. Five ship:

| source | runs | the honest limit, stated in the row |
|---|---|---|
| controller export (CSV/JSON) | everywhere, offline | none — this is the one that always works |
| local HTTP endpoint | served pages only | a `file://` page **cannot** fetch `http://`; an `https://` page cannot fetch a plain-http sensor |
| USB via Web Serial | Chromium, secure context | the browser will not open a port without a click, every session |
| type it in | everywhere | resolution is your visit frequency |
| worked example | everywhere | **generated, not measured** — said in the row, the banner and the export |

`available()` is not decoration. **A monitoring page that fails silently is worse than one that does
not load: it shows you an empty room and lets you believe the room is empty.** Opened from a file,
this page reports the HTTP source as unavailable with the reason, rather than letting you type an
address and wait for nothing.

Adding a sixth is one `GH.register()` call. The page does not know the list.

## Decision 2: leaf VPD, and the number nobody quotes with it

There are two quantities called VPD:

```
air VPD  = es(T_air)  − es(T_air) × RH/100
leaf VPD = es(T_leaf) − es(T_air) × RH/100
```

Most published target bands do not say which they mean. **The suite for this page caught me getting
the size of that gap wrong, in the page's own prose.** The draft said a 2 °C leaf offset "moves VPD
by roughly 0.15–0.25 kPa — about a third of the width of a target band."

Swept across 18–32 °C and 40–85% RH, the real figure is **0.25 to 0.51 kPa, median 0.36**. The
vegetative band is 0.4 kPa wide. So the leaf assumption alone is worth **61% to 128% of the entire
band** — at the top of that range it is *wider than the band it is being compared against*.

A target band quoted without its leaf assumption is not a number. The page now says so, with the
range recomputed by the suite rather than pinned as a string.

The direction was wrong too, and the same check found it: a cooler leaf has a lower saturation
pressure, so a **larger** offset gives a **lower** VPD. My first assertion said the opposite.

SVP is Buck (1981) — what NOAA publishes and what most controllers implement, so a number here
matches the controller's own screen. A measured leaf temperature in the log overrides the assumed
offset entirely.

## Decision 3: two numbers share the name "g/W", and both ship

```
g/W   = yield ÷ RATED fixture watts      the industry figure
g/kWh = yield ÷ energy actually consumed the one that divides into your bill
```

A fixture run at 60% for half the cycle uses 0.60 × 0.50 = 0.30 of the energy, so its g/kWh is
1 ÷ 0.30 = **3.3 times higher** at identical g/W. Anyone comparing g/W across two rooms with
different duty cycles is comparing nothing. The page leads with g/kWh, reports g/W beside it, and
prints the duty cycle next to both.

## Decision 4: the integrals are integrals

- **kWh = ∫P dt**, trapezoid. Controllers that claim to log every five minutes drop samples under
  load, and a rectangle sum silently attributes each gap to whichever endpoint it used. The suite's
  fixture has deliberately uneven spacing so the two methods *disagree* — a fixture where they agreed
  would test nothing.
- **DLI** both ways: the closed form `PPFD × h × 0.0036`, and the trapezoid over the actual PPFD
  curve. The page shows both and names the gap, because the closed form is only right when PPFD is
  constant for the whole photoperiod, which a dimming ramp is not.
- **Time outside band by duration, not sample count.** Ten samples in one bad hour and one sample per
  good hour reads as 50% of samples and about 4% of time. The suite uses exactly that fixture.
- **Trend by least squares**, reported *with r²*. A slope through a cloud of points is a number with
  no meaning, and the page says so in the banner instead of drawing the line.

## What is refused

**Lumens → PPFD has no default factor and the engine will not invent one.** Lumens weight photons by
the human photopic response, which peaks at 555 nm — green, where a leaf absorbs least. PPFD counts
400–700 nm flat. The ratio is a property of the *spectrum*: 24 lux per µmol/m²/s for a red-and-blue
LED, 82 for HPS — 82 ÷ 24 = 3.4. Give the engine a factor and it converts, names the factor in the
output, and carries that name into the export. Leave it blank and it returns nothing rather than
three significant figures from a guess.

Also refused: predicting a yield, pricing a harvest, and telling you whether more light would pay.
The first needs a controlled trial, the second is not a horticultural question, and the third depends
on where you sit on a diminishing-returns curve only your own record can locate.

## Verification

`tools/verify/verify_gh.py`, **99 checks**, every quantity recomputed by an independent Python model —
Buck against published values at six temperatures, leaf VPD, dew point by inverting SVP, both
trapezoids, OLS with r², and the duration-weighted excursion.

**Thirteen seeded faults, thirteen caught:** Buck's coefficient nudged (18 checks fired), leaf temp
swapped for air (7), trapezoid replaced by a rectangle sum (2), the DLI constant scaled (1), a
default lux factor invented (1), g/W dividing by kWh (3), time-outside counting samples (1), r²
hard-coded to 1 (1), unmapped columns hidden (1), the HTTP source claiming it works from a file (2),
a measured leaf temperature ignored (1), a throwing probe swallowed (1), the demo made
non-deterministic (1).

The kit's own tools found two more on the way in: an `input[type=file]` at 14px (iOS zooms the page
on focus) and a nullable stepper with no `start`, so its first tap would have landed on 0 W — and
**0 W is a claim about the room**, not an empty field.

## A note on the emitter

`gh.py` templated its version with `%`-formatting, like every other module here. That broke the
moment the module carried prose about percentages: `40-85% RH` in a docstring and `width:100%` in a
CSS rule are both format directives to Python, and escaping them by regex double-escaped the ones
already escaped. It now substitutes a token nothing else can look like. **A templating scheme whose
escape character appears in the content is a bug waiting for the first paragraph that mentions a
percentage.**

## Consequences

45 of 45 jobs green, 3245 checks. Registered in `verify_emitters` with both canaries — script banner
and stylesheet — since the one-canary version of that suite let a dead CSS-write line pass twice.

**The rule this leaves behind:** when a page's job is to tell you what is happening in a room, every
path that can fail must say so before you trust it, and every assumption baked into a displayed
number must travel with the number. A VPD without its leaf offset and a PPFD without its lux factor
are both numbers nobody downstream can check.
