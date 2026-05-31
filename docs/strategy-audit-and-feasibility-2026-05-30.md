# CSRBT — Strategy audit & end-goal feasibility (2026-05-30)

Two questions: (1) are the four balancing strategies correct, and (2) can the
project actually deliver what it states it wants to be — the adaptive,
health-checked, workload-driven ordered-set engine described in the README and
`docs/DESIGN-adaptive-engine.md`?

New tests added this pass: `StrategyInvariantTest` drives each strategy directly
through `RedBlackTree` (bypassing `TreeContext`'s auto-morph) and checks each
algorithm's own invariant against a `TreeSet` oracle, plus order-statistics
exactness, degenerate inputs, and cross-strategy edge cases.

---

## Part 1 — Per-strategy correctness

### RedBlackStrategy — solid
CLRS-faithful insert/fixup and delete/fixup; the per-tree NIL sentinel and
threaded `xParent` handle the sentinel-parent problem correctly. The delete
parent-cycle hang found earlier is fixed (local splice link). Augment (subtree
size) is maintained through rotations via the `*Local` link variants, so order
statistics stay exact. New tests assert RB validity (root black, no red-red,
uniform black-height), the `2·log₂(n+1)` height bound, and order-stats exactness
under a 4k-op mixed workload. No correctness issues found.

### AVLStrategy — solid, now strictly tested
Balance factor maintained in `{-1,0,1}`; `rebalanceUp` walks to the root after
both insert and delete (a single delete can need several rotations). The same
splice-cycle bug existed here and is fixed. Prior tests only checked "height ~
log n"; the new suite asserts **strict** `|bf| ≤ 1` at every node after mixed and
delete-heavy workloads, and the `1.44·log₂(n+2)` height bound. No issues found.

### SplayStrategy — correct as a self-adjusting BST
Zig / zig-zig / zig-zag are correct; insert and search splay the touched node to
the root; delete uses split-and-join. New tests assert the accessed/inserted key
becomes the root, BST order and size track the oracle under a hot-key workload,
order statistics stay exact, and the root's parent is always the sentinel. No
issues found. (Amortized O(log n) is a cost property, not asserted directly.)

### HybridStrategy — correct, but see the cost caveat below
Default `depthThreshold = Integer.MAX_VALUE` ⇒ tolerance 1 everywhere, so it
behaves as strict AVL balance plus a recolor pass; new tests assert `|bf| ≤ 1`
and a black root. Functionally correct. **However** `fixInsert`/`delete` run
`rbRecolorPass` over the **entire tree on every write** (`O(n)` per op). That is
exactly the kind of tree-wide hot-path work the design's non-functional goal G5
forbids. It doesn't corrupt anything, but it makes Hybrid `O(n)` per write rather
than `O(log n)`. See Finding S1.

### Strategy-level findings
- **S1 (perf, medium).** `HybridStrategy` does an O(n) full-tree recolor pass per
  insert and per delete. Inconsistent with the stated "individual ops stay
  O(log n)" goal. Either make the recolor local to the affected path, or document
  Hybrid as a non-O(log-n) experimental strategy.
- **S2 (cost, low).** `rbRecolorPass` doesn't establish real red-black validity
  (no rotations, no black-height guarantee) — it only flips a red parent of a red
  node. So a "Hybrid" tree is AVL-shaped with cosmetic colors, not an RB tree.
  Fine for balance, but `TreeDiagnostics.isValidRedBlack()` will report it
  invalid (see C3).

---

## Part 2 — Can it meet the stated end goal?

**Stated goal (README + DESIGN §1):** an ordered set that observes the live
workload, scores strategies, and *morphs to the cheapest one, switching only
after a health check confirms the new tree is valid*, with O(log n) ops, rare
amortization-gated morphs, generic keys, and explainable decisions (goals G1–G9).

**Verdict: the primitives are there and now correct; the adaptive control loop
is partially built and, most importantly, the headline safety guarantee is not
actually implemented.** Concretely:

### C1 (HIGH) — "health-checked morph" is claimed but absent
The README says morphing happens "only after a health check confirms the new tree
is valid," and DESIGN §3.4 specifies build-aside → validate → atomic swap with
free rollback. The actual morph path is `TreeContext.setStrategy()` →
`inOrderTraversal` → rebuild in place → trust. There is **no validation** of the
rebuilt tree and **no rollback**: `this.tree` is replaced before anything checks
it. A buggy strategy would corrupt live data with no gate to catch it. This is
the single biggest gap between claim and code. (Note `selfRepair()` *does*
validate, but it's RB-specific and not on the morph path — see C3.)

*Fix is well-scoped:* build the candidate in a fresh `RedBlackTree`, validate
(in-order equals sorted keys, size matches, per-strategy invariant, select/rank
spot-checks), and only then assign `this.tree`; on failure keep the incumbent.

### C2 (HIGH) — two competing, uncoordinated morph mechanisms
There are two adaptation systems that don't know about each other:
1. `TreeContext.add` → `morphIfStressed()` auto-morphs to **AVL** whenever red-red
   violations exceed a hardcoded threshold — always on, one-way, not workload-aware.
2. `GenomeDrivenTreeController` — the real(er) loop (stress/entropy/fragmentation,
   eval cadence, memory-biased selection) — but it's an **opt-in wrapper** around
   `TreeContext`.

If you use the controller, mechanism (1) still fires underneath and fights the
controller's decisions. And mechanism (1) contaminates `StrategyBattleRunner`:
each competitor runs through a `TreeContext`, so a "RedBlack" competitor can
silently become AVL mid-race, invalidating the benchmark it exists to produce.

### C3 (MEDIUM) — health/diagnostics are RB-only, not strategy-aware
`TreeDiagnostics.isValidRedBlack()` and `selfRepair()` assume red-black
invariants. Run against an AVL, Splay, or Hybrid tree they report "invalid"
(those trees aren't RB-colored), so `selfRepair` would "repair" a perfectly good
tree and still return FAILURE. DESIGN §3.4 requires a *per-strategy* invariant
check (RB validity for RB, height balance for AVL, …). That abstraction doesn't
exist yet, and it's a prerequisite for a real health gate (C1).

### C4 (MEDIUM) — no MorphPolicy (thrash protection)
DESIGN §3.3 requires min-improvement margin, cooldown, amortization vs O(n)
rebuild, and stability before morphing. The controller has only a single
morph-pressure threshold plus stagnation mutation — no hysteresis or cooldown, so
it can thrash A→B→A. Goal G4 ("≤1 morph to converge; 0 on steady workload") is
not yet guaranteed.

### C5 (MEDIUM) — keys are `int` only
DESIGN calls generic `<K>` + `Comparator` "a prerequisite for real workloads"
(G7). Everything is hardcoded to `int`, including the persistence format. Strings,
timestamps, and composite keys — the motivating applications — aren't supported.

### C6 (MEDIUM) — no windowing / eviction (G2)
The "exact streaming-percentile over the last N" north-star application needs a
bounded set with evict-oldest. There is no eviction path at all; G2 is entirely
unbuilt.

### C7 (LOW) — the genome machinery is the thing the design wants to replace
DESIGN §6 and §13 explicitly demote `TreeGenome` / `TreeEcology` / `TreeAgent`
(self-interpreting fitness, alien-seed, clone-army, relic beacons) in favor of
four small testable control-plane units (WorkloadMonitor / StrategyScorer /
MorphPolicy / MorphController). Today the genome model is the *only* adaptive
implementation, and the whimsical surface lives in `core`, not an `experimental/`
module. So the codebase is carrying the design's "before," not its "after."

### What already works toward the goal
- G1 (exact order statistics under churn): **met** for a fixed strategy and now
  verified across a forced morph (tag/augment preservation work + these tests).
- G9 (range/interval surface): present (`OrderStatisticsOps`, `IntervalAugmentor`)
  and now maintained across rotations and morphs.
- Strategy set RB/AVL/Splay/Hybrid: present and correct.
- Persistence, undo/redo, registry honesty: present.

---

## Recommended sequencing (matches DESIGN's roadmap)

1. **C1 + C3 together** — add a per-strategy `invariant(engine)` check and a
   health-gated `setStrategy` (build-aside, validate, swap-or-rollback). This makes
   the README's central claim true and is the highest-value, well-scoped fix.
2. **C2** — pick one morph authority: either remove `morphIfStressed` from
   `TreeContext` (let the controller decide) or have the controller own the
   threshold. Make `StrategyBattleRunner` drive strategies directly (as the new
   tests do) so benchmarks aren't contaminated.
3. **C4** — add cooldown + min-improvement + stability gating to the controller.
4. **C5 / C6** — generic keys and windowing/eviction; larger, schedule as their
   own efforts.
5. **C7** — move the biological surface to `experimental/`; keep `core` clean.

The good news: nothing here is blocked by a broken primitive. The trees, order
statistics, augmentation, and persistence are correct and tested. The gap is
almost entirely in the control plane and the safety contract around morphing —
which is buildable incrementally on top of the now-stable core.

---

## Resolution status (updated 2026-05-30, later same day)

Worked the backlog after the audit; current state:

- **C1 — DONE.** `TreeContext.setStrategy` now builds the candidate aside, runs
  `StrategyHealthCheck` (contents, size, BST, per-strategy invariant, order-stat
  spot-checks), and swaps only on a full pass; failure keeps the incumbent
  untouched. Covered by `HealthGatedMorphTest`.
- **C2 — DONE.** The facade's stress auto-morph is now opt-in (off by default), so
  morph authority lives solely in the control plane / controller.
- **C3 — DONE.** Per-strategy invariant validation lives in `StrategyHealthCheck`
  (RB validity / AVL-Hybrid balance / Splay none).
- **C4 — DONE.** `GenomeDrivenTreeController.MorphPolicy` gates morphs on cooldown,
  stability, and a minimum-improvement margin; unit-tested in `MorphPolicyTest`.
- **C6 — DONE.** Sliding-window / bounded set via `TreeContext.setMaxSize`
  (oldest-first eviction, order statistics exact on survivors); `WindowingTest`.
- **G8 — DONE.** One structured `event=morph_eval …` line per evaluation.
- **S1 (Hybrid O(n) recolor) — DONE.** The recolor pass now walks only the
  affected path (`rbRecolorPathUp`), so Hybrid writes are O(log n) again instead of
  doing a full-tree DFS per operation. Verified by the existing Hybrid invariant
  tests (balance + black root + order-stats).
- **C5 (generic `<K>` keys) — OPEN.** The remaining large refactor; recommended as
  its own session with iterative compilation.

