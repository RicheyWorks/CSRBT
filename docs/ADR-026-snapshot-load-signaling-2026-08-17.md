# ADR-026: Snapshot load failure signaling — 2026-08-17

## Status

Accepted, implemented. Trigger: ADR-025's own **Held**, bullets 1 and 2 — "`loadSnapshot`
returning `null` for both 'absent' and 'malformed' is the same class of weak signal on the read
side" and "`listSnapshots` returns an empty list on I/O failure, indistinguishable from an empty
directory". ADR-025 deferred both on one argument: *"unlike a save, a caller can act on `null`
(fall back, rebuild)"*. That argument is measured below and it holds for exactly one of the nine
ways a load returns `null`.

## Context

ADR-025 gave the write side an answer and left the read side with none. The asymmetry is not
cosmetic: a save that fails leaves the previous snapshot intact, so the worst case is a stale
checkpoint. A load that fails is handed to a caller who is deciding **what state to run on**.

**What `null` means today.** Probed against the real adapter, real files, real filesystem:

| what happened | `loadSnapshot` / `loadOrderedSet` | what the caller should do |
|---|---|---|
| no snapshot of that name | `null`, WARN | start fresh — correct |
| file is empty (0 bytes) | `null`, WARN | do not start fresh; the file is broken |
| header has fewer than 4 fields | `null`, WARN | same |
| header size field is non-numeric | `null`, WARN | same |
| header present, no data line | `null`, WARN | same |
| **size mismatch — truncated or tampered** (S6-03) | `null`, ERROR | same, and *keep the file* |
| **structural validation failed** (M-2 gate) | `null`, ERROR | same |
| a key token cannot be decoded | `null`, ERROR | the serializer is wrong, not the disk |
| **I/O error opening or reading** | `null`, ERROR | retry, or fail over — the data may be fine |

Nine causes, one answer. The probe's measured shapes: a good 200-key snapshot truncated at the
midpoint of its data line refuses at `header=200, parsed=105`; an empty file, a one-field header
and a `many` size field each return `null` from a different branch; a bad key token surfaces as
`NumberFormatException`; and a **directory occupying the target path** produces a genuine
`IOException: Is a directory` at `readLine`. All nine return the same `null` to the caller.

**Who draws a wrong conclusion, in-repo.** `TreeContext.loadSnapshot:254-259` — the facade
persistence entry point — does `if (snapshot == null) { logger.warn("Snapshot '{}' not found."); return; }`.
It reports **"not found"** for a truncated file, for a tree that failed the structural gate, and
for an I/O error, then returns normally and leaves the live context on its current contents. The
one thing that is certainly true of eight of those nine cases is that the snapshot *was* found.
That is the same shape as ADR-023's demo printing `h=7` where the height was 6: one in-repo
consumer, one public accessor, and a wrong answer most of the time.

**The sixth pass made this worse, not better — on purpose.** S6-03 added the declared-size
tripwire to the persistent flat loader, S6-04 added it to `loadEnsemble`, and hardening M-2 added
the structural gate to both structured paths. Every one of those fixes converted a real defect
("silently loads wrong data") into an ambiguity ("returns `null`"). The refusals are right. The
reporting did not keep up with them, and the population of *malformed* → `null` grew the same day
`trySaveSnapshot` landed.

`listSnapshots()` is the same shape one level up: with the snapshots directory removed, it logs
`NoSuchFileException` at ERROR and returns `[]` — the same value an empty directory returns.

## Options considered

- **Throw on malformed.** Loudest, and a behavior break with no compile-time warning — the exact
  option ADR-025 rejected for `UncheckedIOException` on save, for the same reason: a caller whose
  startup path tolerated a missing snapshot now aborts on a corrupt one.
- **A sentinel `TreeContext`.** A distinguished "malformed" instance the caller compares against.
  Cheap, and every caller that forgets the comparison runs on a fake empty set. Rejected outright.
- **Separate `snapshotExists(name)` probe.** Two calls, a race between them, and it still cannot
  tell a truncated file from an unreadable disk.
