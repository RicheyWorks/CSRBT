# ADR-040: Twenty-six open findings, twenty-six false positives

**Status:** Accepted and implemented — three rules in `tools/audit_frontend.py` rewritten, one deleted, `--only` added; `tools/verify/verify_audit_frontend.py` (19 checks) canaries the finder itself.
**Date:** 2026-08-26
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** `tools/audit_frontend.py`, `tools/verify/run_all.py`

---

## Context

`audit_frontend` had carried **26 open MED findings** across the kit for weeks. They survived every
slice because each one, looked at individually, seemed like something to get to later.

Looked at together, they were the finding.

## What each rule was actually doing

**`external-resource` — 16 rows, 16 false.** The rule matched any `src` **or** `href` pointing at an
external host, on the stated grounds of "CSP risk when published". Fifteen of the sixteen were
`<a href>` citations in ADRs and reference pages — links a reader taps, not requests the page makes.
A link is not a fetch. Now restricted to tags the browser actually loads from (`link`, `script`,
`img`, `iframe`, `source`, `video`, `audio`, `embed`, `object`, `track`) plus CSS `@import`.

**`unguarded-ref-to-absent-id` — 8 rows, 8 false.** All eight were controls the page's own script
writes into markup moments before dereferencing them: `koDo` and `koNo` in the food web's knockout
verdict, five in Pheno Tracker's card, one in the ecology lab. That is not an unguarded reference, it
is a constructor. The rule now skips an id whose `id="X"` appears inside a `<script>` block — markup
the page *writes* rather than markup it *ships*.

**`innerHTML-unescaped-value` — 3 rows, 3 false, and 0 true positives available.** This is the one
worth dwelling on.

The rule searched a 200-character window after `innerHTML=` for the substring `.value`, and for
`esc(` in that same window. It was wrong three ways at once: `.value` also matches `.values`
(that was the Ordination row); a comparison operand `x.value === y` is a test, not an interpolation
(cp-bench and soil-bench); and the 200-character cap truncated every multi-line template, so an
`esc()` call further down was invisible.

Then the real test. **Seeding the exact ADR-031 defect — removing `esc()` from a live warning path in
the food web — produced zero findings.** Not a near miss: the rule cannot see that class of defect at
all, because these pages assemble HTML into a variable with `+=` and assign it once, so the
`innerHTML =` expression never contains the concatenation.

**A rule that reports only false positives and cannot see the defect it is named for is not a weak
check. It is an anti-check** — it occupies the slot where a real check would go, and it teaches you to
skim a list that will one day have something in it.

## Decision

Delete it. Following taint through hand-written JavaScript is real static analysis with a long
false-positive tail, and this kit already measures escaping where the question is decidable: at
runtime, by typing markup into a page and reading back what the page rendered
(`audit_escaping.py`, `verify_escaping_slice.py`, and each page's own suite — the food web's caught
all six `esc()` removals seeded at it last slice). `audit_escaping` also **names the one page it
cannot drive** rather than counting it clean, which is the behaviour this rule should have had.

In its place, one thing that *is* decidable statically: a page that concatenates HTML and defines no
escaper at all. Two refinements were needed before that rule was honest, and both came from running
it:

- It first reported `field-season.html`, whose escaper is called **`escv`**, not `esc`. Naming a
  helper differently is not a defect. The rule now detects an escaper by its **signature** — a
  `replace()` over the entity character class — not by its name.
- A page with no free-text field has nothing to inject *through*. Those are reported LOW, with the
  reason stated, rather than sharing a severity with pages that take typed input.

Result: **HIGH 0, MED 0, LOW 2**, and both LOW rows are true and labelled with why they are low.

## But 26 → 0 is also what a broken finder looks like

Which is why this slice does not end there. `tools/verify/verify_audit_frontend.py` copies the kit to
a scratch tree, plants one defect at a time, runs the audit, and reads the rows back. **Nineteen
checks: every rewritten rule fires on a real fault and stays silent on the lookalike that used to
trip it, and every rule left alone still fires.**

| seeded | must |
|---|---|
| remote `<script src>`, stylesheet, `<img>`, CSS `@import` | fire |
| one more clickable citation | stay quiet |
| escaper removed from a page with a text field | fire |
| deref of an id nothing ever creates | fire |
| ids the script builds; an escaper named `escv` | stay quiet |
| duplicate id, dead link, no viewport, no print block, input under 16px, unguarded localStorage, JS error | fire |

Two of those checks failed on first run, both in the scaffolding rather than the audit: copying a
*subset* of pages made every sibling link dead (50 phantom HIGH rows), and the food web has **two**
`@media print` blocks, so removing one left the rule correctly quiet. Stub pages fixed the first —
and the stubs then generated findings of their own until they satisfied every rule the audit applies.
*A test fixture is a page too.*

## Consequences

`--only=a.html,b.html` was added to the audit, scoping which pages are **swept** while leaving every
file on disk so links still resolve. Re-checking one page went from a 37-page browser sweep to six
seconds, and it took this suite from nine minutes to ninety seconds. That flag should have existed
from the first day; its absence is why nobody ever ran the audit on a single page.

**The rule this leaves behind:** a finding you have decided not to act on is a claim you are making
about your own code, and an unexamined backlog of them is a claim you have stopped checking. Twenty-six
rows sat in a report that ran green every day. The number was true. Every row in it was false.
