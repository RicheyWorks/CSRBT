# ADR-200 — The claim moves to the act: a task says what the page said, and the kit's second message convention

**Status:** accepted · **Date:** 2026-09-13 · **ADR-199 gave every act `said` — the messages the page announced while it ran — and then said in its own closing section that it had not made the six steps polling `boxes.toast` correct, only unnecessary. This is that slice. It turned out the task grammar could not state the claim at all, and that the kit has two message conventions rather than one.**

## 1. The claim the grammar could not make

`said` is a **list of strings**. The claim a task wants about it is almost
never exact equality: a refusal reads

    model logistic needs 4 parameters

and the next one reads

    No rule, no verdict — write the rule first (Step 3)

where the task is about the first half. `contains` on a list is *exact
membership of one element* — deliberately, since a table row is written as a
list of cells and widening it would quietly loosen every list claim in the kit.
So there was no way to write "one of the messages this act raised holds this
text", and six steps in three tasks were written instead as a whole
`read-report` of the toast **box**, taken inside the message's 1.7-second life,
against a box holding whatever the *last* message happened to be.

Two ops, not one:

    "output.said": {"op": "any-contains",  "value": "needs a DBH"}
    "output.said": {"op": "none-contains", "value": "needs 4 parameters"}

The mirror is not symmetry for its own sake. **Absence is a claim**, and a task
that cannot state it states a guess instead — ADR-132's lesson, one container
deeper. The new claim in this slice that could not have been written before is
on the experiment guide's *second* model: having refused `logistic` with two
parameters, the page must not repeat that refusal when four arrive.

Three edges, each with its own check and its own mutant:

- **A path that is not a list is false in both directions.** A string is not a
  list of messages, and answering either way about one would let a task claim
  about `boxes.toast` through the very grammar built to get it off
  `boxes.toast`.
- **A missing path does not prove silence** — the rule `excludes` already
  carries, so a typo in a path cannot read as evidence.
- **`contains` is unchanged.** The new op is a second claim, not a loosening of
  the old one.

## 2. Six steps, and four that were only ever the race

| task | was | now |
|---|---|---|
| protocol library | `copy` → `read-report boxes.toast` | `copy` claims `said` **and** `produced == 1` |
| protocol library | `g178-copy2` → `read-report` | same |
| survey design | `rm` → `read-report boxes.toast` + `treeStat.events` | `rm` claims `said`, `produced == 0`; the read-report keeps its figure |
| experiment guide | `early` → `read-report boxes.toast` | `early` claims `said`, `produced == 0` |
| experiment guide | `madd` → `read-report boxes.toast` | `madd` claims `said`; `madd2` claims `none-contains` |
| experiment guide | `photo` → `read-report boxes.toast` + two `eco-out` claims | `photo` claims `said`; the read-report keeps both |

Four of those read-reports existed *only* to catch the toast and are gone. Two
had a figure to assert as well and stayed, minus the race. No task reads
`boxes.toast` any more, and a check says so by scanning every task file rather
than by trusting this table.

Every claim that moved was confirmed against the real runner before it was
written down: the protocol library's copy says `Copied — save as a .eco file`
exactly once and produces exactly one payload, which the old two-way `in`
against a clipboard-fallback string had been hedging about.

## 3. The kit had two message conventions

ADR-199 read the live-region standard and converted every element carrying this
kit's `.toast` convention. A probe that presses every control on every page and
watches for text appearing outside a live region found the rest: **two pages
answer in a persistent status line** — a dedicated `msg(text, bad)` that writes
a sentence into a paragraph and colours it red when the news is bad.

    greenhouse   #runMsg   "Load a source first — there is nothing to save."
    greenhouse   #srcMsg   "Log cleared."
    tree-visualizer #msg   "inserted 10 into all 4"

Same job, different furniture, and the same silence. The greenhouse's refusal
is the *entire* outcome of that press — there is nothing else on screen to
tell you the run was not saved — and it reached neither a screen reader nor the
door. All three now declare `role="status" aria-live="polite"`, and
`tree-visualizer.html` is a page this kit's toast convention had never touched,
which is the argument for reading the standard rather than the class name,
made twice.

**Pinned, not pattern-matched.** Whether an element is a message or a caption
is a judgement. The greenhouse's `#logNote` reads *"337 readings loaded; the
last 12 are shown"* — a caption on what a render just drew, and announcing it
on every render is noise rather than access. A regex would have to pretend to
make that call. The list states it instead. The audit that proposes additions
to it is filed, not built.

## 4. What is checked

- `verify_tasks` 371 → 380. Both ops in both directions, the empty list (the
  pair a silent refusal is caught by), the non-list path, a non-string value,
  the missing path, `contains` still exact, the op table, and a scan proving no
  task file reads `boxes.toast`.
- `verify_report` 242 (section N): the pinned channels declared and shipping
  empty, read through the docs directory the run is *serving*; then the
  greenhouse's refusal and its second status line through the door, and the
  tree visualizer.
- `mutate_tasks` 80 → 87: the op reversed, made exact, reading only the first
  message, the mirror that is not a mirror, answering about a non-list, a
  missing path proving silence, and `contains` quietly widened.
- `mutate_report` 141 → 145: each status line un-declared, one shipping with a
  sentence, and the page outside the toast family left mute.

## 5. Still filed

The general audit — every element a page writes a sentence into, proposed
against a ledger of the ones that are deliberately captions. The stand sheet's
remaining silent no-op exports. `Clear trial` raising no confirmation. The
collection sheet's stale voucher label and unlabelled guild-spectrum
percentages. The pheno tracker's asymmetric exports.
