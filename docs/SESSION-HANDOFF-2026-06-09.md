# Session handoff — 2026-06-10 (was 2026-06-09; kept as the single live handoff)

For the next agent session. Read this before touching code.

## Where things stand

- Suite: **487 tests, green** at commit `a2e3669` (ADR-011 V1).
- **ADR-001 through ADR-010 all Accepted.** Held threads keep their documented triggers
  inside their ADRs (ADR-006 V2 / ADR-007 W2 burst escalation; ADR-008 D2/D3 disk pages;
  ADR-009 G1 Gradle/JMH / G2 jqwik).
- **The active frontier is ADR-011 (the evolution machine), staged V1–V5.**
  - **V1 done** (`a2e3669`): `WeightBalancedStrategy(Δ, Γ)` on the mutable seam +
    strategy-supplied invariant hook in the health gate. First empirical finding: (5,3)
    is in-bounds but *unsound* — self-disqualified via its own invariant, pinned as a
    regression. See `CHANGELOG-2026-06-10-adr011-v1-weight-balanced.md`.
  - **V2 done (2026-06-10, suite 504 green):** `core.evolution.PolicyGenome`
    (bounds-checked vector, seeded-Random pure perturbation/blend, value identity =
    V3 arm identity) + `core.evolution.Fitness` (explainable Evaluation record:
    writeFraction×rotationsPerWrite + readFraction×meanDepth/log₂(n+1)).
    See `CHANGELOG-2026-06-10-adr011-v2-genome-fitness.md`.
  - **V3 done (2026-06-10, suite 515 green):** `PolicyBandit` (pure UCB1, no RNG) +
    `PolicySearchController` (trial windows on a shadow, promotion via MorphPolicy with
    −cost desirability, throne/lab swap) + `TreeEvent.Trial` in the recorder. Also landed
    the predicted parameterized-identity seam: `TreeStrategy.samePolicyAs` — the old
    class-based no-op guard silently refused WB(3,2)→WB(4,2).
    See `CHANGELOG-2026-06-10-adr011-v3-policy-bandit.md`.
  - **V4 done (2026-06-10, suite 521 green):** `PolicyEvolutionController` — (μ+λ) on
    nursery slots, elitism, graveyard breeding, out-of-box behind a flag
    (`weightBalancedUnboxed`), `TreeEvent.Lineage` + CULLED deaths in the recorder.
    See `CHANGELOG-2026-06-10-adr011-v4-evolution.md`.
  - **V5 done — ADR-011 Accepted, verdict negative (2026-06-10, suite 523 green):**
    `EvolutionAcceptanceExperimentTest` — 5 families × 3 seeds, deterministic
    comparisons/op (wall-clock proved >10% noisy; documented). No family sustains ≥10%
    over its best fixed strategy; the search converged to WB(3,·). The honest no, on the
    record. See `CHANGELOG-2026-06-10-adr011-v5-experiment.md`.

## Roadmap (written 2026-06-10 at session end)

**The direction has a name now: ADR-012, the ecology turn** (Proposed; full reasoning in
`docs/ADR-012-ecology-turn-2026-06-10.md`). The reframe: ADR-011's optimization thesis is
closed (V5 said no — fixed four cover *steady state*), but V5 only tested the stationary
axis. The open, falsifiable, and far more interesting axis is **adaptation under a
*changing* environment** — where diversity stops being decoration and becomes a measurable
performance property. The machine becomes a microscope for general principles of adaptive
informational systems under a hard viability filter (honest scope: artificial-life /
complex-systems principles, *not* biological claims — the mapping is too lossy and the ADR
says so). We are well-placed because we already have the two things such projects lack: the
safety boundary (health gate) and full observability (recorder/arena).

Priority order; each is one session-sized arc. **Instruments before mechanisms** (the E1–E2
viability map + diversity metrics are pure observation; E3 is the experiment that matters).

1. **Ship visibility** — **mostly done (2026-06-10, second session).** Landed:
   `experimental.SearchArenaSession` → `docs/arena-search-session.json` (38 events, nothing
   staged: WB(5,3) founder dies by its own invariant at gen 1 — V1's finding replayed
   live — a WB(2,1) mutant dies at gen 3, WB(3,2) the literature point is SELECTED through
   the morph gates off a splay primary; seed swept until the *real* controller exhibited
   the story, which is selection of a run, not staging of events). Visualizer now renders
   Trial/Lineage first-class (chips: ⊕ born / = scored / ✂ culled / ☠ disqualified /
   ★ selected; narration per phase) — smoke-tested all 39 frames render without
   undefined/NaN. Suite 523 green after. **Done same session: the public story** — README
   section "The evolution machine: the story, told honestly" (V1's blood-drawing first
   run → the samePolicyAs seam bug → the metric that caught itself being weather → the
   honest no → the replayable search session → the ADR-012 pointer), plus README intro
   now points at `arena-search-session.json` and the Design history list gained
   ADR-010/011/012. Link-checked. **Item 1 is closed.**
