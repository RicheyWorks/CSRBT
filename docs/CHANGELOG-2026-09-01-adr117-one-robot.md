# Changelog — 2026-09-01 — ADR-117: one robot for every target

The first robot walks every target: `tools/harness_walk.py` (was
`organism_walk.py`) drives the organism, the science lab and a kit page from
the manifest and the snapshot alone, one merged ledger per target in
`tools/walk_ledger.json`. Its first walk of the other two targets found a
`StackOverflowError` in csrbt-core and five plugin defects.

## Fixed — `csrbt-core`

`StrategyHealthCheck.isBst` is iterative. A Splay candidate built aside from
sorted keys is a chain as deep as the set, and the recursive BST check
overflowed at ~1,000 frames — inside a morph, killing the lab console.
`HealthCheckDeepChainProbeTest` (60k chain) pins it.

## Fixed — the plugins and consoles

Both plugins drain stderr into a bounded tail (a console dying loudly filled
the pipe, blocked, never exited, and the reader waited out its timeout).
Both consoles catch `Error` like `Exception`. Page plugin: `set-text` /
`set-slider` / `set-checkbox` on the wrong kind of control and `attach-file`
on a non-file (or two files to a single-file input) are `invalid_argument`,
not raises; `drop-files` on anything but a registered drop zone is refused
rather than "succeeding".

## Changed — `tools/harness_walk.py`, `tools/walk_ledger.json`

`--target organism | lab | page | both | all`; every plugin in the manifest
walked; scoped pools (`"<action>.<argument>"`) preferred every time;
`unreachable` for a tool whose published pools were empty throughout;
cross-checks keyed by plugin id (organism reads, lab counters, page
invariants from `read-page`); arrays formed one-first; default page
`collection-sheet.html`. `organism_walk.py` and `organism_ledger.json` are
removed.

## Changed — `tools/harness_plugin_page.py`

`argumentPools` in every snapshot: per-action selector pools from the
swarm's kind map (including controls behind a closed tab), `pane`, `page`
(this page), `choose-option.value`; examples on `value`, `pane`, `files`
(an enum of the fixture names); `open` stays on its page. Widened discovery
(the swarm's kinds) through the shared target builder.

## Changed — `tools/harness_contract.py` (`verify_contract` 85 → **87**)

An enum on an array argument is checked per item and published on the items.

## New — `tools/verify/verify_walk.py` (**49 checks**; replaces `verify_organism_walk`)

## Docs

`docs/ADR-117-one-robot-for-every-target-2026-09-01.md`;
`docs/AUTOMATION-HARNESS.md`; `docs/AI_HARNESS.md`.
