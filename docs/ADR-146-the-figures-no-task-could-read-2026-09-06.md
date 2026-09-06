# ADR-146 — The stand sheet, entered whole — and the figures no task could read

**Status:** accepted · **Date:** 2026-09-06 · **ADR-145's method applied to the second page: the stand sheet goes 9 → 51 of 51 fields, 56 → 214 confirmed expectations. Entering it whole surfaced something the kit had never measured — `read-report` reads the elements the kit NAMES as outputs, and a page that writes a figure under any other name is invisible to it, silently. 40 such elements across 12 pages, 26 after this slice. `tools/audit_readable.py` measures it and ratchets it downward**

## 1. The second page

ADR-144 measured what the kit's tasks enter and ADR-145 took the first page from
6 of 63 fields to 59. The stand sheet was the next-largest gap: **9 of 50**, and
every figure the other 41 feed — the plot area and expansion factor, Reineke's
SDI, Curtis & McIntosh's importance value, van Wagner's line intercept, McCune &
Keon's heat load, the Darwin Core coordinate uncertainty, the field sheet — was
computed by a page nothing had ever driven past a four-stem tally.

The task now enters all of it: **149 steps, 9 → 51 of 51 fields, 56 → 214
confirmed expectations.** The kit goes **237 → 279 of 518 (46% → 54%)**, and the
stand sheet is the first page in the kit entered **whole**.

## 2. What is held, and what is recomputed

| block | held to |
|---|---|
| the key | 34 species → 16 in the Sierra → 7 in bundles → 4 at five per bundle → 2 matching "white" → 1 matching "whitebark"; the species card carries *Pinus albicaulis* and its key characters; Start over returns all 34 |
| species packs | a pack missing `sci`, `leaf`, `reg` and `key` is **rejected whole** and nothing is loaded; a good one adds one species and one region — 34 → 35, 4 → 5 |
| the stand | 4 live stems, 100 stems/ha, 6.9 m² BA/ha, QMD 29.7 cm, **SDI 132**, top height 34.0 m; a snag counts and undo removes it; DBH 0 is refused |
| composition | **Douglas-fir IV 78.6** against the pine's 21.4, from relative density 75.0/25.0 and relative dominance 82.3/17.7 — and the sheet says it leads *on both* rather than on dominance, because the gap is 7.3 points and its own rule is 12 |
| plot geometry | 11.28 m → 400 m², EF **25.0**; 5.64 m → 100 m², EF **100.1** (not 100.0 — the area is 99.92 m²); 20×20 m rectangle → the same 400 m² and the same EF |
| heat load | SW folds to **180°** and reads *hot*, NW to **90°** and *warm*, NE to **0°** and *cool*, on a 35% slope |
| coarse woody debris | 12 8 31 45 9 cm on 30 m = **134.7 m³/ha**, on 60 m = **67.3** |
| Darwin Core | a 39.4312 / −120.2381 fix, 30 m of GPS, on the 11.28 m circle = **47 m**; **5406 m** with the datum unknown; **50 m** as a 20×20 m rectangle, because the same 400 m² of ground reaches 14.14 m from its centre and not 11.28 |
| height | 20 m at 42° and −8° = **20.8 m** (68 ft) in degrees, **10.0 m** in percent |
| interactions | 2 links, 4 taxa, 2 types, 1 seen — and the export writes each in the direction the record stores it |

Every figure in that table is printed by a Python oracle that ports the page's
own arithmetic. A number a tool can compute is never a number a task author
remembers.

## 3. Blank still means blank

The stand sheet's method notes make a claim in prose: *"Aspect, slope position,
texture, moisture and every cover field start unrecorded and stay out of the
export until you touch them. Aspect 0° is north, and this sheet will not enter
it on your behalf."* Nothing checked it. The task now does, both ways:

- before anything is entered, the export **excludes** `# site:`, `# cover:`,
  `# disturbance:` and `# notes:`, and the heat-load readout is empty;
- and it **includes** `min DBH 5 cm` and `breast height 1.37 m` from the start,
  because those two are method parameters with defaults and the sheet is right
  to record them;
- after entry, the site line reads exactly
  `# site: aspect 45° · slope 35% · mid slope · mesic · sandy loam · granodiorite`.

This is the check ADR-145 said the collection sheet's four blank reagents were
owed. It is held here first because this page states the rule out loud.

