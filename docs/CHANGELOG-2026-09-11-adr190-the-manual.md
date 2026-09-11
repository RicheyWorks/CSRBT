# 2026-09-11 — ADR-190: the manual

**The door stops publishing a figure and withholding what a reader needs to act
on it: complete pools that say how complete they are, an address on
`read-control`, a box split where the page splits it, and the page's own prose
about its own arithmetic. The third of the seven slices of
`docs/PLAN-operator-api-2026-09-11.md`, and the last of ADR-187's door
findings.**

## Changed — the door

- `tools/harness_plugin_page.py`:
  - `PICK_CAP, POOL_CAP = 80, 600` (was 6 per picker, 20 per select). Every
    picker and select publishes what it offers, and `observe` carries
    `pickers`: selector, kind, host, `shown`, `of` — so a cap that bites says
    so instead of looking complete.
  - `read-control` answers with the control's `address` (ADR-188).
  - `read-report` carries `lines`: every box split into the page's own leaf
    blocks, beside the unchanged `boxes`; a line cut at 300 characters is
    trimmed again.
  - `read-report` carries `rules`: the innermost `.hint` and `.fine` on the
    page, each with its identified host, capped at 40 × 400 characters —
    quoted, not interpreted.

## Changed — suites

- `verify_report` 149 → 160: section H. A picker's pool is every option it
  offers and `shown == of` on the collection sheet's 66; an option past where
  the old pool stopped is one `pick` actually takes; a built list longer than
  the cap publishes the cap and says how many there were; every control read
  one at a time answers with the address the snapshot publishes, and
  `read-control` takes that address; every box is published split as well as
  whole and the two name the same boxes; every line of every box is that box's
  own text with nothing invented; the page's prose is handed over with its
  host, one piece per innermost `.hint`/`.fine`, and on the pheno tracker it
  carries the scoring rule a blind operator had to recover by experiment.
- `mutate_report` 95 → 104 / 104: the sample restored, the count silenced, the
  address dropped, the split emptied, nested blocks taken, the cut's trailing
  space kept, the prose withheld, handed over twice, and handed over without
  its host.

No page and no task was edited; `boxes`, `figures` and `by` are byte for byte
what they were.
