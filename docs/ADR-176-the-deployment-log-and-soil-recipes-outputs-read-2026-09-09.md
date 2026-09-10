# ADR-176 — The deployment log's field sheet and the soil recipes' shopping list, read

**Status:** accepted · **Date:** 2026-09-09 · **Two pages, four exports, none read: the deployment log's field sheet and print, the soil recipes' scaled list and print. Both tasks now press and hold them byte for byte; the sheet's arithmetic is pinned by `verify_dep`'s ports and the list by a new port of the page's own scaling rules in `verify_recipes`. Unread outputs 9 → 5.**

## Two pages, one shape

With every page carrying three or more unread outputs closed (ADR-172 to
ADR-175), the worklist is pages with one or two. Two a slice from here.

**The deployment log.** Its task (ADR-152) already held the CSV; the *field
sheet* — the thing a technician tapes to the recorder — and the print were
unread. The task presses `Copy field sheet` in its end state and holds the
sheet **byte for byte**: three deployments in the order logged (flight, logger,
recorder), the flight's `GSD 2.10 cm/px` at 120 m, the logger's `every 1 min,
90 d planned`, the recorder's `sr 48 kHz, mono, 600 s in 600 s, 30 d` with
`Nyquist 24.0 kHz` and its caveats; then `Print / save PDF` → one print. 174
→ 183 confirmed. `verify_dep` pins the literal's arithmetic from its own
ports: the GSD from the sensor the task typed over the RedEdge preset (6.17 mm,
8.8 mm focal, 4000 px — the sheet keeps the preset's *name*, which is the
page's behaviour and is recorded as such), the Nyquist from the sample rate,
and the deployment order. 105 → 109.

**The soil recipes.** Its task (ADR-158) scaled Coot's mix to a quarter batch
and read the tiles; `Copy the list` and the print were unread. The task presses
both and holds the list **byte for byte**: author and source, one part each of
peat, compost and aeration, a cup of kelp meal scaled to `4 tbsp`, the half
cups to `2 tbsp`, the flax range to `2–4 tbsp`, the rock-dust range to `12
tbsp–1 cup`, the cook and the warning, the transcription footer. 40 → 49.
`verify_recipes` gains a **port of the page's scaling and formatting rules**
— the rules its prose states: the published wording at 1×, a scaled cup below
one cup in tablespoons and a tablespoon below one in teaspoons to one decimal,
a range keeping both ends and dropping the first unit only when both agree —
applied to the recipe data the page carries, and holds both the page's export
and the task's literal to it. 238 → 241.

## What moved

    deployment-log outputs      1 → 3 of 3 held      ceiling 2 → 0
    soil-recipes outputs        0 → 2 of 2 held      ceiling 2 → 0
    the kit's unread outputs    9 → 5 of 66          (5 pages, one each)
    page-deployment-log-science   174 → 183     verify_dep       105 → 109
    page-soil-recipes-scaling      40 → 49      verify_recipes   238 → 241

No page was edited: two tasks, two page suites, and the ledger.

## Held

- The field sheet labels the custom-sensor flight `MicaSense RedEdge`: the
  camera dial's label is written to the log while the numbers typed over it
  decide the GSD. The task holds what the page does; whether the sheet should
  say "custom" is a page question, noted here and not answered here.
- `12 tbsp–1 cup` is the range rule working as stated: 0.75 cup prints as
  tablespoons and 1 cup as a cup, so the units differ and both are shown.
- Not done here: farm-scout, pheno-tracker, field-season, soil-bench,
  eco-protocol-library — one unread output each.
