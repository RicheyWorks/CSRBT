# 2026-09-09 — ADR-177: the last five outputs, read — the outputs loop closes

**Five pages had one unread output each. Every one is now pressed and held by
its task — the soil bench's recipe and the protocol library's first protocol
byte for byte, the three prints to one payload — and the protocol library
gets a suite that runs its five protocols through the engine. Unread outputs
5 → 0 of 66.**

## Changed — tasks

- `page-farm-scout-science` 117 → 120: `Print / save PDF` on the export pane
  → one print, nothing else; the scouting figures unchanged after.
- `page-pheno-tracker-science` 102 → 105: `Print / save PDF` on the
  segregation pane → one print; the selection differential +1.44 after.
- `page-field-season-replay` 35 → 41: `Print the season` after the grade →
  one print; the results card still says the meadow held 101 voles.
- `page-soil-bench-science` 72 → 78: `Copy recipe` on the 1:1:1 mix → the
  recipe byte for byte (`Mix recipe — 3 parts total`, one line per part with
  its 33% share); nutrient load `1.00 / 5` after.
- `page-eco-protocol-library-reference` 9 → 12: the first `Copy` →
  `meadow-disturbance.eco` whole, one clipboard payload and nothing else.

## Changed — suites

- `verify_fs` 45 → 48, `verify_pt` 60 → 63, `verify_two` 37 → 40: stub
  `window.print`, press the button, hold one print and the export unchanged;
  pin the task's print step.
- `verify_soil` 70 → 75: a port of the recipe as the prose states it (parts
  over the total, whole percent, one line per part); the page's clipboard and
  the task's literal held to it; an empty mix copies nothing.

## New — `tools/verify/verify_epl.py` (40)

- The page: five `*.eco` protocols, one `Copy` each, each copied byte for
  byte; every line a directive, a comment or blank; the meadow's
  `hot 2000 5 90` line and its one *deliberately wrong* expectation.
- The engine: each copied protocol run through `ExperimentLab` — no problem
  line; seed, phases, models and expectations counted as the text carries
  them; every `expect:` graded in order; notes, datasets and crosses reaching
  the bench; the deliberately-wrong line the one refuted. Skipped and said so
  where the engine is not built. `MUTATE_ROLE = "subject"`.
- The task's literal is the first protocol's text.

## Finding

`two-ponds.eco` grades 1 of 3 and `activity-budget.eco` 0 of 2 in the kit's
own engine: `evenness(pondA) is uneven` observes 0.763 (*moderate*),
`brayCurtis(pondA, pondB) > 0.4` observes 0.311, `evenness(morning) is
uneven` observes 0.894 (*very-even*), `brayCurtis(morning, afternoon) > 0.3`
observes 0.237 — predictions the page presents as the experiment's, with
comments asserting them. Recorded in the suite as `KNOWN_REFUTED`; a page
edit with a republish, not made here.

## Numbers

    unread outputs   5 → 0 of 66      every page's ceiling 0
    verify_epl       new, 40

One page edited: `docs/soil-suite.html`'s Soil Bench card, `70/70 verified` →
`75/75 verified` (the hub advertises `verify_soil`'s size; `verify_advertised`
holds it), republished and swept.
