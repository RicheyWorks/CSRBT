# ADR-171 — Figure provenance: read-report says where each number was read from, and the readable audit credits every channel

**Status:** accepted · **Date:** 2026-09-09 · **The readable-figures audit disagreed with the reader it measures: thirteen figures a task already held were counted as figures no task could read. The reader now names the element each figure came from, the audit credits every channel the reader has, and the kit's worklist goes from 22 blind figures on 7 pages to none.**

## The instrument accusing working code

ADR-146 built `tools/audit_readable.py` to find the figures a page publishes
that `read-report` cannot see, and it was careful not to hold a second copy of
the reader's naming rule: WRITTEN is what the page's text says changed, and
READABLE is what the reader itself returned. But it asked the reader for only
part of what it returns — the `boxes` channel (ids named like boxes) and the
table and chart hosts — and not the `figures` channel, the `.v`/`.l` pairs
the reader keys by their LABEL. A figure the reader reads under its label,
from an element whose id is not named like a box, was therefore counted as
unreadable.

Thirteen of the kit's 22 "unreadable" figures were exactly that, and the
tree-visualizer's task has asserted `output.by.singleWrap.Height` and
`.Nodes` since ADR-128 — the figure was read AND held, and the audit said no
task could see it. The other four on that page, the comparison cards
`cc-AVL/RB/Splay/WB`, sit inside `#cmpGrid`, which IS a box: their numbers were
in `boxes.cmpGrid` all along, and the audit, counting at the deepest id, never
looked up the chain. That is the same shape as ADR-109's `sequenced` bucket:
the instrument accusing working code, and the accusation looking exactly like
a finding.

## What changed

**The reader says where each figure came from.** `read-report` returns a new
`sources` map beside `figures`, keyed the same way: for each labelled figure,
the id of the `.v` element it was read from when it has one (the visualizer's
`#mH`, the notebook's `#mrC`, the proofs' `#spPhi`), else the id of the pair
(a `.tile` with an id), else the box around it. Additive — no existing key
moves, no task assertion changes — and provenance, not a second value.

**The audit credits every channel the reader has.** `readable` is now boxes
∪ table and chart hosts ∪ the sources of the labelled figures ∪ the elements
read THROUGH the box around them — the last only when the box's RETURNED text,
capped at 4000 characters as the reader returns it, carries the element's text
whole. Held against the returned text and not the DOM, because a card past the
cap, or longer than it, is in the DOM and not in the report, and crediting it
would be the audit trusting the DOM over the reader it measures. The through-a-
box reading is the weakest one — a substring of a blob, not a keyed value — so
the ledger names it per element (`through`), and it is not hidden inside the
readable count.

**An empty element holds no figure.** The greenhouse's `srcExtra` is the host
the source-settings controls mount into; once a source with no settings is
picked it is empty, and an empty element cannot be a figure the harness fails
to read. WRITTEN now requires text.

**`*Board` is a box.** The pheno tracker's `momBoard` (the mothers held in
veg, with their scores) and `rankBoard` (the ranked run — rank, plant, score)
are figures, and the ranking board was invisible twice over: not named like a
box, and skipped by the audit as an entry host because each row carries
buttons. Added to the reader's naming beside `*Card` and `*List`; the
mutation anchor on that regex line is widened with it (ADR-140's lesson) and
a mutant of its own holds the new name.

**Three declared furniture, with reasons in the ledger.** field-season's
`dayLabel` ("day 4 of 12") repeats the `days left` tile the figures channel
reads (`total − day + 1`, the page's own `daysLeft()`); its `seasonTag`
("Season #4217") repeats the seed the setup card's control holds and the
results box prints at the end of the season; cp-characters' `genCards` is
eighteen cards of reference prose painted at boot from the key's own table,
changed by nothing entered — reading matter, like a reference page's
headings, while the key's verdict `kRes` is read.

**The comparison cards are held.** The tree-visualizer task enters compare
mode after the four morphs and holds `boxes.cmpGrid` to the four cards whole
— `Red-Black h=7 · height 7 · nodes 20 · rotations 14`, AVL 5/20/15, Splay
20/20/19, Weight-Balanced 6/20/14 — the same figures the four morphs already
hold against verify_tv's Python port of every strategy, read a second way; then
leaves compare mode and reads the single tree once more, unchanged.

**The push script names the session that generated it.** `deliver.py`'s
trailer carried one session line as an invariant; a handoff to a new session
is not a hand edit any more than a model handover is (ADR-155), so `--check`
now accepts every trailer a real slice was signed with — coauthor and session
— and generates with the current one. That turned up a stale mutant anchor in
`mutate_delivery`: "a hand-edited script is not compared" had anchored on a
line ADR-155 rewrote, and the ledger still said *killed* from the run before
— ADR-140's lesson, again. Re-anchored; 30 of 30.

## What moved

    figures readable       248 of 270  →  268 of 268      0 blind, was 22 on 7 pages
    every page's ceiling                →  0
    tree-visualizer task    91 → 98 confirmed, 0 refuted
    verify_report          109 → 114     mutate_report     64 → 68 / 68
    verify_readable         28 →  33     mutate_readable   23 → 30 / 30, one recorded equivalent

No page was edited: the reader, the audit, their suites and runners, one task,
the ledger, and the delivery script's trailer.

## Held

- `sources` is keyed like `figures`, never empty, and never coarser than `by`:
  the `.v`'s own id, else the pair's, else the box — three mutants, one per
  rung.
- A labelled figure whose `.v` carries an id outside the convention is
  readable and its id is named; a composite inside a box is readable through
  the box and the box is named; a card past the cap, or longer than the cap,
  stays on the worklist; an element created and left empty is not written.
- Only the tree-visualizer's four comparison cards are read through a box
  anywhere in the kit. Every other written element is read directly.
- The readable audit's `written` totals move a little from run to run (the
  audit sees only what the page's own entry makes it write — ADR-146's
  coupling); the ceilings are on `unreadable`, and every one is 0.
- Not done here: `rankBoard` is now read as a box, but the audit still skips
  it as an entry host, so a figure with a button inside it is still not
  counted as written — ADR-146's known hole, unchanged. The through-a-box
  reading is a string claim; giving the comparison cards `.v`/`.l` structure
  would make them keyed, and that is a page edit with a republish behind it.
