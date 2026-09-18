# 2026-09-17 — ADR-225: WholeHog's build includes thirteen siblings and its CI checked out eleven

## Fixed

- **WholeHog's CI checks out Rub and Sizzle.** Every push since they joined the
  composite build had failed at configuration. The workflow travels as
  `WholeHog/ci/ci.yml` and `push-adr225-siblings.ps1` installs and pushes it.
- **`ecosystem.ci_gap(repo)`**: an engine's composite closure minus what its
  workflow checks out; `None` with no workflow.

- **SmokeHouse: `get()`/`range()` no longer throw when a compaction wins eight
  races in a row** — the ninth read is taken under the store lock, where a
  commit cannot intervene. The handoff's "concurrent-compaction test failure"
  was this; 82 / 82 now.

## Checked

`verify_ecosystem` 99 → 116: one check per engine (fourteen), written before the
fix and failing on WholeHog alone, plus a fixture where a transitive include is
the one missing. `mutate_engines` 13 → 16.
