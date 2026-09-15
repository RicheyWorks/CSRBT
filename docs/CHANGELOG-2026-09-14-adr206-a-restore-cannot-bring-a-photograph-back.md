# 2026-09-14 — ADR-206: a restore cannot bring a photograph back, and must say so

**Four sheets mounted the photograph component and had no autosave at all.
Driving the fix found the larger fault underneath: on the nine pages that *do*
keep your work, adding a photograph touched the autosave not at all, and a
restore dropped every frame — silently, since ADR-201.**

## Fixed

- **A photograph touched no autosave, anywhere.** Adding a frame fires no
  `input` and no `change` — the file input is hidden and a drop is neither — so
  every autosave in the kit sat still while a reader photographed, and a session
  that was *only* photographs was saved by nothing. `FEK.photos` now dispatches
  one bubbling `fek-change` and KEEP listens for it, so a page added tomorrow is
  covered on the day it mounts the component.
- **The frames were in no snapshot.** All five older photograph-bearing sheets
  restored perfectly and lost every frame. Six pages fixed.
- **A `typeof` guard hid it a third time.** On the pheno tracker the autosave is
  wired three hundred lines above `FEK.photos`, so the restore ran before there
  was anything to restore into and `typeof PHOTOS === "undefined"` swallowed it.
  The records are held and handed over after the component exists, with **no
  guard** — that line should throw if it runs too early, not shrug.
- **The `execCommand` fault ADR-203 fixed was alive on four more pages.** That
  check was written over the pages that had an *outbox* rather than over the
  pages that have a *clipboard*. The field notebook carried the clipboard dance
  **three times**, so a fix applied to one helper survived twice on one page.
  Both consumer lists are the emitters' now, by ADR-204's rule.

## Added

- **KEEP and the outbox on the ethogram, field notebook, selection log and farm
  scout.** They kept nothing at all.
- **`FEK.photos.restore()`** (FEK 1.5.0 → 1.6.0). A restore keeps the *record* —
  filename, size, capture time, checksum, caption — lists what it no longer
  holds, and takes frames back **by checksum** when the same files are dropped
  in again, so the caption comes back with the frame. By checksum and not by
  name: a camera roll renames on export and two cards both start at `DSC_0001`.
- `have` on every photograph record, and awaited frames in `associatedMedia`: a
  photograph has an identifier even when the bytes are on a card, and an export
  that dropped it would break the only link between the row and the file.
- `verify_fek` 123 → 134, `verify_keep` 151 → 218, `verify_outbox` 188 → 262,
  `mutate_fek` 13 → 21 (all killed).

## Changed

- **The photograph check is driven, not spelled.** Its first version looked for
  `photos:PHOTOS.get()` in the source and failed three pages that carry the
  frames through a local variable — a check about spelling is the kind that gets
  edited to match the code. Every page that mounts the component is now driven
  through drop → save → reload → *say what you no longer hold*. That is what
  found the missing event, the five un-snapshotted pages and the guard.
- The field notebook's tally boards expose their whole contents, not only the
  non-zero ones: a category you added and have not yet tallied is work too.

## Noted, not fixed

- **The bytes are still gone.** Nothing here makes a browser hold an image
  across a restore; it makes the loss legible and the caption survivable.
- **The two benches still keep nothing.** ADR-205 gave them exports; they have
  no autosave yet.
