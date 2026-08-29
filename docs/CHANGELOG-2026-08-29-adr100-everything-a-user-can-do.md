# 2026-08-29 — ADR-100: a harness that drives everything a user can do

Companion to `docs/ADR-100-the-instrument-was-the-first-thing-it-found-2026-08-29.md`.

## The falsifier ADR-099 asked for

> **Falsifier: an enumeration of every control, tab, button and export on all forty pages showing
> that each one is driven by some suite.**

Built. `tools/harness.py`, 561 lines, one command:

```
python3 tools/harness.py -j 3
discovered 3684 = driven 2357 + dead 21 + hidden 251 + failed 4 + excluded 1051   OK
```

**The prediction holds and understates it.** The per-page suites drive a few dozen affordances each.
2,357 had never been pressed by anything.

## What it does

Discovers nineteen kinds of affordance by selector — tabs, stepper values and buttons, FEK fields,
text and number and date boxes, selects, sliders, picker searches and options, dial buttons, chips,
the four bespoke chip rows (`kopt` / `ck` / `cv` / `swc`), file inputs, every other button, and links.
Stamps each `data-h="kind:i"`, opens the pane that owns it, drives it with a value new on every pass,
and probes before and after in one round trip.

**Verdict:** *driven* if the visible text or the set of `.on` elements changed; *dead* if three passes
changed nothing; *hidden*, *failed*, or *excluded*. Five buckets, exhaustive, and the report adds them
up — `discovered == driven + dead + hidden + failed + excluded` is asserted on every fixture, because
that number is the coverage claim.

Each action also checks invariants: no uncaught error, no `NaN` / `undefined` / `null` reaching a value
element, no console error, and nothing spilling past a 390px viewport.

## `tools/verify/verify_harness.py` — 22 checks, the new job 61

Six synthetic pages whose defects are known: a button wired to nothing, a button that counts, a handler
leaking `NaN`, a 900px row in a 390px phone, a control behind a closed tab, a handler that throws. Each
asserts the harness reaches the right verdict — including that the working button is **not** reported.
Four more assertions pin the measurement corrections below so they cannot regress.

One fixture failed on first run and the *fixture* was wrong: its readout sat in the pane that closes,
where `display:none` keeps text out of `innerText`. Rewritten to the kit's real pattern.

## Nine false findings, all the instrument's own

| what it reported | why it was wrong | fix |
|---|---|---|
| 10 dead dials | fingerprint counted `.on` elements; a *moving* selection keeps the count | hash which elements are on |
| an open tab, a `clearable:false` dial | already selected, so the press cannot show | `UNSELECT` — and re-baseline *after* the setup click, which the first version did not |
| 941 of 1,026 "hidden" | FEK re-renders subtrees and takes `data-h` with them | re-stamp before every action; hidden → 251 |
| 12 dead spore swatches | all raise the same toast, already on screen | `QUIESCE` before baselining |
| every field dead on pass 2 | refilled with the value it already held | per-action tick, never the same value twice |
| steppers at their bound | a real no-op, not a wiring fault | `HEADROOM` presses the other way first |
| "spills 15px" on two clean pages | `window.innerWidth` includes the scrollbar | `documentElement.clientWidth` |
| "junk rendered … undefined" | the English word, in a sentence about having nothing to estimate | compare the matched token, not the text around it |
| "console error … ERR_INTERNET_DISCONNECTED" | the webfont ADR-031 loads non-blocking, offline, by design | filter on `location.url` — the console text has no URL |

One pattern: **a control judged from a state where its effect could not appear.**

## Three exclusions, each with a reason

`link` (524) and `nav_link` (526) — a click ends the run on another page; hrefs are resolved against
`tools/artifact_map.json` instead. `readonly_out` (1) — a display, not a control; five had been
reported as affordances the harness *failed to drive*. That is the whole 1,051.

## The worklist it hands on

**`.row2 .g span` declares `overflow:hidden; text-overflow:ellipsis` with no `white-space:nowrap`** —
an ellipsis that can never render. One rule, verbatim, on **fifteen pages**: breeding-bench,
cell-bench, collection-sheet, cp-bench, deployment-log, ethogram, greenhouse, micro-bench, ordination,
releve, selection-log, soil-bench, soil-recipes, stand-sheet, survey-design. Every other ellipsis rule
in the kit carries `nowrap` and is correct.

Also: 21 dead affordances (unread — a worklist, not a verdict), 4 undriveable `ecology-lab` textareas,
selection-log spilling 15–37px and survey-design 9px after the `clientWidth` correction, and 2
`junk rendered` under field-notebook's Copy buttons.

## Not done

No page changed; nothing republished; no staleness owed. The harness is **not** wired into `run_all.py`
— twenty-one unread dead affordances would make a red suite nobody can turn green, and that is how a
gate becomes a decoration. `verify_harness` gates the harness; the harness reports on the kit.

## Suite

```
61 of 61 jobs green, 4322 of 4322 checks passing   (60 / 4300 before)
verify_harness  22/22   new
```
