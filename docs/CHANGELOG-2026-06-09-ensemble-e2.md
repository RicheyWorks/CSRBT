# CHANGELOG 2026-06-09 -- ADR-003 E2: measured promotion (the O(1) primary swap)

Advances the multi-tree ensemble (`ADR-003-multi-tree-ensemble-2026-06-06.md`) from E1's static
mirror to E2's **adaptive** mirror. The ensemble already keeps every member an exact copy of the
logical set, so choosing which member serves reads is no longer a rebuild -- it is a single pointer
publish. E2 adds the controller that makes that choice and the swap it commits with.

The control plane is **reused unchanged** from ADR-002 Phase D: the same `WorkloadMonitor ->
StrategyScorer -> MorphPolicy -> MorphHistory` pipeline. Only the executor differs -- where
`MorphController` commits with `OrderedSet.setStrategy` (an O(n) build-aside), `EnsembleController`
commits with `EnsembleOrderedSet.promote` (an **O(1)** atomic swap). That contrast is the whole
reason the ensemble pays the mirror's write fan-out.

## What changed

- **`EnsembleOrderedSet.promote(EnsembleMember)` -- the O(1) atomic primary swap.** Publishes the
  `volatile primary` under the existing write lock (so a swap never interleaves with a fan-out),
  after checking the member belongs to the ensemble and is `ACTIVE`. No rebuild, no traversal, no
  copy. Returns `false` when the member is already primary; throws on a foreign or non-active
  member. Purely additive -- E1's facade and its oracle test are untouched.

- **`core.ensemble.EnsembleController<K>` -- the measured-promotion loop.**
  - *Data-plane facade.* `add` / `remove` / `contains` apply to the ensemble and fold each op into
    the monitor (`recordAdd` / `recordRemove` on **effective mutations only**; `recordSearch` on
    every read), so the read/write mix and hot-key skew the scorer needs are captured without a
    tree scan.
  - *Control loop.* `evaluateAndMaybePromote(opsElapsed)` snapshots the workload, scores the
    strategies, and gates the switch through `MorphPolicy`. The ranking is **filtered to members
    the ensemble actually carries** before the policy sees it, so a scored-but-absent strategy
    (e.g. Hybrid) can never win the gate and the policy still compares against the cheapest
    *available* candidate. On `MORPH` it resolves the winner to its member via an
    `EnumMap<StrategyId, EnsembleMember>` built at construction and calls `promote`. Threads a
    `MorphHistory` (cooldown clock + win streak) exactly as `MorphController` does.
  - *Observability.* One `event=morph_eval ... decision=PROMOTE|HOLD ...` line per evaluation,
    carrying the `WorkloadFeatures`, ranked costs, and **per-member meters** (node height -- computed
    iteratively so a deep splay tree cannot overflow -- size, and `avgInsert/DeleteTimeMs`).
  - Returns `PromotionResult(promoted, from, to, reason)`.

## Behaviour

- **Decision = pure function of the workload.** A skewed, read-dominated stream drives the cost
  model toward Splay; once Splay clears the anti-thrash gates it is promoted in a single swap and,
  being then the incumbent and cheapest, every subsequent eval holds -- so a sustained regime
  promotes **at most once**.
- **Promotion never rebuilds.** `promote` only reassigns the primary pointer; the promoted member's
  engine instance and contents are exactly what they were. (`setStrategy` / `selfRepair` build a
  fresh `RedBlackTree`; `promote` does not -- which the test asserts by engine identity.)
- **Only carried strategies are promotable** -- the controller degrades to a hold rather than
  picking a strategy it cannot serve.

## Tests

- `EnsembleControllerTest` (E2):
  - *skewed reads promote Splay exactly once, no rebuild* -- the headline ADR-003 E2 acceptance: a
    hot-key read stream promotes the Splay member once, the promoted member's engine is the same
    instance (no rebuild), and every member is still an exact mirror of a `TreeSet` oracle.
  - *uniform write-heavy stream holds Red-Black* -- a skew-free write stream yields **0** promotions.
  - *`promote()` unit swap* -- swaps the primary in place, is a no-op on the current primary, and
    preserves order statistics read from the newly-promoted member.

## Follow-ups (out of scope here)

- **E3** -- per-member health / quarantine / heal + failover (the `QUARANTINED` / `RETIRED` states
  `EnsembleMember` already reserves).
- Real per-member **rotations/write** instrumentation (the engine does not yet count rotations; the
  E2 meter line reports height + timings, and rotation churn is carried at the workload level by
  `WorkloadFeatures.rotationsPerWrite`).
- A facade-level monitor hook so traffic that bypasses the controller is still observed (parity with
  the Phase D follow-up).