2. **ADR-012 E1 — the viability map. Done (2026-06-10, suite 525 green).**
   `experimental.ViabilityMap` + `docs/viability-map.json` + visualizer heatmap +
   `ViabilityMapTest`. **Finding: the viable region is a sliver — (3,2) and (4,2), 2 of
   46 cells**; Γ=1 dies everywhere, Γ≥3 dies everywhere in-box (mostly by op 300), all
   unboxed samples dead. Retroactively explains V5's convergence: there was almost
   nowhere else viable to go. See `CHANGELOG-2026-06-10-adr012-e1-viability-map.md`.
3. **ADR-012 E2 — diversity as a first-class output. Done (2026-06-10, suite 526 green).**
   `TreeEvent.Diversity` per generation (survivors, founder lineages, pairwise spread,
   disqualified/culled) through controller → recorder → visualizer. **Finding: K_collapse
   = 1 — the viability filter, not (μ+λ), collapses diversity** (3 of 4 corner founders
   die gen 1, every seed); the ±1 mutation walk to the sliver takes 6–7 generations; all
   seeds end at (3,2)+neighbor. Also demonstrated: viability is diet-relative ((6,1)
   dies under E1's churn, survives E2's milder mix). E4's job is now precise: preserve
   what the gate kills. See `CHANGELOG-2026-06-10-adr012-e2-diversity.md`.
4. **ADR-012 E3 — the non-stationary harness. Done (2026-06-10, suite 527 green).
   Verdict: no, decisively.** `NonStationaryExperimentTest`: 8 regime blocks × 2 cycles,
   seven contestants, byte-identical streams, exploration priced at the ensemble
   comparator. ELITE 2.7×, POP ~5× the best fixed (AVL 16.2 cmp/op), all seeds.
   **Mechanism: O(n) candidate rebuilds per generation dominate — exploration scales
   with n, serving with log n.** Re-adaptation lag ≈ 0 for balanced fixed trees (no
   policy to re-adapt); only SPLAY shows transients. Documented gaps: cadence is a free
   parameter; rotations unpriced. **Follow-up done same day: the ADR-002 selector raced
   as the eighth contestant** — 24.5–25.0 cmp/op, ~1.5× best fixed (per-morph rebuilds
   beat per-generation rebuilds; the cost model holds near RB under default gates), so
   on this schedule no adaptive scheme of any architecture wins. Caveat recorded: the
   schedule (fixed before any contestant ran) turned out AVL-dominated, which is the
   condition under which the verdict generalizes. E4's bar is now measured: cut lag
   without adding rebuilds — a mechanism that breeds more is going the wrong way. See
   `CHANGELOG-2026-06-10-adr012-e3-nonstationary.md`. (E4/E5/E6 still staged in the ADR.)

