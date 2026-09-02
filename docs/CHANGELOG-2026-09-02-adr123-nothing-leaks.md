# Changelog — 2026-09-02 — ADR-123: nothing leaks

## Changed — WholeHog `HarnessConsole`, csrbt-experimental `LabConsole`

A `jvm` verb (threads — by name on the organism —, open file descriptors or
−1, heap in use) and a `jvm` field in every `observe`. `HarnessConsoleTest`
(ten restarts leave the same threads by name) and `LabConsoleTest` (twenty
controller runs grow none): WholeHog 21, csrbt-experimental **257**.

## Changed — `tools/harness_plugin_organism.py` (35 actions), `tools/harness_plugin_lab.py` (9)

`jvm`, READ, on both.

## Changed — `tools/harness_walk.py`

`leak_checks`: round one is the baseline; a thread not there in round one is
reported by name; descriptors may rise by the segments the store rolled plus
a slack of eight. Wired into the organism's and the lab's cross-checks.
Ledger regenerated for both targets over both transports.

## Changed — suites and runners

`verify_organism` (310 → **317**): section Y, forty restarts; the bound-pair
pools (every `range.lo` below every `range.hi`, and the same for
`count-range` and `overlap`) pinned, after the 35th tool's shuffle left
`overlap` refused four times out of four in the short suite walk. `verify_walk`
(102 → **107**): section H. `verify_lab` at nine actions; `verify_mcp` at 21
allowed tools. `mutate_walk` **24 killed** / 0 / 2; `mutate_organism` **31
killed** / 0 / 4 (jvm reporting no thread names; the pair pools dropped).

## Docs

`docs/ADR-123-nothing-leaks-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`; `WholeHog/docs/CHANGELOG-2026-09-02-engine-two.md`
gains the jvm verb.
