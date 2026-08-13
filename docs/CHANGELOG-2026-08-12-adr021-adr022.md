# CHANGELOG 2026-08-12 — ADR-021 + ADR-022: the two held design decisions, fired

The two design-level items flagged by the 2026-08-12 audits, now implemented.
Suite **801 green** (643 core + 158 experimental), 0 failures. JDK 21.

## ADR-021 — atomic navigation (deep-sweep finding D-1)

- **`OrderedSet`** gains native single-acquisition navigation: `floor` / `lower` /
  `ceiling` / `higher` (one BST descent under one `guardedRead`, `findReadOnly`'s
  step-bound and torn-read discipline), `countUpTo(k, inclusive)` (one rank descent
  over intrinsic subtree sizes), and `countBetween(lo, loInc, hi, hiInc)` — both
  bound descents inside ONE optimistic stamp, so no write can slip between them.
- **`NavigableOrderedSet`** rebases on the primitives: navigation delegates 1:1,
  `Range.size()` is a single `countBetween`. The old count→contains→select
  compositions spanned 2–4 lock epochs; a write between them made read-only
  navigation throw or answer wrong (audit probe: 399 exceptions / 1,870 contract
  violations in 3.7M concurrent calls on keys the writer never touched).
- Probe: `NavigationAtomicityProbeTest` — 3 readers × 2.5 s against a churning
  writer: zero exceptions, zero violations; plus boundary-semantics pins. The
  pre-existing `TreeSet`-parity suite passes unchanged (single-threaded semantics
  identical).

## ADR-022 — battle-runner methodology (fourth-pass findings V-C/V-D)

- **`StrategyBattleRunner`** search ops now do a measuring walk (realized depth +
  hit via `OrderedSet.searchDepth`) and then the STRATEGY'S OWN engine-level search —
  so Splay actually splays in the workloads documented to favor it (`contains` never
  splays by R1 design, which had disabled Splay's defining move and guaranteed it
  last place). Every competitor pays the same two-walk cost.
- **`avgSearchDepth` is now the realized per-search mean**, not the root height
  (worst case, ×3 weight) it silently was.
- **Warmup + median-of-3 timing**: one untimed pass per competitor, then three timed
  passes on fresh contexts, median reported — the first competitor no longer pays
  JIT on the clock (3.6× cold-vs-warm measured), and rank order stops varying on
  identical inputs.
- **Tournament results are re-scored under the new methodology** — historical rank
  orders do not carry over (called out in the ADR).
- Probe: `BattleMethodologyProbeTest` — Splay's LOCALITY_BURST realized depth < 100
  (old proxy ≈ 3000), cross-competitor hit/size fairness pinned, realized depths
  sane for every competitor.