Held items still on their own triggers only (ADR-008 D2 disk pages; ADR-006/007 burst
escalation; ADR-009 G1 Gradle/JMH — note G1 also cures V5's wall-clock weather). The
composite cost metric (comparisons + w·rotations) and its rotation counters get a real
consumer at E3/E5. Splay-p / hybrid-mix is E5, *not* a standalone — on the steady-state
axis it just repeats V5.

A fresh-eyes audit of the five V-slices (they landed in one day) is always a legitimate
alternative to starting E1.

**2026-06-10, second session, end state:** E1–E3 + selector addendum + **E3b** done (all
negative, all instrumented — see the changelogs), consolidation audit done
(`CHANGELOG-2026-06-10-ecology-audit.md`; one fix: RedBlackTree absent-remove WARN →
debug), README story updated, suite **528 green**.

**E3b (`DiscriminatingScheduleExperimentTest`) is the sharpest result:** pre-registered
uniform↔sequential schedule from V5's own winners table (oracle gap ~13.5%, premise
hard-asserted: AVL×4/SPLAY×2 block winners). Verdict still no — **the ADR-002 selector
never morphed once through a 36% opportunity** (its rows are byte-identical to RB's).
The premise survives; the *perception* fails: `CostModelStrategyScorer`'s predictions
don't track realized comparison costs well enough to clear the 20% margin 3 wins
running.

**The calibration slice is DONE (same session, suite 528 green):** scorer constants
refit to the realized comparisons tables (shape kept; V5 rule applied to the scorer's
own worldview — see `CHANGELOG-2026-06-10-scorer-calibration.md`). Re-pinned:
`StrategyScorerTest` write-heavy/balanced → AVL; `ControllerConvergenceTest` G4 → "one
morph to AVL, then holds". Result: **SELECT went from never-morphing (−52/−56%) to
tying hindsight-best AVL** — 16.20–16.45 vs 16.12–16.26 on E3, 17.81–17.96 vs
17.21–17.34 on E3b. Both verdicts remain success=false (tying ≠ the registered ≥10%
win). The residual oracle gap (~13%, the sequential blocks where Splay pays 33%) is a
*perception* item, named and held: recency-aware locality feature or margin/cadence
schedule — only if the oracle gap ever needs claiming. Everything else (E4 — no lag to
cut; E5/E6 — ADR triggers) stays staged.

**2026-06-11, end state:** README story extended through E3b + calibration; ADR-012 E3
action item ticked with the calibration pointer; **fresh-eyes audit of the calibration
slice done** (`CHANGELOG-2026-06-11-calibration-audit.md`) — slice survives: constants
faithful, dominance algebra checked (RB now strictly dominated in the model, intended),
E3b protocol sound, suite **independently rebuilt and re-run: 528 green** (javac 17.0.19
+ JUnit console, clean shadow tree). Three stale-doc nits fixed (StrategyScorerTest
class javadoc, regime-change @DisplayName, the mixed-convention "16–40%" range →
per-diet figures). One named sensitivity, recorded not fixed: G4's pure-write RB→AVL
gap is 12.3% — 2.3 points over the eager harness margin; under production 20% a
pure-write diet would not morph (mixed diets ~27% do).

**Same session, E3c done (`SwitchingCostExperimentTest`, suite 529 green):** the held
recency-feature item is **retired by measurement**. Two clairvoyant switchers (real
morph rebuilds; MIRROR-ensemble O(1) promote) were handed the per-block winners table
and lost ~50% to fixed AVL on all three seeds — `claimable=false 0/3`. The cheapest
real switching quantum (~8.6 cmp/op standing fan-out) exceeds the free-oracle prize
(~2.4 cmp/op) >3×; E3b's "oracle gap" was a free-switching fiction at 6k-op blocks.
Consequence, recorded in README/ADR-012/calibration changelog: the calibrated
selector's hold on AVL through sequential blocks is *correct economics*, and the
adaptive claim's honest ceiling on discriminating schedules is "match best fixed
without hindsight" — which the selector already delivers. The axis that would change
the answer is named, not built: longer blocks, or a switching mechanism cheaper than
both quanta. Neither has a trigger.

**Same session, ADR-012 dispositioned (docs-only, suite 529 unchanged):** status →
**Accepted**, new §8 in the ADR-009/010 reconciliation tradition
(`CHANGELOG-2026-06-11-adr012-disposition.md`). E4 parked (premise measured away
twice: no lag to cut, switching quantum > prize), E5 parked by its own E4 gate, E6
untouched (machinery transfer, orthogonal, optional). Three re-arming triggers named
in §8. README design-history updated.

**Same session, E6 done (suite 533 green; `experimental.cache` + 
`CacheTransferExperimentTest`):** the last staged slice. Verdict split and published
(`CHANGELOG-2026-06-11-adr012-e6-transfer.md`): **patternTransferred=true,
loopReusedVerbatim=false** — MorphPolicy/TreeEvent/TreeEventListener crossed to the
cache space unchanged; the loop class is genome-typed and was re-typed (~345 lines,
`CacheEvolutionLoop`). Gate killed the in-box lethal genome (protectedTenths=10, no
probation) with zero unsafe promotions; determinism pinned. Performance motif again:
evolution found pure LRU beats textbook SLRU under drift, converged, tied best fixed
Δ+0.000. ADR-012 item 6 ticked; README story closed. Generic-loop extraction = held,
trigger: a third policy space.

**Same session, post-push: CI red, weather-proofed
(`CHANGELOG-2026-06-11-ci-weatherproof.md`):** the pushed head failed CI on both JDKs;
the identical tree is green locally under the exact CI invocation (real ant, three
verification routes). Diagnosis by elimination (CI logs are admin-only): the ADR-007
benchmark's hard `optimistic < locked` — the suite's only strict comparison of two
wall-clock measurements under contention, a pre-V5-rule holdout. Re-asserted as
best-of-3 (one win proves the property; a real regression loses all three). If CI
reds again: pull the `test-reports-*` artifact from the run page for the failing test
name before touching anything.

**If the user says "next" after this:** ADR-012 is now fully resolved (E1–E3c done,
E4/E5 parked with triggers, E6 done). The open surface is exactly: **held
infrastructure** (ADR-009 G1 Gradle/JMH, ADR-008 D2 disk pages — triggers unfired),
or **ship/rest** (the arc is complete and publishable). Nothing else is queued; do
not invent work. The story, one line: the machine found its own miscalibration, fixed
exactly that, proved its remaining "failure" was correct economics, closed its own
research program honestly — and then showed the whole discipline transfers to a
second domain, where the textbook answer won again.

The honest claim, measured: *the calibrated
selector matches the best fixed choice without hindsight; it does not yet beat it.*

## If the user says "next" (post-ADR-011)

ADR-011 was the roadmap's last open frontier. There is no unblocked code work queued —
do not invent some. Honest options: ship visibility (the evolution-machine story is
genuinely publishable: a search that found unsoundness, confirmed the literature, and
published its own negative result); start a held item **only if its trigger fired**
(rotation counters now have a named consumer — the V5 composite-cost refinement — if the
verdict ever needs revisiting; ADR-008 D2 disk pages; ADR-009 G1 Gradle/JMH); or an
audit pass with fresh eyes over the five V-slices, which landed in one day.
- The README polish (V1 + ADR-011 frontier paragraph) rides in the V2 commit.

## If the user says "next" / "continue"

Continue ADR-011 in stage order: V2 (genome+fitness) → V3 (`PolicyBandit` over ensemble
shadows + `TreeEvent.Trial` + arena replay) → V4 ((μ+λ) population search) → V5 (the
acceptance experiment; verdict published either way). Each V is one additive slice:
changelog per slice, tick the ADR action item, green through `ant clean test`.

## Sandbox mechanics (cost an hour once — don't rediscover)

- **JDK/ant:** sandbox has JRE 11 only, no root. Download user-space:
  `curl -sfLo jdk17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"`,
  ant 1.10.14 from `archive.apache.org`; untar in `~`; export `JAVA_HOME`/`PATH` per call
  (no env carryover between bash calls).
- **Shadow tree:** the repo mount **cannot delete files** (`ant clean` fails in-place).
  Build out-of-tree: copy `src build.xml *.jar snapshots` to `~/csrbt`, run ant there.
  The shadow tree is ephemeral — rebuild it each session.
- **No-ant shortcut (worked 2026-06-10):** skip ant entirely — `javac --release 17 -d
  /tmp/classes @srcs.txt`, then run the suite with the in-repo
  `junit-platform-console-standalone-1.9.2.jar` via `--scan-class-path /tmp/testclasses`
  (put `/tmp/classes:src/main/resources:log4j jars` on `--class-path`). 523 green in ~11 s.
- **Mount staleness (the truncation trap):** *edits* to existing repo files (file tools)
  often appear **truncated** through the bash mount for minutes; *new* files sync fine; the
  Windows side (file tools) is always authoritative. After editing an existing file, do
  **not** `cp` it from the mount into the shadow tree — re-apply the same edit to the
  shadow copy with a python patch (assert exactly one match), or route content through a
  brand-new file. Verify with `wc -l` both sides when in doubt.
- Git is host-side only (the user commits in PowerShell); stray temp files can only be
  deleted host-side.

## House style reminders

- One slice per commit; changelog per slice; tick the ADR action item with a pointer;
  ship green through `ant clean test`.
- No background threads (rejected three times). Caller-cadenced control is load-bearing.
- `TreeContext` stays Integer (documented adapter); generic callers use `OrderedSet<K>`.
- Benchmarks are in-suite printed rows with soft assertions, not JMH (until G1).
- Engines added to ensembles must honor `OrderedSet` semantics exactly (`RankedSet`
  voting-parity contract) and either be immutable, R1-guarded, or synchronized — the
  ADR-007 optimistic vote reads members lock-free.
