# CHANGELOG 2026-06-09 -- ADR-003 E6: ensemble persistence + docs; ADR-003 Accepted

Final step of ADR-003 (`ADR-003-multi-tree-ensemble-2026-06-06.md`): snapshot persistence for the
ensemble, the README "Ensemble" coverage, and the ADR flipped from **Proposed** to **Accepted**.
With E1-E5 already landed (mirror fan-out, O(1) promotion, quarantine/heal/failover, VERIFIED
quorum reads, parallel fan-out, SAMPLED_SHADOW, and the adaptation benchmark), this closes the
ADR's action-item list.

## What changed

- **Ensemble snapshot I/O on `FilePersistenceAdapter`.** Two thin methods over the existing,
  battle-tested generic `OrderedSet<K>` snapshot path -- no new on-disk format:
  - `saveSnapshot(name, EnsembleOrderedSet, KeySerializer)` snapshots the **primary** only. The
    primary *is* the logical set (every ACTIVE mirror is an exact copy; in SAMPLED_SHADOW it is
    the one exact copy), so persisting K member trees would store the same keys K times. The
    recorded strategy name is informational on this path.
  - `loadEnsemble(name, KeySerializer, target)` clears the caller-built target ensemble and
    replays the snapshot's keys **through the facade**, so the normal write path rebuilds every
    member: exact mirrors in MIRROR/VERIFIED, the sampled stride in SAMPLED_SHADOW -- exactly as
    if the keys had arrived live. Member strategies, mode, comparator, and executor are runtime
    configuration, deliberately not serialized: the same snapshot can wake up under a different
    member line-up. Returns false (target untouched) on a missing/malformed snapshot.
- **README.** The ensemble is now first-class in the intro, an "Ensemble (ADR-003)" architecture
  paragraph, a Quick-start snippet (builder, fan-out, O(1) promote, snapshot round-trip), a
  Features bullet, the `core/ensemble` package in the project layout, the eight `Ensemble*Test`
  classes in the suite list, and a Concurrency paragraph mapping the design doc's
  single-writer/multi-reader goal onto the ensemble's writer lock + volatile primary swap.
- **ADR-003 status: Proposed -> Accepted.** All six action items E1-E6 are checked off.

## Tests

- `EnsemblePersistenceTest`:
  - *mirrorRoundTrip* -- randomized contents, a non-initial member promoted before saving (proving
    the *primary* is what gets snapshotted); reload rebuilds every member as an exact mirror.
  - *reloadIntoShadowMode* -- the same snapshot wakes up under SAMPLED_SHADOW: primary full,
    shadows hold exactly their stride and are marked inexact.
  - *shadowEnsembleSavesFullSet* -- saving a SAMPLED_SHADOW ensemble persists the full logical
    set; the sketches never leak into the snapshot.
  - *missingSnapshotLeavesTargetUntouched* -- a failed load reports false and mutates nothing.

## ADR-003 closed

| Step | Slice | Changelog |
|---|---|---|
| E1 | facade + mirror fan-out | CHANGELOG-2026-06-09-ensemble-e2.md (landed with E2) |
| E2 | EnsembleController + O(1) promotion | CHANGELOG-2026-06-09-ensemble-e2.md |
| E3 | health / quarantine / heal + failover | CHANGELOG-2026-06-09-ensemble-e3.md |
| E4 | VERIFIED quorum reads | CHANGELOG-2026-06-09-ensemble-e4.md |
| E5 | benchmark; parallel fan-out; SAMPLED_SHADOW | CHANGELOG-2026-06-09-ensemble-e5-{benchmark,fanout,shadow}.md |
| E6 | persistence + docs; ADR Accepted | this entry |
