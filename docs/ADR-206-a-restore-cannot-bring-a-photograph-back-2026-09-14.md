# ADR-206 — A restore cannot bring a photograph back, and must say so

**Four sheets in this kit mounted the photograph component and had no autosave at all. Driving the fix found the larger fault underneath it: on the nine pages that *do* keep your work, adding a photograph touched the autosave not at all, and a restore dropped every frame — silently, since ADR-201.**

## 1. The slice as it started

ADR-201 put photographs on nine pages. Five of those keep your work; four —
the ethogram, the field notebook, the selection log, the farm scout — kept
nothing. A reader could photograph four stations, score an hour of behaviour,
take a phone call, and lose the lot.

Wiring KEEP and the outbox into those four is the obvious half. It is not the
interesting half.

## 2. What a restore cannot do, and what it must therefore say

A page cannot hand a `File` back to a file input. `FEK.photos.set()` has always
refused to pretend otherwise, and that refusal is right.

On its own it is the quiet version of the same loss. **A sheet the autosave
restores comes back one frame short and the reader believes their morning is
whole** — which is worse than losing it loudly, because nothing prompts them to
go back to the camera.

So the **record** survives even though the bytes do not: filename, size,
capture time, checksum, and the caption the reader wrote. The component lists
what it is missing, names each file with its checksum, and takes them back **by
checksum** when the same files are dropped in again — so the caption, which is
the expensive part, comes back with the frame.

**By checksum and not by name**, because a camera roll renames on export and two
cards both start at `DSC_0001`. The checksum is the only thing that says *this
is the frame that caption was written about*. A same-named file with different
bytes does not take a caption that was not about it.

**And a frame that was taken stays in the record whether or not this browser
holds it.** `have` says which is which, and `associatedMedia` names both: a
photograph has an identifier even when the bytes are on a card, and an export
that dropped it would break the only link between the row and the file.

## 3. What driving it found: two faults older and wider than this slice

**A photograph touched no autosave anywhere.** Adding a frame fires no `input`
and no `change` — the file input is hidden and a drop is neither — so every
autosave in the kit sat still while a reader photographed. A session that was
*only* photographs was saved by nothing at all. That is ADR-201's own finding
("a session that is only photographs is still a session") one layer down, and it
had been true on every page since. The component now dispatches one bubbling
`fek-change`, and KEEP listens for it, so a page added tomorrow is covered on the
day it mounts the component rather than on the day somebody remembers.

**And the frames were not in any snapshot.** All five of the older
photograph-bearing sheets restored perfectly and lost every frame. Six pages
fixed; the check is written over **every page that mounts the component**, not
over the ones this slice touched.

**A `typeof` guard hid it a third time.** On the pheno tracker the autosave is
wired three hundred lines above `FEK.photos`, so the restore runs before there is
anything to restore into — and `typeof PHOTOS === "undefined"` swallowed exactly
that. The records are now held and handed over on the line after the component is
built, with **no guard**: if that line ever runs too early it should throw, not
shrug.

## 4. The check that found it was nearly the wrong kind

The first version looked for `photos:PHOTOS.get()` in the page source. It failed
three pages that carry the frames through a local variable — a check about
**spelling** rather than about behaviour, and that is the kind that gets edited
to match the code instead of the other way round.

It is driven now. Every page that mounts the component gets a frame dropped on
it, a save, a reload, and one question: *does it say what it no longer holds?*
All nine are asked. That check is what found the missing `fek-change`, the five
un-snapshotted pages and the swallowing guard — none of which a source scan
would have seen.

## 5. And the execCommand fault was alive on four more pages

ADR-203 fixed a clipboard fallback that ignored `execCommand`'s return value and
toasted "Copied" over a copy the browser had refused. It fixed it on five pages
and wrote a check over **the pages that had an outbox** — rather than over the
pages that have a **clipboard**. The four sheets wired here all carried it, and
the field notebook carried the clipboard dance **three times**, so the fix
applied to one helper survived twice on the same page.

Both consumer lists are now the emitters', by ADR-204's rule. `verify_outbox`
drives all twelve; the refusal check is asserted to cover every one of them,
rather than a representative.

## 6. What is checked

`verify_fek` 123 → 134: the awaited frames are in the record and in
`associatedMedia`; the missing block names file and checksum; a returning frame
restores its caption and says it matched; a same-named file with different bytes
does not; `clear()` forgets the awaited list.

`verify_keep` 151 → 218: every consumer is the emitter's, and every page that
mounts the component is driven through drop → save → reload → *say what you no
longer hold*.

`verify_outbox` 188 → 262: twelve consumers, every one driven through a real
export button with the clipboard accepting and then refusing.

`mutate_fek` 13 → 21, all killed.

## 7. What this does not do

**The bytes are still gone.** Nothing here makes a browser hold an image across
a restore; it makes the loss legible and the caption survivable. The durable
copy is still the export, and the outbox on these four pages now says whether
it has left.

**The benches still keep nothing.** ADR-205 gave the cell bench and the micro
bench exports; they have no autosave yet. Filed.
