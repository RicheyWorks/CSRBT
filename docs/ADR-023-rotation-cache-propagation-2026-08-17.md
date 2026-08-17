# ADR-023: Rotations carry the cached height — 2026-08-17

## Status

Accepted, implemented. Trigger: sixth-pass audit 2026-08-17, finding 21 — itself the item
AUDIT-2026-08-14 **F-1** deferred ("rotations still use the non-propagating local setters") and
that the sixth pass (**S6-21**) closed by correcting the documentation rather than the code.
This ADR settles it with measurement.

## Context

Both rotation bodies in `TreeStrategy` link through the `*Local` node setters, which recompute
size, augment, height and black-height for the **touched nodes only** and never walk to the root.
That is the whole point: propagating from a rotation once made each rotation O(height) and each
insert O(height²). The justification comment, until S6-21, appealed to subtree size being
ancestor-invariant under a rotation — true for `size` and `augmentedValue`, and **false for
`height` and `blackHeight`**, which genuinely propagate upward. AVL and Hybrid masked it (their
rebalance walks call `refreshHeight()` from the modification point to the root); Red-Black and
WeightBalanced did not. `TreeNode1.getHeight()` is public API on a published module.

Two questions had never been answered with numbers: *how wrong is it*, and *what would exactness
cost*. Both are answered below; nothing here was decided by intuition.

### How wrong it was

Probe: five strategies × five workload shapes (random, ascending, descending, zipf-ish, mixed
add/remove), 3 seeds × 1500 ops, every node's cached height and black-height compared against a
full recomputation after every operation for the first 400 and every 10th thereafter (~2.5M node
checks).

| strategy | height-stale nodes | max height error | ops leaving ≥1 stale node | black-height-stale nodes |
|---|---|---|---|---|
| RedBlack | 2.4–5.7% | 2 | 70–95% | 0% insert-only, 2.7% mixed |
| WeightBalanced | 1.5–5.2% | **5** | 61–91% | same as height |
| AVL | 0% | 0 | 0% | 1.3–6.0% |
| Hybrid | 0% | 0 | 0% | 0.2–8.5% |
| Splay | 0% | 0 | 0% | 0% |

The number that decides it is not the node percentage but the **root**, which is what a caller
actually reads (3 seeds × 3000 ops):

| strategy | root height wrong after… ascending | random | mixed | max error |
|---|---|---|---|---|
| RedBlack | **98.7%** of ops | 59.7% | 47.1% | 1 |
| WeightBalanced | 74.3% | 46.7% | 33.5% | **8** |
| AVL / Hybrid / Splay | 0% | 0% | 0% | 0 |

**Who reads it, in-repo.** Every call site of `getHeight()` / `getBlackHeight()` was checked.
`AVLStrategy:176` and `HybridStrategy:468` read the cached height for balance factors — correct
before and after, since those two refresh it themselves. `ReconstructionHeightProbeTest` asserts
exactness, but only on AVL and Hybrid. `BulkBuildTest` uses `blackHeight()` (the exact recursive
walk), not the cache. That leaves exactly one consumer that drew a wrong conclusion:
`TreeContextTesterAdditions:128`, the experimental adaptive-morph demo, prints
`getRoot().getHeight()` for an ascending Red-Black build and **printed `h=7` at n=15 and n=20
where the real height is 6**. One demo — but a public accessor that is wrong 60–99% of the time
is not a defect you leave in place because the current callers happen to be few.

### What exactness costs

Two independent measurements, because wall clock on this class of change is mostly noise.

**Deterministic — extra ancestor visits per operation** (n = 100k, seed 7). `refreshHeightUpward`
is a *fixed-point climb*: a node's cached height is a pure function of its two children's, so once
a level recomputes unchanged, no ancestor can change either.

| strategy | sorted-insert | random-insert | mixed add/remove |
|---|---|---|---|
| RedBlack | **22.7** (22.7 / rotation) | 1.24 | 0.80 |
| WeightBalanced | **17.3** | 1.05 | 0.78 |
| AVL / Hybrid / Splay | 0 | 0 | 0 |

**Wall clock — A/B in one JVM.** Both library versions loaded behind isolated class loaders and
their passes *interleaved* (A,B,A,B…, alternating which arm goes first) so drift, GC and frequency
scaling hit both arms equally; ADR-022 discipline otherwise (untimed warmups, then 51 timed
rounds, median). n = 100k, `-Xms4g -Xmx4g -XX:+UseSerialGC`. A **same-code control** (before vs. a
copy of before) puts the noise floor at ±6% worst case, ±3% typical — quoted deltas are the median
of the per-round paired ratios, with the count of rounds in which the fixed arm was slower.

