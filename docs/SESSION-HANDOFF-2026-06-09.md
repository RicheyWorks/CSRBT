# Session handoff — 2026-06-09 (end of session)

For the next agent session. Read this before touching code.

## Where things stand

- Suite: **466 tests, green** (`ant clean test`, verified in-sandbox on JDK 17).
- ADR-001–008 Accepted. ADR-009 Proposed: **P1 done** (O(1) size), **P2 done**
  (NavigableSet adapter), **G0 done** (CI workflow). Each has a changelog in `docs/`.
- All work since commit `ebbb183` is uncommitted (the user commits host-side; the sandbox
  cannot write `.git`). Pending commit suggestion is in the chat; roughly: ADR-006/007/008
  slice + ADR-009 + P1 + P2 + G0 + handoff docs.

## Next up (in order, per ADR-009 §4)

1. **P3** — `TreeEventListener` seam (insert/remove/rotate/morph-with-reason/repair/
   quarantine/promote/failover; records, no-op default, **allocation-free when no listener
   is registered — assert with a benchmark row**) + `TreeExport.toJson(set)` (nodes:
   key/color/size/depth + strategy + meters) as the visualizer contract; check a demo JSON
   into `docs/`. Touches `OrderedSet`/strategy hot paths — do it early in a fresh session,
   not near a limit.
2. **G1/G2** — held; triggers documented in ADR-009 §2.
3. ADR-006 V2 / ADR-007 W2 / ADR-008 D2+D3 — held; triggers in their ADRs.

## Sandbox mechanics (cost an hour last time — don't rediscover)

- **JDK/ant:** sandbox has JRE 11 only, no root. Download user-space:
  `curl -sfLo jdk17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"`,
  ant 1.10.14 from `archive.apache.org`; untar in `~`; export `JAVA_HOME`/`PATH` per call
  (no env carryover between bash calls).
- **Shadow tree:** the repo mount **cannot delete files** (`ant clean` fails in-place).
  Build out-of-tree: copy `src build.xml *.jar snapshots` to `~/csrbt`, run ant there.
  The shadow tree is ephemeral — rebuild it each session.
- **Mount staleness (the truncation trap):** *edits* to existing repo files (via the file
  tools) often appear **truncated** through the bash mount for minutes; *new* files sync
  fine, and the Windows side (file tools) is always authoritative. Therefore: after editing
  an existing file, do **not** `cp` it from the mount into the shadow tree — re-apply the
  same edit to the shadow copy with a python/sed patch (assert exactly one match), or
  route content through a brand-new file. Verify with `wc -l` both sides when in doubt.
- Stray `sync_probe.tmp` and similar can only be deleted host-side by the user.

## House style reminders

- One slice per commit; changelog per slice (`docs/CHANGELOG-<date>-<slice>.md`); tick the
  ADR action item with a pointer; ship green through `ant clean test`.
- No background threads (rejected three times: ADR-006 C, ADR-008 D, ADR-009).
  Caller-cadenced control is a load-bearing decision.
- `TreeContext` stays Integer (documented adapter); generic callers use `OrderedSet<K>`.
- Benchmarks are in-suite printed rows with soft assertions, not JMH (until G1).
