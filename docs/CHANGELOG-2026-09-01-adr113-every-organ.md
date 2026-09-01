# Changelog — 2026-09-01 — ADR-113: every organ, by name

The organism plugin grows from a key-value store with a vault to the whole
ecosystem: **14 → 33 actions**, every engine reachable by its own surface,
one oracle per engine, chaos through the front door. The contract, gateway,
policy, replay cache and transport are untouched again.

## Changed — `WholeHog/HarnessConsole.java`

New verbs: `order` (rank/nth/median/percentile/first/last/size, 1-based
ranks), `depth`, `overlap`, `stab`, `groups`, `cacheget`, `fleet`,
`replicaget`, `rebootstrap`, `generations`, `asof`, `retain`, `verify`,
`names`, `compact`, `segments`, `recover`, `history`, `restart`. Every read
the wire can answer takes `[direct|wire]` like the writes. Snapshots add
Brine's stats, the segment count, the armed chaos plan, the restart count and
`replicaObserverDetached`. A rank outside `[1, size]` is `invalid_argument`,
not a crash. `main` owns the organism through `restart` (close + reopen at the
same root under a `ChaosPlan`). `HarnessConsoleTest` 5 → 7 (WholeHog **21**
green).

## Changed — `tools/harness_plugin_organism.py` (14 → **33 actions**)

8 `MUTATE` (put, delete, batch, preserve, rebootstrap, retain-newest, compact,
recover) · 14 `SENSITIVE_READ` · 8 `READ` · 3 `NAVIGATE` (tick, quiesce,
restart) · 0 `DESTRUCTIVE`. `via` on every read the wire answers. `restart`
validates the plan grammar and the latency cap at the boundary.

## Changed — `tools/verify/verify_organism.py` (234 → **284 checks**)

Sections K–V: wire == direct on get/range/count/order; order statistics
against the sorted mirror; Carver span queries against brute force; the
Renderer fold against the attr histogram; Brine hit-after-miss; the fleet,
the replica, a rebootstrap; `as-of` reading the frozen moment and not a later
key; `retain-newest`; Jerky verify + names; segments summing to the garbage,
compact changing no read; a clean journal; Rub history; and the recovery
road — arm `once:2`, watch a batch fail, restart clean, read it back whole in
every index. Section A now asserts every engine is reachable by name.

## Changed — `tools/mutate_organism.py` (11 → **19 mutants, 19 killed**)

Eight new: reads dropping their route; `restart` relabelled `MUTATE`; `groups`
relabelled `READ`; median answering first; overlap running a stab; the cache
reporting a hit on a store read; `as-of` reading the live store; `restart`
ignoring its plan. Two ADR-112 anchors came back **BAD MUTANT** after the
console rewrite and were re-anchored — the guard working as built. Three
recorded equivalents, with reasons.

## Docs

`docs/ADR-113-every-organ-by-name-2026-09-01.md`; `docs/AUTOMATION-HARNESS.md`
(the full action table, chaos); `docs/AI_HARNESS.md` §7d; WholeHog
`README.md`/`CLAUDE.md`.

## Held

The replica cannot be held behind the primary (needs a `Sizzle.slow` seam on
the replication tail — not cut for a harness); `compact` asserted weakly at
this churn; the per-response snapshot still unpriced.
