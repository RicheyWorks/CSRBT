# 2026-09-14 — ADR-204: the promise nobody checked

**KEEP prints the only sentence in this kit a reader takes as a promise —
*Saved on this device* — and had 112 checks with no mutant runner. Breaking it
on purpose found that the sentence it exists for was asserted by nobody, and
that three of the eight pages carrying it were never opened by its suite.**

## Added

- **`mutate_keep`** — 23 mutants, all killed. The probe that assumes instead of
  probing, the swallow that comes back, the classifier that stops classifying,
  both escapes dropped, the format stamp and the timestamp left off, the format
  guard removed, `JSON.parse` unguarded, the "not a backup" line and the forget
  button removed, forget not cancelling its own pending write, the snapshot
  taking one field, the FEK bridge disabled and its guard inverted, the flush
  not wired, a refused restore announced as a success, and one in
  `keep_emit.py` that drops a page from the list the suite reads.
- `verify_keep` **112 → 151**:
  - **A browser that keeps nothing says so, at page open.** Storage that throws
    on the accessor itself — a private window, site data off, a policy — must
    read as nothing being saved before the work is lost, not as a *refused
    write* at the first save. This is the component's whole reason for
    existing and nothing asserted it.
  - **A tab hidden inside the debounce flushes** rather than losing the last
    edit — the exact case KEEP exists for, never driven.
  - **A restore the page refused is not announced as one.** `restore()`
    returning false, or throwing, must leave the strip claiming neither a
    restore nor a save.

## Fixed

- **Three pages inlined the autosave layer and its suite never opened them.**
  `keep_emit.py` wires eight consumers; `verify_keep` listed five, so the
  deployment log, the survey design and the greenhouse went untested. The
  suite now reads the emitter's list, so a page wired tomorrow is covered
  tomorrow. All three were fine — that is the good outcome, not the point.
- The per-consumer blank-sheet check now asserts that **nothing at all** was
  written, rather than nothing under one known key: a renamed key would have
  passed by writing somewhere the suite was not looking.

- **A missing control crashed the suite instead of failing it.** Remove the
  forget button and `verify_keep` timed out reaching for it — no pass, no fail,
  just a fallen instrument. The press is now conditional on a check that the
  button is there, so a sweep is told what it broke.
- **A restore that THREW was announced as a restore.** The refused-restore check
  drove `restore()` returning `false` and never one that blew up halfway, which
  is the same lie with a worse cause.

## Noted, not fixed

- **Only relevé is driven end to end.** The other seven consumers are held to
  loading clean, mounting the strip and saving nothing on a blank sheet. A page
  whose own `restore()` silently dropped half its records would still pass —
  that is a per-page suite's job.
