# ADR-113 — Every organ, by name

**Status:** accepted · **Date:** 2026-09-01 · **Extends ADR-112; closes two of its three held items**

## 1. What ADR-112 reached, and what it did not

ADR-112 put the organism behind the contract and proved the contract
target-neutral. It did so through the store: put, delete, batch, get, range,
count, one Carver query over the secondary index, preserve, cold-scan, and
the meters. That is a key-value store with a vault. It is not the ecosystem.

The ask was *the substantial amount of wiring the harness needs to operate
everything*. "Everything" has a definite meaning here — fourteen engines, each
with a public surface WholeHog composes and each with a suite that asserts
it — and after ADR-112 a client holding the manifest could not tell that
Renderer, Brine or PitBoss existed, could not ask CSRBT the one question it
exists to answer (an order statistic), could not read over the wire, could
not look into a generation, and could not touch chaos at all.

## 2. The decision

The console and the plugin grow until **every engine is reachable by its own
surface, by name, through the same four operations** — 14 actions become 33,
and `verify_organism` gains one oracle per engine, each against the same
mirror the ADR-112 oracle already keeps. The contract, the gateway, the
policy, the replay cache and the transport are again untouched; the suite
still pins that `serve()` names no target.

| engine | actions | oracle in `verify_organism` |
|---|---|---|
| CSRBT | `order` (rank, nth, median, percentile, first, last, size), `depth` | each statistic against the sorted mirror; depth ≥ 1 live, negative absent; nth 0 and nth n+1 are `invalid_argument`, not crashes |
| SmokeSignal | `via = direct \| wire` on every read that the wire can answer (`get`, `contains`, `range`, `count-range`, `order`) | every read over the wire equals the same read direct; the wire's own meters counted them |
| Carver | `query` (secondary), `overlap`, `stab` (the SPAN interval index) | six random spans and six random points against brute force; the plan names the interval index |
| Renderer | `groups` | group count and top-k totals against the mirror's attr histogram, gap-free |
| Brine | `cache-get` | the mirror's value twice; the second read a cache hit, not a store read |
| PitBoss | `fleet`, `replica-get`, `rebootstrap` | one replica, lag 0, gap-free; agrees with the primary on eleven keys; catches a write after a rebootstrap |
| DryAge | `generations`, `as-of`, `retain-newest` (+ `preserve`) | `as-of` returns the *frozen* value for a key changed since, and not a key written after; `retain-newest 1` releases the older generation; a released generation is `not_found` |
| Jerky | `verify-archive`, `archive-names` (+ `cold-scan`) | the archive verifies; names include `scan.run` and a manifest |
| SmokeHouse | `compact`, `segments` | segments sum to the snapshot's garbage with one active; compact reduces garbage and changes no read |
| Twine | `recover` (+ `batch`) | a clean journal has nothing to replay |
| Rub | `history` (+ `tick`, `pulse`, `report`) | history grows by one per tick and its last sample is the tick's |
| Sizzle | `restart` | §3 |

The risk ladder absorbed all of it without a new rung: 8 `MUTATE`, 14
`SENSITIVE_READ`, 8 `READ`, 3 `NAVIGATE`, still **0 `DESTRUCTIVE`**. Two
calls were worth arguing about. `groups` is `SENSITIVE_READ` although it
returns no key: a histogram of attribute values is data about the data, the
same reasoning as `count-range`. `verify-archive` and `archive-names` are
`READ`: a CRC verdict and entry names are facts about a file, not its
contents.

## 3. Chaos, through the front door

ADR-112 held chaos: Sizzle is a constructor seam on the Organism, a
`ChaosPlan` is fixed at standup, and *a harness that presses buttons nobody
can reach* is ADR-103. The temptation was a runtime knob upstream —
`Sizzle.arm(plan)` — which would have been a cut made for the harness's
convenience rather than a consumer's need.

