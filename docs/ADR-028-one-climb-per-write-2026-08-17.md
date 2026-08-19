# ADR-028: Maintain the cached height once per write — 2026-08-17

## Status

Accepted, implemented. Trigger: **ADR-023's own Held, bullet 1** — *"Maintain height once per
write instead of twice"* — fired by the second of the two triggers it named ("the next change that
touches height maintenance in `TreeNode1` for any other reason" is this one; the first, someone
measuring Red-Black sequential-insert write throughput as a bottleneck, is what ADR-023's own
+27% cell already was). ADR-023 recorded the hypothesis and declined to attempt it, because the
propagation path it wanted to change is AUDIT-2026-08-14 **F-1**'s fix, three days old and pinned
by `ReconstructionHeightProbeTest`, and "the reconstruction paths would each need their own
explicit repair". **This ADR closes that Held item.** The second Held bullet — exact ancestor
black-height — is untouched and stays open on its own trigger.

## Context

ADR-023 made `TreeNode1.getHeight()` ancestor-exact on every strategy by having
`TreeStrategy.rotateLeft`/`rotateRight` carry the change up with a fixed-point climb. It cost
**+27.2%** on Red-Black monotone (sorted) insert and was inside the noise on the other thirteen
strategy × workload cells. ADR-023 instrumented both walks and said exactly why:

| workload | link-walk levels / op | of which the height actually changed | rotation-climb levels / op |
|---|---|---|---|
| sorted-insert | 27.7 | 26.7 | 22.7 |
| random-insert | 13.6 | 2.4 | 1.24 |

On a monotone stream the BST link's `recomputeAugmentAndPropagate` pushes a height change up the
whole spine and the rebalancing rotation takes it straight back off. Height is maintained **twice
per write, in opposite directions**, while the tree's real height moves only O(log n) times across
the whole run.

### Re-establishing both baselines on this machine

Everything below was measured on the machine this change was made on, with all three library
versions in the comparison, so ADR-023's numbers and this ADR's numbers are never mixed across
hosts. Three arms, each compiled from its own source tree:

- **pre023** — `TreeStrategy.rotateLeft`/`rotateRight` delegate straight to the `*Local` bodies,
  i.e. exactly the pre-ADR-023 engine (Red-Black and WeightBalanced left ancestor heights stale).
- **cur** — the repository as ADR-023 left it.
- **new** — this change.

Harness: all arms loaded behind isolated `URLClassLoader`s inside one JVM, their passes
**interleaved** with the arm order rotated (and reversed on odd rounds) so every arm occupies
every position equally often, and drift, GC and frequency scaling hit them all the same. ADR-022
discipline otherwise: untimed warmups (12), then 51 timed rounds, paired per-round ratios,
medians. n = 100k, `-Xms2g -Xmx2g -XX:+UseSerialGC`. Workload generation is
`RotationHeightPropagationBenchmark`'s, key for key. Five independent JVM invocations, **255
paired rounds per cell**; the tables quote the median of the per-run paired medians and the total
count of rounds in which the numerator arm was slower.

**Noise control, stated honestly.** Other agents were building on this two-core machine throughout;
load average ranged 0.9–3.3 across the runs. Interleaving is what makes that survivable — both
arms of every ratio see the same interference within the same round — but it does not make the
machine quiet, so two independent controls are carried in every table:

- a **same-code control arm** (`new` loaded a second time under a second class loader), which
  measures ±0.1–2.8% per cell;
- **AVL, Hybrid and Splay in the `cur`-vs-`pre023` column**, which run byte-identical code in both
  arms and so are a second same-code control across a *different* class loader pair: they span
  −3.2% to +0.9%.

Taking both together the floor is **±3% typical**, and one cell is worse than that on its own:
WeightBalanced/sorted, where the `pre023` arm alone is bimodal across JVMs (median 38.8, 40.4,
42.1, 50.1, 50.5 ms on five runs) and even the two identical arms disagree by up to 5% inside a
single JVM. That is a JIT compilation-plan lottery, not load, and it means **WB/sorted cannot be
resolved below about ±10% here**; it is reported with that caveat rather than dressed up.

