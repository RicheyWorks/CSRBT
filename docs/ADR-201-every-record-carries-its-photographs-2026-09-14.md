# ADR-201 — Every record carries its photographs, and the address the refusal named

**Status:** accepted · **Date:** 2026-09-14 · **One page in this kit took a photograph. Twenty did not. The kit emits Darwin Core, and `associatedMedia` — the term whose whole job is to name the frames — was not in the column list at all, so every deposit this kit has ever produced left its media unnamed. Closed, on nine record-producing pages, through one shared component. Getting the door to drive that component then found a second defect, in the harness rather than the pages: two of its eight action pools named kinds the snapshot never published.**

## 1. The record carries the reference, not the image

Three reasons, all pointing the same way:

- A CSV cell cannot hold a JPEG.
- A base64 photograph inside a `.eco` export turns a 40 kB record into a 4 MB
  one, and the export is a thing people paste into a message.
- Darwin Core asks `associatedMedia` for an **identifier of** the media, not
  the media. A photograph's home is the camera roll or the card, where it
  already is.

So what travels is what lets a person — or a script — put the row and the file
back together six months later:

    filename | bytes | captured | crc32

**CRC-32 and not SHA-256, deliberately.** `crypto.subtle` does not exist on a
`file://` page, because a file URL is not a secure context, and this kit is
opened off a card in the field as often as it is served over https as an
artifact. A digest available in only one of those two is worse than a weaker
one that gives the same answer in both: the whole point is that the number
written on the sheet in the field still matches the number computed back at the
desk. It is an **integrity** check — has this file changed, is this the same
file — and it is not, and must not be described as, cryptographic. The check
value is the standard one: `crc32("123456789") == cbf43926`, and the suite
asserts exactly that rather than a number this kit made up.

**`captured` is the file's mtime, not EXIF.** `File.lastModified` is what a
browser gives a page without parsing the JPEG. For a frame straight off a
camera it is the shutter; for a file copied between cards it is the copy. The
field is named for what it usually means, and the pages say plainly what it is.

The images never leave the tab. Object URLs, revoked the moment a frame is
removed, so a session that adds and drops a hundred does not hold a hundred
blobs.

## 2. One component, not ten copies of a file reader

`FEK.photos` lives in the shared entry layer, which every data-entry page in
this kit inlines. A file reader copied into ten sheets is ten places for a
checksum to be computed differently, and the kit already learned that lesson
about escaping (v1.1) and about bad numeric input (ADR-151).

It carries its own live region, by the rule ADR-199 put on every other message
here: a PDF dropped on a photo zone is **refused out loud, naming the file**. A
reader who dropped six and got four has to be able to find out which two.

`set()` deliberately cannot put a photograph back. A page cannot hand a `File`
to a file input, and a component that pretended to restore one would be
restoring a caption.

Nine pages mount it — collection sheet, relevé, deployment log, field notebook,
pheno tracker, farm scout, selection log, ethogram, survey design — and
`associatedMedia` joins the Darwin Core term list for the deposits.

**The stand sheet is not migrated.** Its photo pane predates the component and
carries a *Link species* button the component knows nothing about; rewriting
that under a slice about photographs would be two changes wearing one hat. What
it did take is the shared checksum, so the reference it writes has the same
shape as every other page's. One column, one meaning. The migration is filed.

## 3. The address the refusal named

`drop-files` has always taken a control of kind `drop_zone`. The refusal a bad
address earns has always **advertised** `@kind=drop_zone` in its message. And
`KINDS` — the list every snapshot is built from — did not carry it. It lived in
`swarm.py`, which only the swarm reads.

So the door named an address its own snapshot never published, and the only
drop zones any task could ever reach were the ones that happened to sit on an
element some other kind already claimed. That is **ADR-141's rule backwards**: a
snapshot never advertises what the door would refuse, and a refusal must not
advertise what the snapshot does not publish.

The check written for it is over the **pools**, not over the one kind that
prompted it — and it immediately found a second: `set-checkbox` pools
`checkbox`, which was in the same private list. A tick box was addressable only
by an id a task already knew.

Two more rules came out of fixing it:

- **The zone is found by the mark the capture leaves** — the same
  `data-h-drop` attribute `drop-files` checks before it will dispatch. What is
  published and what is accepted are read off one mark rather than two.
- **No kind is listed twice.** Promoting the two into `KINDS` left them also in
  the swarm's additions, and a kind listed twice is discovered twice: the
  selectors renumber, and a diff starts reporting controls appearing that
  nobody added. That is asserted now, in both lists.

## 4. Two things this slice did not break, and found anyway

**A check that was passing by luck.** Three checks in `verify_report` failed the
moment the suite ran on its own — and failed on the *committed ADR-200 tree*
too, which had been green inside `run_all`. The page autosaves on a debounce,
and the widget that appears when a saved copy exists was arriving after the
baseline snapshot and before the `since` read. The diff was right; the check was
wrong. It passed or failed on how loaded the machine was, which is not a
property of the door. The suite now waits for two consecutive observations to
agree on the stamp before taking its baseline — the stamp is exactly *has this
moved*, so asking it twice is asking the page whether it is done.

**A guard that hid a bug.** On the survey design the component was wired to
`ecoOut()` behind `typeof x === "function"`. That page's export writer is
`outOut()`. The guard turned a wrong function name into silence, and the
photographs simply never reached the export. Caught because the check asserts
the reference is *in the export*, not that the wiring exists.

Three pages also had an export that said *nothing logged* whatever else the
session held. A reader who photographed four stations before typing any
settings copied a sheet claiming their morning had not happened. **A session
that is only photographs is still a session.**

## 5. What is checked

- `verify_fek` 101 → 122: the standard CRC check value, the padding, a single
  changed byte, the record's shape, the reference-not-the-image rule, the
  separator on **two** frames (it is invisible with one), the live region and
  its empty ship state, the refusal naming the file, and `set()` refusing.
- `verify_harness` 28 → 33: every kind an action pools is a kind the snapshot
  publishes; no kind is listed twice, in either list; the zone is found by the
  capture's own mark.
- `verify_report` 242 → 246 (section O): all nine pages driven through the
  door — the page takes a frame and says so, its export carries the filename
  **and** the checksum, and a non-image is refused out loud.
- `verify_dwc` 150 → 154: `associatedMedia` is a column, it carries name and
  checksum, nothing base64 rides in the deposit, and every occurrence carries
  it.
- **`mutate_fek`, new**: the one file nineteen pages inline had no mutant
  runner at all, which was invisible until this slice put a checksum in it.
  Thirteen mutants, all killed — wrong polynomial, unpadded output, no
  pre-load, checksum of the size, capture time from the clock, the image in the
  record, a comma separator, a dropped checksum, a swallowed refusal, an
  undeclared region, a zone with no address, and a lying `set()`.
- `mutate_harness` 18 → 22, and the runner now runs **both** harness suites: a
  mutant only `verify_harness` could see was, until this slice, a mutant
  nothing could see.
- `mutate_report` 145 → 148.

## 6. Still filed

The stand sheet's migration onto the shared component. The general audit —
every element a page writes a sentence into, proposed against a ledger of the
ones that are deliberately captions. The stand sheet's remaining silent no-op
exports. `Clear trial` raising no confirmation. The collection sheet's stale
voucher label and unlabelled guild-spectrum percentages. The pheno tracker's
asymmetric exports.
