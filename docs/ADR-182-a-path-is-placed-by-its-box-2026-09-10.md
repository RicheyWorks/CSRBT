# ADR-182 — A path is placed by its box: the lab's bars are read, and its workbench charts are held to a port of the chart they are drawn with

**Status:** accepted · **Date:** 2026-09-10 · **ADR-140's chart reader placed marks by `cx` and by `x + width/2`, and counted a path's points as its `M`s and `L`s. The ecology lab draws every bar as a rounded path (`M V Q H Q V Z`) and its survivorship line with `H` and `V`, so its sixteen readable charts came back as rows of transparent hit-rects at one y, every bar's height nowhere in the report, and a step line read as one point. `read-report` now reports each path's box — the smallest `[x0, y0, x1, y1]` holding every point a command ends at, absolute or relative — counts every command that ends somewhere as a point, rounds a rect's centre like every other number, and leaves an unplaced mark out of `at`. The lab's two workbench charts are held by their task to a Python port of `barChart`, fed from the task's own typed counts, and `verify_eco` holds the page's paths and the task's literals to the same port.**

## What the reader could not see

The lab's `barChart` draws a bar as

    M x,y+h  V y+r  Q x,y x+r,y  H x+w-r  Q x+w,y x+w,y+r  V y+h  Z

— a path, not a rect — and lays a transparent `rect` over each column for the
tooltip. ADR-140's reader placed rects by their middle and circles by their
centre and read a path only for how many `M` and `L` it carried. So a bar
chart read as *n* hit-rects, all centred at the frame's mid-height, and *n*
paths of "one point" each: the count of bars was right and every height was
missing. The survivorship curve, drawn `step: true` with `H` and `V`, was one
point. And the hover dot `lineChart` appends before it has a position
(`circle r=4 opacity=0`, no `cx`) came back as `[null, null]`, while a rect
whose centre fell on float noise came back as `58.050000000000004`.

Probed at the lab task's end: sixteen charts read (the cap), ten of
them bar charts, and nothing a task could hold about any bar but that it was
there.

## What changed

**`spans`, per chart.** For each `<path>` (up to 40), the box its commands'
endpoints span, in the svg's own units, rounded to two places. The parser
follows `M L H V C S Q T A` and `Z`, upper and lower case, with the implicit
line pairs after an `M`; it takes the point each command *ends* at and not a
curve's control points, which are not on the curve — for the lab's bars the
control points sit at the box's corners and it changes nothing; for a wide
curve the box is understated by the bulge. That is stated rather than fixed
because the honest alternative is a curve flattener, and no page in the kit
draws a curve whose bulge a task would want to hold.

**`longest` counts every command that ends somewhere.** Under `[ML]` a step
line was one point and a rounded bar one; now the step line is its steps and
a bar is six. Nothing held moves: every path a task holds `longest` on is
drawn with `M` and `L` only.

**`at` is rounded, and an unplaced mark is nowhere.** A circle without `cx`
is still counted in `marks` (it is drawn) and is not placed (it is not
anywhere yet). A rect's centre goes through the same two-place rounding as
every other number in the report — `0.1 + 0.2` is the fixture.

**The lab task holds its workbench charts.** At `field-back` — after typing
robin 34, sparrow 21, wren 8, finch 3, thrush 1 — `wb-field-out` holds five
boxes, the tick column 36 / 27 / 18 / 9 / 0, the marks, `longest` 6 and the
first hit-rect's centre; at `quad-twelve` — twelve quadrats, five of them
empty — `wb-quad-out` holds seven boxes (an empty quadrat draws no bar),
twelve hit-rects, ticks to 63, the last hit-rect's centre. Every number comes
from `bar_chart()` in the patch, not from the page: margins 42 / 10 / 12 / 34,
`yMax = 1.05 × max`, ticks `fmt(yMax·i/4)` with the page's decimals rule and
half-up rounding, bars of `iw/n − 2` at `x = 42 + i·iw/n + 1`.

**`verify_eco` holds both ends.** It types the same field and the same
quadrats into the live page, parses each path's `d` with its own box
routine, and holds the page's boxes, tick labels, rect and line counts to the
port; then holds the task's literals to the same port and the task's typed
text to the port's input. Moving a box by a hundredth in the task fails the
suite; so does changing a tick.

## What moved

    verify_report                 115 → 120     mutate_report        69 → 75 / 75
    verify_eco                    138 → 143
    page-ecology-lab-science      202 → 211
    every page task               44 / 44 held under the new reader (the canary refuted)

Two reader rules, one suite, one runner, one page suite, one task. No page was
edited.

## Held

- The box is the endpoints' box. A `Q` or `C` whose control point lies
  outside the endpoints is understated; the comment in the reader says so and
  the ADR says so, and the lab's bars are exact.
- A relative path is placed where it ends up: the fixture's second bar is
  drawn with `m v q h q v z` and must read at the same box as its absolute
  twin shifted right.
- The lab's remaining charts: the terrarium's two and the ten station charts under the cap
  are drawn from the shipped session and from a seeded stream, and the port
  here is of the *chart*, not of the data — a station chart is held only when
  its series is; `verify_lab` reproduces the shipped protocol and could feed
  the port next. The theory bench's logistic curve (61 points) is a `lineChart`
  and its port is the model, which this slice does not carry.
- The sixteen-chart cap: the lab's stations past `station-grid` (models, the
  keys, the tree, the deck) are not read at the task's end because sixteen
  earlier svgs are. ADR-140's cap stands; a task that wants a later chart
  reads it on a pane where fewer are visible, and the lab has no panes.
- Not done here: the visualizer's tree, the character keys' figures, the
  cp-bench dormancy chart and the greenhouse's second chart still draw
  unasserted (ADR-181's list, less nothing). The rest of ADR-181's held list
  stands.
