# 2026-09-14 — ADR-203: what has not left this device

**KEEP says "saved on this device" and, in the same breath, "this is not a
backup". Nothing in the kit said what that leaves you exposed to: which of your
work exists on exactly one device. That is the question a reader with twenty
minutes of satellite has, and it was being answered from memory.**

## Added

- **`OUT`, the outbox** (`tools/outbox.py`, emitted by `tools/outbox_emit.py`
  into the eight pages that keep your work). Per declared export, the state of
  the sheet at the moment that export actually left, against the state now. A
  **ledger, not a transport** — a page opened off a card cannot send anything,
  and the strip says so where a reader sees it rather than in a comment.
  - The mark lives in the clipboard's **resolve path**, never the button's
    listener.
  - **Per export, not per sheet**: copying the CSV must not make the Darwin Core
    look sent.
  - An export the ledger does not know **turns the strip red and names the
    string**, which is what makes a mis-wired call site loud.
  - The baseline that stops a blank sheet nagging is **not** taken after a
    restore: work the autosave brought back is entirely outstanding.
  - One checksum for the kit — FEK's CRC-32 over UTF-8 the outbox encodes
    itself, with **no fallback**: if FEK is absent it refuses and says so.
- **`verify_outbox`** (188 checks) and **`mutate_outbox`** (20 mutants, all
  killed). The wiring is read off the pages, so a page that gains an export is
  covered on the day it gains it.
- `KEEP.wire` returns `snapshot()` (**keep.py 1.0.0 → 1.1.0**). One description
  of "what is on this page", shared, rather than two to keep in step.

## Fixed

- **Five pages reported copies that never happened.**
  `document.execCommand("copy")` says no by **returning false** and throws in
  only some of the ways it can fail; the clipboard fallback on relevé, the stand
  sheet, the collection sheet, the greenhouse and the pheno tracker ignored the
  return value and toasted "Copied" regardless. The fault predates this slice by
  a long way — the ledger is what made it visible, because a wrong toast is
  forgotten in a second and a wrong ledger is believed a week later.
- **The pheno tracker carried the clipboard dance twice, inline** — the only
  sheet in the kit without a `copyText` of its own. Two copies of a success path
  are two places to hook and one to forget.

## Changed

- `verify_emitters` covers `outbox_emit` (130 → 156 checks). A regenerator
  nothing regenerates against is the drift it exists to prevent.

## Noted, not fixed

- **It over-reports, once, on purpose.** Pending is computed on the whole
  sheet's state, so editing a field no export reads marks every export stale.
  That is the safe direction; closing it would mean declaring what each export
  reads, a list that would go out of date silently.
- **"Left this device" is not "arrived".** A clipboard copy has left the sheet,
  not necessarily the building. The strip claims only what the evidence
  supports.
- **Thirteen data-entry pages are not covered.** A page that does not keep your
  work cannot honestly say whether it has left; wiring KEEP into them is its own
  slice.
