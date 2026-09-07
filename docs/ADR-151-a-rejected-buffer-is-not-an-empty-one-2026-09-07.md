# ADR-151 — A rejected keystroke buffer is not an empty one

**Status:** accepted · **Date:** 2026-09-07 · **ADR-150 found one of these by hand and wrote the rest down as a worklist. This is the looking: 185 number boxes across 22 pages, asked the question mechanically. 63 of them, on 16 pages, could not tell a buffer the browser rejected from a box nobody touched. All 63 are fixed; the kit is at zero and the ratchet holds it there.**

## The silence

`<input type=number>` has two things in it. There is the **value**, which is what
the page reads, and there is the **raw keystroke buffer**, which the page cannot
see at all. When the browser cannot parse the buffer it hands the page the
**empty string** — the same string a box nobody has touched hands it.

So a page that treats blank as meaningful cannot tell the two apart:

| the reader did | `.value` | `validity.badInput` | what the page concluded |
|---|---|---|---|
| left the box alone | `""` | `false` | not recorded |
| typed `3e` | `""` | **`true`** | not recorded |

The box shows their characters. The page reads a blank. Nobody is told.

`badInput` is the only thing that separates them, because it is about the buffer
rather than the value — which is exactly why nothing in this kit could ask the
question until ADR-150 built `type-text`. **An assignment cannot fill a keystroke
buffer**, so every task in the kit had been driving the one half of the input
space where the distinction does not exist.

ADR-150 fixed three boxes on one page and held the rest as a worklist:

> the other number inputs across the kit have NOT been retyped, so anywhere a
> page treats a blank field as meaningful the same silence is possible and
> nothing here has looked — that is a worklist, stated rather than done.

## The instrument

`tools/audit_badinput.py`. Per number box, the page is put in three states and
read each time, and the third is typed rather than assigned:

    GOOD    a value inside the box's own min/max/step, ASSIGNED
    BLANK   the empty string, ASSIGNED
    BAD     "3e" -- a number the reader has started and not finished -- TYPED,
            with validity.badInput confirmed TRUE afterwards

and the page's rendered report is compared:

    GOOD != BLANK   the page READS THIS BOX LIVE
    BLANK != BAD    the page CAN TELL THEM APART
    BLANK == BAD    CANNOT TELL -- the finding

**The first comparison is the control, and it is what makes the second one a
finding.** Without it, every box whose figure only appears when a button is
pressed would join the worklist, and the worklist would be four hundred lines of
pages doing nothing wrong. Those boxes are reported as INERT — a fact about how
they were measured, stated rather than hidden — and 107 of the kit's 185 are.

**What counts as telling them apart is what the reader would see**, not what the
harness finds convenient to read: a sentence, a mark (`aria-invalid`, a class),
or a sentence in an element carrying no id at all. Elements are keyed by id
where they have one and by where they sit in the document where they do not, one
key per element — so a page that answers in an unnamed element is not called
silent by the kit's own naming convention, and a clock takes only its own key
out of the comparison instead of every card around it. Ids that move on their
own are found by reading the page twice at rest and dropped, or every box on
that page would look like it was being told apart.

**The page gets every chance to say something.** A verdict only moves up a
ladder — unreachable, inert, cannot-tell, tells — and a box is re-asked in every
state the page can be put in until it tells. The finding is *in no state this
audit could reach did the page say a different thing*, which is a claim worth
making; *it said nothing in the state I happened to look at* is not.

## What it found

    63 live number boxes on 16 pages, of 185 measured on 22

| page | blind | what was silent |
|---|---|---|
| cell-bench.html | 15 | the whole spectrophotometry and cell-count bench |
| experiment-guide.html | 12 | four factor boxes, the grader's seed and passes, six measurement cells |
| micro-bench.html | 8 | OD₆₀₀, colonies, dilution, titre, the two breakpoints |
| greenhouse.html | 6 | dry yield, PPFD, illuminance, cycle length, fixture power, electricity rate |
| deployment-log.html | 5 | cloud oktas, focal length, image width and height, sensor width |
| ecology-lab.html | 4 | the Hardy–Weinberg and mark–recapture workbenches |
| farm-scout, field-season, pheno-tracker, stand-sheet | 2 each | seeds/germinated, the season counts, the two phenology counts, gps accuracy and elevation |
| collection-sheet, releve, selection-log, survey-design, tree-visualizer | 1 each | gps accuracy ×2, a selection value, effort value, select k-th |

