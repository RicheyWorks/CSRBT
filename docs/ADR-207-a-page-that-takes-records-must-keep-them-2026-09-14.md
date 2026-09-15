# ADR-207 — A page that takes records must keep them

**Six pages accepted between eighteen and forty-seven typed values and kept none of them: close the tab, lose the morning. One of them — the page that takes more typed values than any other in this kit — carried the exact `try{ localStorage.setItem(...) }catch(e){}` that KEEP was built to replace, beside a check whose entire purpose is to find that pattern, running green. The check was written over the pages that had already been converted.**

## 1. A rule enforced over the converted set cannot find the unconverted one

`verify_keep` has said *"%s has no silent setItem left"* since KEEP existed. It
said it about twelve pages: the ones already using KEEP. The experiment guide —
47 entry controls, a whole designer's worth of phases, models, datasets,
hypotheses and measurement rows — was not one of them, so the check never
looked, and the original bug sat there for eleven slices with a green suite
beside it.

That is the same shape as ADR-204's consumer list and ADR-205's skipped page,
a third time. **Both checks are over every page now**, not over a list of the
pages that have already been fixed.

## 2. The six, and what each keeps

- **experiment guide** — converted off its own silent `setItem`. `saveState()`
  survives as the name every call site uses; it is a debounced touch on the
  autosave rather than a write of its own.
- **ecology lab** — *not* converted, and named in the suite with a reason: it is
  a workbench, not a record. Every box ships with a worked example, and what a
  reader types into it is an exploration of the maths rather than something they
  made. The session files it charts come from the sheets, which keep.
- **cell bench, micro bench, cp bench** — KEEP and the outbox.
- **breeding bench** — KEEP, and **no outbox**, because it has nothing to
  export. See §4.

## 3. The rule, driven

Every page in the kit is opened, its value-carrying controls counted from the
harness's own `TYPED` list, and a page at or above four must mount KEEP or be
named with a reason. Driven rather than read off the source, for ADR-206's
reason: a check about spelling is the kind that gets edited to match the code.

An exemption is a written judgement, not an absence — the same rule ADR-205 put
on pages that hand nothing over, applied to pages that keep nothing.

## 4. Two things this found and did not fix

**The breeding bench has no export at all.** Eighteen typed values across a
roguing log and a yield trial, and no way to get any of it off the screen. It is
an ADR-205 data trap, and the rule written there missed it — because that rule
asks whether a page has an output *button*, and this page has one that emits
nothing. **A silent button is not an output.** Named here, fixed in the next
slice, along with the blind spot itself.

**The cp bench copies a soil recipe and nothing else** — not its water log, its
plants, its observations, its temperature record or its crosses. Same class.

Both now keep what you type, which is the half that stops the loss. Neither can
yet hand it to anybody, which is the half that makes it data.

## 5. What is checked

`verify_keep` 221 → 279. The record-keeping rule over all 41 pages; the
silent-`setItem` rule over all 41; the exemption must carry a reason.

`mutate_keep` 23 → 28, and the first three of the new ones **survived**, which
is the finding: **a rule with no violators left cannot show that it fires.**
Every page keeps now, so narrowing the rule back to the converted set changed
nothing a check could see. It is run twice instead — over the kit, where it must
find nothing, and over a **canary directory** built by the suite, where it must
name exactly the page that deserves it and leave the one that does not. ADR-127's
point about a refusal nobody has watched, arriving on a rule rather than on a
gateway.

The five that now stand: the rule names nothing; the rule names every page
without an autosave; the bar dropped to one control; the silent-`setItem` finder
looking past the page's own script; and a page counting as keeping merely because
it carries the component. All live in the suite rather than in `keep.py`, because
the rule is the thing under test.

`verify_outbox` 262 → 316: three more consumers, each driven through a real
export button with the clipboard accepting and then refusing.

## 6. And one the full run found: a control that does not survive a repaint

`audit_focus` reported, intermittently, that a page had a control *"mounted
after the last stamp and could not be measured"* — on the ethogram once, on the
breeding bench once, never twice on the same page. An intermittent finding is the
worst kind, because it reads as a flaky instrument rather than as the defect it
is.

It was the defect. KEEP's `paint()` wrote the whole strip with `innerHTML`, so
its **Forget this device's copy** button was destroyed and re-created every time
the autosave changed state — which is every time it saves. **A control that does
not survive a repaint cannot be stamped, addressed or kept in focus across one**,
and which page the sweep caught mid-save was a coin toss.

KEEP 1.1.0 → 1.2.0: the strip is built once and only its words change. Checked
by marking the button, typing, waiting for the save, and asking whether the same
element is still there — with a second check that the words *did* change, so the
first cannot pass because nothing repainted.

## 7. One check relaxed, on purpose

The outbox suite required a page to declare **two** exports. That is a claim
about how many exports a page ought to have, not about the ledger. The cp bench
makes exactly one copy and its outbox is no less true for it; the bar is one.
