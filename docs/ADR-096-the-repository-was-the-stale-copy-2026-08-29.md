# ADR-096 — The repository was the stale copy

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-031 (the three-way provenance gate), ADR-051 (the kit contradicting itself),
ADR-055 / ADR-056 / ADR-078 (staleness is a property of the published copy), ADR-061 (silent
exclusion with a plausible face), ADR-077 (a rule a sentence about the rule can break), ADR-094
(a worklist with a front)

This slice set out to work the front of ADR-094's claims worklist: **twelve BARE claims**, with a
prediction that most would resolve as a source that exists elsewhere or a convention that needed
labelling, and a named falsifier — *one of the twelve turning out to be wrong rather than merely
unsourced.*

Nine pages had to be republished afterwards, which meant reading the live copy of each one first.
That reading is the slice.

## 1. Eight of the nine published pages said something the repository did not

| page | what the live copy carried that `docs/` did not |
|---|---|
| `breeding-bench` | the 20/100 floor called "the seed-savers' rule of thumb, not a measured threshold"; the sweet-corn figure cited to ***The Seed Garden*** (Colley & Zystro, 2015); the selection intensities cited to **Falconer & Mackay, 1996** |
| `cell-bench` | the chamber factor shown with its derivation inline (1 mm × 1 mm × 0.1 mm = 0.1 µL); "conventional 24 h" where the repo said "plausible"; the corner square "1 mm on a side by definition of the **improved** Neubauer ruling" |
| `deployment-log` | a `.src` sentence saying where the three AudioMoth figures come from; the speed-of-sound approximation written out (331.3 + 0.606 × 20 = 343.4); the duty legend printing its own arithmetic — "60 s of 600 s = 10.0% duty" |
| `cp-characters` | ***Utricularia*** bladders as **0.2 mm to 1.2 cm (Taylor, 1989)** — cited, where the repo had an uncited range |
| `fungal-characters` | "Read at the **conventional** 30 s"; the 35 °C drying floor labelled a practitioners' rule of thumb |
| `micro-bench` | "**The conventional volumes** are 0.1 mL spread, 1.0 mL pour" |
| `cp-bench` | the top-up equivalence carrying its arithmetic, (10 × 50 = 500) |
| `eco-protocol-library` | the 90% skew called "**an arbitrary skew**, chosen to make the collapse unmistakable" |

Only `ecology.html` matched. **Eight of nine.** Every one of those edits is a provenance improvement,
and several are precisely the corrections this slice was about to make from scratch — including the
one that was going to be its falsifier.

`publish_state` did not miss this; it was never asked. Its own docstring (ADR-078) draws the line:

> `via "publish"` — these are the bytes I handed the publisher. **Says nothing about whether the
> publisher kept them.**

Twenty-two of the forty pages were stamped that way. A publish-stamp is blind to an edit made in the
artifact afterwards, and somebody had been making them. The kit built the instrument that answers
this — `publish_state --verify`, which stamps via *read* only when a saved live copy contains the
build verbatim — and then mostly did not run it. **Nothing was wrong with the design. The measurement
had not been taken.**

The correction is not a new tool. It is that eight pages were **back-merged into `docs/`** and every
one of the forty is now stamped: 18 measured from the live page, 22 from a publish, **0 behind, 0
unknown**.

**The rule this adds:** before republishing a page, read the live copy and diff it. A republish
without that read overwrites edits nobody recorded — and this slice would have destroyed eight
pages' worth of sourcing if the publisher had not refused the first attempt for exactly that reason.

## 2. The count ADR-094 recorded was never measured

ADR-094 §2 took two hub cards that restated figures their tool pages source properly, put the source
into the card, and recorded **30 → 28, 14 BARE → 12**.

Only one landed. The compost card names **40 CFR 503 App. B**, which the finder's `STD` pattern
matches. The water card names **California Carnivores**, which nothing in the finder matches — its
`CITED` pattern is author-and-year. A named *organisation* is not a citation to this tool, and that
claim never left the list. Re-running the finder would have said so in fifteen seconds.

Same failure as §1, one level down: **a fix a tool does not accept is not a fix**, and every number
in this document is therefore decomposed rather than asserted.

## 3. Two provenance tests in one file, disagreeing

`audit_claims.py` asks its question twice — strictly, in the claim's own neighbourhood, and loosely
across the enclosing section (the `near` column ADR-094 added). Each carried its own copy of the same
three regexes, and the copies had drifted:

| token | section-level | block-level |
|---|---|---|
| `40 CFR`, `ISO`, `ASTM`, `IUCN`, … | yes | yes |
| **FDA BAM, AOAC, USP, APHA, Standard Methods** | **yes** | **no** |

So the strict test was *weaker* than the loose one on five tokens: a claim naming FDA BAM **in its own
sentence** read BARE, while a claim three paragraphs from one read `near`. That is not a strictness
setting, it is a contradiction (ADR-051). The vocabulary is now written once and substituted into
both probes.

It also explains §6: ADR-094 could offer micro-bench's plating volumes as its worked example of a
number no standard in the card covers, partly because the tool it was reading could not have seen
one there.

## 4. The strongest escape in the file had no floor

