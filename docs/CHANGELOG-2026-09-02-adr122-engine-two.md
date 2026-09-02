# Changelog — 2026-09-02 — ADR-122: engine 2, observed

## Changed — SmokeHouse (82 tests)

- `SmokeHouse.RecoveryReport` + `recovery()`: what the last open did — entries,
  checkpoint used, bounded, sorted, the sort's strategy / comparisons / moves /
  millis, the feed's sortedness / inversions / nearly-sorted, the born tree,
  the tier.
- `SmokeHouse.abandon()` and `IndexedStore.abandon()`: release the handles
  without the checkpoint — the crash a drill can call.
- **Fix:** recovery's last-writer-wins map is a `LinkedHashMap` in arrival
  order, not a `TreeMap`. The `TreeMap` handed SuperBeefSort a sorted feed on
  every open: sortedness 1.0, zero inversions, an insertion pass, and a born
  strategy advised from a profile of the map rather than the workload. The
  first `RecoveryReport` ever read said so.
- `RecoveryReportTest` (cold open sorts and says so; warm open does not and
  says that; a delta past the checkpoint sorts again; abandon is idempotent
  with close).

## Changed — WholeHog (21 tests)

`Organism.crash()`; `HarnessConsole` `restart [PLAN] [LATENCY] [REPLICA-LAG]
[clean|cold]`, `recovery` verb, the report's headline in `observe` and
`restart`.

## Changed — CSRBT

- `tools/harness_plugin_organism.py`: `restart` gains `how` (clean | cold);
  action 34, `recovery` (READ, SuperBeefSort).
- `tools/verify/verify_organism.py` (301 → **310**): section X.
- `tools/mutate_organism.py` (26 → **29 killed**, 0 survived, 4 equivalent);
  the replica-lag anchor re-anchored for the new `send`.
- `tools/verify/verify_walk.py`: the organism is 34 tools; `walk_ledger.json`
  regenerated for the organism over both transports.
- `tools/ecosystem_ledger.json`, `WholeHog/docs/atlas.html`: SmokeHouse 82.

## Docs

`docs/ADR-122-engine-two-observed-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`; `WholeHog/docs/CHANGELOG-2026-09-02-engine-two.md`.
