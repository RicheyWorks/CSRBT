# CHANGELOG 2026-06-10 — ADR-010 X1: the strategy-aware repair gate

The one real defect the third external review stumbled onto (while calling it "naming
polish"): `TreeContext.selfRepair()` short-circuited on `diagnostics.isValidRedBlack()`
**regardless of the current strategy**. A healthy AVL/Splay/Hybrid tree legitimately fails
RB color discipline, so after any morph the healthy-path short-circuit never fired and
every `selfRepair()` call paid a needless O(n) rebuild. (The inverse miss — skipping repair
on a broken non-RB tree — was improbable but never argued impossible.)

## The fix (`TreeContext.selfRepair`)

- The gate is now `StrategyHealthCheck.validate(engine, currentStrategy, contents)` — the
  same per-strategy validator the morph health gate and `OrderedSet.selfRepair` already
  trust (RB color rules only for `RedBlackStrategy`, height balance for AVL/Hybrid,
  structural checks for Splay).
- The check moved inside the write lock (it reads live engine structure; the old gate ran
  unguarded before acquiring it).
- `TreeDiagnostics.isValidRedBlack()` keeps its name — it *is* an RB validity check — and
  gains a javadoc scope line: RB-strategy introspection only, never a strategy-agnostic
  gate.

## Tests (`SelfRepairGateTest`, 3 tests; suite 477, green)

Observable proof via engine identity (no timers, no log scraping): the short-circuit
returns the *same* `getTree()` instance, a rebuild returns a fresh one.

- Healthy RB: same engine.
- **The fixed case:** healthy AVL-morphed and Splay-morphed trees short-circuit — same
  engine, contents untouched (previously: rebuild on every call).
- Genuine corruption (root recolored red out-of-band): fresh engine, no data loss, RB
  invariant restored.

ADR-010 remaining: X2 (session replay arena), X3 (happens-before paragraph).
