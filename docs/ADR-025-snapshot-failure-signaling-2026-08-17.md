# ADR-025: Snapshot save failure signaling — 2026-08-17

## Status

Accepted, implemented. Trigger: the held ADR candidate recorded in
`AUDIT-2026-08-14-wiring-and-fifth-pass.md` ("the three `FilePersistenceAdapter.saveSnapshot`
variants log-and-swallow `IOException` with a `void` return — a caller cannot programmatically
detect a failed save. Changing to `boolean`/`UncheckedIOException` is an API decision, not a
stub") and carried unchanged through the sixth pass.

## Context

Measured against the current code, not the audit's memory of it — the sixth pass's **S6-05**
changed the staging scheme, so the failure surface was re-derived from probes against the real
filesystem.

**What actually happens today.** All four save shapes — `saveSnapshot(String, TreeContext)`,
the generic `OrderedSet` path, the persistent-engine flat path, and the ensemble path — write a
per-call staging file `<name>.rbt.<pid>.<seq>.tmp` and publish it with an atomic rename
(consolidation **D-3**, made per-call-unique by **S6-05**). Probed failures:

| failure | what the caller sees |
|---|---|
| open cannot create the staging file (missing directory, revoked permission, name too long, no space) | `void` return, ERROR in the log |
| I/O error mid-write (surfaces at flush/close) | `void` return, ERROR in the log |
| full disk at close | `void` return, ERROR in the log |
| commit rename cannot publish | `void` return, ERROR in the log |

In every case the previous snapshot of that name survives intact and the staging file is
cleaned up — D-3 works. What the caller gets is **nothing**: the same `void` return as a
success. A shutdown checkpoint, an ensemble snapshot before a risky morph, a save loop over
many names — all proceed believing state is durable when it is not.

Two things are *not* in scope and stay as they are: a malformed snapshot name throws
`IllegalArgumentException` before any I/O (pinned by `RegressionFixesTest`), and a key that
serializes to a token containing `';'` throws `IllegalArgumentException` from the persistent
path. Both are caller defects — deterministic, not retryable, fixed by changing code, not by
changing the disk.

**On the "ensemble save fan-out".** There is none. `saveSnapshot(name, ensemble, ks)` snapshots
the **primary only** — every ACTIVE mirror is an exact copy of it, so persisting K member trees
would store the same keys K times. One file, one staging write, one atomic commit. There is no
state in which some members were persisted and others were not, and a save mutates no member.
The read side is where an ensemble-wide partial *could* exist, and `loadEnsemble` already
validates before it mutates (finding 4) and already returns a `boolean`.

## Options considered

- **Checked exception on `saveSnapshot`.** Maximum pressure to handle it; breaks every existing
  caller at compile time and every existing implementor. The largest possible break for a
  published 0.2.0 seam.
- **Unchecked `UncheckedIOException`.** No signature change, binary-compatible — and therefore
  the most dangerous option: it silently converts every existing caller's "logged and carried
  on" into "threw". A checkpoint loop that used to skip one bad name now aborts the loop. A
  behavior break with no compile-time warning is worse than an API break.
- **`boolean`.** Cheap, but it cannot distinguish "the volume is full, retry or fail over" from
  "this configuration can never write here, tell an operator" — and the entire justification for
  the signal is that the caller can *act* on it. Also still a return-type change: source-breaking
  for implementors, binary-breaking for callers.
- **Result object on a new, additive method (chosen).**

## Decision

**Keep `void saveSnapshot` exactly as it is. Add `trySaveSnapshot`, returning a `SaveResult`.**

- `TreePersistenceAdapter.trySaveSnapshot(String, TreeContext)` is a **`default` method**. Its
  default body calls `saveSnapshot` and returns `UNREPORTED`. Existing implementors compile
  unchanged and inherit an answer that is honest about not being one.
- `FilePersistenceAdapter` overrides it and adds the same twin for the three overloads
  (`OrderedSet`, `PersistentTreeEngine.Snapshot`, `EnsembleOrderedSet`). All four `void` shapes
  now delegate to their reporting twin and discard the result, so their behavior — the same
  ERROR line, the same "previous file left intact", the same staging cleanup — is byte-for-byte
  what it was. One `stageAndCommit` helper replaces four copies of the try/catch/finally.
- `SaveResult` is a record `(name, status, detail, cause)` with three states:
  - **`SAVED`** — committed and loadable.
  - **`FAILED`** — nothing published; the previous snapshot of this name is intact; the
    `IOException` is carried, and a compact-constructor invariant makes "FAILED" and "carries a
    cause" the same condition, so the signal can never be a bare boolean in disguise.
  - **`UNREPORTED`** — this adapter does not report. Returning `SAVED` here would be the signal
    lying, which defeats the purpose more thoroughly than having no signal.
  - **No `PARTIAL`.** D-3 staging plus the atomic rename means a target is either the complete
    new snapshot or the complete previous one, never a blend, and the ensemble path is a single
    save. A state no implementation can reach is a state every caller handles for nothing.
- `SaveResult.orThrow()` escalates a `FAILED` to `UncheckedIOException` carrying the original
  cause. The exception option is therefore **not rejected — it is made opt-in at the call site**,
  instead of imposed on every caller of a published API.

**What the caller can do with it,** which is the test any signal has to pass: retry (a full
volume that later drains, an NFS blip); fail over to another adapter or directory; abort a
shutdown sequence rather than exit believing state is durable; surface a misconfiguration to an
operator with the reason attached. The `detail` string is what separates the retryable case from
the never-going-to-work case.

## Consequences

- **Not a breaking change.** Adding a `default` method is source- and binary-compatible for both
  callers and implementors. Adding overloads to a class is additive. No existing signature,
  return type, or behavior changed. **The next release is 0.2.1, not 0.3.0.**
- One honest caveat: `SaveResult` and `SaveStatus` are nested in the interface, so implementors
  inherit those two simple names into scope. A third-party implementor with its *own* type named
  `SaveResult` referenced by simple name inside the class body would now see it shadowed. This
  is a theoretical source hazard, not a signature change, and the alternative (two new top-level
  types in `interfaces`) trades it for a wider public surface; recorded rather than hidden.
- The constructor's swallowed `Files.createDirectories` failure is now *visible*: the first
  `trySaveSnapshot` returns `FAILED` carrying the `NoSuchFileException`. The constructor's
  behavior is unchanged — the adapter stays constructible so a mount that comes up later still
  works.
- Nothing in-tree is forced to migrate. Call sites that do not care keep calling `saveSnapshot`.

*Tests:* `SnapshotFailureSignalingTest` (9). The failures are real and uid-independent: a
**commit rename blocked by a non-empty directory at the target path**, and an **open that cannot
create the staging file because the name exceeds the filesystem's component limit**. A
read-only-directory probe was written first and **rejected** — the suite can run as root, where
permission bits are bypassed and the probe silently passes while testing nothing. The only
double is a `LegacyAdapterDouble` implementing the published seam and nothing else, which is
what pins the additive default. Each behavior was verified red by reverting the corresponding
decision in isolation (report success unconditionally; make the default claim `SAVED`; drop the
FAILED-carries-cause invariant).

## Held

- **`loadSnapshot` returning `null` for both "absent" and "malformed"** is the same class of
  weak signal on the read side. It is not fixed here: unlike a save, a caller *can* act on
  `null` (fall back, rebuild), and the load paths already log the distinction. Worth its own
  pass if a caller ever needs to tell the two apart programmatically.
- **`listSnapshots` returns an empty list on I/O failure**, indistinguishable from an empty
  directory. Same shape, same argument, not urgent.
- **No `fsync`.** The atomic rename orders the publish, but neither the staging file's contents
  nor the directory entry is forced to stable storage, so `SAVED` means "the filesystem has
  it", not "it survives a power cut". Making that claim would need `FileChannel.force` on both
  the file and its parent directory, and a decision about the cost. Named here so `SAVED` is not
  read as more than it is.