The sharpest one is the first row. **ADR-150 took `experiment-guide.html` whole —
52 of 52 fields, 220 confirmed expectations — and left twelve boxes on that same
page reading a rejected buffer as blank.** Taking a page whole means every field
was *entered*. It never meant every field was *asked this question*, and until
there was an instrument nobody could have known the difference.

## The fixes, and where they belong

**The Field Entry Kit, once, for thirty-nine of them across ten pages.** `tools/fek.py` v1.3.0 → v1.4.0.
Both numeric components — the stepper and the instrument field — read `.value`
and treated `""` as "not recorded". They now check `validity.badInput` first,
mark the row, and print the box's own name with what happened to it. The blur
handler no longer repaints the old value over the reader's characters: a blur
used to erase the evidence and take the message down with it, the page quietly
deciding it knew better. Re-emitted into all 19 consumers, which is what that
file is for.

**And once more for the boxes FEK did not build — seven more, on three pages.**
Every page that mounts those components also carries plain number boxes of its own — an elevation, an effort
value, five camera settings — with the same silence for the same reason. One
delegated listener in capture phase rather than a wrapper per box, because the
boxes a page builds *later* (a row added, a pane rendered, a measurement grid
opened) have to be covered too: a guard that only knew about the boxes present
at load would go quiet exactly when the sheet gets long.

**experiment-guide.html**, twelve. The four factors emitted *nothing* when
rejected, and emitting nothing is how that page says "the neutral value" — so a
typed factor the browser could not parse silently became 1, or 0 for distance.
The grader's seed and passes fell back to 42 and 3. A measurement cell said
"waiting for every cell", which is what it says about a cell nobody has filled
in; it now names which cell and why, and the computed line carries an id like
every other figure on the page.

**ecology-lab.html**, four. The exporter on that page already knew the
difference — `boxNum` has checked `badInput` since ADR-148 — and the two live
workbenches next to it did not, taking their counts with `+el.value` and
answering a rejected buffer with "enter non-negative counts". Named boxes rather
than a count, because "one of these three" is not an answer when the reader is
looking at three boxes.

**tree-visualizer.html**, two — the audit found one and the fix found its twin:
`select k-th` and `rank of` share a line and shared the bug.

    the kit    63 -> 0 blind, 12 -> 75 telling, across 185 number boxes

## The ratchet

The ceiling is per page and it is a **ceiling**: the number of blind boxes may
not go up, and it comes down as pages are fixed. All 22 pages that carry number
boxes are recorded at **0**, so the next box added to this kit that reads a
rejected buffer as blank fails the day it is added rather than being found a
month later by someone wondering why a sheet went quiet. It fails with no flag,
because `run_all` runs an audit with no arguments. A box that genuinely should
not care is declared in the ledger **with a reason**; nothing is declared today.

`verify_badinput` **32**, `mutate_badinput` **24**.

## What this is not, and what is still owed

It is **not** a claim that a page which tells them apart says the *right* thing —
only that it says a different thing. Grading the wording is a separate question
and no instrument here asks it.

It is **not** about `type=text` boxes holding numbers: those have no `badInput`,
the page is handed the characters, and there is nothing to be blind to. Whether
a page *should* have used `type=number` is a design question this does not
touch.

**Three boxes on `releve.html` were never asked.** `type-text` refused to focus
them in every state the audit could reach, and a box the instrument could not
put a question to is reported as unreachable rather than as passing. That is
three of 185, and it is stated rather than hidden.

**107 boxes are INERT**, read by nothing until a button is pressed. The audit
does not press the page's buttons, so it cannot say whether the report they feed
would tell a rejected buffer from an empty one. That is the honest boundary of
this measurement and the obvious next slice.

**The before number was measured with the instrument as it stands, not as it
stood.** The first reading said 33, taken while the report channel was still
keyed by id alone — it could not see the pages that answer in unnamed elements,
and it was undercounting the very boxes the Field Entry Kit mounts. Rather than
publish a fall from one instrument's number to another's, the kit's own pages
were checked out at the ADR-150 commit and measured again with the final
instrument: **63**. A ratchet whose two ends were measured differently is not a
ratchet.

And the audit costs about eight minutes on the kit — three page states walked
per box, a keystroke at a time — which is the price of asking a question that no
assignment can ask.
