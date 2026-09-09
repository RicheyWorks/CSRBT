# 2026-09-09 — ADR-171: figure provenance — the readable audit credits what the reader reads

**The readable-figures audit counted thirteen figures a task already held as
figures no task could read, because it asked the reader for its boxes and not
its labelled figures. The reader now says which element each figure came from,
the audit credits every channel, and the worklist goes 22 → 0.**

## Changed — `tools/harness_plugin_page.py`

- `read-report` returns `sources` beside `figures`, keyed the same way: the id
  of the `.v` each figure was read from, else the pair's id, else the box.
  Additive; nothing existing moves.
- `*Board` joins the box naming (the pheno tracker's `momBoard`, `rankBoard`).

## Changed — `tools/audit_readable.py`

- READABLE = boxes ∪ table/chart hosts ∪ figure sources ∪ elements read
  through the box around them (only when the box's returned, capped text
  carries the element whole; a truncated element is never credited).
- WRITTEN requires text: an element created and left empty holds no figure.
- The ledger records `through` per page — the elements a task can only hold
  by string.

## Changed — `tools/readable_ledger.json`

- Every ceiling is 0. Furniture declared, with reasons: field-season
  `dayLabel` and `seasonTag`, cp-characters `genCards`.
- tree-visualizer: `cc-AVL/RB/Splay/WB` recorded as read through `cmpGrid`.

## Changed — `tools/tasks/page-tree-visualizer-science.json`

30 → 34 steps, 91 → 98 confirmed. After the four morphs: compare mode on,
`boxes.cmpGrid` held to the four cards whole (the same heights, node counts
and rotations the morphs already hold against verify_tv's port), compare mode
off, the single tree read again unchanged.

## Changed — `tools/deliver.py`, `tools/mutate_delivery.py`

- The push script's session line names the session that generated it;
  `--check` accepts every coauthor × session a real slice was signed with.
- `mutate_delivery`'s "hand-edited script" mutant had a stale anchor since
  ADR-155 (the ledger still said killed); re-anchored, 30/30.

## Suites and runners

    verify_report     109 → 114     mutate_report    64 → 68 / 68
    verify_readable    28 →  33     mutate_readable  23 → 30 / 30 (+1 recorded equivalent)

## Numbers

    figures readable   248 of 270 → 268 of 268
    blind figures       22 on 7 pages → 0

## Held

- Provenance is never coarser than `by`; three mutants, one per rung.
- A card past the box's 4000-character cap, or longer than it, stays on the
  worklist: the audit trusts the reader's returned text, not the DOM.
- Only the four comparison cards are read through a box anywhere in the kit.
- `rankBoard` is read as a box now but still skipped by the audit as an entry
  host — ADR-146's known hole, unchanged. No page was edited.
