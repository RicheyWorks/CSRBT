# Fourth-pass bug audit — 2026-08-12 (ensemble + evolution machine)

**Scope:** the last un-swept subsystems, in four parallel adversarial passes: the
ensemble machinery (`EnsembleOrderedSet`, `EnsembleController`, executors, ensemble
persistence — the ADR-003/004/006/007 fault-tolerance surface), the genome layer
(`TreeGenome`, `GenomeDrivenTreeController`), the policy-evolution machine
(`PolicyGenome`, `PolicyBandit`, `PolicyEvolutionController`, `PolicySearchController`,
`StrategyBattleRunner`, `Fitness`), and the remaining core files (`RedBlackTree`
directly, `PersistentRankedSet`, `TreeEngineRegistry`, morph plumbing, event/export
records, arena replay mains) — plus adversarial re-verification of two earlier "clean"
claims. Complements `AUDIT-2026-08-12-model-domain.md` and
`AUDIT-2026-08-12-deep-sweep.md`.

**Method:** hand-derivation plus probe programs against the compiled classes
(differential oracles, 6,000-op ensemble parity streams, concurrency stress at 20M+
epoch reads, bandit convergence runs, exhaustive `buildBalanced` validation to
n=100,000). Every fixed defect has a probe test that FAILED against the unfixed code
(15 probes, all red pre-fix). Suite after: **797 green** (639 core + 158
experimental, +15 probes and one corrected pinning assertion), 0 failures. JDK 21.

**Result: twelve defects fixed (probe-verified), one schema doc corrected, six
documented findings.** The two re-verified claims HOLD (`buildBalanced` valid at every
size probed with independent RB checkers; window eviction matches the FIFO oracle).
Verified clean this pass: vote majority math and quarantined-voter exclusion, ensemble
persistence round-trips, READ_REPLICA and ADR-007 optimistic votes under concurrency
stress, sequential-vs-parallel executor determinism, `PolicyBandit` UCB1 (converges
999/1000 to the cheap arm; no re-admission hole), `PolicyGenome`/`CacheGenome`
mutation boxes, `Fitness` direction consistency incl. NaN ranking last,
`StrategyBattleRunner` stream fairness (identical replay per competitor),
`RedBlackTree` core ops, `PersistentRankedSet`, `TreeEngineRegistry`, `TreeExport`
escaping, and morph-history streak semantics (the eval-before-credit gate is pinned
as intentional).

---

## Fixed — the ensemble fails at its own job (probe-verified)

### E-A (High). A VERIFIED vote let a divergent member's exception reach the caller.

A content-divergent member makes order-statistics queries THROW (`rank` of a key it
silently lost, `select` past its smaller size) rather than return a wrong value — and
`vote`/`voteLocked` called `fn.apply` unguarded, so the exception propagated, the 2/3
healthy majority was never consulted, and the dissenter stayed ACTIVE. `contains`
masked; `rank`/`successor`/`select` became an exception storm — the fault-masking
VERIFIED exists for failed exactly when divergence was loudest. *Fix:* a per-member
throw is wrapped as a first-class answer (`Thrown`, equality by exception class): a
lone thrower is outvoted and quarantined like any dissenter; if the majority throws,
the majority's exception is rethrown as the true answer. The optimistic pass escalates
on any throw. Probe: `throwingDissenterIsOutvoted`.

### E-B (High). checkHealth healed the honest majority FROM a content-divergent primary.

The cadence health check validated the primary only against its own `inOrder()` —
content divergence invisible — then used it as the reference and quarantined + healed
every honest member from it: key 42, held by 2 of 3 members, erased from ALL members,
permanently and silently, destroying the very majority evidence VERIFIED needs. *Fix:*
with ≥ 3 exact voters the primary's contents are cross-checked against the
exact-member majority; if a strict majority agrees with each other and not with the
primary, the primary is the dissenter — failover goes to a majority-content member,
and the deposed primary is quarantined and healed. No majority → keep the primary
(vote semantics). Probe: `divergentPrimaryDoesNotEraseTheMajority`.

### E-C (Medium-High). Quarantine was permanent — the health check never healed it.

