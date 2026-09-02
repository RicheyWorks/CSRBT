# Changelog — 2026-09-02 — ADR-120: nothing held

## Changed — `tools/harness_contract.py` — protocol **1.2**

Every execute response prices its snapshot: `snapshotMs` beside `ms`, timed
separately. `harness_mcp.py` reports server version 1.2.

## Changed — the replication feed seam, three engines deep

- **SmokeHouse** `ReplicationServer.serve(store, opts, feed)`: a wrapper
  applied to each client's tail listener before it is subscribed
  (`ReplicationTest` +1 → **80**).
- **PitBoss** `over(primary, opts, autoRebootstrap, feed)`; and `tick()`
  now measures a replica's lag **from the conductor's seat** — the first
  time the feed was held back the fleet reported lag 0 for a replica twenty
  frames behind, because `Replica.lagSequence()` learns the primary's
  sequence from the frames it has not yet received (`PitBossTest` +1 →
  **4**).
- **WholeHog** `Organism(root, seed, plan, replicaLagMillis)` puts
  `Sizzle.slow` on the feed; `HarnessConsole` `restart [PLAN] [LATENCY]
  [REPLICA-LAG]` (cap 500), `observe` and `restart` report `replicaLagMs`
  (`HarnessConsoleTest` extended; WholeHog 21 green).
- **CSRBT** `harness_plugin_organism.py` `restart` gains `replica-lag-ms`
  (0–200).

## Changed — `tools/harness_walk.py`, `tools/walk_ledger.json`

The price of the snapshot and of the action, read from the responses, per
target: median, p95, max. Organism 0 ms median; lab 0; **page 91 ms — more
than its actions (69 ms)**. Ledger regenerated (8 rounds per target).

## Changed — `tools/verify/verify_organism.py` (291 → **301**)

Section S asserts `compact` strongly: after a churn that rolls segments,
reclaimed equals the closed segments' garbage exactly, none left, at most
one closed segment, no read changed. Section **W**: restart with a replica
lag, the fleet reports the replica behind, a quiesce lands it, lag reads 0,
the last write is on the replica; a lag past the cap refused; ten snapshots
priced under 250 ms.

## Changed — `tools/mutate_organism.py` (22 → **26 killed**, 0 survived, 4 equivalent)

Four new mutants (the feed let go, the lag dropped by the plugin, the fleet
reporting 0, compact reporting every dead byte reclaimed); the "pump dies"
anchor, BAD MUTANT since ADR-117's stderr-drain rewrite, re-anchored.

## New — `tools/atlas.py`; `WholeHog/docs/atlas.html`

The Atlas's source is in the repository; the engine table and its stamp are
regenerated between markers from `tools/ecosystem_ledger.json` and each
repo's build file; `--check` fails on drift. The published Atlas is
regenerated (seven versions and eleven suite counts were stale; the passes
since 2026-08-20 added; record-granularity as-of moved from held to closed).

## Changed — `tools/verify/verify_ecosystem.py` (52 → **56**), `verify_contract.py` (87 → **89**), `verify_walk.py` (→ **74**)

The Atlas is what the ledger renders; the response prices its snapshot and
a slow observe is charged to it; the committed walks carry the price.

## Docs

`docs/ADR-120-nothing-held-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