- **Result object on new, additive methods (chosen).** The same shape ADR-025 already argued,
  tested and shipped; adopting a second design for the twin problem would be the worse outcome
  even if the second design were marginally better.

## Decision

**Keep every existing load signature and its `null`/`false`/`[]` return exactly as it is. Add
`tryLoad*` / `tryListSnapshots` twins returning a `LoadResult<T>`.**

1. **`LoadStatus`** has five states, and the split is the one a caller *acts* on:
   - **`LOADED`** — the value is here and passed every gate.
   - **`ABSENT`** — there is no snapshot of that name. A legitimate answer, not an error: this is
     the one case where "start fresh" is right.
   - **`MALFORMED`** — the file exists and is not a usable snapshot. Deterministic: retrying reads
     the same bytes. The file is still on disk, untouched, for inspection.
   - **`FAILED`** — an `IOException` prevented reading. Retryable, or worth failing over; the
     snapshot may be perfectly good.
   - **`UNREPORTED`** — this adapter does not report, and will not pretend otherwise.

   `MALFORMED` and `FAILED` are separate for exactly ADR-025's reason: "the volume is full, retry"
   and "this will never work, tell an operator" are different instructions. On the read side the
   line falls where the code already catches — `IOException` is the environment, anything else is
   the file — so the split costs one `instanceof` in one place.

2. **`LoadResult<T>(name, status, value, detail, cause)`**, with two compact-constructor
   invariants that make the states unfakeable: **`LOADED` carries a value and no other status
   may**, and **`FAILED` carries an `IOException` and no other status may**. `orElse(fallback)` is
   the one-liner for the fall-back-and-rebuild caller ADR-025 named. `orThrow()` escalates
   `FAILED` and `MALFORMED` — the two states in which the caller does *not* have the data and
   something is wrong — and deliberately does not escalate `ABSENT`, which is an answer the caller
   asked for. `MALFORMED` has nothing to carry (nothing threw; the file simply is not a snapshot),
   so `orThrow` synthesizes an `IOException` from the detail rather than making callers catch a
   second exception type.

3. **The interface default is honest in both directions, and it is not ADR-025's default.**
   `trySaveSnapshot`'s default must return `UNREPORTED` even on success, because a `void` save
   says nothing at all. A `loadSnapshot` that returns a **non-null** context has said something:
   it loaded. So `tryLoadSnapshot`'s default reports `LOADED` on a non-null return and
   `UNREPORTED` on `null` — which is precisely "I know it worked; I cannot tell you why it did
   not." `tryListSnapshots` uses the same rule: a non-empty list was certainly read.

4. **`FilePersistenceAdapter` overrides them, and the reporting twin is now the implementation.**
   All five load shapes (`TreeContext`, generic `OrderedSet`, persistent flat, ensemble, listing)
   compute a `LoadResult`; the published methods delegate and discard, exactly as ADR-025's `void`
   saves delegate to `trySaveSnapshot`. Every log line, every refusal, every "the target is left
   untouched" guarantee is byte-for-byte what it was — the outcome is simply no longer something
   only the log knows.

5. **Argument validation is unchanged.** A name that escapes the snapshot directory, an empty
   name, a null `KeySerializer` or a null ensemble target still throw `IllegalArgumentException`
   before any I/O. Those are caller defects: deterministic, not retryable, fixed by changing code.
   The result object is for what the disk did.

## Consequences

- **Not a breaking change.** Two `default` methods on the interface, new overloads on a class, one
  new nested record and enum. No existing signature, return type, or behavior changed.
  **The next release is 0.2.1, not 0.3.0.**
- `TreeContext.loadSnapshot` stops claiming "not found" for a file it found: it now reports the
  real reason and, for a `MALFORMED` snapshot, says the file was left in place. Its signature and
  its "leave the live context alone" behavior are unchanged — a load that cannot happen still does
  not happen. Honestly scoped, in the ADR-022 tradition: the **behavior** is pinned
  (`thePublishedReturnsAreUnchanged` asserts the live context still holds its 9 keys after both a
  truncated and a missing snapshot); the **sentence** is not. Log assertions across test classes
  are order-fragile here (`CLAUDE.md`), and inventing a capture harness to pin a WARN string would
  cost more than it protects.
