# ADR-203 — What has not left this device

**Status:** accepted · **Date:** 2026-09-14 · **Every sheet in this kit answers what you have typed, and since KEEP it answers whether that survives the tab closing. Nothing anywhere answered whether any of it has ever LEFT. That is the question a reader with twenty minutes of satellite actually has, and until now it was answered out of memory — the same mechanism that loses mornings.**

## 1. What was asked for, and what is honest to build

The request was Starlink: field biologists have it, so the kit should use it.

The honest version of that, for a page opened off a card over `file://`, is not a
dish. A page cannot speak to a modem, a satellite or a server; a component that
pretended to would be the exact lie this kit exists to refuse, and it would be a
lie about data safety, which is the most expensive kind. What a page *can* do —
and what nothing in the kit did — is know precisely what is on this device and
nowhere else, so that a few minutes of signal go on the right bytes.

So: **a ledger, not a transport.** The strip says so in the page, where a reader
sees it, rather than in a comment.

## 2. Why this is not KEEP with a different word on it

KEEP says *saved on this device*, and immediately says it is not a backup. The
outbox is the other half of that sentence: *and here is what only exists there.*

They share exactly one thing, on purpose. `KEEP.wire` now returns `snapshot()`
(v1.1.0), and the outbox reads the sheet through it. A second description of
"what is on this page" would be a second thing to keep in step, and the one the
outbox used would be the one nobody tested.

## 3. Three ways the obvious version is wrong

**It marks on success, never on click.** The hook is inside the clipboard
promise's resolve path. A ledger that stamped on the button would tell a reader
their morning is safe when it is on no device but this one — a wrong toast is
forgotten in a second, a wrong ledger is read as reassurance a week later.

**It is per export, not per sheet.** One stamp for the sheet would go quiet
about the Darwin Core the moment the CSV was copied. That is under-reporting,
which is the direction that loses data. Each declared export carries its own
stamp of the state at the moment it actually left.

**An export it does not know is an error, not a shrug.** `sent("csv")` from a
sheet that never declared `csv` turns the strip red and names the string. That
is what makes a mis-wired call site loud — the failure ADR-201 found the hard
way, when a `typeof x === "function"` guard hid a wrong function name for the
length of a field season.

## 4. Declared, and counted, are two different lists

**Every copy a sheet can make is declared** — including the AI prompt and the
species pack, which carry no records. If they were not declared, a call site
could hand bytes out that the ledger has never heard of, and the strip would
report a sheet fully sent while an export of it walked around unlisted.

**Only the ones that carry records are counted.** An outbox that nagged you to
re-copy an AI prompt every time you added a stem is an outbox nobody reads, and
an outbox nobody reads is worse than none, because the page still looks like it
is keeping track.

Both directions are checked: an id no declaration knows is an error at runtime,
and a declared id no call site passes is a static failure — an entry that can
never stop being pending trains the reader to ignore the list.

## 5. The sheet as it came out of the box is not work

Three of these pages fill a date in for you, so "the snapshot is not null" is
not the same question as "is there anything here to send". An outbox that opened
saying four exports were overdue on a sheet nobody had touched would be ignored
by the second morning.

So the baseline is the state at wire time — **unless the autosave just restored
something**, in which case every export is genuinely outstanding and saying so
is the entire point. A morning's work that came back from the autosave has been
on exactly one device, and greeting it with "nothing on this sheet yet" would be
the most expensive sentence in the kit.

## 6. One checksum for the kit

FEK's CRC-32, over UTF-8 bytes the outbox encodes itself. **No second
implementation and no fallback**: a sheet whose photographs and whose outbox
disagreed about what a byte string hashes to is a sheet nobody can reconcile,
and an outbox that hashed with something nothing else uses would report
"unchanged" for a reason unrelated to the sheet. If FEK is not there it
**refuses** and says the strip is not tracking anything.

The encoder and the checksum are held to Python's `str.encode` and
`zlib.crc32` on a corpus with an accent, an em dash and a surrogate pair. A hash
that were merely self-consistent would report "unchanged" on a sheet that had
changed, and nothing else in the kit would notice.

## 7. What driving it found: four pages reported copies that never happened

`document.execCommand("copy")` reports failure **by returning false**, and
throws in only some of the ways it can fail. Five of the eight consumers ignored
the return value in their clipboard fallback, so a browser that refused the copy
still got a "Copied" toast. That fault predates this slice by a long way; the
ledger is what made it visible, because a wrong toast is forgotten and a wrong
ledger is believed.

The check is written **against every consumer**, driven through a real button
with both clipboard paths refusing — and, first, with both accepting, so the
refusal check cannot pass for the boring reason that the button never copied
anything at all. A check written only on the page where the fault was found
would have left it standing on four others.

The pheno tracker also carried the clipboard dance twice, inline, once per
export — the only sheet in the kit with no `copyText` of its own. Two copies of
a success path are two places to hook and one to forget. It has one now.

## 8. It is observable with no new protocol

The strip is a live region (`role=status`, `aria-live=polite`), so what changes
when an export lands reaches a screen reader and reaches the door through
ADR-199's `said` and ADR-200's `any-contains`. Nothing in the harness had to
learn about the outbox; ADR-199 defined the channel and this is a thing that
uses it.

## 9. What this does not do

**It does not send anything, and it never will from a `file://` page.** It also
cannot know whether what left the device arrived — a clipboard copy has left the
sheet, not necessarily the building. The strip says "left this device", which is
exactly the claim the evidence supports.

**It over-reports rather than under-reports**, once. Pending is computed on the
whole sheet's state, so an edit to a field that no export reads will mark every
export stale. That is the safe direction, and closing it would mean declaring
what each export reads — a list that would go out of date silently, which is the
unsafe direction wearing a tidier hat.

**It covers the eight pages that keep your work.** A page that does not claim to
look after what you typed cannot honestly claim to know whether it has left. The
other thirteen data-entry pages are filed.

## 10. What is checked

`verify_outbox`, 188 checks. The wiring is read off the pages rather than listed
in the suite: every copy a sheet makes must name a declared export, every
declared export must be makeable, the hook must exist exactly once and take the
id. Then the component is driven — blank, filled, one export gone, the sheet
changed underneath it, everything gone, an undeclared id, a restored sheet, a
ledger for an export that no longer exists, a quota that fails mid-session, and
a browser with no storage at all. And every consumer is driven twice through a
real export button: once with the clipboard accepting, once refusing.

`mutate_outbox`, 20 mutants, all killed. Fifteen in the component, five in one
page's wiring — because a fault in the component arrives on eight pages at once
and a fault in the wiring arrives on one, silently, which is the more dangerous
of the two.
