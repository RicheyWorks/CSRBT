# Changelog — 2026-09-02 — ADR-118: the engines' own suites, ratcheted

## New — `tools/ecosystem.py`, `tools/ecosystem_ledger.json`

Every engine repo named as a sibling with its test modules; `--read` walks
the JUnit XML into a merged, per-engine ledger with a floor that only rises
on a read; `--run` executes each repo's `./gradlew test` first; `--lower
ENGINE N --reason` lowers a floor on the record. First reading: fifteen
suites, **1624 tests, 0 failures** — SuperBeefSort's main suite (318) runs on
JDK 17+ after all; only its native module needs JDK 22 + Rust.

## New — `tools/verify/verify_ecosystem.py` (**52 checks**)

Every repo the composite build reaches listed (derived from the settings
files — a neighbouring Gradle project is not an engine) and nothing else;
every listed repo present; per engine with results newer than its sources:
green, tests ≥ floor, reading not older than the XML; absent or stale
results `NOT VERIFIED` by name with the date; floors and reasons; the
arithmetic. Both refusals canaried — and the first run on the author's
machine failed ten checks wrongly (a card game listed as an engine; a
month-old build called a shrunken suite) before the two rules above were
written.

## Docs

`docs/ADR-118-the-engines-own-suites-ratcheted-2026-09-02.md`;
`docs/AI_HARNESS.md` §8.