- A caller can finally distinguish the three startup paths that matter: *no checkpoint, start
  fresh* (`ABSENT`), *the checkpoint is corrupt, do not overwrite it and do not silently start
  empty* (`MALFORMED`), *the disk is unhappy, retry or fail over* (`FAILED`).
- One caveat inherited from ADR-025, recorded rather than hidden: `LoadResult` and `LoadStatus`
  are nested in the interface, so an implementor with its own simple-named `LoadResult` sees it
  shadowed inside the class body. Same theoretical hazard, same trade, same reason.
- `Files.exists` returns `false` for a path whose name exceeds the filesystem's component limit,
  so such a name reports `ABSENT` rather than `FAILED`. That is `exists()`'s semantics, not a
  decision made here, and it is the same answer the pre-ADR-026 code gave.
- The failure surface is re-runnable rather than folklore: `SnapshotLoadSignalingTest` builds each
  of the nine causes against the real filesystem — including an `IOException` from a directory
  occupying the target path, which is uid-independent and so cannot silently pass when the suite
  runs as root (the rejected probe ADR-025 documents).

*Tests:* `SnapshotLoadSignalingTest` (13). Each decision was verified red by reverting it in
isolation: collapse `MALFORMED` back into `ABSENT` (5 red); drop the `IOException`/format split so
everything the catch sees is `MALFORMED` (3 red); let the listing call an unreadable directory an
empty one (1 red); let the additive default guess `ABSENT` from a `null` (1 red); drop the
LOADED-carries-value invariant (1 red); let `orThrow` escalate only `FAILED`, so a corrupt snapshot
slips past (1 red).

## Held

- **`deleteSnapshot` returns `false` for both "there was nothing to delete" and "the delete
  failed"** — the third instance of this exact shape, and the only one ADR-025 did not name. It is
  out of scope here because the slice is ADR-025's held list, not every boolean in the class, and
  because the caller's action is the same in both cases far more often than it is for a load.
  **Trigger:** a caller that must confirm a snapshot is gone — a retention sweep, or a delete
  before a re-save under the same name.
- **Nothing in-tree is migrated to the reporting twins except `TreeContext.loadSnapshot`.** The
  other call sites are tests asserting the published `null` contract, and they should keep
  asserting it. **Trigger:** a caller that needs to branch, which is what the twins are for.
- **`MALFORMED` does not say *which* bytes are wrong**, only which gate rejected them. A caller
  cannot repair a snapshot from the detail string, and is not meant to: the D-3 staging scheme
  means a malformed file is a file something outside this library damaged. **Trigger:** a repair
  or forensic tool, which would want the byte offset and the raw line, not a sentence.
- **No checksum.** `MALFORMED` is decided by the header size tripwire and the M-2 structural gate,
  which catch truncation and tampering that changes the shape — not a single flipped bit inside a
  key token that still parses. Making that claim would need a digest in the header and a format
  version bump. Named here so `LOADED` is not read as more than it is, exactly as ADR-025 named
  the missing `fsync` so `SAVED` would not be.

---

## Amendment, 2026-08-18 — the delete signal, and what durability `SAVED` may claim

This ADR's own **Held** list is what the amendment closes: clause 1 (`deleteSnapshot`'s ambiguous
`false`) and clause 4 (no checksum), plus ADR-025's held `fsync` bullet, which belongs with clause 4
because both are about what a status word is allowed to promise.

### 1. `deleteSnapshot` — closed, the same way twice already worked

**Trigger, as recorded:** "a caller that must confirm a snapshot is gone — a retention sweep, or a
delete before a re-save under the same name."

`Files.deleteIfExists` already knows three things and the published `boolean` reported two. Under a
retention sweep the collapsed pair is the damaging one: *nothing of that name* means the name is
free and the sweep may move on, while *the delete failed* means the file is still there and the
sweep has quietly stopped sweeping. A delete-before-re-save reads the same `false` and cannot tell
"clear to write" from "something is in the way".

