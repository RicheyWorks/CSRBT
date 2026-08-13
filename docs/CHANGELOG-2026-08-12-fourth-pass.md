# CHANGELOG 2026-08-12 — fourth pass: the ensemble fails at its own job; the dead walk

Four parallel adversarial passes over the last un-swept subsystems — the ensemble
fault-tolerance machinery, the genome layer, the policy-evolution machine, and the
remaining core files — probe-first per house discipline (15 new probes, all red
against the unfixed code). Full findings in `docs/AUDIT-2026-08-12-fourth-pass.md`.
Suite **797 green** (639 core + 158 experimental), 0 failures. JDK 21.

## Fixed — ensemble (the fault-tolerance surface)

- **E-A (High) — `EnsembleOrderedSet` vote paths:** a divergent member's exception
  (`rank`/`successor`/`select` on content it silently lost) propagated to the caller
  instead of being outvoted — VERIFIED failed exactly when divergence was loudest. A
  member's throw is now a first-class vote answer: lone throwers are outvoted and
  quarantined; a throwing majority's exception is rethrown as the true answer.
- **E-B (High) — `EnsembleController.checkHealth`:** a structurally-valid but
  content-divergent primary passed self-validation, became the reference, and every
  honest member was quarantined and healed FROM it — permanent silent data loss.
  The primary's contents are now cross-checked against the exact-member majority;
  a dissenting primary is deposed toward a majority-content member.
- **E-C (Med-High) — `EnsembleController.checkHealth`:** quarantined members were
  skipped forever (quarantine was permanent; VERIFIED silently degraded below
  quorum). A third pass now heals and reactivates them, or retires unhealable ones.
- **E-D (Medium) — `EnsembleOrderedSet` write path:** the "write did not commit"
  throw paths ran before the quarantine loop, leaving half-applied members ACTIVE
  and divergent. Failed non-primary recipients are quarantined before the throw.
- **E-E/E-F — hygiene:** `toString()` no longer runs a vote (it read `size()` through
  the VERIFIED read path — a log line could quarantine members); `quarantine()` is
  idempotent.

## Fixed — evolution machine

- **V-A (High) — `PolicyEvolutionController`:** dead genomes were resurrected through
  two holes — the (μ+λ) pool refill re-admitted a dead parent's stale score, and
  duplicate on-trial bodies of one genome value could split the verdict (one body's
  death vs a sibling's score) within a single generation. Traced live (seed 46 gen 7:
  a genome in both `parents` and `graveyard`). Both holes closed; "the dead stay
  dead" now holds by construction, not by seed luck.
- **V-B (Medium) — `MorphPolicy`:** the ∞-cost "no comparable incumbent" sentinel
  produced improvement = ∞/∞ = NaN, silently HOLDing every promotion forever over an
  engine-backed primary. Infinite incumbents now auto-lose the margin gate.

## Fixed — genome controller

- **G-A (High):** `computeEntropy` bucketed by absolute key value over the whole int
  range (bucket width ≈ 5.4e8) — uniform-random and single-hot-key windows both read
  0.0, blinding the documented Splay locality signal. Now bucketed by the window's
  observed range.
- **G-B (High):** the incumbent came from the genome's preference, not the installed
  strategy — a mismatch (reachable via `breedWith`) held "already optimal" forever.
  Now inferred from the context.
- **G-D (Medium):** fragmentation and performance memory read the cached height only
  AVL/Hybrid maintain (RB: cached 9 vs real 15 → fragmentation 0.0, memory biased
  toward RB). Both sites now measure by traversal.
- **G-C (Medium) — `TreeGenome`:** an in-womb trait mutation on a crossover child
  rewrote its provenance (MUTATED origin, phantom parent, generation double-bump).
  The crossover frame is now restored after the mutation.
- **G-F (Low):** the provenance note is capped at 512 chars (was O(ops); 11.7k chars
  after 20k ops).

## Fixed — observability

- **B1/B2 (Medium) — `TreeSessionRecorder`:** Lineage events emitted a duplicate
  `"op"` JSON key (last-wins parsers — including the visualizer — lost every birth's
  op position); the operator is now `"breedOp"`, and all event strings are
  JSON-escaped (one quote in an arm name used to corrupt the session). The shipped
  test that pinned the duplicate key was corrected.
- **B4/B5 (Low):** `WorkloadFeatures.toString` and the morph_eval line are
  locale-safe (comma-decimal JVMs broke the key=value floats); `MorphHistory`'s
  cooldown clock saturates instead of overflowing negative (~2.1B held ops used to
  freeze morphing permanently). `TreeEvent.Trial.pulls` doc corrected (B7).

## Documented, not fixed

Battle-runner methodology (Splay benchmarked with splaying disabled on reads + root
height as the depth metric ×3 → structurally last; no warmup, single-pass wall-clock
→ rank order varies on identical inputs) — a scoring change that would re-order
historical tournaments, flagged for its own decision. Canonical replay sessions embed
wall-clock meters (never byte-reproducible; decision sequences ARE deterministic).
`ArenaSession` comment narrative vs recorded story. Stability-gate eval-before-credit
asymmetry (pinned as intentional; doc drift noted), `remove()` not feeding the access
window, control-plane getter doc drift, `lineageTag` slow growth.

## Verified clean (worth not re-deriving)

Vote majority math and quarantined-voter exclusion; ensemble persistence round-trips;
READ_REPLICA + optimistic votes under 20M-read concurrency stress; seq-vs-parallel
executor determinism; `PolicyBandit` UCB1 (converges to the cheap arm 999/1000, no
re-admission hole); `PolicyGenome` mutation boxes and blend validity; `Fitness`
direction consistency (NaN ranks last); battle-stream fairness (identical replay per
competitor); `RedBlackTree.buildBalanced` re-verified valid at every size to 100k
with independent checkers; window eviction re-verified against the FIFO oracle;
`PersistentRankedSet`, `TreeEngineRegistry`, `TreeExport` escaping, morph plumbing.
