# ADR-091 — the blind spot named after the wrong mechanism

*2026-08-28. Status: accepted. Closes the exposure named in
[ADR-089](ADR-089-the-digit-a-reader-was-shown-2026-08-28.md) and
[ADR-090](ADR-090-the-session-nobody-had-rendered-2026-08-28.md).*

## 1. There are no canvases

Both previous records named the same remaining gap, in the same words: *a figure drawn only into a
`<canvas>` changes no text and reads as "not displayed."* I wrote it twice, and it was an assumption
about how the charts are built, never checked.

```
canvases on ecology-lab.html:  0
<svg> elements:               20
<svg text> elements:         138
```

The charts are SVG. What `innerText` actually misses is **SVG `<text>`**, which it excludes because it
reports layout text, and **tooltip content**, which exists only while a chart element is hovered. A
blind spot named after the wrong mechanism is still a blind spot, and worse than an unnamed one,
because it points the search away from the thing.

That is the second time in three slices: ADR-090 sent three fixtures to a reader that never read them,
and this record was ready to go looking for canvas plots that do not exist. Both were assumptions
about implementation, both cheap to check, neither checked.

## 2. What "on screen" now means

```
observed = innerText  +  every <svg text>  +  every tooltip a chart element yields
```

The tooltips are harvested deterministically: dispatch `mousemove` on each sized element inside each
`<svg>` and read the tooltip node after every one. No physical pointer, no per-chart knowledge, one
round trip. The flagship page has **305 hit rects** and yields **258 distinct tooltips**.

Physical `mouse.move` over the charts found nothing at all beforehand, which is worth recording: the
first attempt to look at tooltips reported an empty result and looked like an answer, for the third
time in this arc.

## 3. What the wider view found

| | before | after |
|---|---|---|
| ties reaching a reader (flagship fixture) | 4 of 8 | **6 of 8** |
| rounded at the tie | 0 | **0** |

`structural` (0.575) reaches a reader **only** through a chart tooltip — it was invisible to every
earlier pass. It is displayed at one decimal, because ADR-087 changed that tooltip along with the six
other heredity renderings, so the wider view found no new fault. That is the good outcome, and it is
worth separating from the bad one it could have been: the fix that made it safe was made blind, one
slice before anything could see it.

The three loaded fixtures are unchanged: 9 of 16, 2 of 2, 1 of 2 reaching, **zero rounded at the tie**
anywhere.

## 4. The guard that matters

`verify_tie_render` is now **13 checks**, and the new one is the fragile-link check:

```
PASS  the tooltip harvest is live -- a figure that appears only in a tooltip is still seen
```

If the harvest ever breaks — a renamed tooltip node, a chart that stops using `mousemove` — every other
check in the file still passes, and the pass silently narrows back to what it could see two slices ago.
This one fails instead. `structural` is named in it precisely because it is the only figure that
depends on the tooltip path.

## 5. What is still outside the definition

`OBSERVE` is a definition, not a discovery, and it is now stated in one place so it can be argued with.
Outside it: a `title` attribute, anything only a print stylesheet reveals, and any page whose charts
work differently from these. The verdict is worded **"reaches what a reader can see"** rather than
"is visible", because the first phrase is about the definition and the second would be a claim about
the world.

**The next prediction, and its falsifier.** The tie work is finished on the evidence available: four
loading surfaces, three observation channels, zero figures rounded at a tie. **Falsifier: a display
channel not in `OBSERVE` carrying one** — a print stylesheet is the likeliest, since the kit has print
cards and they are not rendered by any pass. I am not guessing at how likely that is; the last three
guesses in this arc were all wrong in the same direction, which is a pattern worth more than any of
them.
