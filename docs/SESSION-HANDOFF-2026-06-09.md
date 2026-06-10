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
  - **Next: V3** — `PolicyBandit` (UCB1 over the discretized box) driving ensemble
    shadows, `TreeEvent.Trial` events, arena replay of a recorded search session.
    Caller-cadenced; promotion through the existing `MorphPolicy` gates.
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
