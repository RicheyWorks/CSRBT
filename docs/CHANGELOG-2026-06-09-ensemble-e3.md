# CHANGELOG 2026-06-09 -- ADR-003 E3: health / quarantine / heal + failover

Adds the ensemble's fault tolerance (`ADR-003-multi-tree-ensemble-2026-06-06.md`, step E3). E1 made
members exact mirrors; E2 made the serving choice an O(1) swap. E3 makes a corrupt member a
recoverable event rather than a silent wrong answer: each member is health-checked on a cadence,
a faulty one is quarantined and healed from the primary, and a faulty *primary* fails over to a
healthy member instantly -- reusing the E2 swap -- so queries are never served from a known-bad tree.

The health verdict is the existing `core.util.StrategyHealthCheck` (the same validator the single-tree
morph gate uses), so "healthy" means the same thing everywhere: correct contents, BST order, the
strategy's own structural invariant, and an order-statistics spot check.

## What changed

- **Lifecycle primitives on `EnsembleOrderedSet` (all write-locked, additive):**
  - `quarantine(member)` -- mark `QUARANTINED` so E1's fan-out (which already skips non-`ACTIVE`
    members) drops it from serving and writes. The serving primary cannot be quarantined directly.
  - `healFromPrimary(member)` -- rebuild the member's backing set from the **current primary's**
    `inOrder()` (the source of truth) and return it to `ACTIVE`, an exact mirror again under its own
    strategy. O(n) in the live size.
  - `retire(member)` -- mark `RETIRED` (permanently out of service) when a heal still won't validate.
- **`EnsembleController.checkHealth()` -- the cadence check + repair, returning a `HealthReport`:**
  1. **Primary first.** Validate the primary by its own structural invariants. If it fails, find a
     healthy member, `promote` it (the E2 O(1) failover), `quarantine` the deposed primary, then
     `healFromPrimary` it (retiring it only if the heal still won't validate). Failover precedes
     quarantine, so a read is never served from the bad primary.
  2. **Then the rest.** Validate every other `ACTIVE` member against the now-trusted primary's
     contents; quarantine + heal (or retire) any that diverge or break their invariant.
  - Emits one `event=health_check primary=... failedOver=... quarantined=... healed=... retired=...
    members=[...states...]` line per pass.

## Behaviour

- **Invariant: always keep a known-good serving member.** The primary is repaired by *replacement*
  (failover), never in place, so reads always resolve to a validated tree.
- **Heal is from the primary, not self.** A drifted member is rebuilt from the primary's contents
  (unlike `OrderedSet.selfRepair`, which rebuilds from a member's own -- possibly wrong -- keys), so a
  member that lost/gained keys is brought back into exact sync.
- **Single-writer.** `checkHealth` runs under the same single-writer model as the rest of the engine;
  each primitive takes the ensemble write lock.
- **Scope note.** The primary is validated against *itself*, so this E3 pass catches a structurally
  broken primary (bad invariant / BST / order-stats) but not a primary that is internally
  self-consistent yet wrong -- catching that needs cross-member read voting, which is **E4 (VERIFIED
  mode)**. Non-primary members are checked against the primary, so their content drift *is* caught.

## Tests

- `EnsembleHealthTest` (E3):
  - *corrupt non-primary -> quarantine + heal, queries uninterrupted* -- a member is drifted by
    dropping a key behind the fan-out; the check quarantines and heals it back to an exact mirror
    while the primary keeps serving correct reads the whole time.
  - *corrupt primary -> instant failover* -- the primary's root is painted red (a red-black root must
    be black); the check fails over to the first healthy member (AVL), heals the deposed primary, and
    reads stay correct from the new primary.
  - *healthy ensemble -> no repair* -- a clean ensemble reports no change and leaves every member
    `ACTIVE`.

## Follow-ups (out of scope here)

- **E4 -- VERIFIED mode:** per-read quorum + majority serve + dissenter quarantine (catches a
  self-consistent-but-wrong primary).
- A scheduled/automatic health cadence wired to an op counter (E3 exposes `checkHealth()` for the
  caller to drive, mirroring how `evaluateAndMaybePromote` is caller-driven).
- Snapshot fallback if **all** members fail at once (ADR section 5 "keep >=1 known-good member").