The reproduced baseline: **cur vs pre023 on Red-Black sorted-insert is +21.7% (253 of 255 rounds
slower)**, against ADR-023's +27.2% (50/51) on its own machine. Same sign, same order, same single
outlier cell — the rig reproduces the thing it is meant to re-measure.

### Every path that depends on the height leg

Enumerated before touching it — every caller of the propagating setters, plus everything
`ReconstructionHeightProbeTest` and `RotationHeightPropagationTest` pin:

| path | who | what it needs |
|---|---|---|
| BST insert link | all five strategies | height on the write's terms |
| delete transplant + successor splice | RedBlack, AVL, Hybrid, WeightBalanced | same |
| **snapshot deserialization** | `FilePersistenceAdapter.deserializePreOrder:465,472` | top-down wiring: `setLeft`/`setRight` must converge from arbitrary order — **F-1** |
| **two-pass deep copy** | `TreeCloner.deepCopyTwoPass:262,263` | pass 2 wires an `IdentityHashMap` iteration order — **F-1** |
| **depth-limited clone** | `TreeCloner.cloneDepthLimited:304,305` | bottom-up, but on a deliberately truncated (invalid) tree |
| recursive deep copy | `TreeNode1.deepCopy` | links, then overwrites the caches from the source |
| `reaugment()` | `IntervalAugmentor:232`, `GenericIntervalAugmentor:137`, `OrderedSet:1020` | augment-only, but rides the same walk |
| `setAugmentor` | `OrderedSet:800`, `TreeCloner`, `TreeHistory` | same |
| O(n) sorted bulk build | `RedBlackTree.buildBalancedNode:113,116` | already `*Local`, bottom-up |
| out-of-band rotation | `MutableTree.rotateLeft`/`rotateRight` | must stay exact with no write around it |

Only the first two rows are the hot path. **The other eight are not the engine's write path at
all**, and the decisive design consequence follows from that: this change does not touch
`setLeft`/`setRight`, `recomputeAugmentAndPropagate`, or any file outside the strategies and
`TreeNode1`'s new methods. F-1's fix keeps running exactly as it did, on exactly the code it was
written for. ADR-023 expected "each reconstruction path would need its own explicit repair"; the
measured answer is that none of them does, because the cost being removed is only ever paid by a
caller that has an end-of-write to hang a single repair on.

## Options considered

- **Drop the height leg from `recomputeAugmentAndPropagate` outright** — ADR-023's literal
  sketch. Rejected: that walk is the *only* thing that makes arbitrary-order wiring converge, and
  a reconstruction path has no "end of write" to repair at. Simulated as a revert (making
  `setLeft`/`setRight` use the no-height walk) and it puts all three
  `ReconstructionHeightProbeTest` cases red — F-1, exactly.
- **Make the height leg of the link walk a fixed-point climb.** Correct on every path, and worth
  nothing: on a monotone stream the height genuinely changes at 26.7 of 27.7 levels, so the fixed
  point never fires where it would matter.
- **One unconditional bottom-up repair from the anchor to the root.** Correct and simple, and
  close to a wash: it trades the 22.7-level rotation climb for a 27.7-level repair walk while
  removing 27.7 *fused* height recomputes from the link walk — and the fused ones turn out to be
  nearly free (see the last row of the deterministic table: `pre023` carries them and is not
  measurably slower than an arm that carries none).
- **A per-node write stamp**, so the repair could climb "while the node was written this write".
  Four more bytes per node and a store per write, to replace two identity comparisons per level.
  Rejected on cost for a problem the marker below solves for nothing.
- **Landed: link with no height at all, rotate locally, repair once at the end.** Below.

## Decision

**Maintain the cached height exactly once per write, at the end of the write, and leave every
non-write path exactly as F-1 left it.**

