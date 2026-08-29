# ADR-100 — The instrument was the first thing it found

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-031 (three-way provenance gate; the offline constraint), ADR-061 (silent exclusion
with a plausible face), ADR-065 (a page with no suite), ADR-069 (a check that cannot fail is not a
check), ADR-094 (a worklist with a front), ADR-099 (the prediction was wrong, and the reverse was
true)

ADR-099 closed with a prediction and named its falsifier:

> I expect the same class of defect to exist there in a different form: **an affordance on a page
> that no suite ever exercises**, passing by omission rather than by observation. **Falsifier: an
> enumeration of every control, tab, button and export on all forty pages showing that each one is
> driven by some suite.**

That enumeration is `tools/harness.py`. It exists, it runs, and it produces the number:

```
discovered 3684 = driven 2357 + dead 21 + hidden 251 + failed 4 + excluded 1051   OK
```

**The prediction holds, and it understates the case.** The per-page suites do not drive 2,357
affordances. They drive a few dozen apiece. The overwhelming majority of what a user can touch on
these forty pages had never been pressed by anything, and until this slice there was no way to say
that in a number, which is exactly the shape ADR-065 named.

## 1. What "everything a user can do" was taken to mean

Nineteen kinds of affordance, discovered by selector, in this order — the earlier match wins, so a
`.fek-step .val` is a stepper value and not a generic text box:

| kind | what it is |
|---|---|
| `tab` | `.tab[data-pane]` — the pane switchers |
| `step_val` / `step_btn` | the FEK stepper's editable value and its `+` / `−` |
| `field_in` | `.fek-field input` |
| `readonly_out` | readonly / disabled boxes — **excluded**, see §5 |
| `text_in` | text, number, date, textarea |
| `select`, `slider` | `select`, `.fek-slide input[type=range]` |
| `pick_search`, `pick_opt` | the picker's search line and each of its options |
| `dial_btn`, `chip` | `.fek-dial button`, `.fek-chip` |
| `kopt`, `ck`, `cv`, `swc` | the four bespoke chip rows the kit grew before FEK existed |
| `file_in` | `input[type=file]` |
| `action_btn` | every other `button` — the exports, the adders, the clears |
| `link`, `nav_link` | rail links and hub cards — **excluded**, see §5 |

Each is stamped `data-h="kind:i"`, activated (its owning pane opened first), driven with a value that
is new on every pass, and probed before and after in one round trip.

## 2. The verdict a control gets, and how it is reached

A control is **driven** if pressing it changed something a user could see: the page's visible text,
or *which* elements carry `.on`. It is **dead** if three passes of that produced no change at all.
**hidden** if it was never visible to press, **failed** if the press itself raised, **excluded** if it
is one of the three kinds §5 declares out of scope with a reason.

The five buckets are exhaustive by construction and the report adds them up. `verify_harness` asserts
that identity on every fixture, because the number this tool reports **is** a coverage claim: a
harness that loses an affordance between discovery and verdict is claiming to have driven what it
never saw.

## 3. Six defects, all of them the harness's own

Every one of these was found by reading a finding that was wrong, not by reasoning about the design.
Each is recorded because each was, for a while, a confident false report:

1. **The fingerprint counted `.on` elements instead of naming them.** A dial where the selection
   *moves* from one option to another leaves the count unchanged. **Ten dials reported dead.** Fixed
   by hashing the set of on-elements, not its size.
2. **A control that was already selected could not show its press.** An open tab, a `clearable:false`
   dial. `UNSELECT` deselects first — but the first version baselined *before* the setup click, so
   setup and target cancelled and the control read dead anyway. Fixed by re-baselining after setup.
3. **Widget re-render destroyed the stamps.** FEK rebuilds whole subtrees, so `data-h` went with
   them; the harness looked for an element that no longer existed and wrote it off as invisible.
   **941 of 1,026 "hidden" were "the page rebuilt it away."** Fixed by re-stamping before every
   action. Hidden fell to 251.
4. **The toast was already on screen.** Twelve spore swatches all raise the same toast; if it is
   still showing, raising it again changes nothing. `QUIESCE` clears `.on` from toasts before the
   baseline.
5. **Fields were refilled with the value they already held.** On pass 2 every text box read dead.
   Fixed with a per-action tick, so no value is ever written twice.
6. **A stepper at its bound cannot move.** Pressing `+` at the ceiling is a real no-op, not a wiring
   fault. `HEADROOM` presses the other direction first and re-baselines — and was then extended to
   the bespoke `+` / `−` buttons that predate FEK.

Three further false invariants were retracted the same way:

* **"spills 15px sideways"** on two pages that did not — the metric was `scrollWidth -
  window.innerWidth`, and `innerWidth` includes the vertical scrollbar. Corrected to
  `document.documentElement.clientWidth`. (This did **not** clear selection-log or survey-design;
  those survived the correction and are in §7.)
* **"junk rendered … the estimate is undefined"** — the English word, in prose, in a sentence
  explaining that there is nothing to estimate yet. The comparison now tests the matched *token*,
  never the sixty characters around it.
* **"console error … ERR_INTERNET_DISCONNECTED"** on field-season — the webfont ADR-031 deliberately
  loads non-blocking, failing offline by design. Filtered by the message's `location.url`, because
  the console *text* does not carry it.

The pattern across all nine is one thing: **a control was judged from a state in which its effect
could not appear.** That is the harness's version of ADR-069 — not a check that cannot fail, but a
check that cannot pass.

