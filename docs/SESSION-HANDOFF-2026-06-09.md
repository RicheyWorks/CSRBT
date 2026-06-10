# Session handoff — 2026-06-09/10

For the next agent session. Read this before touching code.

## Where things stand

- Suite: **474 tests, green** (`ant clean test`, sandbox JDK 17).
- **ADR-001 through ADR-009 all Accepted.** Every implementation item is landed; every
  open thread is *held with a documented trigger* inside its ADR:
  - ADR-006 V2 / ADR-007 W2 — burst auto-escalation → real dissent bursts in traffic.
  - ADR-008 D2 (disk pages) → a working set that misses RAM; D3 (registry/genome) → after D2.
  - ADR-009 G1 (Gradle/JMH/coverage) → publishing or external contributors;
    G2 (jqwik) → an invariant bug the seeded oracle tests miss, or G1.
- Extras beyond the ADRs: `demo/visualizer.html` (animated drawer over the
  `docs/visualizer-contract.json` export schema), README current, CI workflow in
  `.github/workflows/ci.yml` (fires on first push to GitHub).
- A consolidation audit closed the session: see
  `CHANGELOG-2026-06-10-consolidation-audit.md` (TreeExport made spine-proof).

## If the user says "next"

There is no unblocked code work left by design — do not invent some. The honest options:
ship visibility (push to GitHub → CI goes live; demo clip of the visualizer morph;
README/thread material), start a held item **only if its trigger has fired**, or another
audit pass with fresh eyes.

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
