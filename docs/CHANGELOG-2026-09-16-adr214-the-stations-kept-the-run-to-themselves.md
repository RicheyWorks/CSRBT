# 2026-09-16 — ADR-214: nine stations charted a morning's run and let you carry away none of it

**ADR-213 left 19 figures on the ecology lab that reach no file: the nine
stations. A reader could see a run's meadow at J′ 0.52 with 11 effective species
and carry it away only by retyping it off the screen.**

## New

- **`ecology-lab.html` — *Copy the run record*.** A card at the foot of the
  stations carrying every figure they report: the meadow's phases, the demography
  and growth fit, the archipelago's occupancy, the fossil record's inheritance,
  the island's equilibrium.
- **Built from the session, not from the tiles.** `runRecord(S)` takes the same
  field each tile takes and never touches the DOM — a record scraped off the page
  would agree with it by construction and could never catch it being wrong.
- The lab's own task presses the button and holds the bytes (ADR-153).

## Checked

- `verify_eco` reads the figures off the **tiles** and requires each in the
  record; plus that `runRecord` reads `S` rather than the DOM, and that a page
  with no session carries no record card.

## Declared

Six Terrarium readings stay on the screen with their reason in the ledger: the
two live demonstrations redraw on every drag, so the figure is a picture of a
parameter you are moving rather than a record of anything that happened.

**19 → 0. Kit-wide: 132 → 0 of 317.**