1. **`TreeNode1.linkLeft` / `linkRight`** (`TreeNode1:567,576`) — the BST-descent link. Carries
   size, augment and black-height to the root exactly like `setLeft`/`setRight`
   (`recomputeAugmentAndPropagateWithoutHeight`, `TreeNode1:700`) and touches height **nowhere**,
   here or above. `setLeft`/`setRight` are unchanged and remain the safe default, in the same
   relation as `setLeft` vs `setLeftLocal`.
2. **`TreeNode1.repairHeightUpward(TreeNode1)`** (`TreeNode1:415`) — the single per-write repair:
   recompute this node's height, then climb its strict ancestors, stopping at the first one above
   the write's last rotation whose height comes out unchanged.
3. **`RedBlackStrategy` and `WeightBalancedStrategy` rotate through the `*Local` primitives** and
   call the repair once per write —`RedBlackStrategy:145` (insert), `:225,226` (delete);
   `WeightBalancedStrategy:106` (insert), `:146,147` (delete).
4. **`AVLStrategy`, `HybridStrategy` and `SplayStrategy` need no repair call at all.** Their own
   passes already recompute every node from the modification point to the root — they must, because
   they steer by those heights (AVL, Hybrid) or rotate all the way to the root (Splay). They only
   move to the `link*` pair, which *removes* the duplicate walk the propagating setters were making
   underneath them.
5. **`TreeStrategy.rotateLeft`/`rotateRight` keep their ADR-023 climb** and stay the
   self-contained, height-carrying seam `MutableTree.rotateLeft` promises, for rotations fired
   from outside a write. No strategy in this repository calls them any more; a third-party one
   that does still gets exactness by default and pays for it, which is the right way round.

**One-line justification: the engine was maintaining height twice per write in opposite
directions, and doing it once removes ADR-023's only regression — Red-Black monotone insert goes
from +21.7% over the pre-ADR-023 engine to +1.1%, inside the noise floor — while `getHeight()`
stays exact on every path, including the reconstruction paths, which this change does not touch.**

### Why one climb needs a mark: the three ways it goes wrong

A pure fixed-point climb from the anchor is correct only for a change that **originates at the
anchor**. A write has up to three origins, and each of the two extra ones was observed red while
this was being built:

1. **The link.** Origin at the newly linked node (insert) or at the parent of the spliced-out
   position (delete). A fixed-point climb sees it at every level until it dies out — this one is
   free.
2. **A rotation.** It changes the height of the subtree it rearranges, and that change is
   invisible from anywhere below it, so a climb that has already reached its fixed point lower
   down stops short. Measured: a weight-balanced ascending build reports root height 7 where the
   real height is 6, first at **n = 38**. Fixed by passing the ancestor that *adopted* the write's
   highest rotated subtree (`TreeStrategy.rotationAdopter`, `TreeStrategy:129`) as
   `unconditionalThrough`: the climb is unconditional up to and including that node — the last
   node the write wrote a height into — and exact by the fixed-point rule from its parent up. The
   rebalance passes here all walk upward, so the last rotation is the highest one.
3. **A successor splice.** A delete with two children moves the in-order successor into the removed
   node's place, which changes the height at *that* position with nothing between it and the anchor
   writing a height at all. Measured: Red-Black mixed add/remove, `Random(0)`, wrong at **op 122**.
   Fixed by an explicit second repair from the spliced node (`RedBlackStrategy:226`,
   `WeightBalancedStrategy:147`) — almost always a single level, since the first repair has
   usually already passed through it.

Everything else is covered by the shape of the code rather than by a special case: every rotation
in this repository is fired either at an ancestor of the write's anchor or at a child of one, and
both shapes recompute their touched triple bottom-up from children that are themselves anchor-free
and therefore exact.

## Consequences

### The work actually done, deterministically

