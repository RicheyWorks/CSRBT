# Changelog — 2026-09-01 — ADR-114: operable from the manifest alone

A client that has read nothing but the manifest can now drive all
thirty-three organism actions, and one does: `tools/organism_walk.py`, the
first robot, found four things on its first walk that 287 source-informed
checks had not.

## Changed — `tools/harness_contract.py` (protocol 1.0 → **1.1**)

`ArgumentSpec` gains `minimum`, `maximum`, `pattern`, `examples`: published
in the JSON Schema, enforced by the gateway before the plugin runs (bounds
inclusive; patterns full-match; array patterns per item). A pattern without
examples, an example failing its pattern, `minimum > maximum`, a bound on a
string, an example outside its enum: refused at construction.

## Changed — the plugins

`harness_plugin_organism.py`: every hand-enforced bound published; batch ops
and chaos plans as patterns with examples; example pools for keys and
generations; the snapshot publishes **`argumentPools.generation`** (the
generations that exist now); `pulse` before two ticks is `ok` with `null`;
`conflict` mapped. `harness_plugin_page.py`: selector and page-name grammars
as patterns with examples.

## Changed — `WholeHog/HarnessConsole.java`

`IllegalStateException` (Twine wedged after a crash mid-batch) → `conflict`,
not `failed`; `start > end` and `nth` past the size refused before any route,
so direct and wire answer with the same code; `generationIds` in `observe`.
`HarnessConsoleTest` covers both; 21 green.

## New — `tools/organism_walk.py` + `tools/organism_ledger.json`

Imports nothing from the kit; stdio only; forms every call from the schema;
five buckets with the accounting identity; per-round cross-checks; coverage
floor (every tool driven or the run fails); UNSCHEMABLE rather than guessing.
Ledger: 896 commands, 796 driven, 96 refused, 0 declined, 4 chaos, 0 failed,
33/33 driven, 0 invariants broken.

## New — `tools/verify/verify_organism_walk.py` (**26 checks**)

The walker is an outsider; the generator respects every kind of bound and
reports the unformable; the live walk and the committed ledger both meet the
bar. NOT VERIFIED ×1 without the build.

## Changed — suites

`verify_contract` 70 → **85**; `verify_organism` 287 → **291**;
`mutate_organism` 19 → **22 killed, 0 survived, 4 equivalent** (the ADR-112
cap mutant became equivalent when the bound moved into the schema — recorded,
replaced by one the manifest check kills).

## Docs

`docs/ADR-114-operable-from-the-manifest-alone-2026-09-01.md`;
`docs/AUTOMATION-HARNESS.md` (schema bounds, `argumentPools`, the walker);
`docs/AI_HARNESS.md` §7d; WholeHog `README.md`/`CLAUDE.md`.