`checkHealth` skipped every non-ACTIVE member, so E3's documented quarantine → heal →
reactivate never ran from the cadence path: after one dissent a 3-member VERIFIED
ensemble ran on 2 voters forever, where the next divergence is an undetectable 1-1
tie. *Fix:* a third pass heals each QUARANTINED member from the primary and
reactivates it, or retires it if the heal won't validate. Probe:
`quarantinedMembersAreHealedByTheCadenceCheck`.

### E-D (Medium). "Write did not commit" left half-applied members ACTIVE.

Both total-failure throw paths ran before the quarantine loop, so a member that threw
mid-write (possibly half-applied — the exact fault class the loop's own comment names)
stayed ACTIVE and silently divergent in MIRROR mode. *Fix:* failed non-primary
recipients are quarantined before the throw (the primary cannot be quarantined; its
risk is bounded by the next vote/health check). Probe:
`totalWriteFailureQuarantinesRecipients`.

### E-E (Low-Medium) / E-F (Low). Side-effecting toString; non-idempotent quarantine.

`toString()` called `size()` → `read()` → a VERIFIED vote — a log line could
quarantine members and perturb the verify stride. Now reads the primary's size
directly. And a second `quarantine()` returned `true` and re-emitted the event; now
idempotent. Probes: `toStringDoesNotVote`, `quarantineIsIdempotent`.

## Fixed — the evolution machine (probe-verified)

### V-A (High). Dead genomes were resurrected — two holes, one per generation phase.

"DISQUALIFIED = dead permanently" was enforced on every breeding path but not on
selection: (1) the (μ+λ) pool refill re-admitted a dead parent's stale score; (2)
within one endGeneration, duplicate bodies of the same genome value (elite + bred
copies) could split the verdict — one body's invariant death sent the genome to the
graveyard while a sibling body's score carried it into the survivors. Traced live:
seed 46, gen 7 — WB(Δ=3,Γ=1) in both `parents` and `graveyard`. The shipped
"the dead must stay dead" test passed only by seed luck (its μ=1 config never made a
victim a parent first). *Fix:* the refill skips dead genomes; the scoring loop skips
already-dead duplicates and purges `scored`/`bodies` of anything killed this
generation. Probe: `theDeadStayDead` (seeds 40–46 × 8 generations).

### V-B (Medium). The ∞-cost incumbent sentinel NaN-blocked every promotion.

Both evolution controllers use infinite incumbent cost as "no comparable incumbent —
any scored candidate beats it" (engine-backed primary). `MorphPolicy` then computed
improvement = ∞/∞ = NaN, which fails every `>=` gate: the machine ran generations
forever and could never install a winner — silent degradation to pure observation.
*Fix:* an infinite incumbent short-circuits to improvement = +∞ in both `evaluate`
and `shouldMorph` (cooldown/stability gates still apply). Probe:
`infiniteIncumbentAutoLoses`.

## Fixed — the genome controller (probe-verified)

### G-A (High). The entropy metric was blind to every realistic workload.

`computeEntropy` bucketed the access window by ABSOLUTE key value over the whole int
range — bucket width 2^32/8 ≈ 5.4×10⁸ — so uniform-random keys in [0, 1e6) and a
single hot key both landed in bucket 0 and read 0.0: indistinguishable, making the
documented "primary signal for Splay preference" a constant. *Fix:* bucket by the
window's observed min..max span (one distinct key reads 0.0 — genuinely zero
entropy). Probe: `entropyMeasuresLocality` (uniform ≈ 1.0 vs hot 0.0).

### G-B (High). The controller's incumbent was the genome's wish, not the tree's strategy.

