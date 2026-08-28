# ADR-089 — the digit a reader was shown

*2026-08-28. Status: accepted. Settles the open question in
[ADR-088](ADR-088-the-sweep-that-was-owed-2026-08-28.md); the third occurrence of the wall in
[ADR-084](ADR-084-the-guard-in-front-of-its-own-evidence-2026-08-28.md), this time in the tool built to
find the others.*

## 1. Asking the page instead of the source

ADR-088 found 28 figures sitting exactly on a rounding boundary and refused to say which were
displayed, because binding a fixture value to a call site by key name reports `p`, `q` and `observed`
against every page using those names — a fact about names, not data flow (ADR-077).

`tools/tie_render.py` answers it the way the kit answers questions about pages: **by changing the input
and looking at the output.**

```
render the page
render it again with the figure moved one unit of the displayed place
if the rendered text differs, the figure reaches the page
```

No name matching, no JS parsing. Then the sharper question — is it rounded *at* the tie? — gets a
second, much smaller nudge across the boundary itself. Only a display whose precision sits exactly on
that boundary can notice a move that small.

## 2. Two figures a reader was seeing

On `ecology-lab.html`, 4 of the 8 ties in the shipped session reach the rendered text, and **two of
those were rounded at the tie**:

| figure | value | shown | the other digit |
|---|---|---|---|
| carrying capacity `K` | 138.5 | **139** | 138 |
| `chao1` | 103.5 | **104** | 103 |

ADR-088's falsifier — *a rendering pass finding a displayed tie other than the one already fixed* —
fires, twice. Both are now displayed at one decimal, which `toLocaleString` drops when it is not
needed, so nothing else on the page moves.

## 3. The one no sweep of the data could have found

Fixing `chao1` at its three tile sites did not clear it. The remaining site was in prose:

```js
`Chao1 estimates ≈ ${fmt(c,0)} — about ${fmt(c - s,0)} rare keys unseen`
```

`c - s` is 103.5 − 100 = **3.5** — a tie that exists in no fixture, because it is made here by
subtraction. ADR-088's sweep reads recorded literals and could never have seen it; the render pass
found it without being told to look, because it was never looking at the data in the first place.

**Ties are not only recorded, they are computed.** Any arithmetic on displayed figures can land on a
boundary, and a difference of two perfectly ordinary numbers is the easiest way to get there.

## 4. The wall, a third time — in the tool that finds walls

The first version of the boundary nudge stepped **up**, and reported a clean board: 0 of 4 rounded at
the tie. It was not clean. Under the half-away-from-zero rounding the pages use, `.5` and `.5 + a hair`
produce the same digit, so **an upward nudge can never flip a tie** and that check could not fail on any
input.

ADR-084 called this a guard with no satisfiable path; ADR-085 rebuilt one by accident; this is the
third, and it was written into the tool whose whole purpose is finding figures nobody checked. It was
caught only because the answer looked too good — the same instinct that has been doing most of the work
in this arc.

Both directions are tried now, and `verify_tie_render` checks that the downward one is the one doing
the work:

```
PASS  CANARY: with a zero-decimal rendering seeded back in, it is caught
PASS  an upward-only nudge cannot catch it -- a tie and a tie plus a hair round the same way
PASS  ...so the downward nudge is doing the work, not decoration
```

The seeded fault is the exact edit this record undid, rather than a stand-in that might not behave like
it. **7 checks.**

## 5. What is covered, and what is named as not

`tie_render` renders `ecology-lab.html` only — the one page that inlines its session. The other three
fixtures holding ties are read by `demo/visualizer.html` and the protocol reference when a reader drops
the file in, so covering them means driving a file drop. They are listed in the tool's output as not
rendered, not passed over.

The other blind spot is stated in the same place: **a figure drawn only into a `<canvas>` changes no
text and reads as "not displayed."** Two of the eight (`structural`, at both precisions) report exactly
that, and one of them is a chart tooltip — so at least one "no change on screen" is a limit of the
method rather than a fact about the page. The verdict is worded "reaches the rendered text", not "is
invisible", for that reason.

**The next prediction, and its falsifier.** The flagship page is now clean, and it is the only page
measured. **Falsifier: driving a session file into `demo/visualizer.html` and finding a tie rounded
there.** I am not putting a number on how likely that is — the last two guesses in this arc lost, and
the sweep is cheap enough that guessing is the expensive option.
