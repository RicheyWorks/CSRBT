# ADR-010: Second roadmap reconciliation — the "beastmode" review, audited

**Status:** Proposed (X1–X3 scoped; held items carry triggers)
**Date:** 2026-06-10
**Deciders:** Richmond
**Builds on:** ADR-009 (the first external-review audit; its method is reused verbatim),
ADR-002 step 6 (control plane), ADR-009 P3 (the event seam + export contract this ADR's
centerpiece consumes), `demo/visualizer.html`.
**Goal:** audit a second pasted review against the code, fix the one real defect it
stumbled onto, and design the one genuinely new idea it contains — turning the static
visualizer into a session **replay arena** fed by the event seam — without re-deciding
anything that already carries a trigger.

---

## 1. Context — the audit

The review describes the repo as it stood before ADR-002 step 4 landed. Verified today:

| Claim | Verified status |
|---|---|
| "Still Integer-centric; OrderedSet<K> facade hasn't landed" | **Stale.** Landed (ADR-002 steps 2–6, Accepted); `TreeContext` is the documented Integer adapter (re-litigated and rejected in ADR-009). |
| "Implement WorkloadMonitor / StrategyScorer / MorphPolicy / MorphController" | **Stale.** All shipped in `core.control` (ADR-002 step 6), wired and default-on, with the hysteresis/cooldown/min-improvement gates the review specifies. |
| "Make morphIfStressed() opt-in, default off" | **Stale.** It is — `TreeContext` javadoc: "legacy facade-driven stress auto-morph (default off)", with accessors. |
| "Move TreeGenome to experimental/" | **Overtaken.** The genome path is `@Deprecated` behind the one-switch control-plane flag (its documented rollback story). Relocating a deprecated rollback path is churn; the right end state is *deletion*, not relocation — held, trigger below. |
| "No memory model documentation" | **Mostly stale.** README's Concurrency section + ADR-004/005/007 document the model; what's missing is one explicit happens-before paragraph (X3, small). |
| "Reads aren't protected" | **Stale.** ADR-004 R1/R2; ADR-005 wait-free; ADR-007 lock-free votes. |
| "RB leakage: isValidRedBlack / selfRepair / naming" | **One real defect found here.** `StrategyHealthCheck` already dispatches per strategy (claim stale), and `TreeDiagnostics.isValidRedBlack()` is honestly named (it *is* an RB-specific diagnostic). But `TreeContext.selfRepair()` short-circuits on `isValidRedBlack()` **regardless of the current strategy**: a healthy AVL/Splay/Hybrid tree fails RB color discipline, so after any morph, every `selfRepair()` call skips the short-circuit and pays a needless O(n) rebuild (the inverse miss — skipping repair on a broken non-RB tree — is improbable but not argued impossible). X1 fixes the gate. |
| Ant → Gradle/Maven coordinates, JMH, Javadoc publishing | **Held** (ADR-009 G1; trigger: publishing/external contributors). |
| Count-Min sketch for skew | **Not demanded.** `RollingWorkloadMonitor`'s O(1) skew estimator feeds the scorer adequately; a sketch is an upgrade for when a workload defeats it — noted, not scheduled. |
| Battle arena / live visualizer with explainable decisions | **The genuinely new item.** The review imagines a server (Javalin + d3). This codebase has a better-fitting answer it didn't know about: the ADR-009 P3 event seam *is* the explainability feed. X2 designs the arena as **record-and-replay**, serverless. |
| Evolutionary/bandit/RL layer; cross-project integration; research-note reports | **Held** as experimental-tier ideas, undemanded; cross-project work lives outside this repo. |

---

## 2. The new design — X2, the session replay arena

### Options

