# ADR-199 — What the page said back: an act is answerable for the message it raised

**Status:** accepted · **Date:** 2026-09-13 · **Every page in this kit answers a refusal in a transient message — *A stem needs a DBH*, *No stems to export*, *Both partners are needed*. The door could not hear one. `activate` answered `ok: true`, which means the control took the press, and said nothing about whether the page did what the press asked; the two were the same answer. The message lives 1.7 seconds and then is gone, so it could not be fetched afterwards either. Three tasks in this kit are written as a whole read-report taken inside that window against a box holding whatever the *last* message was — a race dressed as a claim.**

## 1. The channel is the live region, not the class name

The obvious reader is `document.querySelector(".toast")`. It would have passed
every check in this slice and been wrong on the first page somebody writes
with a `role="log"` line, an alert bar, or any message element this kit has no
convention for.

The platform already has a definition of *a message the reader is meant to
receive without moving focus*: `role="status"`, `role="alert"`,
`aria-live` other than `off`. So the door reads the standard.

That decision immediately produced a finding, because reading the standard
means asking which pages meet it. **Twenty of the kit's twenty-one transient
message elements were plain `<div class="toast">`** — announced to nobody, and
invisible to a reader keyed on the standard. Only `experiment-guide.html` had
ever declared one. The pages were the defect; the door was right.

All twenty now carry `role="status" aria-live="polite"`, and the check that
says so reads the docs directory *the run is serving* rather than the
checkout's, because a page mutant arrives through `CSRBT_DOCS_DIR` and a
kit-wide scan that read past it would be green over a page the run had broken
on purpose.

**They also ship empty.** A live region is in the accessibility tree whether
or not it is on screen, so a toast whose markup reads `Saved` is a sentence a
screen reader can find at any moment, before anything has been saved. Nineteen
of them shipped with exactly that. The text was decorative — every page
overwrites it on the first message — and decorative text in a live region is
an announcement.

## 2. Two fields on every act

    execute("activate", {...}) -> {..., "said": ["A stem needs a DBH"], "produced": 0}

`said` is spliced at the end of the act: a message belongs to the act it was
raised during, exactly as a payload does. `produced` is a **monotonic counter
read either side of the act**, not the length of the outbox — `collect-output`
splices the outbox, so its length reports a backlog somebody else left rather
than what this press did. Two exports with the first still uncollected are one
and one, not one and two.

The act's own note carries the first message and the payload count, so a trace
reads `activate @control:csvCopy -- the page said 'No stems to export'` where
it used to read `activate @control:csvCopy`.

## 3. The same refusal twice is two refusals

The first draft of the observer skipped a message identical to the one still on
screen. The stand sheet's second *A stem needs a DBH* — a second press, a
second refusal — vanished.

That is **ADR-100's fault exactly**: a raise whose result looks like the
previous state is still a raise, and that reasoning once accused twelve live
controls of being wired to nothing. Setting `textContent` replaces the
region's children whether or not the string changed, so the *write* is
observable even when the text is not. One entry per observer callback: it
coalesces a write that lands as two mutation records without coalescing two
writes. Verified empirically before the guard came out, not reasoned about.

The observer also does **not** take what a region already holds when it starts
watching. A page's own state at the moment the door arrives is not something
it said to this session. Section 1 emptied every one of them, so there is
nothing there to take either way.

## 4. What is checked

`verify_report` 223 → 237. Fourteen checks, in three registers:

- **The kit's source**, scanned for a transient message element that is not a
  live region, or one that ships with text in it.
- **Through the door**, on the stand sheet: an empty export that answers
  `said: ["No stems to export"], produced: 0`; a refusal, then the *same*
  refusal; a success answered in the same channel, so `said` is what the page
  did rather than a list of complaints; a real export counting one payload,
  a second export counting one more, `collect-output` handing over both, and
  an act after a collection still counting from the page's own total. Then the
  collection sheet, refusing through the same reader with no page-specific
  code, because this is the kit's channel and not one page's.
- **A built fixture**, not a page of this kit: `role="log" aria-live="polite"`,
  a bare `role="alert"`, and an undeclared `<div>`. The first two are heard;
  the third is not, and must not be — a door reporting it would be inventing
  an accessibility the page does not have.

Seven new mutants in `mutate_report.py`, all killed: the class-name reader, the
dropped duplicate, the length-of-outbox counter, the take-on-attach, reading
`aria-live="off"`, dropping `role="alert"`, and a page whose toast loses its
role.

## 5. What this does not do

It does not make the three tasks that poll `boxes.toast` correct — it makes
them unnecessary. Rewriting them is the next slice's work, and until then they
keep passing on the same race they always did.

It does not give the door a *history*: `said` is capped at sixteen entries per
act and 240 characters per message. An act that raises seventeen messages is
an act nobody is reading the seventeenth of.

Still filed, still open: the stand sheet's silent no-op exports on the other
panes, `Clear trial` raising no confirmation, the collection sheet's stale
voucher label and unlabelled guild-spectrum percentages, the pheno tracker's
asymmetric exports.
