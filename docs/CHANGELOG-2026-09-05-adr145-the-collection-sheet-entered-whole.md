# Changelog — 2026-09-05 — ADR-145: the collection sheet, entered whole

ADR-144 measured what the kit's tasks actually enter. The flagship data-entry
page read **6 of 63 fields**. This slice enters the rest.

## The task — `tools/tasks/page-collection-sheet-science.json`

35 steps → **104**. Site and weather, coordinates, one specimen described in
full, a spore print, four spot tests, a voucher label.

```
collection-sheet.html    6 → 59 of 63 fields   (9 → 66 confirmed expectations)
the kit                185 → 237 of 517 fields  (36% → 46%)
```

| block | held to |
|---|---|
| site & weather | **14 days after a 32 mm event**, inside the 7–21 day window, soil at 10 cm |
| coordinates | `coordinateUncertaintyInMeters` **36 m** → **5395 m** (datum unknown) → **36 m** |
| the specimen | the field-sheet export, line by line |
| spore print | the print note and the export |
| voucher | the label: locality with coordinates, habitat, substrate with host, spore print, fresh characters, spot tests |

The three coordinate figures are **recomputed**, by a Python port of the page's
own point-radius `uncertainty()` — 30 m of GPS plus 5.53 m for four decimal
places at this latitude is 36 m; an unknown datum adds 5359 m. A number a tool
can compute is never a number a task author remembers.

**Four reagent rows are left blank on purpose.** The sheet's rule is that blank
means *not tested*, which is not negative, and the export keeps them apart.
Filling them to raise a coverage number would be inventing observations. So the
page reads 59 of 63, and the four are a decision rather than a gap.

## A page coupling, held both ways

Typing the stand's dominant trees **replaces** the host picker's regional list
with your stand. `Quercus gambelii` is refused; `Pinus contorta` is taken.

That one refusal exposed three defects — all in the instrument.

## `tools/harness_plugin_page.py` — a picker cannot stop being a picker

`pick` checked for an option in the DOM **before** typing. This sheet *removes*
non-matching options rather than hiding them, so after one refused filter the
picker had none — and every later pick answered `not a picker`, including the
one that would have cleared the filter. A single refused pick made the control
unusable for the rest of the session.

Whether something is a picker is **structural**; whether it has options is a
fact of the moment. The guard now stands on `.fek-pick`, and where there is
none, on the control's **own** options (`:scope > .opt`, `:scope > .opts > .opt`)
— the first fix searched the whole parent subtree, and a pick aimed at a plain
text input reached another picker's options and clicked one.

## `tools/harness_tasks.py` — a refusal is a move too

The gateway raises before it observes, so a refused response carries no
snapshot — and the next `@control:<name>` resolved against the last
**successful** step's snapshot, which the refusal had just made stale by
rebuilding the picker. The runner blamed the page for a stale name of its own.
`run_task` now observes after a refusal and attaches the snapshot to the refused
result.

## `tools/audit_states.py` — an identity that survives the page growing

The stamp is `tag#id.class` plus occurrence among identical siblings. For a
dial's options — no id, no distinguishing class — the occurrence index *was* the
whole identity, counted across the **whole document**. Adding a collection row
anywhere above renumbered everything below it, so a control measured before the
row existed was a different control after: the stand-age dial came back from
ADR-144's measurement as *never entered* by a task that had just clicked it.

The index is now counted **within the nearest identified ancestor**
(`…@hostId`), which is stable against the growth that actually happens. This was
ADR-144's own stated caveat, found biting three days later by the first task
that made a page grow while measuring it — and fixing it recovered phantom
misses on every page whose task makes it grow, which is most of the kit's
+52 fields.

## Verification

- `verify_report` **85** (+6): a picker whose filter matches nothing is refused
  as *no option matches*, not as *not a picker*; the page really has removed
  every option; the next pick still works; a pick on a plain text input is still
  *not a picker*; and each picker's option pool is keyed by its own search box.
- `verify_audit_states` **67** (+3): a control with no id keeps its stamp when
  the page grows somewhere else — and a control **with** an id is keyed by the
  id alone, no host in the stamp, so moving it into a different identified
  ancestor keeps every measurement taken under it. (A surviving mutant asked
  that second half: scoping a named control to its host too would re-key it the
  moment the page moved it, which is the failure the host scoping exists to
  prevent.)
- `verify_tasks` **284** (+2): a refused step carries a snapshot, and is still
  recorded as a refusal.
- `mutate_report` **52**, `mutate_audit_states` **45**, `mutate_tasks` **63**.

## Held

- ecology-lab 7 of 40, stand-sheet 9 of 50, deployment-log 17 of 37 are still
  where this page was. The method is now a worked example rather than a plan.
- **A held export line is not a held science.** The sheet echoing "odour faintly
  raphanoid" proves it carries what was entered, not that the odour was recorded
  correctly.
- **The four blank reagents are a claim too**, and unheld: nothing checks that a
  blank row exports as *not tested* rather than as negative.
- The coordinate oracle ports the page's own arithmetic, so it catches a change
  in the page but not a shared misunderstanding of the method.

## Docs

`docs/ADR-145-the-collection-sheet-entered-whole-2026-09-05.md`;
`docs/AI_HARNESS.md`.