**Option A — Live server arena (the review's shape: Javalin + websockets + d3).**
Run workloads in the JVM, stream states to a browser.
*Pros:* truly live; interactive workload knobs.
*Cons:* first server, first websocket, first frontend dependency in a dependency-free
codebase; a running process to babysit in every demo; none of it reusable as a library
seam. Cost is mostly plumbing, not substance.

**Option B — Record-and-replay over the existing contract (chosen).**
A library-side `TreeSessionRecorder` (a `TreeEventListener`) buffers every structured
event and snapshots the tree (`TreeExport`) at decision points; `toJson()` emits one
self-describing session file. The existing `demo/visualizer.html` gains a replay mode:
load a session, scrub/step/play through it — states animate (the node-matching tweening
already exists), and a decision log narrates each morph/promote/quarantine/heal with its
from→to and verdict. Workload generators are a small driver (`experimental.ArenaSession`)
that scripts regimes (uniform → hotspot → delete-heavy), runs the *real* controller, and
records. One canonical session checked into `docs/` makes "watch it decide" a double-click.
*Pros:* zero new dependencies; the recorder is a tested library feature (anyone can record
production sessions and replay them); demos are reproducible files, not fragile live runs;
builds directly on two seams that exist because earlier ADRs built them.
*Cons:* not interactive-live; "what-if" requires re-recording. Accepted — replay covers
the demonstrable claim ("it watches and decides"), and a live mode can layer on later
without redesign because the file format is the contract.

**Option C — GIF/video only.** No artifact, no contract, nothing testable. Rejected.

### Session file shape (v1)

```json
{ "version": 1,
  "events": [ {"op": 1234, "type": "Morph", "from": "RedBlackStrategy",
               "to": "SplayStrategy", "committed": true,
               "state": { ...TreeExport schema... }}, ... ],
  "final": { ...TreeExport schema... } }
```

Insert/remove events are *counted between* decision points, not stored individually
(50k inserts must not mean 50k array entries); lifecycle events carry a full state
snapshot so the replay animates exactly what the structure did.

---

## 3. Decision

1. **X1 — strategy-aware repair gate.** `TreeContext.selfRepair()` short-circuits via
   `StrategyHealthCheck.validate(...)` against the current strategy instead of
   `isValidRedBlack()`. `TreeDiagnostics.isValidRedBlack()` keeps its name and gains one
   javadoc line scoping it to RB-strategy introspection. Test: a morphed-to-AVL/Splay
   context short-circuits selfRepair without a rebuild; a genuinely corrupted tree still
   repairs.
2. **X2 — the replay arena**, per Option B: `core.export.TreeSessionRecorder` (+ tests),
   replay mode in `demo/visualizer.html`, `experimental.ArenaSession` driver, one recorded
   session in `docs/`.
3. **X3 — happens-before paragraph** in README's Concurrency section (monitor edges,
   volatile publish points, stamp validation, the optimistic-vote argument).

**Held with triggers:** genome **deletion** (not relocation) when the control-plane flag
has soaked one release; Gradle/JMH/coordinates (ADR-009 G1 trigger); Count-Min skew
estimator (a workload the rolling estimator misjudges); evolutionary/bandit layer (an
experimental-tier consumer).

---

## 4. Consequences

**Easier:** repair stops punishing morphed trees; "self-adapting" becomes a file anyone
can replay, scrub, and inspect — recorded from the real controller, not a mock-up;
production sessions become debuggable artifacts for free.

**Harder:** the session file is a second public JSON contract to keep stable (versioned
from day one); the visualizer grows real UI state (timeline, play/pause) — still
single-file, still dependency-free, or it has failed its own constraint.

---

## 5. Action items

1. [ ] **X1** — strategy-aware selfRepair gate + scoped javadoc + tests.
2. [ ] **X2a** — `TreeSessionRecorder` + session-format tests.
3. [ ] **X2b** — visualizer replay mode (timeline, decision log) + `ArenaSession` driver
   + one canonical recorded session in `docs/`.
4. [ ] **X3** — README happens-before paragraph.

---

## 6. Verification & rollback

X1 changes one gate behind the existing health-check machinery and ships with both-ways
tests. X2 is additive (new class, new demo mode, new docs file); rollback is deletion.
Everything green through host `ant clean test` per `CLAUDE.md`, one slice per commit.