The organism's own test already takes a different road:
`theOrganismSurvivesAChaosBatchOnItsWritePath` constructs under
`crashOnceAtOp(3)`, watches a batch throw, **closes, and reopens at the same
root** — and construction replays Twine's journal into every index. That is
not a workaround; it is the recovery story, and it is what a client should
be able to drive.

So `restart [chaos] [latency-ms]` closes the organism and reopens it at the
same root under a plan (`none | once:N | every:N | prob:SEED:P`), and is the
crash-recovery road whether or not a plan is named. Section V of the suite
drives it end to end:

1. `restart chaos=once:2` — same store, same keys, plan armed (the snapshot
   says `chaos: once:2, restarts: 1`);
2. a three-op batch → `failed` (`Sizzle.Crash at op 2`); `chaosCrashes: 1`;
3. `restart` — `journalReplays: 1`;
4. a full `range` equals the mirror **including the crashed batch**, and the
   Renderer fold's group count agrees — the batch came back whole, in every
   index.

`restart` is `NAVIGATE`. It changes no record. A plan only makes *later*
writes fail, and failing is something `MUTATE` already permits; a client that
cannot write cannot crash anything.

One honest bound carried from the organism's own javadoc: after
`rebootstrap`, Rub's replica observer stays attached to the store the
replica was born on, so every snapshot from then until the next `restart`
says `replicaObserverDetached: true`. The snapshot tells the truth about its
own instrument rather than printing a vitals line for a store nobody reads.

## 4. What the console's tester caught

`mutate_organism.py` grew 11 → 19 mutants. On the first run after the
console was rewritten, **two of the original eleven came back `BAD MUTANT`**:
the count-range anchor no longer matched (the line moved into the `via`
branch) and the sample-cap anchor now matched *twice* (range grew the same
two lines). Neither would have been noticed by a runner that skipped
unmatched anchors — both would have printed `killed` forever while testing
nothing. ADR-111 built that guard for `mutate_harness` and it earned its
place here on the first day it could.

Three survivors are recorded equivalent with their reasons: the plugin's
order-arg check (the console refuses the same two inputs with the same code),
the plugin's batch-op regex (carried from ADR-112), and `replica-get` reading
the primary — the suite cannot hold the replica *behind* the primary without
a `Sizzle.slow` seam on the replication tail, which the organism does not
expose. That one is a real gap in what the harness can distinguish and is
named as such rather than filed as a kill.

Final: **19 killed, 0 survived, 3 equivalent.** `verify_organism` 234 → 284.

## 5. One check that was wrong about what it matched

Section P first asserted that after `rebootstrap` the fleet report would say
`rebootstrapped: true`. It said `false`, and it was right: that flag reports
what **the tick** did about a gap it found, not what a caller asked for. The
check was reading a field by its name rather than by its meaning — the
kit's standing defect, in a suite written the same day as the ADR that
names it. The check now asserts the flag stays `false` and says why, and the
action's description in the manifest says so too, because a model reading
the schema would have made the same mistake.

## 6. Still held

- **Reads over the wire are the wire's read surface, not its whole surface.**
  `wire.stats()` (OP_STATS) is in every snapshot; the wire's `size` and
  `rangeQuery` are covered by `order size` and `range`. Nothing on the wire is
  unreachable now, but nothing here drives a *second* concurrent client
  either.
- **The replica cannot be held behind the primary** (§4). A `Sizzle.slow`
  seam on PitBoss's replication tail is the upstream cut that would make
  `replica-get`'s independence measurable. Not made here — a harness slice is
  not a consumer need.
- **`compact` is asserted weakly** — garbage after ≤ before, reads unchanged.
  Forcing a real reclaim needs a churn heavy enough to close a segment, which
  the 160-op oracle does not reach; the WholeHog and SmokeHouse suites do.
- **The per-response snapshot** now carries Brine's stats and the segment
  count as well; still unpriced on either plugin.
