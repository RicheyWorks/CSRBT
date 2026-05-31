# CSRBT — system-design audit (2026-05-30)

A system-design-framework pass over CSRBT *as built*, scoring it against its own
requirements and surfacing scale/reliability gaps. Complements the target design
(`DESIGN-adaptive-engine.md`) and the forward decisions (`ADR-002`). Scope: an
embeddable, single-node, in-memory ordered-set engine — not a service.

## 1. Requirements — and how the build scores

### Functional
| Requirement | Status | Notes |
|---|---|---|
| Ordered-set API (add/remove/contains/inOrder/size/clear) | ✅ | set semantics; duplicates are no-ops |
| Order statistics O(log n) (select/rank/median/percentile/range) | ✅ | exact across rotations and morphs; oracle-tested |
| Interval / range queries | ✅ | overlap + stabbing; tags survive morph & snapshot |
| Pluggable balancing (RB/AVL/Splay/Hybrid) | ✅ | invariants property-tested per strategy |
| Strategy morph without data loss | ✅ | build-aside + **health gate** + swap-or-rollback |
| Adaptive *automatic* strategy selection | ◑ | controller + MorphPolicy exist; not fed by a live workload monitor |
| Sliding-window / eviction | ✅ | `setMaxSize`; order stats exact on survivors |
| Durable snapshots; undo/redo + checkpoints | ✅ | text format; inverse-command history |
| Generic keys | ❌ | `int`-only (C5, deferred — see ADR-002) |

### Non-functional
| Requirement | Status | Notes |
|---|---|---|
| O(log n) per op; no tree-wide work on hot path | ✅ | the prior O(n)/O(n²) per-op offenders removed; Hybrid recolor now path-local |
| Morphs O(n) and **rare** | ✅ | amortization/cooldown/stability gating via MorphPolicy |
| Correctness first (no corruption, no infinite loops) | ✅ | the delete parent-cycle hang fixed; health gate rejects bad candidates |
| Observability | ✅ | one structured `event=morph_eval …` line per evaluation |
| Embeddable, no external services | ✅ | pure JVM library |
| Concurrency | ◑ | single-threaded by design (documented); atomic-swap multi-reader model is future |

Legend: ✅ met · ◑ partial · ❌ absent.

## 2. High-level design (as built)

```
            ┌──────────────── DATA PLANE ────────────────┐
 client ──▶ │ TreeContext (facade)                        │
            │   add/remove/contains/inOrder/size/clear    │
            │   order stats · interval · history ·        │
            │   persistence · windowing · health-gated    │
            │   setStrategy                               │
            │        │                                    │
            │        ▼  MutableTree seam                  │
            │   RedBlackTree (engine)                     │
            │        │ getRoot/setRoot/getNIL/rotate      │
            │        ▼                                    │
            │   TreeStrategy: RB | AVL | Splay | Hybrid   │
            └──────────────┬──────────────────────────────┘
                           │ stress/entropy/frag (ad hoc today)
                           ▼
            ┌──────────── CONTROL PLANE ──────────────────┐
            │ GenomeDrivenTreeController                   │
            │   chooseStrategyWithMemory → MorphPolicy →   │
            │   setStrategy (health gate) → morph_eval log │
            └─────────────────────────────────────────────┘
 experimental: TreeAgent, TreeEcology (depend on core only)
```

**Seam quality is the headline:** `MutableTree` (5 methods) is the only contract a
strategy needs, so strategies, engine, and facade evolve independently. The
registry maps every `StructureType` to buildable/unsupported with no silent gaps.

## 3. Deep dive

**Data model.** `TreeNode1` carries key (`int`), color, cached height/black-height,
a pluggable augmentor, a `tag` (interval hi endpoint), and per-tree NIL sentinel
identity. **Design smell:** one `augmentedValue` field is overloaded for two
meanings — subtree size (order statistics) *and* interval max-hi — which makes the
two features mutually exclusive on one tree and is the main thing complicating the
generic-key refactor. *Fix (ADR-002):* a typed augmentor payload.

**API contract.** `setStrategy` returns `boolean` (accepted/rejected by health
gate) — a binary-incompatible change to watch if ever published. Read methods and
`getTree()` expose live internals; the contract is explicitly single-threaded.

