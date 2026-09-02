# Changelog — 2026-09-02 — ADR-119: the robot, broken on purpose

## New — `tools/harness_plugin_fixture.py` (`csrbt-fixture`)

A fourth plugin, served only by `--target fixture` and listed by no
production manifest: eleven actions that each land in a known bucket every
time (`ok`, `refuse`, `decline`, `crash`, `boom`, `pooled` — accepts only the
slot the latest snapshot publishes and rotates it per call —, `empty-pool`,
`reached`, `unformable`, `array`, `broken`; `die` with
`CSRBT_FIXTURE_DIE=1`). `harness_targets.py` stands it up; it is never part
of `--target all`.

## New — `tools/mutate_walk.py` (**17 mutants, all killed, 2 equivalent**)

Breaks `harness_walk.py` — refusals filed as driven, chaos never recognised,
pools not re-read, arrays never one first, the alarm for a dead target
removed, the verdict ignoring failures … — against `verify_walk` in
`CSRBT_WALK_QUICK=1` mode (no engine, no browser; under a second a mutant).

## Changed — `tools/harness_walk.py`

The per-tool tick starts at zero (the first call takes the first enum value
and a one-item array — the fixture found the old `round × 100 + i` handing
out two items first, so "one first" was true in the unit check and false in
every walk); `unreachable` also requires `driven == 0`; a `csrbt-fixture`
cross-check (its counters equal the walk, its `consistent` flag holds).

## Changed — `tools/verify/verify_walk.py` (49 → 74 with ADR-120)

Section **F**: exact bucket counts over the fixture, the fixture's own
counters against the walk, unreachable vs reached, unschemable named and
never sent, the cross-check every round, `bad()` on each spoiled field, the
walk raising when the target dies. `CSRBT_WALK_QUICK=1` skips section C.

## Docs

`docs/ADR-119-the-robot-broken-on-purpose-2026-09-02.md`;
`docs/AUTOMATION-HARNESS.md`, `docs/AI_HARNESS.md`.
