# ADR-122 — Engine 2, observed

**Status:** accepted · **Date:** 2026-09-02 · **Closes the last engine the harness had never seen work, and corrects what it was doing**

## 1. The engine nobody could see

ADR-113 put every organ of the organism behind the gateway by its own
surface — CSRBT, Carver, Renderer, Brine, PitBoss, DryAge, Twine, Jerky,
SmokeHouse, Rub, Sizzle, the wire. It named twelve. The fourteen-engine
organism has one more: **SuperBeefSort, engine 2, the recovery engine** —
the sort that turns a scanned log into a sorted feed for the index, and
the profiler whose measurement of the data is supposed to pick the tree the
index is born as ("born optimal", the two-engines-talking seam of the
ecosystem ADR).

It had no surface. `SmokeHouse.open` ran the sort, used its `DataProfile`
and `SortResult` to prime the control plane, and dropped both. Nothing a
caller could read said whether recovery had sorted anything, by what, at
what cost, over how disordered a feed. And through the harness it had never
run at all: the organism's `restart` closes the store cleanly, a clean close
writes the hint checkpoint, and a reopen under a checkpoint that covers the
log skips the sort. Twenty-one restarts in the committed walk; SuperBeefSort
idle in every one.

## 2. The decision

**SmokeHouse** keeps what the open did: `RecoveryReport(entries, hintUsed,
bounded, sorted, sortStrategy, comparisons, moves, sortMillis,
sortednessRatio, inversions, nearlySorted, bornStrategy, tier)`, read by
`recovery()`. And it can die: `abandon()` releases the store's handles
**without** the checkpoint a clean `close()` writes — what the process dying
after its last append looks like to the next open — so a drill can walk the
road every real crash takes. Whatever hint an earlier clean close left
stays, as it would; the delta since it is what the next open must scan and
sort. `IndexedStore.abandon()` passes it through the fan-out.

**WholeHog** `Organism.crash()` releases every organ as `close()` does and
abandons the store. `HarnessConsole` `restart [PLAN] [LATENCY] [REPLICA-LAG]
[clean|cold]` and a `recovery` verb; `observe` and `restart` carry the
report's headline.

**CSRBT** `restart` gains `how` (`clean` | `cold`); a 34th action,
`recovery` (READ, SuperBeefSort by name in the engine map). `verify_organism`
section **X** (301 → 310): a clean restart's report says checkpoint used,
nothing sorted; forty shuffled keys, a compaction (which retires the
checkpoint), a cold restart — and the report says every live key came back
from the log alone, sorted, by a named strategy, at a counted cost, over a
measured disorder, into a named tree; every record then equals the mirror
and the Renderer fold agrees; a way of restarting that is neither clean nor
cold is refused at the boundary; a clean restart after it is warm again.

## 3. What the report said the first time it was read

The first `RecoveryReportTest` asserted that 400 keys written in random
order and recovered cold would show a disordered feed. It failed:

    sortStrategy=insertion, comparisons=326, moves=0,
    sortednessRatio=1.0, inversions=0, nearlySorted=true

**Recovery was handing SuperBeefSort a `TreeMap`'s iteration.** The
last-writer-wins map that the log scan fills was a `TreeMap` keyed by the
comparator (chosen so that the warm-start-no-delta path, which skips the
sort, builds from a key-sorted list — `HashMap` order is only accidentally
ascending below 2^16 keys). So on every open, whatever the log had done,
engine 2 received a sorted feed: its profile read sortedness 1.0 and zero
inversions, its "sort" was an n−1-comparison insertion pass, and the born
strategy was advised from a profile that described the map, not the
workload. The two-engines-talking seam had one engine talking to itself.
Right about what it measured; wrong about what the measurement meant — the
kit's recurring defect, one layer below the harness this time.

The map is a `LinkedHashMap` now, in **arrival order**: the hint's entries
first, in the key order the hint wrote them, and the delta appended in log
order. A warm start with no delta is therefore still key-sorted (the
`TreeMap`'s reason survives), and any open that scans records hands the
sort the disorder it actually found. The same test then read, for 200
shuffled keys through the organism:

    sortStrategy=intro, comparisons=1576, moves=2522,
    sortednessRatio=0.52, inversions=9315, nearlySorted=false,
    bornStrategy=RedBlackStrategy

Engine 2 doing the work it was named for, and the profile that picks the
born tree describing the data for the first time.

Then section X failed on *its* first run — sortedness 1.00 again — because
the draft wrote keys 960..999 in order, and the delta past the checkpoint
was sorted because the test had sorted it. Right about what it measured.
Shuffled now, with a compaction so the cold open is a whole-log scan.

## 4. Numbers

SmokeHouse 80 → **82** (`RecoveryReportTest`, two tests); WholeHog 21 green
(`HarnessConsoleTest` extended: cold restart after thirty puts, `count` 39,
the snapshot's headline); `verify_organism` **310**; `mutate_organism` +3
(a cold restart that closes cleanly; the plugin dropping `how`; a report
that always says sorted) → **29 killed, 0 survived, 4 equivalent**; walk
ledger regenerated for the organism over both transports at 34 tools.

## 5. Held

- `EleventhPassProbeTest.rangeSurvivesAConcurrentCompactionCommit` failed
  once in this session's first SmokeHouse run ("key 1 stayed unreadable
  after repeated re-resolution … sustained compaction") and passed on the
  next four runs, including the full suite. It is a timing probe under a
  loaded sandbox; not touched, on the record.
- The report is the last open's. A `preserve`/`seedFrom` road builds a
  store by `importSorted`, which never sorts; its report says so
  (`sorted: false`) and that is correct, not a hole.
- The ensemble tiers' born strategy is reported as `ensemble(<primary>)`;
  the organism runs STATIC and the suite pins that tier only.
