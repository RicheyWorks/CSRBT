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
2. **ADR-012 E1 — the viability map.** Sweep (Δ, Γ) (+ unboxed behind the flag), record the
   health-gate/invariant rejection spectrum → an artifact the arena renders as a heatmap.
   Pure instrument; thesis: the viable region has structure (V1's (5,3) is the first
   counterexample — map the whole boundary). Mutational robustness, for free.
3. **ADR-012 E2 — diversity as a first-class output.** Population-diversity metrics in the
   recorder; quantify the stationary (μ+λ) collapse rate (V5's convergence, measured not
   just observed).
4. **ADR-012 E3 — the non-stationary harness (the axis V5 skipped).** Regime-shifting
   workload; fixed vs elite-only vs full-population on re-adaptation lag + integrated cost.
   *This is the experiment that justifies the whole turn.* Verdict published either way.
   (E4 diversity-preserving selection, E5 widened genome/speciation, E6 generalize to a
   second policy space all follow — see the ADR.)

Held items still on their own triggers only (ADR-008 D2 disk pages; ADR-006/007 burst
escalation; ADR-009 G1 Gradle/JMH — note G1 also cures V5's wall-clock weather). The
composite cost metric (comparisons + w·rotations) and its rotation counters get a real
consumer at E3/E5. Splay-p / hybrid-mix is E5, *not* a standalone — on the steady-state
axis it just repeats V5.

A fresh-eyes audit of the five V-slices (they landed in one day) is always a legitimate
alternative to starting E1.

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
