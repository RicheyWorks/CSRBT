# 2026-09-13 — ADR-199: what the page said back

**Every page in this kit answers a refusal in a transient message. The door
could not hear one: `activate` answered `ok: true`, which says the control
took the press and nothing about whether the page did what the press asked.
Acts now carry `said` and `produced` — and reading the platform's own
definition of that channel found twenty of the kit's twenty-one message
elements were not announced to anybody.**

## Fixed

- **twenty pages** — the transient message element was a plain
  `<div class="toast">`: invisible to a screen reader and to the door. All
  twenty now declare `role="status" aria-live="polite"`. Only
  `experiment-guide.html` had ever done so.
- **nineteen pages** — that element shipped with `Saved` (or `Copied`) in it.
  A live region is in the accessibility tree whether or not it is on screen,
  so decorative placeholder text there is a sentence a reader can find before
  anything has been saved. All ship empty.

## Added

- `harness_plugin_page.py` — a live-region observer keyed on
  `role=status` / `role=alert` / `aria-live`, rescanned as the document
  changes so a region a page *builds* is watched too. Every act answers with
  `said` (the messages raised while it ran) and `produced` (payloads pushed
  during it). `produced` is a monotonic counter read either side of the act,
  because `collect-output` splices the outbox and its length would report
  somebody else's backlog. The act's note carries both, so a trace reads
  `activate @control:csvCopy -- the page said 'No stems to export'`.
- `verify_report` section M (223 → 237): the kit's source scanned for a
  message element that is not a live region or ships with text; the stand
  sheet's refusals, successes and payload counts through the gateway; the
  collection sheet refusing through the same reader with no page-specific
  code; and a built fixture — `role="log"`, a bare `role="alert"`, and an
  undeclared `<div>` — proving the reader keys on the standard rather than on
  this kit's class name, and that the undeclared div is correctly *not* heard.
- `mutate_report` (134 → 141): seven mutants, all killed — the class-name
  reader, the dropped duplicate message, the length-of-outbox counter, taking
  a region's contents on attach, honouring `aria-live="off"`, dropping
  `role="alert"`, and a page whose toast loses its role.

## Changed

- The same-refusal-twice guard. The first draft skipped a message identical to
  the one still on screen, and the stand sheet's second *A stem needs a DBH*
  vanished — ADR-100's fault exactly, the one that once accused twelve live
  controls of being wired to nothing. One entry per observer callback instead:
  it coalesces a single write that lands as two mutation records without
  coalescing two writes.
