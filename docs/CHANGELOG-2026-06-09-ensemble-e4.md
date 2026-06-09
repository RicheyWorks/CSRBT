# CHANGELOG 2026-06-09 -- ADR-003 E4: VERIFIED mode (N-version read voting)

Adds the ensemble's correctness vote (`ADR-003-multi-tree-ensemble-2026-06-06.md`, step E4). E3
catches a member whose tree is *structurally* broken, but not one that is internally self-consistent
yet wrong -- a latent strategy bug or memory corruption that still passes its own invariant check.
VERIFIED mode catches exactly that by fanning each read to a quorum and serving the majority.

## What changed

- **`EnsembleMode { MIRROR, VERIFIED }`** (new) and `EnsembleOrderedSet.mode` -- set via the builder
  (`.mode(VERIFIED)`) or `setMode(...)` at runtime. Default stays **MIRROR**, so E1-E3 behaviour and
  every existing caller are byte-for-byte unchanged.
- **Voting read path.** All reads -- `contains` / `size` / `inOrder` / `isEmpty` and the order
  statistics -- now route through a single `read(fn)` dispatcher:
  - **MIRROR:** `fn.apply(primary.set())` -- the old primary-served, lock-free read, untouched.
  - **VERIFIED:** `vote(fn)` polls every ACTIVE member, tallies answers, serves the
    **strict-majority** answer, and **quarantines** any dissenter. If the dissenter is the serving
    **primary**, it **fails over** first (promote a majority member, then quarantine the old primary),
    so a wrong primary can never decide the result. With no clear majority (a tie) the read falls
    back to the primary and quarantines no one -- the fault can't be adjudicated. Emits an
    `event=verified_dissent` line when it acts.
- **Builder/runtime guard:** VERIFIED requires at least three members (a 2-member ensemble can't form
  a majority).
- Voting runs under the write lock (a dissent mutates membership), so VERIFIED trades read
  concurrency and a quorum-many reads for cross-checked correctness -- the opt-in cost the ADR
  describes. Healing of a quarantined dissenter is left to the E3 cadence `checkHealth`.

## Behaviour

- **Deterministic members never disagree**, so in steady state every VERIFIED read is unanimous and
  quarantines nothing; a disagreement is a real fault, which is why quarantine-on-dissent is safe.
- **Catches what E3 cannot:** a member that lies on reads while staying self-consistent (the test's
  buggy `search`) is invisible to the per-member health check but is outvoted here -- including when
  it is the primary.

## Tests

- `EnsembleVerifiedTest` (E4), using a `BuggyContainsStrategy` (writes delegate to Red-Black so the
  tree is correct, but `search` always returns NIL so `contains` lies -- a self-consistent read bug):
  - *buggy member outvoted + quarantined* -- the ADR headline: the buggy member's `contains(7)=false`
    is outvoted 2-1, the correct `true` is served, and the member is quarantined.
  - *buggy primary fails over* -- with the buggy member as primary, the vote serves the majority and
    fails over off it (the case E3's self-check misses).
  - *MIRROR does not vote* -- the same buggy member is never consulted or quarantined in MIRROR.
  - *VERIFIED needs three members* -- the builder rejects a 2-member VERIFIED ensemble.

## Follow-ups (out of scope here)

- **E5** -- parallel fan-out + SAMPLED_SHADOW mode + a `StrategyBattleRunner`-style benchmark.
- Per-read healing (currently a dissenter is quarantined immediately and healed on the E3 cadence).
- A configurable quorum size / read-repair policy (today every ACTIVE member votes).