| strategy | sorted-insert | random-insert | mixed add/remove |
|---|---|---|---|
| RedBlack | **+27.2%** (50/51) | +1.9% (31/51) | −1.8% (18/51) |
| WeightBalanced | +4.1% (41/51) | −0.1% (25/51) | +3.1% (45/51) |
| AVL | −3.1% (17/51) | −0.3% (21/51) | −1.3% (18/51) |
| Splay | — | +0.4% (33/51) | +0.1% (26/51) |
| Hybrid | +0.4% (29/51) | +0.9% (33/51) | −1.3% (18/51) |

One cell is outside the noise. Absolute ns/op for it: RedBlack sorted-insert 466 → 582.

A further control — the new call structure present but the climb call removed — measured RedBlack
sorted-insert at +2.3%, i.e. **the +27% is the climb doing real work**, not call overhead.

### Why the sorted cell is the expensive one

Instrumenting both walks explains it exactly (RedBlack, n = 100k):

| workload | link-walk levels / op | of which the height actually changed | rotation-climb levels / op |
|---|---|---|---|
| sorted-insert | 27.7 | **26.7** | 22.7 |
| random-insert | 13.6 | 2.4 | 1.24 |

On a monotone stream the BST link's `recomputeAugmentAndPropagate` pushes a height change up
essentially the entire spine, and the rebalancing rotation then takes it straight back off — the
engine maintains height **twice per write**, in opposite directions. On a uniform stream the link
changes 2.4 heights and the climb walks 1.2. Nothing about the climb is inefficient; the sorted
shape is simply where the quantity really does move at every level.

### Cheaper variants, and why they lost

- **Lazy invalidation with a dirty bit.** Marking a rotation's ancestors dirty is itself the
  O(height) walk we are trying to avoid. The only O(1) marking is a tree-global epoch, which makes
  the *first* `getHeight()` after any rotation anywhere an O(subtree) recompute.
- **Refresh-on-read / version stamp.** Same O(subtree) recompute, plus 8 bytes per node, plus it
  makes a read *mutate* — which this codebase's whole read model forbids (ADR-004 R1, ADR-021: every
  public read runs under one optimistic `StampedLock` acquisition and must not write). And an
  O(subtree) read is *worse* than the advice the old javadoc already gave ("recompute it yourself").
- **Carrying black-height on the same climb.** Costs ~6% more climb steps and buys almost nothing:
  rotation is not black-height's dominant staleness source. `setColor`/`flipColor` update the
  recoloured node alone, and the RB fixups recolour O(log n) nodes per write, so exactness there
  means a propagation walk per recolour on the hottest path in the engine. Measured and dropped.
- **Eager climb with no exemptions** (the first implementation): +18.6% RedBlack / +10.8%
  WeightBalanced / +5.0% AVL / +11.3% Hybrid on sorted-insert, and **+25%/+30% on Splay**, which
  splays ~20 rotations per operation and needed the climb for nothing.
- **Asking the strategy per rotation** (`maintainsAncestorHeights()` queried inside the rotation
  body): a megamorphic call once more than one strategy class is live in a JVM — the normal state
  here, between ensembles, morphing and the battle runner — and Splay pays it 20× per operation.
  Measured +10.4%/+12.3% on Splay *while doing no climb at all*. Routing the same query through
  `MutableTree` (monomorphic) halved it but did not remove it.

## Decision

**Land it, for `height` only, with the redundant work removed by construction rather than by a
runtime query.**

1. **`TreeNode1.refreshHeightUpward()`** — refresh the cached height of every strict ancestor,
   stopping at the first ancestor whose height recomputes unchanged. Height only: it touches
   neither size nor augment (ancestor-invariant under rotation) nor black-height.
2. **`TreeStrategy.rotateLeft` / `rotateRight` now carry the height.** They capture the adopting
   parent's height, delegate to the primitive, and climb only if it moved.
3. **`TreeStrategy.rotateLeftLocal` / `rotateRightLocal`** are the old bodies, unchanged and
   renamed — the rotation counterpart of the existing `TreeNode1.setLeft` vs `setLeftLocal` pair,
   with the same meaning ("no upward propagation") and the same rule: *the suffix-free one is the
   safe default*.
4. **`AVLStrategy`, `HybridStrategy` and `SplayStrategy` call the `*Local` primitives**, each with
   the proof at the call site. AVL and Hybrid rotate only from inside a rebalance walk that calls
   `refreshHeight()` on every node from the modification point to the root — they must, because
   they steer by those very heights. Splay rotates only from inside `splay()`, which runs until the
   splayed node is the tree root; each step recomputes the new subtree root and the parent that
   adopts it bottom-up, and the next iteration recomputes that parent again from one level higher,
   so every node on the access path is recomputed after all of its descendants are final. They
   therefore run **byte-identical** code to before — measured 0 climb steps, 0% wall-clock change.