## 4. The figures no task could read

`read-report` reads the elements the kit **names** as outputs — an analysis
(`an*`), an `*Out`, a `*Box`, `*Stats`, `*Verdict`, `*Card`, `*List` and the
rest of the convention. A page that writes a figure into an element named
anything else is invisible to it, and to every task, and to every suite built on
one — **silently**, because a task cannot fail to hold a figure it cannot see.

The stand sheet had four: `sArea` (the plot area and expansion factor),
`sHeatload` (the folded aspect and its band), `kCount` (the key's match count)
and `tHist` (the diameter distribution). Written on every visit, read by
nothing. `verify_ss` was green about all four the whole time, because
`verify_ss` reads the DOM directly — it is the harness that could not.

`tools/audit_readable.py` measures it per page, and **not with a second copy of
the naming rule**, because a rule written twice is a rule that drifts:

    WRITTEN     every element with an id whose rendered text differs from what
                the FILE says -- the baseline is the page with its scripts off,
                so a figure painted at boot counts, not only one a task brings
                into being -- at the DEEPEST id in each chain, since a parent's
                text changes whenever a child's does.
    READABLE    what read-report ITSELF returned: boxes by name, plus the two
                other channels it has -- tables by their host, charts by the
                svg's host (ADR-140).

    UNREADABLE = WRITTEN - READABLE - furniture

**An entry host is not a report.** The Field Entry Kit mounts widgets into a div
and the div's text then changes, so the first reading called every `*Entry`
mount in the kit a figure the harness cannot see — 170 of 429, four fifths of it
noise. The rule is structural rather than by name: an element that **holds a
control** is an entry host, and `entry_reach` is the file that accounts for what
is inside it. That, and the two other channels, took the reading from 170 to 40.

**Furniture is declared, not guessed.** A `<marker>` definition and a hint that
repeats what a control already says are written elements that are not figures.
Two are declared, each with a reason in the ledger.

**The ratchet runs downward.** The floor here is a *ceiling*: a page may not grow
a figure the harness cannot read. It fails by default with no flag, because
`run_all` runs an audit with no arguments.

## 5. The reading

    stand-sheet.html        9 → 51 of 51 fields   (56 → 214 confirmed expectations)
    the kit               237 → 279 of 518 fields  (46% → 54%)
    figures readable      230 of 256 written elements — 26 blind, on 9 pages

The worklist, named: tree-visualizer 8 (`mH`, `mN`, `mOpt`, `mRot` and the four
complexity cards), tree-proofs 6 (the splay potential — `spPhi`, `spN`, `spSA`,
`spSM`, `spAm`, `spAct`), field-notebook 3 (the mark-recapture estimates
`mrC`/`mrM`/`mrR`), ecology-lab 3 (`o-cap`, `o-hot`, `o-set`), field-season 2,
and one each on cp-characters, ethogram, greenhouse and pheno-tracker.

## 6. What is now asserted

`verify_readable` **28**, new, on two fixtures: one with a task, one without.
A figure written at boot counts; one written only by the entry counts; one
behind a tab counts; only the deepest id in a chain owns a change; a control is
not a report even when its own label changes; all three of `read-report`'s
channels are read; an entry host is skipped because the **audit** stamped the
controls, not because somebody else's entry happened to; and the ceiling falls
on request, never rises silently, and takes a reason for every piece of
furniture. `mutate_readable` **23**, 23 killed, 0 survived, 1 recorded
equivalent.

`verify_ss` **84**, unchanged in count and re-pointed at the renamed ids.

## 7. Held

- **Renaming is the fix here, and it is only honest where the element really is
  a figure.** `sAreaOut` says "this carries a reading" because it does. The 26
  that remain are named in the ledger and are the next slices' work, not a
  target invented here.
- **An element that holds a control is skipped**, so a figure with a button
  inside it would be missed. It is a stated limit of the structural rule, and
  the ceiling still catches a page that grows a new blind figure elsewhere.
- **A readable figure is not a held figure.** Whether a task holds it is the
  task's business; `entry_reach` measures the other half.
- **The audit sees only what the page's own entry makes it write.** A figure
  that appears only under a condition no task creates is not measured — which is
  the same coupling `entry_reach` has, and the reason growing a task grows this
  reading too.