`activeStrategyType` initialized from `genome.getPreferredStructure()`; with a
genome/context mismatch (reachable via the class's own `breedWith`) every evaluation
saw best == current → HOLD "already optimal" → the tree was never morphed to the
strategy the controller believed was running. *Fix:* infer from the installed
strategy (the same mapping `fromContext` already uses). Probe:
`incumbentInferredFromContext`.

### G-D (Medium). Fragmentation and performance memory read stale cached heights.

Same bug class as `TreeEcology.rKScore` (E-1, third audit): only AVL/Hybrid maintain
the height cache, so under Red-Black a 500-key sequential tree cached height 9 against
a real 15 — fragmentation read 0.0 (true ≈ 0.40) and RB's `avgDepth` was
under-reported, biasing memory-based strategy choice toward RB. *Fix:* both sites
measure the height by traversal. Probe: `fragmentationUsesMeasuredHeight`.

### G-C (Medium). A crossover child that mutated in the womb lost its provenance.

The in-womb trait mutation replaced the child via `mutatedCopy()`, which re-frames
provenance: origin became MUTATED, parentB null, parentA a phantom UUID (the
discarded intermediate), generation double-bumped — 1000/1000 corrupted at
mutationRate 1.0. *Fix:* traits mutate, then the crossover frame (parents, CROSSED,
generation, lineage) is restored. Probe: `crossoverKeepsProvenance`.

### G-F (Low). Unbounded provenance-note growth — `normalizeNotes` now caps at 512 chars
(tail kept); 20k ops used to accumulate an 11.7k-char note with O(len) copy per
mutation.

## Fixed — observability plumbing (probe-verified)

- **B1 (Medium) — `TreeSessionRecorder`:** Lineage events emitted a duplicate `"op"`
  JSON key (the running counter, then the operator string) — last-wins parsers,
  including the visualizer's `JSON.parse`, silently lost every birth's op position.
  The operator is now `"breedOp"` (the visualizer reads `.op` only as the counter, so
  this repairs its Lineage labels too); the shipped pinning test asserted the buggy
  key and was corrected. Probe: `recorderLineageJsonIsSound`.
- **B2 (Medium) — `TreeSessionRecorder`:** event strings (arm/phase/child/parents/
  strategy names) were never JSON-escaped — one quote in a name corrupted the session
  file. All routed through an escaper now (same table as `TreeExport`).
- **B4 (Low) — `WorkloadFeatures.toString` / `MorphController.emitMorphEval`:**
  default-locale `String.format` broke the key=value observability line on
  comma-decimal JVMs; both now `Locale.ROOT`. Probe: `localeIndependentObservability`.
- **B5 (Low) — `MorphHistory`:** the cooldown clock could overflow int negative after
  ~2.1B held ops, permanently freezing morphing (`opsSinceLastMorph < cooldownOps`
  forever true); now a saturating add. Probe: `cooldownClockSaturates`.
- **B7 (doc) — `TreeEvent.Trial.pulls`:** documented that V4 population trials carry
  the generation (which the visualizer renders), vs the V3 bandit pull count.

---

## Documented, not fixed (design decisions)

- **V-C (Medium). `StrategyBattleRunner` cannot be fair to Splay:** battle searches go
  through `OrderedSet.contains`, which is documented "never splays" (engine-level
  splaying is write-path only), so in the very workloads the runner's header says
  "favor Splay" the competitor can never self-adjust — and the depth metric is root
  height (×3 weight), guaranteeing last place (probe: 176–237 ms / depth 3000 vs
  4–13 ms / depth 12, all seeds). Fixing means driving searches through the strategy's
  own path or scoring realized `searchDepth` — a benchmarking-methodology change that
  would re-order historical tournament results; flagged for its own decision.
- **V-D (Low-Medium). Battle timing has no warmup and one pass:** first competitor
  pays JIT (3.6× cold-vs-warm observed), producing different rank orders on identical
  inputs. Fix (untimed warmup + median-of-k) belongs with V-C.
- **B3 (Low-Medium). "Canonical" replay sessions are never byte-reproducible:** the
  decision sequences ARE deterministic, but every snapshot embeds wall-clock
  `avgInsertMs`/`avgDeleteMs` meters, so regenerating `docs/arena-session.json`
  always produces spurious VCS diffs. Zeroing/rounding meters in recorded sessions is
  a schema choice.
- **B6 (Low). `ArenaSession`'s comments narrate a different story than it records**
  (documented "controller holds RB" regime actually morphs RB→Hybrid at op 20; the
  session ends on Hybrid, never re-converging to RB). Retune or fix the narrative.
- **Stability-gate asymmetry (intentional, drift documented):** the control-plane
  `evaluate` reads the streak BEFORE crediting the current win (pinned by
  `MorphControllerTest`), one evaluation stricter than the legacy path which credits
  first. Also: `remove()` does not feed the access window despite `recordAccess`'s
  doc, and the control-plane getter javadoc says "default OFF" while the field (and a
  pinning test) say ON — doc drift, not behavior bugs.
- **`lineageTag` still grows** one char per mutation/crossover (235 chars at 20k
  ops) — minor next to the capped notes; left as is.
