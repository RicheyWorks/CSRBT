# Hardening audit — CSRBT

**Date:** 2026-07-08 · **Scope:** csrbt-core main sources (concurrency, resource lifecycles, persistence
trust, hot-path exposure, dependency posture), including the 2026-07-07 workload-signal seam. Static
analysis of source at commit `922f7af`; no runtime penetration testing.

> **Remediation status (same day):** M-1 fixed (`OrderedSet.emit` + `EnsembleOrderedSet.emit` now
> swallow listener faults), M-2 fixed (`FilePersistenceAdapter.validateRestored` — ascending check +
> `StrategyHealthCheck` gate on both load paths; invalid snapshots are refused), M-3 fixed
> (per-op key logging demoted to DEBUG). **L/I follow-ups closed 2026-07-08:** L-1
> (`Builder.optimisticVotes(boolean)` per-instance pin; the static remains the default seed), L-3
> (`Serializable` stripped from the deprecated `TreeGenome` and its nested trait classes), I-1
> (`selfRepair` cost warning on `SelfHealingTree`). L-2/I-2/I-3 remain accepted-and-documented.

## What's already hardened well

Credit where due — this codebase is defensively written to an unusual degree. Snapshot names are
path-traversal-guarded (`snapshotPath` rejects separators and `..` outright, then verifies the
normalized parent). The persistence format is plain text parsed with explicit `NumberFormatException`
handling and a broad terminal catch — no `ObjectInputStream`, so no Java-deserialization gadget surface
on the load path. The pre-order deserializer is iterative (no `StackOverflowError` from adversarially
deep files). log4j is 2.26.0 — far past the Log4Shell line — and the dependency catalog is one audited
file with nothing vendored. Fan-out threads are daemons behind `close()`, so a forgotten close leaks no
non-daemon threads. Reads are torn-read-free by construction (stamp-validated optimistic walks with
step bounds and locked fallbacks), morphs and self-repairs build aside and publish under the write
stamp, and `buildAllFromSorted` fails loud on any member failure rather than half-committing silently.

## Findings

### M-1 · Event listener exceptions propagate into the write path (Medium)

`OrderedSet.add/remove` call `emit(...)` while holding both the monitor and the write stamp. The
`TreeEventListener` contract documents "fast, non-reentrant," but nothing enforces it: a listener that
throws propagates out of `add()` *after* the mutation has committed. Locks release correctly
(`finally`), so there is no corruption or deadlock — but the caller sees a spurious failure for an
insert that actually happened, and a hostile-or-buggy listener can fail every write on the set.
**Recommendation:** catch-and-drop (or catch-and-unregister) around `emit`, or state loudly that a
throwing listener poisons the write path. (SuperBeefSort's `TreeEventBridge` has the mirror-image
finding; hardening either side closes it.)

### M-2 · Loaded snapshots are structurally trusted (Medium)

`loadSnapshot`/`loadOrderedSet` parse the file, `setRoot` the result, recompute size, and warn on a
header mismatch — but never run `StrategyHealthCheck.validate` on the restored tree. A tampered or
corrupted `.rbt` can install a tree that violates the strategy's invariant (wrong colors, wrong
ordering, degenerate depth) and it will be served silently: worst case wrong query results, likely case
O(n) operations. The machinery to reject this already exists and is used on every morph.
**Recommendation:** validate post-load; on failure, refuse the snapshot or route through `selfRepair`.

### M-3 · Key values logged at INFO on the hot path (Medium)

`RedBlackTree.add/remove` log `value={}` at INFO per operation (and the control plane logs `event=`
lines with key hashes). The published jar deliberately ships no logging config, so most apps default
this off — but any application with an INFO root logger will write **every key it stores** into its
logs: a data-exposure channel and a throughput tax. **Recommendation:** demote per-op value logging to
DEBUG/TRACE, or log key hashes only.

### L-1 · Process-global concurrency kill switches (Low)

`EnsembleOrderedSet.OPTIMISTIC_VOTES` is `public static volatile`; `OrderedSet.OPTIMISTIC_READS` is a
static constant. The former means any code in the JVM — including a dependency — can flip read-path
semantics for *every* ensemble at runtime. Rollback switches are good; global mutable ones are a
footgun. **Recommendation:** per-instance flag (builder knob), keeping the static as the default seed.

### L-2 · Unsynchronized long counters (Low)

`OrderedSet.rotationCount()` (2026-07-07 seam) and the timing counters (`totalInsertTime`, …) are plain
`long`s written on the locked write path but readable from any thread without synchronization. Benign
data race on 64-bit JVMs; on a 32-bit JVM a torn long read is theoretically possible (JLS §17.7).
Metering deltas across a morph is already documented (`max(0, after−before)`). **Recommendation:**
accept and document, or make the counters `volatile` if 32-bit targets matter.

### L-3 · Deprecated `TreeGenome` implements `Serializable` (Low)

No `serialVersionUID`, no `readObject` validation, on a class the ADR-011 work explicitly deprecated.
It is dead surface that keeps the Java-serialization door ajar for any app that deserializes untrusted
streams with this jar on the classpath. **Recommendation:** drop `Serializable` (and the nested trait
classes') when the deprecated type is next touched.

### I-1 · `selfRepair` is an O(n) rebuild with no rate limit (Info)

By design it is the most defensive operation, but any caller loop (see SuperBeefSort's
`PrecisionFeeder`, which may invoke it per insert) turns a feed into O(n²) and repeatedly discards
strategy state (a splay tree's learned layout). Not a bug — an interaction hazard worth a javadoc
warning on `SelfHealingTree.selfRepair`.

### I-2 · Controllers and monitors are single-threaded by contract (Info)

`RollingWorkloadMonitor` says "not thread-safe by design"; the morph/ensemble/evolution controllers are
caller-cadenced. Current wiring (including SuperBeefSort's) respects this — fan-out worker threads never
touch the monitor. The invariant is load-bearing and only documented in one place; violating it corrupts
the sketch silently. Keep it loud in any new adapter.

### I-3 · `int` size counters (Info)

`OrderedSet.size` and friends are `int`: a 2³¹−1 key ceiling. The B+tree engine positions CSRBT for
"large n"; if that ever means >2 billion keys, the facades cap out first. Noted for the roadmap, not
actionable now.

## Suggested order

M-1 and M-3 are one-file changes. M-2 reuses existing machinery. The rest are notes for the next time
each file is open.