**Persistence.** Human-readable pre-order text; header now
`VERSION|TIMESTAMP|STRATEGY|SIZE|AUGMENTOR` (backward-compatible). Path-traversal
guarded; (de)serialization iterative (stack-safe). Key serializer is `int`-bound —
a blocker for generic keys.

**Health gate.** Candidate built aside → validate (contents, size, BST,
per-strategy invariant, select/rank spot-checks) → atomic-ish ref swap under the
write lock → rollback-free on failure. This is the reliability centerpiece.

## 4. Scale & reliability

**Load estimation (single node, in-memory).** Per-op cost is O(log n) with small
constants; the dominant constant is the O(height) augment propagation on BST
links (rotations use O(1) local recompute). For n=10⁶, height ≈ 20 (balanced) — a
handful of cache-missy pointer chases per op. Morph cost is O(n) build + O(n)
validate, gated so amortized frequency → 0 on stable workloads.

**Failure modes & responses (as built):**
| Failure | Detection | Response |
|---|---|---|
| Buggy candidate strategy | health gate clause | discard candidate, keep incumbent |
| Morph thrash | MorphPolicy cooldown/stability/margin | suppressed |
| Deep/degenerate persistent tree | iterative traversals | O(n) time, no stack overflow |
| Corrupt snapshot | structural validation on load | return null, log; no bad publish |
| Duplicate insert drift | dup guard in `add` | size/history stay correct |

**Reliability gaps:**
- **No live `WorkloadMonitor`.** Automatic adaptation runs on ad-hoc signals
  (rotation-derived stress, key-bucket entropy, height fragmentation) rather than a
  rolling op-mix/skew feature vector. G3/G4 (converge-to-Splay-under-skew,
  bounded-op convergence) are therefore not yet *demonstrable* end to end.
- **Concurrency is single-writer-ish but leaky** (`getTree()` hands out live
  state). The design's `volatile` root + atomic-swap multi-reader model is unbuilt.
- **`PersistentTreeEngine` is unbalanced** — O(n) worst case; fine as a demo
  engine, not as a first-class O(log n) member of the registry.
- **Versions retained unbounded** in the persistent engine (inherent to
  persistence, but no prune API).

## 5. Trade-off analysis (explicit)

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Morph safety | build-aside + validate + swap | mutate-in-place + repair | rollback is free; live data never at risk |
| Morph authority | single (control plane), facade auto-morph opt-in | always-on facade morph | stops the controller fighting the facade and benchmark contamination |
| Augment field | one `int`, overloaded | typed payload | (current) simple but couples size vs interval; flagged for change |
| Concurrency | documented single-threaded | atomic-swap MR / lock-free | honest now; atomic-swap is the next safe step |
| Keys | `int` (today) | generic `<K>` | phased migration chosen in ADR-002 |
| Adaptation | genome scorer (live) | 4-unit control plane | extract scoring kernel + add monitor incrementally |

## 6. What I'd revisit as it grows
1. **Typed augmentor payload** — unblocks size + interval coexistence and the
   generic-key refactor; do it alongside C5 step 3.
2. **Live `WorkloadMonitor` + extracted `StrategyScorer`** — turn "adaptive" from
   plausible into *demonstrable* (synthetic workload harness asserting convergence
   and morph rarity, replacing `StrategyBattleRunner` as the benchmark of record).
3. **Atomic root-swap concurrency** — `volatile` engine ref + single writer lock;
   stop leaking live internals via `getTree()`.
4. **Balanced persistent engine** — or relabel it demo-grade in the registry.
5. **Generic keys + pluggable key serializer** — the gateway to the motivating
   applications (string/timestamp/price/IP keys).
6. **Boxing cost** — only if profiling shows it matters once keys are generic
   (specialized primitive variants are a documented non-goal until then).

## Assumptions
- Single-node, working set fits in RAM (explicit non-goal: larger-than-memory).
- Exactness over approximation for percentiles/rank (the differentiator vs
  t-digest/HDR).
- No durability/transactions or distribution in scope (pair with a real store).