## 4. The seeded fixtures: showing it fail

`tools/verify/verify_harness.py` writes six pages whose defect is known and asserts the harness
reaches the right verdict on each: a button wired to nothing (`dead`), a button that counts (`driven`,
and **not** dead), a handler leaking `NaN` into a value element (invariant break), a 900px row in a
390px viewport (`spills`, naming the element), a control that exists only behind a closed tab
(`driven`, not `hidden`), and a handler that throws (`failed`, reported not swallowed). The accounting
identity is asserted on all six. Four assertions pin the corrections in §3 so they cannot silently
regress. **22 of 22.**

One of those fixtures failed on first run, and the fixture was wrong: its readout lived in the pane
that closes, where a `display:none` ancestor keeps text out of `innerText`. The harness was right.
The fixture was rewritten to match the kit's real pattern.

## 5. The three exclusions, each with its reason

Exclusion is the hole ADR-061 is about, so there are exactly three and each carries a sentence, not a
label. `verify_harness` asserts every excluded kind is one the harness actually discovers and that
every reason is longer than a label:

* **`link` (524) and `nav_link` (526)** — a click navigates away and ends the run on a different page.
  Every `href` is instead resolved structurally against `tools/artifact_map.json`.
* **`readonly_out` (1)** — a readonly or disabled box is a display, not a control. Typing into one is
  not something a user can do; five of them had been reported as affordances the harness *failed to
  drive*, when the truth was that nobody can drive them.

That is the whole of the 1,051. Nothing else is out of scope.

## 6. The numbers

```
pages driven                          40
affordances discovered              3684   over 3 discovery passes
  driven                            2357
  dead                                21
  hidden                             251   (1026 before the re-stamp fix)
  failed                               4
  excluded                          1051   (524 link + 526 nav_link + 1 readonly_out)
actions that broke an invariant       62

viewport                       390 x 844   a phone, held in a wet field

suite   61 of 61 jobs green, 4322 of 4322 checks passing   (60 / 4300 before)
        verify_harness 22/22 is the new job
```

Twelve pages discovered affordances but drove none: they are the prose pages — the ADR, the essay, the
glossary, the field card, the four suite indexes, the hub. Their entire surface is rail and nav links,
which is the correct answer for a page whose only affordance is going somewhere else.

## 7. The worklist this hands on

**The one real defect, and it is on fifteen pages.** `.row2 .g span` declares
`overflow:hidden; text-overflow:ellipsis` with **no `white-space:nowrap`**. An ellipsis cannot render
on wrapping text; the rule can never fire. It is one rule, copied verbatim into fifteen pages:

```
breeding-bench  cell-bench  collection-sheet  cp-bench  deployment-log  ethogram
greenhouse  micro-bench  ordination  releve  selection-log  soil-bench
soil-recipes  stand-sheet  survey-design
```

Every other `text-overflow:ellipsis` in the kit (farm-scout, field-notebook, and the second rule on
those fifteen) carries `white-space:nowrap` and is correct. This is a rule that cannot fire, sitting
next to the same rule written correctly — ADR-069's shape, in CSS.

Also handed on, unfixed:

* **21 dead affordances.** breeding-bench "Clear trial"; cp-bench's *Brocchinia* option; ecology-lab
  ×6; ethogram's two sampling `kopt`s; field-notebook "↩ Undo" and "Copy CSV"; pheno-tracker "✕" and
  "🍎 fruit program"; releve's two scale `kopt`s; selection-log's first stepper value; stand-sheet's
  two region `kopt`s and "📷 Add photos"; tree-proofs "New random tree". Some of these will be
  correct no-ops — pressing the already-chosen scale, clearing an empty trial. **None has been read
  yet.** The list is a worklist, not a verdict, and calling it one would be exactly the
  over-claim ADR-094 is about.
* **4 undriveable `ecology-lab` textareas** — `fill` times out on all four.
* **The surviving overflow reports.** selection-log 15px ×36 and 37px ×1; survey-design 9px ×23. They
  survived the `clientWidth` correction, so the spill is real; the exact state that triggers it was
  not isolated in this slice.
* **2 `junk rendered` on field-notebook** — both under the two Copy buttons, both naming the
  Lincoln–Petersen readout before a recapture exists.

## 8. What is not done

* **No page changed.** This slice is `tools/harness.py`, `tools/verify/verify_harness.py` and the
  ledger. Nothing was republished; no artifact was touched, so no staleness is owed.
* **The harness is not a gate.** It writes `tools/harness_ledger.json` and prints. Wiring its verdicts
  into `run_all.py` would make the twenty-one dead affordances a red suite before anyone has read
  them, and a red suite nobody can turn green gets ignored — which is how a gate becomes a decoration.
  `verify_harness` gates the *harness*; the harness reports on the *kit*.
* **`hidden` is honest but coarse.** 251 affordances were never visible across three passes. Some are
  behind states the harness never reached — an export that only appears once a row exists. It does not
  currently distinguish "unreachable" from "not reached by this walk".

**The next prediction, and its falsifier.** The twenty-one dead affordances are claimed by me, here, to
be *mostly* correct no-ops. I expect that to be wrong: **at least three of the twenty-one are genuinely
unwired — a handler never attached, or attached to a selector that no longer matches.** **Falsifier:
reading all twenty-one against the page source and finding that every one of them is a legitimate
no-op.** That reading is the next slice, and it comes with the fifteen-page `white-space` fix, which
is one line and can be measured before and after by the harness that found it.
