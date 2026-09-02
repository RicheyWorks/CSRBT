# ADR-120 — Nothing held: the harness program's open findings, closed

**Status:** accepted · **Date:** 2026-09-02 · **Closes the items ADR-112, ADR-113 and ADR-118 held, and the drift they named**

## 1. What was open

Eight harness ADRs in two days each ended with a "Held" section, and the
kit's rule for a held item is that it stays held on a trigger or a price,
never on inertia. Four of them had neither:

1. **The per-response snapshot was unpriced** (held since ADR-112). Every
   execute response carries the target's snapshot; nobody had said what
   that costs, and nothing would have noticed it becoming expensive.
2. **The replica could not be held behind the primary** (held in ADR-113:
   "would need a `Sizzle.slow` seam on the replication tail — not cut for a
   harness"). So the fleet's `lag` had only ever been read at zero, and a
   reading that has only ever been zero is not known to be a reading.
3. **`compact` was asserted weakly** (ADR-113): "reclaimed ≤ garbage before
   and no read changed" — true of a compact that reclaims nothing.
4. **The Atlas's engine ledger was stale by a month** (ADR-118): the
   published map of the ecosystem carried suite counts and versions typed
   by hand on 2026-08-20. Seven versions and eleven suite counts had moved,
   and a held item it still listed had been cut on 2026-08-22.

This ADR closes all four. Two of them turned up defects on the way.

## 2. The snapshot, priced — protocol 1.2

The gateway now times the action and the snapshot **separately** and puts
both on every execute response: `ms` (the action, as before) and
`snapshotMs` (what the target charged to be asked about itself). That is a
new response field, so the protocol is **1.2**; nothing a 1.1 client sends
changes.

The robot reads the price from the responses themselves — an outsider's
measurement, not the gateway's word — and writes it into the walk ledger
per target as median, p95 and max. From the committed 8-round walks:

| target | snapshot median | p95 | max | action median |
|---|---|---|---|---|
| csrbt-organism | 0 ms | 5 | 14 | 0 ms |
| csrbt-lab | 0 ms | 2 | 5 | 12 ms |
| csrbt-page | **91 ms** | 153 | 177 | 69 ms |

The organism's observe is a dozen meters and a directory listing, and it is
free. **The page's is not**: reading a page's state means evaluating the
control map over the DOM in the browser, and on collection-sheet that
costs more than the action it rides on. This is the number the held item
was waiting for. It is bounded now — `verify_walk` and `verify_organism`
refuse a median over 250 ms, `verify_contract` pins that a slow observe is
charged to the snapshot and not the action — and it is the price of the
"observe after every act" design, on the record rather than assumed to be
nothing.

## 3. The replica, held behind the primary — and what the fleet said

The seam is cut, three engines deep, each one line of plumbing:

- **SmokeHouse** `ReplicationServer.serve(store, opts, feed)` takes a
  wrapper applied to each client's tail listener before it is subscribed —
  the one place a caller can slow the replication feed itself. Identity by
  default; `onGap` must pass through.
- **PitBoss** `over(primary, opts, autoRebootstrap, feed)` passes it down.
- **WholeHog** `Organism(root, seed, plan, replicaLagMillis)` hands
  `Sizzle.slow(listener, millis)` — the wrapper the gap-and-meter slice cut
  on 2026-08-20 for tail consumers — to the feed; `HarnessConsole` `restart
  [PLAN] [LATENCY] [REPLICA-LAG]`; the plugin's `restart` gains
  `replica-lag-ms` (0–200, so a `quiesce` can still converge). The replica
  is **late, never wrong**: frames arrive in order and none are dropped.

The first time the feed was actually held back, **the fleet reported lag
0 for a replica twenty frames behind.** `Replica.lagSequence()` is
`primarySequence − applied`, and `primarySequence` is read *from the
frames* — a replica whose feed is held back has not yet received the frame
that would tell it how far behind it is. Right about what it measured,
wrong about what the measurement meant. PitBoss holds the primary, so
`tick()` now measures from the conductor's seat: the primary's committed
sequence minus what the replica has applied. The `ReplicaStatus` javadoc
says why.

Pinned, one layer at a time: `ReplicationTest` (a 40 ms feed holds a
replica behind 25 writes and it still converges; every frame went through
the wrapper) — SmokeHouse **80**; `PitBossTest` (a 50 ms feed, the tick
reports lag > 0 and not gapped, then 0 after the await) — PitBoss **4**;
`HarnessConsoleTest` (`restart none 0 150`, six puts, `fleet` reports the
replica behind, `quiesce` lands it, `count` is 9); and `verify_organism`
section **W** through the gateway, with a lag past the cap refused at the
boundary and a plain restart letting the feed go.

## 4. `compact`, asserted strongly

Section S now churns first — ten keys overwritten twelve times, so the
organism's 4 KiB segments roll and the closed ones carry garbage — reads
the per-segment garbage, and requires that `compact` reclaims **exactly**
the closed segments' dead bytes, leaves no dead byte in a closed segment,
and at most one closed segment, and changes no read. On the first run it
held exactly: the store's garbage accounting and its compaction agree to
the byte.

## 5. The Atlas, regenerated from the ledger

The Atlas's source now lives in the repository — `WholeHog/docs/atlas.html`
— and `tools/atlas.py` rewrites its engine table between markers from
`tools/ecosystem_ledger.json` (suite counts, green or not, or "no
reading" — never an invented number) and each repo's `build.gradle.kts`
(versions). `verify_ecosystem` gained check **7**: the file's table and
stamp must be exactly what the tool renders from the ledger, the rows must
be the fourteen repos the ledger lists, and every ledger engine must feed
exactly one row (52 → 56). A version typed by hand is drift, and drift
fails.

The regenerated Atlas is republished at the same URL. Beyond the table it
gained the passes since 2026-08-20 that the published copy never had — the
tenth, eleventh and twelfth passes, the hardening release, record-granularity
as-of (moved from *held* to *closed*, with its price kept beside the cut),
and the harness program — and a footer naming its source.

## 6. Two things the closing found

- `mutate_organism` had a **BAD MUTANT** since ADR-117: the "pump dies
  without telling the reader" anchor pointed at code the stderr-drain
  rewrite moved. The guard did exactly what ADR-116 built it to do — say
  "the mutation never applied" rather than "killed" — and it was the
  runner's own summary line nobody re-read. Re-anchored; with four new
  mutants for this ADR (restart letting the feed go, the plugin dropping
  the lag, the fleet reporting 0, compact reporting every dead byte
  reclaimed) the runner is at **26 killed, 0 survived, 0 inconclusive, 4
  equivalent**.
- The organism's committed walk now includes restarts under a replica lag,
  and one `quiesce` in it ran to its 15 s budget. That is the walk doing
  what a walk does; the check that matters — the fleet caught up after the
  cross-check's own quiesce — held in every round.

## 7. Still held, with reasons

- **MCP hosts that mint a fresh id per retry defeat replay** (ADR-115). A
  transport cannot know a retry from a new call without the id; documented
  as the host's responsibility.
- **`listChanged` / progress notifications** (ADR-115). No consumer.
- **The operator's own stale results** (ADR-118): on the author's machine
  eleven engines are `NOT VERIFIED` until `python tools\ecosystem.py --run`
  is run there with a JDK 17+. The suite says so by name; nothing here can
  run a Gradle build on a machine it is not on.

## 8. Numbers

`verify_contract` 89 · `verify_organism` 301 · `verify_walk` 74 ·
`verify_ecosystem` 56 · `mutate_organism` 26/0/4 · `mutate_walk` 17/0/2 ·
SmokeHouse 80, PitBoss 4, WholeHog 21 green · ecosystem ledger 1,626
tests, 0 failures.