**Decision — `tryDeleteSnapshot` returning a `DeleteResult`, additively, exactly as ADR-025 and
this ADR did.** `boolean deleteSnapshot` is byte-for-byte what it was and now delegates:
`tryDeleteSnapshot(name).deleted()` is precisely "did this call remove one", which is what the
`boolean` has always meant.

**The status set is four, and each of the omissions is a decision.**

- **`DELETED`** — a snapshot of that name existed and is gone.
- **`ABSENT`** — there was none. Not an error: the caller already has the state it asked for.
- **`FAILED`** — an `IOException` prevented it; the entry is still on disk. Carries the cause,
  under the same compact-constructor invariant the other two results use.
- **`UNREPORTED`** — the adapter does not report.
- **No `MALFORMED`.** A delete never reads the file, so a truncated snapshot and a perfect one are
  removed by the identical call. Unlike the load side, where MALFORMED is the state that carries
  the whole argument, here it is a state no implementation can produce — and this ADR's own case
  for MALFORMED was that a caller *acts* differently on it. ADR-025 refused `PARTIAL` on exactly
  this test; the same test refuses this.
- **No `DENIED`.** A revoked permission is an `AccessDeniedException` inside `FAILED`, where the
  `detail` string separates "retry this" from "tell an operator" — the split ADR-025 argued belongs
  in the detail, not in the enum.
- **No partial delete.** One snapshot is one directory entry.

**`gone()` is the amendment's real answer to this ADR's own objection.** The Held clause deferred
this partly because "the caller's action is the same in both cases far more often than it is for a
load", and that observation is correct — so the common caller gets a one-liner rather than a switch:
`gone()` is true for `DELETED` and `ABSENT`, false for `FAILED`, and false for `UNREPORTED`, because
an adapter that does not know has not said the name is free. That is the retention sweep's actual
question, phrased the way the sweep asks it.

**`orThrow` escalates `FAILED` and nothing else**, and the reason is sharper here than on the load
side. `LoadResult.orThrow` spares `ABSENT` because "there is no snapshot" is an answer the caller
asked for; `DeleteResult.orThrow` spares it because `ABSENT` *is the goal met*. Escalating it would
make `orThrow` throw on the successful half of `gone()`.

**The default is the load side's rule, not the save side's.** `true` from a `boolean` delete is
unambiguous evidence that a file was removed → `DELETED`; `false` is the ambiguous half →
`UNREPORTED`. Same asymmetry, same justification: a `void` save says nothing at all, while a
`boolean` delete says something in one of its two directions.

### 2. `listSnapshots` — already closed; the record is corrected, not extended

The empty-list-on-I/O-failure ambiguity was **ADR-025's** Held bullet 2, and *this* ADR closed it:
`tryListSnapshots` reports `LOADED` with a possibly-empty list when the directory was read and
`FAILED` carrying the `IOException` when it was not, pinned by `SnapshotLoadSignalingTest`'s
"listing separates empty from unreadable". `listSnapshots()` keeps its `[]` and delegates. Nothing
was left open there; the entry is noted here so a future reader does not go looking for it.

### 3. `fsync` — ADR-025's held bullet, landed as an **option**, with the cost measured

ADR-025 held it with "a decision about the cost". The cost, measured on this repo's real save path
(ext4 on a virtio disk, 200 saves per configuration after warm-up, two independent rounds):

| snapshot | no force | forced | surcharge |
|---|---|---|---|
| 100 keys (1.4 KB) | 0.16–0.27 ms | 0.53–0.59 ms | ≈ +0.4 ms |
| 10,000 keys (166 KB) | 0.30–0.32 ms | 0.83–0.98 ms | ≈ +0.6 ms |

The surcharge is roughly **constant in the payload** — it is two device flushes, not proportional
work — so it is a 2–3× multiple on the whole save here, and a larger one on rotating or networked
storage where a flush costs milliseconds. Forcing the already-closed staging file by reopening it
measures the same as syncing the writer's own descriptor, so the encode-and-write path is left
untouched, strict UTF-8 encoder included.

