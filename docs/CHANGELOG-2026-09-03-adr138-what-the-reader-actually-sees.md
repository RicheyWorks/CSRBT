# Changelog — 2026-09-03 — ADR-138: what the reader actually sees

## Pages — published copies

Nine artifacts republished from corrected bytes and re-measured at their URLs:
`greenhouse`, `ecology-lab`, `tree-proofs`, `tree-visualizer`,
`douglas-explorer`, `breeding-suite`, `cp-suite`, `soil-suite`, and the Harness
Board. The published **greenhouse** had been serving
`for(var i=0;i= 0){` — a syntax error — since publish.py was written: its whole
`<script>` block failed to parse, so every interactive feature on it was dead.
The other eight had their `<header class="hero">` banner's opening AND closing
tags deleted, so `.hero` never applied.

## Tools — `tools/`

- `publish_reach.py` **(new)**: `--plan` (the artifacts still owed a
  measurement, with their URLs), `--sweep DIR` (attribute and verify every saved
  copy in a directory, newest **version** per page wins), `--check`. It does not
  fetch — an artifact is read through the host's Artifact tool — and says so
  rather than pretending.
- `publish.py`: the shell-strip patterns take `\b` after each tag name and
  `[^<>]*` for attributes, and `strip()` now **proves** it removed only the
  skeleton: N shell tags remove exactly N `<` characters, or the build is
  refused. Also builds the artifacts that are not docs pages.
- `artifact_map.json`: an `others` section — the Harness Board, built as
  `build/publish/_harness-board.html`.
- `publish_state.py`: `mapped_artifacts()` covers both, so the report and
  `--stamp`/`--verify` treat the board like any page.
- `harness_board.py`: `mutate_publish` on the runners list.

## Verification

`verify_publish_reach` 78 (+28) — every artifact mapped and built, the reach
known, `--plan` exact, attribution by artifact id (ambiguous prefix refused,
unnamed copy refused), the two stamps kept apart, the sweep taking the newer
version even when the older file was touched last, and the strip: a `<header>`
pair survives, a JS comparison that reads like a tag survives, the skeleton is
still removed in any case, a span-eating pattern is refused rather than
published, and every page of the kit that opens with a `<header>` still has one
in the bytes handed to the publisher.

**An unmeasured artifact is now `NOT VERIFIED`, never a pass; a URL the repo has
moved past is a failure.** They are different claims and no longer share an
outcome.

`tools/mutate_publish.py` **(new)**: 15 mutants across `publish.py`,
`publish_state.py` and `publish_reach.py`. 15 killed, 0 survived.

`verify_board` 48 (+3). Kit **77 / 77 jobs, 5,674 / 5,674 checks**.

Publish reach after this slice: **42 mapped artifacts, 42 measured at their URLs** —
0 behind, 0 unknown, 0 stamped-only. The first time the kit has been able to say
that.

## Docs

`docs/ADR-138-what-the-reader-actually-sees-2026-09-03.md`;
`docs/AUTOMATION-HARNESS.md`, `docs/AI_HARNESS.md`.
