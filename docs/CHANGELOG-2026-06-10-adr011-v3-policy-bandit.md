# CHANGELOG 2026-06-10 — ADR-011 V3: the bandit searches, live

The search loop exists. A UCB1 bandit tries parameterized policies as live trials on an
ensemble shadow, scores them with V2's fitness, kills the unsound ones through the safety
architecture, and promotes a proven winner through the same anti-thrash gates every morph
has cleared since ADR-002. Caller-cadenced; no background threads.

## `core.evolution.PolicyBandit` (new)

- UCB1 over `PolicyGenome` arms, mirrored for minimization: select the arm minimizing
  `meanCost − exploration·√(2·ln N / nᵢ)`; untried arms first, in arm order; ties to the
  lower index. **No RNG anywhere** — the bandit is a pure, deterministic scoreboard, and
  every `select()` returns a `Selection` with its named terms (one-line explainable).
- `boxGrid()` is the 28-point discretized box — (5,3) included *on purpose*: unsound
  points are arms precisely so they can self-disqualify on the record.
- Disqualification is permanent death; a fully-dead arm set fails loudly
  (`select()` throws), never silently.

## `core.evolution.PolicySearchController<K>` (new)

- The loop: `beginTrial()` UCB1-selects an arm and morphs the designated **trial shadow**
  to it through the health gate (V1's invariant hook included — gate-rejected arms are
  disqualified on the spot); the caller streams ops (data-plane facade feeding the
  `WorkloadMonitor`, mirroring `EnsembleController`); `endTrial(ops)` re-checks the arm's
  *own invariant on the live tree* — a parameterization that survived build-aside but
  degraded under churn is caught and disqualified — then scores arm and incumbent on the
  same `WorkloadFeatures` (only the structural term differs) and rewards the bandit.
- **Promotion reuses `MorphPolicy` exactly:** the legacy desirability form fed
  `score = −cost` makes its improvement fraction equal the cost reduction
  `(incumbent−arm)/incumbent` — V3's promotion discipline is bit-identical to ADR-002's,
  not a parallel re-implementation. Win streaks are arm-keyed (a `StrategyId`-keyed
  `MorphHistory` cannot name a grid point — the §4 consequence, landed). A promote is the
  ensemble's sync-on-promote + O(1) swap, and the deposed primary becomes the new trial
  slot: the throne and the laboratory trade places (engine-tier deposed primaries are
  handled — the slot falls back to a strategy-backed member or fails loudly).

## The seam V3 discovered: policy identity (`TreeStrategy.samePolicyAs`)

`OrderedSet.setStrategy`'s same-strategy no-op guard compared **classes**, so
`WB(3,2) → WB(4,2)` — a real morph — was silently refused, and the bandit's second arm
was wrongly disqualified on its first selection (caught by the integration test, exactly
as ADR-011 §4 predicted parameterized identities would bite). New default method
`TreeStrategy.samePolicyAs` (class identity, exact for the parameterless classics);
`WeightBalancedStrategy` overrides it to compare (Δ, Γ); the guard now asks the strategy.
Classic-strategy behavior is unchanged by construction.

## `TreeEvent.Trial` + recorder (additive to session format v1)

- New sealed-interface member: `Trial(arm, phase, cost, pulls)` with phases
  TRIED / SCORED / DISQUALIFIED / SELECTED; allocation-free when unobserved, like every
  event here. `TreeSessionRecorder` records Trial decisions (cost `null` where unscored —
  JSON has no NaN), so a recorder attached to the trial member's set and registered on the
  controller replays the search in the arena: arms tried, scored, killed, crowned.

## Tests (`PolicyBanditTest` 7 + `PolicySearchControllerTest` 4; suite **515, green**)

- Bandit: hand-computed UCB1 values exact; untried-first order; pure exploitation at
  exploration 0; exploration provably revisits an under-pulled arm; disqualification
  permanence + loud exhaustion; bestArm; construction validation + the 28-point grid.
- Controller, on a real ensemble (SAMPLED_SHADOW, p=1): trial windows score real fitness
  with contents oracle-exact across trial morphs; **(5,3) self-disqualifies live at
  `endTrial` via its own invariant** — V1's finding running as a mechanism — with no data
  lost even then; **WB(3,2) genuinely beats a splay primary** on uniform read-heavy churn
  and is promoted through real gates (cooldown 1k, 5% margin, 2 wins), after which the
  lab is not the throne; a recorded session carries Trial decisions with readable arm
  identity and parseable JSON.

Next per ADR-011: V4 — (μ+λ) population search over genomes (mutation/blend exist since
V2), out-of-box exploration behind a flag, lineage recording.