Extra height recomputes per operation, n = 100k, seed 7, counted with an instrumented
`TreeNode1` in each arm. `link` is the height leg of the link walk, `climb` is ADR-023's
per-rotation climb, `repair` is this ADR's per-write climb, `refresh` is AVL's and Hybrid's own
`refreshHeight()` pass (unchanged by this ADR, and shown so the totals are honest).

| strategy / shape | ADR-023 (cur) link + climb + refresh = **total** | ADR-028 (new) repair + refresh = **total** |
|---|---|---|
| RedBlack / sorted | 27.72 + 22.73 + 0 = **50.45** | 6.00 + 0 = **6.00** |
| RedBlack / random | 13.62 + 1.24 + 0 = **14.86** | 3.57 + 0 = **3.57** |
| RedBlack / mixed | 15.41 + 0.80 + 0 = **16.21** | 3.63 + 0 = **3.63** |
| WeightBalanced / sorted | 21.34 + 17.34 + 0 = **38.68** | 10.63 + 0 = **10.63** |
| WeightBalanced / random | 13.68 + 1.05 + 0 = **14.73** | 3.66 + 0 = **3.66** |
| WeightBalanced / mixed | 15.52 + 0.78 + 0 = **16.30** | 3.74 + 0 = **3.74** |
| AVL / sorted | 15.69 + 0 + 15.69 = **31.38** | 0 + 15.69 = **15.69** |
| AVL / random | 13.57 + 0 + 13.57 = **27.14** | 0 + 13.57 = **13.57** |
| AVL / mixed | 15.24 + 0 + 12.82 = **28.06** | 0 + 12.82 = **12.82** |
| Hybrid / sorted | 15.69 + 0 + 15.69 = **31.38** | 0 + 15.69 = **15.69** |
| Hybrid / random | 13.57 + 0 + 13.57 = **27.14** | 0 + 13.57 = **13.57** |
| Hybrid / mixed | 15.24 + 0 + 12.82 = **28.06** | 0 + 12.82 = **12.82** |
| Splay / random | 18.40 + 0 + 0 = **18.40** | 0 + 0 = **0.00** |
| Splay / mixed | 12.79 + 0 + 0 = **12.79** | 0 + 0 = **1.03** § |

§ Splay's delete severs the removed node's children and re-attaches a subtree, both through
the propagating `setLeft`/`setRight` and both at the tree root, where the walk is one level long;
that is the 1.03, and it is left alone because it costs a level and removes a special case.

The `cur` column reproduces ADR-023's own instrument to the second decimal (27.7 / 22.7 sorted,
1.24 random, 0.80 mixed on RedBlack; 17.3 sorted on WeightBalanced), which is the evidence that
this rig is measuring the same thing ADR-023 measured. Red-Black monotone insert goes from 50.45
height recomputes per write to 6.00 — **8.4×** — and no cell gets more work than before.

### Wall clock

Median of five JVM runs × 51 paired rounds = **255 paired rounds per cell**; parenthesised count
is rounds in which the numerator arm was slower. Positive = slower.

