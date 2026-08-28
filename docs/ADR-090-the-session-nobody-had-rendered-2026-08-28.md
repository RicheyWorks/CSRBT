# ADR-090 — the session nobody had rendered

*2026-08-28. Status: accepted. Extends the render pass in
[ADR-089](ADR-089-the-digit-a-reader-was-shown-2026-08-28.md) to the fixtures a reader loads by hand.*

## 1. Where I sent the files, and where they actually go

ADR-089 rendered the one page that inlines its session and listed the other three fixtures as loaded
"on a drop", pointing them at `demo/visualizer.html`. Driving that file input, the visualizer **refused
two of the three** — out loud, with an `alert()`:

```
Could not load: not a TreeExport state or TreeSessionRecorder session
```

A refusal that specific looks like an answer. It was an answer to the wrong question. The experimental
runner's own javadoc says where those two go:

> writes `docs/ecology-trace-session.json`, which `docs/ecology-lab.html` renders (drag-drop it onto
> the page)

and `eco-protocol-reference.html` says the same for the experiment session, in a row of its own table.
**The reader was documented in three places and I had assumed a fourth.** The tool now carries a
`READERS` table — fixture, page, mechanism — with each entry established by trying it, and it refuses
to report on a fixture whose page did not change when the file arrived, because "0 ties displayed" for
a file the page never read is true and useless (ADR-061).

## 2. Six digits chosen by the rounding rule

With the drop path driven, `ecology-experiment-session.json` on `ecology-lab.html`:

```
16 tie(s), 9 reach the rendered text, 6 rounded at the tie
```

| figure | value | shown | the other digit |
|---|---|---|---|
| evenness J′ | 0.875 | **0.88** | 0.87 |
| allele frequency p | 0.5425 | **0.543** | 0.542 |
| allele frequency q | 0.4575 | **0.458** | 0.457 |

The inline session was clean after ADR-089. The *same page*, fed the session a reader is explicitly
told to drop onto it, was showing six digits the rounding rule picked. Nothing had ever rendered that
file — `verify_engine_sessions` names it as unbound, `verify_visualizer_sessions` checks tree
invariants on other files, and no suite loads it into anything.

Evenness now shows three decimals and the allele frequencies four, which is where those figures stop
sitting on a boundary. `arena-search-session.json` (2 ties, both reaching the text) and
`ecology-trace-session.json` (2 ties, 1 reaching) were already clean.

**All four loading surfaces now report zero.**

## 3. A verdict that named something it had not measured

The first run reported the six as `[('evenness', 2), ('evenness', 0), ('p', 3), ('p', 1), ('q', 3),
('q', 1)]` — as if it had established *which precision* each was rounded at. It had not. The boundary
nudge moves the **value**; it cannot be aimed at a precision, so every row carrying the same literal
gets the same verdict and the precision beside it is the row's tie candidate, not a measurement.

Six findings, three facts, and the extra three came from the report's shape rather than from the page.
That is the same failure as a check that passes for the wrong reason, printed instead of asserted. The
finding is deduped by value now, and the docstring says what the flag is a property of.

## 4. What the suite locks

`verify_tie_render` grew from 7 to **12 checks**: the drop path is driven, the page is confirmed to
have accepted the file, the three figures are checked, and a canary puts one precision back and
confirms it is caught again. Bounded deliberately — the suite re-checks the figures this record fixed
rather than re-rendering all sixteen, because a suite that takes four minutes gets run less often than
one that takes two.

The full sweep across all four surfaces stays in `tools/tie_render.py`, where it is a finder.

## 5. Three blind spots, all named

- a figure drawn only into a `<canvas>` changes no text and reads as "not displayed";
- a page that reports through `alert()` says nothing `innerText` can see — which is why the tool now
  listens for dialogs, after a first version read a refusal as a silence;
- `only=` narrows a scan, so a suite using it is checking what it names and nothing else.

**The next prediction, and its falsifier.** Every fixture the kit ships now has a reader that has been
driven at least once, and every one reports zero. The remaining exposure is the first blind spot:
figures that reach a chart but never the text. **Falsifier: reading the values a chart draws — from the
canvas or from the series handed to it — and finding one rounded at a tie.** Two of the eight in the
flagship fixture report "no change on screen" today and at least one of those is a tooltip, so the
place to look is already named.