**Decision: `new FilePersistenceAdapter(true)` forces; the no-arg constructor does not, and is
unchanged.** Making every existing caller pay a device flush per save, silently, is the same class
of move ADR-025 rejected when it declined to convert `saveSnapshot` into a throwing method: a
behaviour change with no compile-time warning. Making it unreachable is the other failure — the
snapshot directory and its paths are private, so a caller who needs power-cut durability has no
way to fsync around this class. An adapter-level flag is decidable at the call site, which is where
the trade belongs.

**The javadoc was the part that actually mattered.** `SaveStatus.SAVED` read "reached durable
storage", `SaveResult.saved()` read "the snapshot is durable", and `saveSnapshot` promised
"durable storage" — four claims in the published API for a guarantee only ADR-025's Held list
retracted. They now say what is true: the snapshot was written and published, and *how* durable
that is, is the implementation's to state. `FilePersistenceAdapter(boolean)` states it, both ways,
with the table above.

**One limit, recorded rather than hidden:** if the directory force fails (a platform that will not
open a directory for reading — Windows), the save still reports `SAVED` and logs the failure at
DEBUG. By then the rename has published the snapshot, so `FAILED`'s two promises — nothing was
published, the previous snapshot is intact — are both false. On such a platform `SAVED` means what
it means with the flag off.

*Verified by syscall trace, not by reasoning:* the same save issues **0** `fsync` calls with the
flag off and exactly **2** with it on (the staged file, then its directory).

### 4. Checksum — **deferred**, with a trigger that names an event

Not "someday". Assessed:

- **What it would buy** is genuinely missing today: a flipped bit *inside* a token that still
  parses and still leaves the keys ascending — `12,BLACK` becoming `13,BLACK` where 13 also fits
  the slot — passes the declared-size tripwire and the M-2 structural gate, and `LOADED` is
  returned for data nobody wrote. Truncation, shape-changing tampering and inverted keys are all
  already caught; this is the residue.
- **The format is not the obstacle this ADR thought it was.** The Held clause says a digest "would
  need a digest in the header and a format version bump". The version bump is not required: the
  loader reads `header[0..4]` and the `AUGMENTOR` field was itself added as an optional fifth that
  legacy files simply lack (`header.length >= 5`). A sixth field extends the same way, in both
  directions. That correction is recorded here so the deferral rests on its real cost rather than
  an overestimate.
- **The real obstacle is that it cannot be opt-in the way `fsync` can.** `fsync`'s guarantee is per
  adapter and per call, and a caller who wants it knows at the call site. A checksum written only
  by opted-in adapters is verified only for files that happen to carry one, so `LOADED` would mean
  "verified" or "unverified" depending on which file it is — a status whose meaning varies by input
  is precisely the defect ADR-025 and this ADR exist to remove. A checksum therefore has to be
  written unconditionally, which changes the bytes of **every** `.rbt` file in a pending release
  and obsoletes the shipped sample snapshots in the same stroke.
- **And the threat model is narrow.** D-3 staging plus the atomic rename means this library never
  produces a partial file, so a damaged snapshot was damaged by something outside it; a hand
  deliberate enough to flip a byte can recompute a CRC-32, so this buys detection of *accident*,
  not of tampering.

**Trigger:** a snapshot that crosses a medium this library did not write it on — copied over a
network, restored from a backup, committed and pulled onto another machine — or one observed load
that passed both gates and produced a key nobody wrote. On either, the digest goes in as an
unconditional sixth header field across all four save shapes, in the same change that regenerates
the shipped samples and states the export-shape change.

## Held — after the amendment

- **`MALFORMED` still names the gate, not the bytes.** Unchanged from the original list; a repair
  or forensic tool is still the trigger.
- **No checksum** — as above, with the trigger sharpened and the version-bump claim withdrawn.
- **`fsync` is off by default**, so out of the box `SAVED` still means "the filesystem has it".
  That is now a documented property of a documented default rather than an unstated gap.
  **Trigger for flipping the default:** a caller whose snapshots are a recovery point of record —
  at which point the argument is about who pays, not about whether the mechanism exists.
- **Nothing in-tree is migrated to `tryDeleteSnapshot`.** The in-repo delete call sites are tests
  asserting the published `boolean`, and they should keep asserting it. **Trigger:** unchanged — a
  caller that needs to branch.
