# ADR-174 — The food web's outputs, read — and a slash in a label is a label

**Status:** accepted · **Date:** 2026-09-09 · **The food web builder hands over its web export, an edge-list CSV and a print, and nothing read them. The task reads all three byte for byte against `verify_fw`'s port of the meadow — and, to press the print button at all, the task grammar had to learn that a label carrying a slash is a label, not a host and a label. Unread outputs 15 → 12.**

## The button a task could not name

`audit_outputs` listed food-web next: `Copy web export`, `Copy CSV`,
`Print / save PDF`, none read. The first two took a probe and an oracle. The
third could not be named. `@control:<name>` reads a slash as *host/label*
(ADR-128: `rCov/4` is the dial labelled 4 inside `#rCov`), and it read
`Print / save PDF` as host `Print ` and label ` save PDF` — a control that
does not exist. The notebook's print button (ADR-173) was reachable only
because it sits inside `#p-more`, so `p-more/Print / save PDF` split at the
first slash and happened to come out right. The builder's button has no host:
there was no way to write it down.

## What changed

**A name that matches whole is taken whole.** `find_control` now tries the
name as an id, a label or a host first, and reads it as `host/label` only
when nothing answers to it whole. `rCov/4` still scopes (nothing is named
`rCov/4`); `Print / save PDF` now names the print button on any page that
calls it that. Held in `verify_tasks` (a hostless and a hosted print button
side by side, 292 → 293) and by two new mutants in `mutate_tasks` — a slash
that always splits, and a slash that never does — 65 → 67 of 67.

**The task presses every export on the meadow and holds what left**, after
ADR-140's chart read and before the closing intact check:

- `Copy web export` → one clipboard payload, held byte for byte: the header
  (`10 species, 12 links`), `note: connectance 0.120 — longest chain 5
  levels`, and one `note: <eater> eats <food>` per link, twelve, in the order
  the meadow draws them.
- `Copy CSV` → one clipboard payload, held byte for byte: `food,eater` then
  the twelve edges in the same order — the file a reader feeds igraph or
  networkx.
- `Print / save PDF` → exactly one payload, a print.
- Then the tiles and the export box are read once more, unchanged.

**The literals are pinned by the page's suite.** `verify_fw` already carried
a Python port of the meadow (`MEADOW_SP`, `MEADOW_LN`, `trophic`,
`connectance`); it now builds the export and the edge list from that port and
holds the task's literals to them — swap one edge's direction in the task and
the suite fails. 61 → 64.

## What moved

    food-web outputs             0 → 3 of 3 held      ceiling 3 → 0
    the kit's unread outputs    15 → 12 of 66         (8 pages still hand something over unread)
    page-food-web-science        39 → 54 confirmed, 0 refuted
    verify_fw                    61 → 64      verify_tasks 292 → 293      mutate_tasks 65 → 67 / 67

No page was edited: the task grammar, its suite and runner, one task, one
page suite, and the ledger.

## Held

- Whole-name-first cannot steal a scoped name: a control would have to be
  literally id'd or labelled `host/label` for the whole match to win, and no
  page of the kit names anything with a slash except the print buttons.
- The export's link order is the page's drawing order, which is the preset's
  order; the port lists the meadow in that order and the task holds it — a
  reordering that kept the set would be caught.
- Not done here: ordination (3), deployment-log (2), soil-recipes (2),
  farm-scout, pheno-tracker, field-season, soil-bench, eco-protocol-library.
