# CSRBT — change log, 2026-05-30

A single working session of audit-driven fixes and features. All changes are
covered by the JUnit suite (`ant clean test`).

## Correctness fixes
- **Delete parent-cycle hang (critical).** `RedBlackStrategy.delete` (and the same
  latent bug in `AVLStrategy`/`HybridStrategy`) created a temporary parent-pointer
  cycle when splicing the in-order successor, which the augment propagation walked
  forever. Fixed by linking the successor's new right child locally
  (`setRightLocal`). This was hanging the whole test suite.
- **H1 — size/history drift.** `TreeContext.add` no longer increments
  size/metrics/history on a duplicate (which strategies silently skip), and no
  longer records a phantom undo entry.
- **H2 — interval augmentation.** New nodes inherit the context augmentor; `setTag`
  is followed by `reaugment`, so interval `max-hi` is maintained on later inserts.
- **Augmentor preservation** across strategy morph, self-repair, snapshot save/load,
  clone (`TreeCloner`), and checkpoint restore (`TreeHistory`); per-node tags now
  survive all of these.

## Adaptive engine (control plane)
- **C1/C3 — health-gated morph.** `setStrategy` builds the candidate aside,
  validates it (`StrategyHealthCheck`: contents, size, BST, per-strategy invariant,
  order-stat spot-checks), and swaps only on a full pass; failure keeps the
  incumbent. Returns `boolean`.
- **C2 — single morph authority.** The facade's stress auto-morph is now opt-in
  (`setAutoMorphEnabled`, default off).
- **C4 — anti-thrash MorphPolicy.** Cooldown + stability + minimum-improvement
  gating in `GenomeDrivenTreeController`.
- **G8 — observability.** One structured `event=morph_eval …` line per evaluation.

## Features
- **C6 — sliding-window / bounded set.** `TreeContext.setMaxSize(n)`: oldest-first
  eviction, order statistics exact on survivors.

## Backend / infrastructure
- **B1 — `PersistentTreeEngine`** insert/delete/traversal made iterative
  (stack-safe on deep input); still unbalanced (documented). **B6** redundant
  empty-version recording fixed.
- **Experimental split.** `TreeAgent` (alien-seed/swarm) and `TreeEcology` moved to
  an `experimental` package that depends on core, not the reverse.

## Hygiene
- **M1** audit log capped; **M2** Hybrid strategy preserved on snapshot reload;
  **M3** snapshot (de)serialization made iterative; **L1** dead fitness term removed;
  **M5** removed the unused per-node lock and Hybrid's misleading atomics, and made
  the single-threaded contract explicit.

## New test suites
`StrategyInvariantTest`, `AuditFixesTest`, `TagPreservationTest`,
`CloneAugmentorTest`, `HealthGatedMorphTest`, `MorphPolicyTest`,
`PersistentTreeEngineTest`, `WindowingTest`.

## Perf
- **S1 — Hybrid recolor.** Replaced the full-tree O(n) recolor on every write with
  an O(log n) path-local pass (`rbRecolorPathUp`), restoring O(log n)-per-op.

## Persistence
- **B7 — augmentor identity.** Snapshot header now carries `DEFAULT`/`INTERVAL`
  (backward-compatible 5th field); load re-applies it so interval trees round-trip
  without a manual `setAugmentor`.

## Still open
- **C5 — generic `<K>` keys + `Comparator`.** Largest remaining refactor; deferred
  to its own session with iterative compilation.