| strategy / shape | **new vs cur** | **new vs pre023** | cur vs pre023 (ADR-023's cost, re-measured) | same-code control |
|---|---|---|---|---|
| RedBlack / sorted | **−17.5% (4/255)** | **+1.1% (157/255)** | **+21.7% (253/255)** | +0.2% |
| WeightBalanced / sorted | −5.5% (28/255) | +9.5% (158/255) † | +14.8% (199/255) † | −0.6% |
| AVL / sorted | −1.6% (82/255) | −0.5% (135/255) | +0.5% (169/255) ‡ | −0.7% |
| Hybrid / sorted | +0.0% (125/255) | −1.0% (106/255) | −0.7% (126/255) ‡ | +0.8% |
| RedBlack / random | −3.3% (91/255) | −0.7% (103/255) | +2.5% (152/255) | −1.3% |
| WeightBalanced / random | −3.3% (95/255) | −0.4% (115/255) | +3.0% (158/255) | +1.4% |
| AVL / random | +0.5% (122/255) | −3.4% (90/255) | −2.8% (87/255) ‡ | +1.8% |
| Splay / random | −1.0% (106/255) | −1.6% (96/255) | +0.9% (118/255) ‡ | +0.1% |
| Hybrid / random | −2.9% (75/255) | −2.5% (82/255) | −0.5% (124/255) ‡ | +1.7% |
| RedBlack / mixed | −3.9% (59/255) | −3.0% (71/255) | +1.1% (142/255) | +0.6% |
| WeightBalanced / mixed | −2.5% (81/255) | −0.5% (116/255) | +2.1% (162/255) | +1.2% |
| AVL / mixed | −1.7% (106/255) | −2.6% (65/255) | −3.2% (71/255) ‡ | +1.2% |
| Splay / mixed | −1.7% (94/255) | −2.3% (69/255) | −1.7% (92/255) ‡ | +0.9% |
| Hybrid / mixed | −2.8% (74/255) | −1.6% (72/255) | +0.4% (131/255) ‡ | +2.8% |

† WeightBalanced/sorted is the cell whose `pre023` arm is bimodal across JVMs (38.8–50.5 ms) and
whose two identical arms disagree by up to 5% inside one JVM; neither of its `pre023` columns is
resolvable below about ±10%. Its `new` arm is the *stable* one (44.0–46.8 ms across all five
runs), and `new vs cur` — where both arms are stable — is a clean −5.5%.
‡ Byte-identical code in both arms: these six cells are the second same-code control, spanning
−3.2% to +0.9%.

**The claim ADR-023 asked to be tested — "would plausibly leave Red-Black monotone insert *faster*
than before ADR-023" — is not confirmed. It comes out at parity: +1.1%, with the numerator arm
slower in 157 of 255 rounds, against a ±3% floor.** The reason is visible in the deterministic
table: the link walk's height leg is 27.7 recomputes *fused* into a walk that was already visiting
those nodes for size and augment, and it is nearly free; the 22.7-level rotation climb is a second
pointer-chase over the same nodes, and that is where the whole +21.7% lived. Removing the free one
and adding a 6-level chase in its place cancels out. Landing it is still right — the regression it
removes is real and the work it removes is 8.4× — but "faster than before ADR-023" would have been
an overclaim and is recorded here as one.

### Everything else

- **`TreeNode1.getHeight()` is still exact for every node on every strategy**, and its javadoc now
  describes the once-per-write model rather than ADR-023's twice-per-write one. No accessor
  promises more than the code delivers: the arms' own post-build sweep (every node, cached vs.
  recomputed) reports **0 stale nodes for `new`, and for `cur`, in all 14 cells**; `pre023`
  leaves stale heights in 5 of the 14 (21 nodes on RedBlack/sorted, 229 mixed, 1021 random; 859 and
  214 on WeightBalanced random and mixed), which is the ADR-023 defect still standing in that arm
  and an independent check that the three arms really are the three engines they claim to be.
- **F-1 is untouched, by construction.** `setLeft`/`setRight` and
  `recomputeAugmentAndPropagate` are unchanged; the reconstruction paths were not edited and did
  not need to be. `ReconstructionHeightProbeTest` passes unmodified.
- **No API break.** Three additive public methods on `TreeNode1` (`linkLeft`, `linkRight`,
  `repairHeightUpward`) and one additive default on `TreeStrategy` (`rotationAdopter`). 0.2.1 stays
  a patch release.
- **ADR-018's frontier is untouched.** Re-run: 2.3236 → 1.3161 → 1.0638 → 1.0007 → **0.9902**,
  monotone, 5 morphs per run at every block length, the 256k crossing intact — identical to the
  numbers ADR-023 recorded, to four decimals.
- **`MutableTree.rotateLeft`/`rotateRight` are now used by nobody in-repo**, which is how a seam
  rots. `OneClimbPerWriteHeightTest.outOfBandRotationStillCarriesHeight` fires a chain of
  rotations through that seam with no write around them and asserts exactness after each, so the
  ADR-023 climb has a live consumer that is a test rather than a strategy.