5. **`RedBlackStrategy` and `WeightBalancedStrategy` use the carrying pair.** WeightBalanced steers
   by size, never refreshes a height, and owes the climb; Red-Black reaches it through
   `MutableTree.rotateLeft`, which is now documented as the height-carrying seam so an out-of-band
   rotation is safe on any strategy.
6. **`TreeNode1.getHeight()` promises an exact value again.** `getBlackHeight()` does not, and now
   says so on its own terms instead of by reference to `getHeight()`: it is informational
   bookkeeping, `blackHeight()` is the exact invariant-checking answer, and the residual staleness
   is quoted with its real source (recolouring) and its measured size.

**One-line justification: exactness is inside the measurement noise on thirteen of the fourteen
strategy × workload cells, and the fourteenth — Red-Black under a monotone insert stream, +27% —
is a shape for which the library already ships an O(n) rotation-free path.**

## Consequences

- `TreeNode1.getHeight()` is exact for every node on every strategy. Verified across 5 strategies ×
  4 workload shapes after every operation: 8 of those 20 cells (all Red-Black, all WeightBalanced)
  fail on the pre-fix engine and all 20 pass now (`RotationHeightPropagationTest`, red-before /
  green-after run against the pre-fix classes).
- Code written against the S6-21 caveat — recomputing before reading — is still correct, merely no
  longer necessary. Nothing that used to work stops working.
- **Red-Black monotone inserts cost ~27% more write time.** For bulk-loading known-sorted data,
  `OrderedSet.buildFromSorted` is O(n) and rotation-free and is unaffected; this ADR does not make
  that path any less the right answer, and it does not help a *stream* of ascending inserts, which
  genuinely pays.
- `TreeStrategy` gains two default methods (`rotateLeftLocal` / `rotateRightLocal`). A third-party
  strategy that keeps calling `rotateLeft` / `rotateRight` gets exactness by default and pays for
  it; opting out is an explicit, documented proof obligation, which is the right way round.
- **ADR-018's frontier is untouched** — the change adds no comparisons, and the pinned guard is a
  comparator meter. Re-run: 2.3236 → 1.3161 → 1.0638 → 1.0007 → **0.9902**, monotone, one morph per
  regime change at every block length, the 256k crossing intact. The sixth pass saw a morph-path
  change break this test at 1.0006, so it is a live tripwire, not a formality.
- Black-height is now the *only* cache that can read stale, and its dominant source is recolouring,
  not rotation. That is a smaller and more honestly-scoped statement than the one S6-21 had to
  write.
- The cost model above is re-runnable rather than folklore:
  `RotationHeightPropagationBenchmark` (`./gradlew :csrbt-benchmarks:jmh`) sweeps the five
  strategies across the three workload SHAPES that drive the climb, with AVL / Hybrid / Splay
  included as controls that must not move.
- The demo that started this — `TreeContextTesterAdditions`'s adaptive-morph block — now prints
  `h=6` at n = 15 and n = 20, and the root's cached height is exact across every strategy and
  workload measured (0 of 9000 ops wrong in all fifteen cells, against 98.7% wrong before).

## Held

**Maintain height once per write instead of twice.** The measurement above shows the engine pushes
a height change up the whole spine at BST-link time (26.7 levels/op on a monotone Red-Black stream)
and then takes it back off at rotation time (22.7 levels/op) — while the tree's actual height
changes only O(log n) times across the whole run. Dropping the height leg from
`recomputeAugmentAndPropagate` and running a single fixed-point climb at the end of each write
would collapse both walks into one that almost always exits immediately, and would plausibly leave
Red-Black monotone insert *faster* than before this ADR. It is not done here because
`recomputeAugmentAndPropagate` carries heights precisely to fix AUDIT-2026-08-14 **F-1** (trees
wired top-down or in arbitrary order — snapshot deserialization, two-pass deep copy — converged to
correct sizes with stale heights, and AVL/Hybrid then violated their own invariant on the next
insert), that fix is three days old and pinned by `ReconstructionHeightProbeTest`, and the
reconstruction paths would each need their own explicit repair. **Trigger to revisit:** anyone
measuring Red-Black sequential-insert write throughput as a bottleneck, or the next change that
touches height maintenance in `TreeNode1` for any other reason.

**Exact ancestor black-height** stays out of scope, with its cost stated rather than assumed: it
needs a propagation walk per `setColor`, i.e. O(log n) climbs per Red-Black write, for a quantity
with no consumer. **Trigger:** a caller that genuinely needs `getBlackHeight()` to be exact rather
than `blackHeight()` — at which point the recolouring path, not the rotation path, is what has to
change.
