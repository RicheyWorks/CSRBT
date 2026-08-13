# CHANGELOG 2026-08-12 — consolidation: the documented-not-fixed list, closed out

The remaining fixable items from the day's four audits, probe-first (3 probes, all
red pre-fix), plus the canonical replay artifacts regenerated under the fixed
recorder. Suite **804 green** (646 core + 158 experimental), 0 failures. JDK 21.

## Fixed

- **D-2 (Medium) — `TreeHistory` windowed undo:** with a sliding window active, an
  add can evict the oldest key, but only `ADD(v)` was recorded — undo dropped the
  evicted key permanently and undo/redo cycles compounded the loss, against the
  "undo restores the tree's contents" contract. Now: `TreeContext.add` peeks the
  eviction victim before the add (new `OrderedSet.peekOldest()`), the command
  carries it, and undo restores it. Documented semantics: the restored key re-enters
  at the FIFO tail, so a redo RE-EXECUTES the add and may evict a different key —
  the command's eviction record is refreshed on every redo so subsequent undos stay
  exact. Probe: `undoRestoresWindowEvictedKey`.
- **D-3 (Medium) — `FilePersistenceAdapter` atomic saves:** every save wrote
  directly to the final path, and `Files.newBufferedWriter` TRUNCATES at open — a
  save that later failed (I/O error, unencodable key such as an unpaired surrogate)
  had already destroyed the previous good snapshot. All three writer paths (int
  context, generic OrderedSet, persistent snapshot; the ensemble path delegates) now
  write a sibling `.tmp` and commit with an atomic rename; on any failure the
  previous file survives intact and the temp is cleaned up. Probe:
  `failedSaveDoesNotDestroyPreviousSnapshot`.
- **B3 (Low-Medium) — deterministic recorded sessions:** the wall-clock
  `avgInsertMs`/`avgDeleteMs` meters were the only nondeterministic bytes in an
  otherwise fully deterministic session, so regenerating a canonical replay file
  always produced spurious VCS diffs. `TreeExport.toJson` gains an
  `includeMeters` variant; `TreeSessionRecorder` embeds snapshots with meters
  zeroed (schema preserved for the visualizer; live diagnostics keep real meters).
  Probe: `recordedSessionsAreByteDeterministic`. Verified end-to-end: both arena
  mains now regenerate **byte-identical** output across runs.

## Regenerated

- **`docs/arena-session.json`** and **`docs/arena-search-session.json`** — the
  checked-in canonical replay files still carried the duplicate-`op` Lineage key
  (B1) and wall-clock meters. Regenerated with the fixed recorder: valid JSON,
  numeric `op` counters on every frame, `breedOp` on Lineage frames, meters zeroed,
  byte-reproducible.

## Docs aligned (B6 + fourth-pass drift notes)

- **`ArenaSession`** comments now narrate the story the code deterministically
  records (RB→Hybrid at op 20, Hybrid→Splay at 64, Splay→Hybrid at 280, ending on
  Hybrid) instead of the "hold RB / RB→Splay / Splay→RB" arc the tuning never
  delivered.
- **`GenomeDrivenTreeController`:** the control-plane toggle's javadoc said
  "Default OFF" (it is ON, as the field and pinning test agree); `recordAccess`'s
  doc claimed deletes feed the access window (they don't — behavior unchanged,
  doc corrected).

## Still documented-only (by design)

D-4 (FIFO window tracks keys by `equals` vs the tree's comparator — ADR-002 seam
class, no live defect with current key types); `lineageTag` slow growth; the
stability-gate eval-before-credit asymmetry (pinned as intentional); ADR-022's
composite-score weight retune (held until the new realized-depth numbers warrant
a decision).