- **The cost model stays re-runnable.** `RotationHeightPropagationBenchmark`'s javadoc now carries
  both the ADR-023 and the ADR-028 per-shape level counts, and says plainly what a single-version
  JMH run cannot do (compare two library versions) and what the interleaved class-loader harness
  is for.

*Tests:* `OneClimbPerWriteHeightTest` (4). The sweep covers 5 strategies × 8 shapes (ascending,
descending, random, sawtooth, duplicate-heavy, zipf-ish, mixed, delete-heavy) × 3 seeds, checking
**every node after every operation**; a 6000-operation run per strategy checked every 50 ops for
depth; a reconstruct-then-keep-writing case (snapshot round-trip and clone army, then 400 more
writes) on the two strategies that maintain no height of their own; and the out-of-band rotation
seam. Each decision was verified red by reverting it in isolation: drop the
`unconditionalThrough` arming so the climb is a pure fixed point (3 red); drop the spliced-successor
repair (2 red); make `setLeft`/`setRight` stop carrying height, i.e. simulate the F-1 regression
(3 red here **and** all 3 of `ReconstructionHeightProbeTest`).

## Held

- **AVL and Hybrid still refresh every height from the modification point to the root,
  unconditionally** — 15.69 recomputes per sorted-insert operation, now the largest per-write
  height cost in the engine (Red-Black's is 6.00). It is not touched here because that walk is not
  bookkeeping: it is how those strategies *decide*, reading each balance factor from the heights it
  has just refreshed, and it walks to the root because the rebalance condition has to be re-checked
  at every level. Making it stop early is a change to a balancing algorithm, not to a cache, and it
  wants its own measurement — AVL/sorted is inside the noise against both baselines today, so
  nothing is currently paying for it. **Trigger:** anyone measuring AVL or Hybrid write throughput
  as a bottleneck, or a proof that the rebalance condition itself reaches a fixed point.
- **The three origins are enumerated by inspection, not enforced.** A future strategy that writes a
  height somewhere new — a splice, a bulk splice, a rotation fired downward rather than upward —
  would need its own mark or its own repair, and nothing in the type system asks it to. What
  guards it is `OneClimbPerWriteHeightTest`'s per-operation sweep, which fails loudly and
  immediately (both of the origins found during this change were caught in the first run against
  it), plus the rule written at the top of `TreeStrategy`: link with `setLeft`/`setRight` and
  rotate with `rotateLeft`/`rotateRight` unless you can prove your write repairs height itself.
  **Trigger:** a sixth strategy, or any new structural operation on the write path.
- **`repairHeightUpward` takes the mark as a parameter rather than deriving it.** The engine could
  track "the highest node written this write" itself — on the tree, or with a per-node write stamp —
  and the strategies would not have to thread anything. Both were considered and cost more than
  they save (a stamp is 4 bytes per node and a store per write; tree-side tracking puts write state
  on a structure whose interface is public and implemented outside this repository). **Trigger:** a
  third caller needing the mark, at which point threading it by hand stops being the simpler thing.
- **WeightBalanced/sorted is not resolved below ±10% on this hardware.** The `pre023` arm is
  bimodal across JVMs and two identical arms disagree by up to 5% within one, so `new vs pre023`
  for that cell (+9.5%) is reported as unresolved rather than as a regression; `new vs cur` (−5.5%,
  28/255) is the part of it that is measurable here. **Trigger:** a quieter machine, or a
  WeightBalanced sorted-insert workload that someone actually runs.
- **Exact ancestor black-height** remains out of scope, unchanged from ADR-023's second Held
  bullet: it needs a propagation walk per `setColor`, i.e. O(log n) climbs per Red-Black write, for
  a quantity with no consumer. This ADR makes it no easier and no harder. **Trigger:** unchanged —
  a caller that genuinely needs `getBlackHeight()` to be exact rather than `blackHeight()`.
