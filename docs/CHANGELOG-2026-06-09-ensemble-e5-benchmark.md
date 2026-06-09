# CHANGELOG 2026-06-09 -- ADR-003 E5 (partial): ensemble-vs-single-tree benchmark

First slice of E5 (`ADR-003-multi-tree-ensemble-2026-06-06.md`): a StrategyBattleRunner-style
benchmark that pins ADR-003's central claim to assertable facts. No production code changes -- it only
exercises and measures the E1-E4 ensemble against the single-tree morph path. The other two E5 parts
(parallel fan-out, SAMPLED_SHADOW mode) are still open.

## What it shows

- **Adaptation: O(1) swap vs O(n) rebuild (deterministic).** A single tree adapts with
  `OrderedSet.setStrategy`, which builds a fresh engine and re-inserts every key -- the test asserts the
  engine *identity changes* (a rebuild). The ensemble adapts with `promote`, a pointer swap -- the test
  asserts the promoted member's engine *identity is unchanged* (no rebuild), contents intact, AVL now
  serving. Engine identity is the clean, non-flaky proxy for "rebuilt vs swapped".
  Both sides adapt to **AVL** (not Splay): `setStrategy` re-inserts keys in ascending order, which
  degenerates a splay tree into an n-deep chain, and `StrategyHealthCheck`'s recursive invariant walks
  then overflow the stack at n=16000 -- a validator property, not an ensemble one. AVL keeps the rebuilt
  tree O(log n) deep and makes the comparison apples-to-apples (same adaptation target on both sides).
- **Steady-state: Kx write fan-out (deterministic).** After N writes, all K=3 ensemble members hold an
  exact copy (Kx the work) while the single tree holds one (1x) -- the cost the ensemble pays for O(1)
  adaptation, made concrete.
- **Latency at scale (wall-clock, robust margin).** At n=16000 the test asserts the promote is cheaper
  than the rebuild and by a >100x margin -- the signature of O(1) vs O(n) (a node-by-node rebuild is
  milliseconds; a pointer swap is sub-microsecond). A short `[BENCHMARK ADR-003 E5]` line is printed
  with the per-n morph/promote microseconds for reference.

## Tests

- `EnsembleBenchmarkTest`:
  - *rebuildVsSwap* -- single-tree morph rebuilds the engine; ensemble promote reuses it.
  - *steadyStateFanOut* -- every member mirrors all writes (k=3 vs 1).
  - *adaptationLatency* -- JIT-warmed timing; promote dwarfs rebuild at n=16000.

## Still open in E5

- **Parallel fan-out:** ~~a `MemberExecutor` that fans writes to members across threads~~ _(landed
  later the same day -- see CHANGELOG-2026-06-09-ensemble-e5-fanout.md.)_
- **SAMPLED_SHADOW mode:** memory-lean shadows that receive a sampled fraction of writes; promotion of
  a shadow then costs a catch-up sync, and a shadow neither serves nor votes until caught up.
