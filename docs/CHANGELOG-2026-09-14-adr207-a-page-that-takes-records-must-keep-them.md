# 2026-09-14 — ADR-207: a page that takes records must keep them

**Six pages accepted eighteen to forty-seven typed values and kept none of them.
One of them — the page that takes more typed values than any other in this kit —
carried the exact `try{ localStorage.setItem(...) }catch(e){}` KEEP was built to
replace, beside a check whose whole purpose is to find that pattern, running
green. The check was written over the pages that had already been converted.**

## Fixed

- **`experiment-guide.html` had the original bug.** A bare `setItem` in a `try`
  that swallowed every failure — full quota, private window, storage off by
  policy all produced nothing saved and nothing said — on the page with the most
  to lose. It uses KEEP now: `saveState()` survives as the name every call site
  uses and is a debounced touch on the autosave rather than a write of its own.
- **The silent-`setItem` check ran over twelve pages instead of forty-one.** So
  did the new record-keeping rule's ancestor. Both are over every page now. *A
  rule enforced over the converted set cannot find the unconverted one* — the
  same shape as ADR-204's consumer list and ADR-205's skipped page, a third time.
- **A restored design came back without its measurement rows.** Those rows are
  built from what is in `g-sizes` and `g-phases`, so a paint that ran before
  those boxes were filled drew none. The boxes go in before the renders.

## Added

- **KEEP on all six**: the experiment guide, the cell bench, the micro bench,
  the cp bench, the breeding bench. The ecology lab is **named with a reason**
  instead — it is a workbench, not a record: every box ships with a worked
  example, and the session files it charts come from the sheets, which keep.
- **The outbox on the three benches that can export** (cell, micro, cp). The
  breeding bench gets KEEP and no outbox: it has nothing to hand over.
- **The rule, driven**: every page is opened, its value-carrying controls
  counted from the harness's own `TYPED` list, and a page at or above four must
  mount KEEP or be named with a reason. An exemption is a written judgement, not
  an absence.
- `verify_keep` 221 → 279, `verify_outbox` 262 → 316, `mutate_keep` 23 → 28
  (all killed).

## Changed

- **A rule with no violators cannot show that it fires.** The first three
  mutants written against the new rule *survived*: every page keeps now, so
  narrowing the rule back to the converted set changed nothing a check could
  see. The rule is run twice instead — over the kit, where it must find
  nothing, and over a **canary directory** built by the suite, where it must
  name exactly the page that deserves it and leave the one that does not.

- The outbox suite required two declared exports per page. That is a claim about
  how many exports a page ought to have, not about the ledger. The bar is one.

- **A control that did not survive a repaint.** `audit_focus` reported,
  intermittently, that a page had a control "mounted after the last stamp and
  could not be measured" — different page each time, which reads as a flaky
  instrument rather than as the defect it is. KEEP's `paint()` wrote the whole
  strip with `innerHTML`, so its forget button was destroyed and re-created on
  every save. **KEEP 1.1.0 → 1.2.0**: the strip is built once and only its words
  change.
- **A suite must say what its temp directory is for.** `verify_keep` builds a
  canary directory now, and `verify_mutate` rightly refused a suite that reaches
  for `tempfile` without declaring whether it is building fixtures or doing
  something else. Declared `fixture-builder`.

## Noted, not fixed

- **The breeding bench has no export at all** — eighteen typed values, a roguing
  log, a yield trial, and no way to get any of it off the screen. It is an
  ADR-205 data trap that the rule written there missed, because that rule asks
  whether a page has an output *button* and this page has one that emits
  nothing. **A silent button is not an output.** Next slice.
- **The cp bench copies a soil recipe and nothing else** — not its water log,
  plants, observations, temperature record or crosses. Same class.
