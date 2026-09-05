# Changelog — 2026-09-04 — ADR-140: the charts, read

## Harness — `tools/`

- `harness_plugin_page.py`: `read-report` returns **`charts`**, one entry per
  visible `<svg>` (16 max), each with `viewBox`, `texts` (40 max, each with the
  `x`/`y` the page gave it), `n`, `marks` (a count per tag), `longest` (the most
  points any one polyline or path carries), `aligned.row` / `.col` (the longest
  row of text sharing a y, left to right; the longest column sharing an x, top
  to bottom), `points` (each text paired with the nearest mark within 30 units)
  and `at` (every mark centre, labelled or not). Read in the svg's **own units**,
  not rendered pixels, so an oracle can recompute what the page computed.

## Tasks — `tools/tasks/`

- `page-greenhouse-science`: a `charts` step holding `runChart`'s viewBox, its
  5 dots, its 5-point path and **the x of every dot** — 52, 203, 354, 505, 656,
  from a Python recomputation of the page's own `X(i)` — plus the two label rows
  at y 36 and 198. And after the runs are wiped, `output.charts` **excludes**
  `runChart`: there is no chart, and saying so is a fact about the page.
- `page-selection-log-science`: `gradBox`'s viewBox, 6 circles, 3 lines and the
  x of the first, second and last dot (44, 144.4, 546).
- `page-ordination-science`: `ordPlot`'s viewBox, 4 circles, 4 axis lines and
  all four sites present by name. Coordinates deliberately not held — the NMDS
  seed is not pinned by this task.
- `page-food-web-science`: `webSvg`'s viewBox, 10 nodes, 13 links, 20 texts and
  the species column in trophic order.

## Verification

`verify_report` **60** (+11) — the fixture gained two charts and a hidden one:
a visible svg is a chart and a hidden one is not; the viewBox and text count;
marks by tag; the longest series from the path in one chart and the polyline in
the other; the **lowest** aligned row rather than the first found; the leftmost
column top to bottom; the labelled pairs; every centre in `at`, a rect by its
middle; a mark with no text near it placed but not named.

`mutate_report` **47** (+12), 47 killed, 0 survived. Also fixed: the BOX-regex
mutant's anchor had been stale since ADR-135 widened that regex, so it had been
reported inconclusive in every run since.

54 tasks held, both canaries refuted, 12 traces PASS.

Kit **77 / 77 jobs, 5,747 / 5,747 checks**; board 5,337 checks / 272 mutants;
publish reach 42 / 42 measured.

## Measuring the board turned up two more

- `publish_state.py` / `publish_reach.py`: `--taken <epoch|now>` — a third way to
  date a saved copy, for the case where a read comes back as the artifact's own
  HTML with no `<base href="/_f/<epoch>-…">` marker in it. It is **the fetching
  reader stating when it fetched**: below the marker, above mtime, never
  overriding a marker that is present, and recorded as being about the fetch
  rather than about the version. Without it one artifact could never be measured
  at all.
- `harness_board.py`: the board asked for its webfont stylesheet with
  `media="all"`, holding first paint on a font request — ADR-031's rule, broken
  on the one page that reports on everything else. Now `media="print"` with a
  `<noscript>` fallback and the promoter, like every other page of the kit.
  Visible only in a measurement of the PUBLISHED copy, which is where it was
  found.

`verify_publish_reach` 81 (+3); `mutate_publish` 17 killed, 0 survived (+2).

## ...and a third

- `audit_states.py`, two fixes: `coverage()` settles and measures exposure once
  more before counting (the end of the walk is still the last state), and the
  walk now waits for **two animation frames** before measuring in every state.
  `_settle` answers "is anything still moving?" and cannot answer "has the
  browser laid this state out yet?" — a control revealed from a page's own
  `requestAnimationFrame`, or a browser competing for the CPU with the other
  half of `run_all -j 2`, has no box when the click handler returns.
  `audit_focus` and then `audit_contrast` each produced exactly one phantom
  "never exposed" under the parallel run and none of it alone; both are clean
  now, run side by side. `verify_audit_states` 58 (+3); `mutate_audit_states`
  39 killed, 0 survived, **2 recorded equivalent** — the frame wait is defence
  against contention and no fixture can reproduce contention, which is said in
  the ledger rather than asserted by a check that could not fail.

## Docs

`docs/ADR-140-the-charts-read-2026-09-04.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
