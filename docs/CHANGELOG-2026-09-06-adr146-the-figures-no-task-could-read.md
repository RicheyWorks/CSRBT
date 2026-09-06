# Changelog — 2026-09-06 — ADR-146: the figures no task could read

ADR-145's method, applied to the second page — and what entering it whole found.

## The task — `tools/tasks/page-stand-sheet-science.json`

25 steps → **149**. The key, the packs, the tally, the plot geometry, the
physiography, the cover, the coarse woody debris, the disturbance, the notes,
the Darwin Core coordinates, the interactions and the field sheet.

```
stand-sheet.html    9 → 51 of 51 fields   (56 → 214 confirmed expectations)
the kit           237 → 279 of 518 fields  (46% → 54%)
```

**The first page in the kit entered whole.**

Every figure it holds is recomputed by a Python oracle that ports the page's own
arithmetic — Reineke's SDI 132, Curtis & McIntosh's importance value 78.6 against
21.4, van Wagner's 134.7 m³/ha and half that on twice the transect, McCune &
Keon's folded aspect at 180° *hot* / 90° *warm* / 0° *cool*, and the point-radius
coordinate uncertainty at 47 m, 5406 m with the datum unknown, **50 m as a
20×20 m rectangle** — because the same 400 m² of ground reaches 14.14 m from its
centre and not 11.28. A 5.64 m plot is **EF 100.1**, not 100.0: its area is
99.92 m².

### Blank still means blank

The page's method notes claim it in prose; nothing checked it. Now the task
does, both ways: before entry the export **excludes** `# site:`, `# cover:`,
`# disturbance:` and `# notes:` and the heat-load readout is empty — and it
**includes** `min DBH 5 cm` and `breast height 1.37 m`, because those are method
parameters with defaults and the sheet is right to record them.

## New — `tools/audit_readable.py`

`read-report` reads the elements the kit **names** as outputs. A page that
writes a figure under any other name is invisible to it — and to every task and
every suite built on one — **silently**, because a task cannot fail to hold a
figure it cannot see.

```
python3 tools/audit_readable.py
python3 tools/audit_readable.py --page stand-sheet.html
python3 tools/audit_readable.py --raise-floors
python3 tools/audit_readable.py --furniture food-web.html:arrow --reason "..."
```

Measured, not asserted, and **not by a second copy of the naming rule**:

- **WRITTEN** — every element whose rendered text differs from what the *file*
  says (the baseline is the page with its scripts off, so a figure painted at
  boot counts), at the **deepest** id in each chain.
- **READABLE** — what `read-report` itself returned, through **all three** of its
  channels: boxes by name, tables by their host, charts by the svg's host.

Two rules took the first reading from 170 to 40:

- **an entry host is not a report** — a div the Field Entry Kit mounts widgets
  into changes its text and is not a figure; the test is structural (*it holds a
  control*), not the `*Entry` name;
- **a table and an svg are read through the other two channels**, so counting
  them blind would be this audit disagreeing with the reader it measures.

**Furniture is declared with a reason** (two entries), and the ratchet runs
**downward**: a page may not grow a figure the harness cannot read. It fails by
default with no flag; `audit_readable` is registered in `run_all`.

## Fixed — `docs/stand-sheet.html`

Four figures the harness could not see, renamed to what they are:

| was | now | what it carries |
|---|---|---|
| `sArea` | `sAreaOut` | 400 m² = 0.0400 ha, expansion factor 25.0 |
| `sHeatload` | `sHeatOut` | folded aspect and its band |
| `kCount` | `kCountOut` | the key's match count |
| `tHist` | `tHistOut` | the diameter distribution |
| `kDetail` | `kDetailCard` | the species card |

All five are now held by the task. `verify_ss` **84**, unchanged in count.

## The reading

```
figures readable   230 of 256 written elements — 26 blind, on 9 pages
```

The worklist, named: tree-visualizer 8, tree-proofs 6 (the splay potential),
field-notebook 3 (the mark-recapture estimates), ecology-lab 3, field-season 2,
and one each on cp-characters, ethogram, greenhouse and pheno-tracker.

## The board — `tools/harness_board.py`

New tile: **figures readable**, with the count of pages still publishing one the
harness cannot see. `mutate_readable` joins the runner table.

## Verification

- `verify_readable` **28**, new, on two fixtures — one with a task and one
  without, because an audit that leans on somebody else's entry to stamp the
  controls reports every mount on every task-less page as a figure.
- `mutate_readable` **23**, 23 killed, 0 survived, 1 recorded equivalent (the
  baseline snapshot's entry-host flag: the baseline context runs no scripts, so
  nothing in it is stamped and the flag has nothing to act on).

## Docs

`docs/ADR-146-the-figures-no-task-could-read-2026-09-06.md`;
`docs/AI_HARNESS.md`.
