# ADR-178 — The protocol library's predictions hold: two ready-made experiments rewritten to the bands their data sits in

**Status:** accepted · **Date:** 2026-09-10 · **ADR-177 ran the library's five protocols through the engine and found four predictions on two pages refuted by the kit's own instruments, with comments asserting them. The two protocols are rewritten so every prediction the page presents as the experiment's is one the data supports — stated in the report's own bands — the page is republished and swept, the reference task holds the rewritten protocol byte for byte, and `verify_epl` no longer carries recorded exceptions: a protocol with a refuted prediction the page did not call wrong fails the suite.**

## What was wrong, and what the examples should teach

`eco-protocol-library.html` says its five experiments are "ready to copy,
edit, and run — each with its hypotheses pre-registered, each graded by the
engine". The meadow protocol carries one hypothesis marked *deliberately
wrong* so a reader sees what ❌ REFUTED looks like. `two-ponds.eco` and
`activity-budget.eco` carried four more refutations that nothing announced:

    evenness(pondA) is uneven                # duckweed dominates      J′ 0.763 → moderate
    brayCurtis(pondA, pondB) > 0.4                                      observed 0.311
    evenness(morning) is uneven                                         J′ 0.894 → very-even
    brayCurtis(morning, afternoon) > 0.3     # the budget shifted      observed 0.237

Each is an author's intuition — "duckweed dominates", "the budget shifted" —
written down without reading the instrument. Duckweed is 44 of 80 in pond A,
but four other species hold their share and Pielou's J′ lands in the
*moderate* band (0.55–0.85), not *uneven*. The two ponds share duckweed and
rush at similar counts, so Bray–Curtis is 0.31: *moderate* turnover, not the
0.4 the line demanded. The morning budget has five acts and none above half
the scans, which is *very even* by the report's own threshold. And a budget
in which foraging halves and resting nearly doubles still moves Bray–Curtis
only to 0.24, because most scans are the same acts in both contexts.

A wrong prediction is a lesson — that is what the meadow's deliberate one is
for — but an *unannounced* wrong prediction in a library that calls itself
ready to run teaches the reader that the bands are unreliable, when it is the
prediction that never consulted them. The fix chosen is the one the page's
own prose asks for ("commit your prediction before you look"): predictions
that read the instruments' scales, with the reason in the comment.

## What changed

**Two protocols rewritten, four lines.** `two-ponds.eco` now predicts
`evenness(pondA) is moderate` (*duckweed leads, 44 of 80, but four others hold
their share*) and `turnover(pondA, pondB) is moderate` (*shared duckweed and
rush keep the mats closer than they look*) — the second in the report's
qualitative turnover band, so the protocol now shows both band metrics the
grammar offers for entered data. `activity-budget.eco` predicts
`evenness(morning) is very-even` (*five acts, none above half the scans*) and
`brayCurtis(morning, afternoon) > 0.2` (*the budget shifted: forage halved,
rest nearly doubled*). The data, notes and the Jaccard line are untouched.
Every protocol in the library now grades 100% confirmed except the meadow's
one deliberate refutation. Checked both ways the page offers: the engine
(`ExperimentLab`, three of three and two of two confirmed) and the
Interactive Lab's importer (nine and nine lines read, zero problems).

**Republished.** `publish.py` → artifact `d608dd5a…`, read back with the
four new lines in it, stamped, swept: 42 of 42 artifacts measured from the
live page.

**The task holds the rewritten protocol.** `page-eco-protocol-library-
reference` presses the second `Copy` and holds `two-ponds.eco` whole — twelve
lines, one clipboard payload and nothing else — then reads the toast; 12 → 17
confirmed. The first protocol was held by ADR-177; the second is the one this
slice changed, so the task carries the change.

**`verify_epl` drops its exceptions.** `KNOWN_REFUTED` is empty; the check
that recorded the finding now reads *no protocol carries a refuted prediction
the page did not call wrong*, and a new check holds the four rewritten lines
by name. 40 → 42.

## What moved

    eco-protocol-library predictions   4 refuted, unannounced  →  0
    page-eco-protocol-library-reference   12 → 17
    verify_epl                            40 → 42
    artifacts measured from the live page 42 of 42

One page edited and republished; one task; one suite; the ledger.

## Held

- The meadow's deliberately wrong line stays, and stays the only refutation
  in the library — `verify_epl` holds exactly one *deliberately wrong*
  comment on that protocol and every other prediction confirmed.
- `brayCurtis(morning, afternoon) > 0.2` is confirmed at 0.237: a margin, not
  a coincidence, and the suite pins it, so a change to the counts that moves
  the budget under the line is caught.
- `turnover(p, q) is moderate` over entered datasets is graded by the engine
  and read by the lab's importer — both checked here before the page said it.
- Not done here: the `.eco` Reference page's prose lists the qualitative
  bands as "`even` / `uneven`" while the engine's words are `very-even` /
  `moderate` / `uneven` / `dominated` (and `turnover` has `low` / `moderate`
  / `major`) — a page edit with a republish, noted for the next slice.
  `rankBoard` (ADR-146) and the unasserted charts stand.
