# CSRBT — change log, 2026-05-31

Implements the first half of ADR-002 action item #2: **resolve the
`augmentedValue` overloading** so dynamic order statistics and interval
augmentation are no longer mutually exclusive. All changes are covered by the
JUnit suite (`ant clean test`).

## The problem
`TreeNode1` had a single `int augmentedValue` that meant two different things
depending on the installed augmentor: the **default** augmentor wrote it as
**subtree size** (read by `OrderStatisticsOps`), while `IntervalAugmentor` wrote
it as **max-hi** (read by interval search). Because the two shared one slot, a
tree could do order statistics *or* interval queries but never both — installing
`IntervalAugmentor` silently turned `OS-SELECT`/`OS-RANK` into nonsense (they
read the max-hi as if it were a node count).

## The fix — subtree size is now an intrinsic node attribute
- **`TreeNode1.size`** is a first-class field maintained on every structural link
  (`recomputeSize`, called from `recomputeAugment` on the same bottom-up traversal
  used for augment upkeep), exactly like the existing intrinsic `height` and
  `blackHeight`. NIL has size 0; maintenance stays O(1)/link, so insert / delete /
  rotation remain O(log n). New accessor `TreeNode1.getSize()`.
- **`OrderStatisticsOps`** now reads `node.getSize()` instead of
  `node.getAugmentedValue()`, so SELECT / RANK / median / countInRange / range
  queries are correct regardless of which augmentor is installed.
- The pluggable augment slot (`augmentedValue`) is now used **only** by the active
  augmentor (interval max-hi, or a custom one). The default augmentor still mirrors
  size into it, so existing callers that read `getAugmentedValue()` as a size under
  the default augmentor are unaffected.

Net effect: **order statistics and interval augmentation coexist on one tree.**

## Why this shape (vs. a generic `Augmentor<A>` payload now)
ADR-002's risk-first mandate is "every step ships green, the ~295 int tests are
the regression harness." Promoting size to an intrinsic field — the sibling of
`height`/`blackHeight` — removes the overloading with zero changes to the public
augmentor API and zero test churn, and it does not depend on the deferred
generic-`<K>` work (C-step 1/2). A fully generic typed payload (`Augmentor<A>` with
a typed per-node slot) is the natural follow-on once `TreeNode1` becomes generic;
it is no longer *blocked* by the overloading, which was the point of this step.

## New test suite
`AugmentorCoexistenceTest` — proves SELECT/RANK/median/countInRange are exact on a
live interval tree (and that interval search still returns the right overlap at the
same time), that intrinsic size tracks deletes under the interval augmentor, and
that size mirrors `augmentedValue` under the default augmentor. Every order-stat
assertion in it would fail pre-fix.

## Compatibility
No public API removed. `getAugmentedValue()` / `setAugmentedValue()` / the
`Augmentor` interface are unchanged; `getSize()` is additive. `RegressionFixesTest`
(order statistics under the default augmentor) and the interval suites
(`TagPreservationTest`, `CloneAugmentorTest`, `AuditFixesTest`) pass unchanged.

## Still open
- ADR-002 #2 (second half): generify strategies + order statistics against `<K>`.
- ADR-002 #1/#6: the phased generic-key refactor (C5), still its own session.