`.cite` / `.src` / `.ref` exempted a block **by existing**. `<span class="src"></span>` silenced
every number under it and nothing checked. No page had done it — measured, not assumed — but a
mechanism that works only because nobody reached for it is the silent kind of wrong. A provenance
element must now carry three characters of text or a link, canaried both ways on a seeded page.

## 5. An exemption built, and withdrawn the same day

`deployment-log`'s duty legend reads *"one 10 min cycle — 1 min recording, the rest asleep"*: not the
page asserting anything, but the visible half of ADR-031's **third gate**, where the kit refuses to
invent a number and takes the reader's instead. Flagging it asks the reader to cite themselves.

So a `.echo` exemption was written — declared in markup, naming the controls it restates, with a
suite that **drove each named control and required the text to move**, and a seeded static line the
checker had to reject. Good machinery.

Then §1 happened. The live copy of that page already appends `" (60 s of 600 s = 10.0% duty)"`, so
the finder's existing **derivation** exemption covers it and the reader gains the arithmetic. Measured
after the back-merge: `deployment-log` no longer appears on the list at all, and `.echo` has **zero
members**.

An escape with no members is exactly what ADR-094 §3 diagnosed — *a documented mechanism nobody may
use is the silent kind of wrong* — so it was **withdrawn**, with the reason left in the finder where
the next person to reach for it will read it. The better fix already existed and belonged to the page,
not to the tool.

## 6. The falsifier fired, and it fired in the repository

`cp-characters` gave *Utricularia* bladders as **0.2 to 5 mm**: the genus minimum from one source
spliced to the usual maximum from another. Taylor's monograph gives 0.02–1.2 cm — 0.2 to **12** mm;
the usual span across most species is 1–5 mm (Lloyd 1942; Taylor 1989; Płachno 2012; Westermeier 2017,
as stated in *Frontiers in Plant Science* 2019). No source states the range the page had.

**ADR-094's falsifier fires** — the finder was not only measuring unsourcedness. But the sharper point
is where the error lived: the published card had already been corrected to "0.2 mm to 1.2 cm across
the genus (Taylor, 1989)". The wrong range was in `docs/`, which is what every audit in this kit
reads and what anyone cloning the repo gets.

Two more resolved as corrections to the record *about* the record:

* **micro-bench's plating volumes.** ADR-094 called them a number no standard in the card covers.
  FDA BAM Chapter 23 says *"spread 0.1 ml onto MLA"* in so many words, and 1.0 mL is the pour plate's
  defining volume. The claim was citable all along.
* **breeding-bench's 20/100 floor.** Its own source says the number *"differs depending on experts"*,
  and Seed Savers Exchange's crop chart asks 10–20 for a self-pollinator and 80–200 for outbreeders.
  The page now carries the spread and declares the single floor a **deliberate simplification rather
  than an oversight** — the treatment micro-bench's countable window already had.

## 7. The coupling ADR-094 named as not-done

Three suites read a probe out of a tool by splitting its source on one literal sequence. It broke
twice in one hour (ADR-077). ADR-094 added a uniqueness check, said plainly that the coupling itself
was the defect and that a suite could import the module instead, and left it — right at the time, and
no longer possible to leave: §3's fix builds the probe from parts, and a split cannot read an
assembled probe.

`_kit.tool(name)` imports it. A probe is read by its **name**, so renaming one is a `NameError` rather
than a silently wrong body. The uniqueness check retires with the mechanism it protected and is
replaced by the one that matters: **no suite may split a tool's source**, checked across every
`verify_*.py`.

## 8. What each half was worth

| tree | claims | BARE |
|---|---|---|
| before | 29 | 13 |
| **finder changes only**, pages untouched | **29** | **13** |
| page changes only, finder untouched | 15 | 1 |
| both | **15** | **1** |

**The finder changes clear nothing by themselves.** Unifying the vocabulary and putting a floor under
the provenance escape exempt no claim that exists on any of the forty pages today: they remove a
contradiction and close a hole, not an entry. The drop from thirteen to one is page work — and a good
share of that page work was already done, on the published copies, by someone the repository never
heard from.

The one remaining BARE claim is `ecology-lab`'s heredity reading, adjudicated in ADR-094 §3 and left
alone: bound to the engine by `verify_engine_sessions`, which the finder cannot see.

## 9. What is not done

* **Thirty-one published pages have still not been read against the repo.** Eight of the nine that
  were read had drifted. That is the strongest reason in this document to finish the job, and it is
  the next slice: read each remaining artifact, diff, back-merge, `--verify`.
* **No mutation sweep is owed.** No page *logic* changed. The two surviving finder rules carry seeded
  canaries in both directions instead, which is what a sweep would have been testing for.
* **`near` is still fourteen.** This slice did not touch the second column.

**The next prediction, and its falsifier.** I expect the remaining thirty-one to drift at a lower rate
than eight-in-nine — these nine were selected by being the ones this slice edited, and a page somebody
edits is a page somebody was reading. **Falsifier: the rest drifting at the same rate**, which would
say the artifact editor has been the kit's real front end for some time and `docs/` is a mirror that
nobody has been keeping.
