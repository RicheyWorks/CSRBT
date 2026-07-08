# 2026-07-07 — Workload signal seam (rotation metering + measuring reads)

External feeders (SuperBeefSort's `WorkloadAdaptation` in particular) could only feed the control
plane's `recordSearch(hash, depth)` / `recordAdd(hash, rotations)` with **zeros** for depth and
rotations — half the `WorkloadFeatures` vector (`meanSearchDepth`, `rotationsPerWrite`) had no public
origin. This change adds that origin. Additive only; no behavior changes for existing callers.

## Changes

**`MutableTree.onRotation()`** — new default no-op hook, fired once per primitive rotation from the
shared `TreeStrategy.rotateLeft/rotateRight` bodies (the single choke point all four strategies'
rotations flow through; RB calls back via `tree.rotateLeft`, AVL/Splay/Hybrid invoke the inherited
default directly — both paths end in the same bodies). Existing `MutableTree` implementors are
untouched by the default.

**`RedBlackTree.rotationCount()`** — the engine overrides `onRotation()` to count. Monotonic per
engine instance; written only on the already-serialized write path. `buildBalanced` remains
rotation-free (asserted by `RotationDepthSeamTest`).

**`OrderedSet.rotationCount()`** — facade accessor. A morph/self-repair swaps the engine and resets
the counter; callers metering per-op deltas should guard with `max(0, after - before)` (documented).

**`OrderedSet.searchDepth(K)`** — the measuring twin of `contains`: one strategy-independent,
never-splaying walk that answers containment *and* the realized depth. Encoding: `depth` (≥ 1 nodes
touched) when present, `~depth` (negative) when absent. Same ADR-004 R1 concurrency contract as
`contains` (optimistic step-bounded walk, stamp-validated, locked fallback).

## Tests

`test/core/RotationDepthSeamTest.java` — churn counted on ascending inserts, zero rotations on bulk
build, depth encoding (present / absent / empty), and non-mutation of the measuring read.

## Follow-up candidates

- `EnsembleController.contains` still records depth 0; feeding it the primary's realized depth
  without double-walking or bypassing VERIFIED-mode voting needs a read-path seam, not a facade one.
- A windowed ensemble (`setMaxSize` fan-out) would let bounded streaming feeds target ensembles;
  SuperBeefSort now fails loudly on that combination instead of silently streaming unbounded.
