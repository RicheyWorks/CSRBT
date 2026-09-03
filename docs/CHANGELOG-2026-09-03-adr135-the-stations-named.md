# Changelog — 2026-09-03 — ADR-135: the stations, named

## Pages — `docs/`

- `ecology-lab.html`: `card()` takes a slug and every one of the thirteen
  stations carries `id="station-<key>"`, the key the engine uses for it —
  `meadow`, `drift`, `demography`, `models`, `crosses`, `entered`, `notes`,
  `trees`, `hypotheses`, `archipelago`, `fossils`, `grid`, `island`.

## Harness — `tools/`

- `harness_plugin_page.py`: `read-report`'s box pattern accepts `station-*`;
  `FIXTURES["session"]` is the kit's shipped
  `docs/ecology-experiment-session.json`, read from disk rather than pasted in.
- `swarm.py`: a `drop` listener registered on the **window** or the document
  now stamps `document.body` as the drop zone. The lab takes its dropped
  session on the window, so it published no drop zone at all.
- `harness_tasks.py`: `@control:kind=<kind>` names a control the page never
  named — the lab's drop zone is the page's own `<body>`.

## Tasks — `tools/tasks/`

- `two-targets-stations`: the shipped protocol through the lab engine, its
  session dropped onto the page, and the meadow's three phases, the census,
  the theory bench's six models and all three entered datasets held to the
  engine's own figures. 33 expectations.

## Verification

`verify_tasks` 209 (+6); `mutate_tasks` 44 (+3); `verify_report` 50.

## Docs

`docs/ADR-135-the-stations-named-2026-09-03.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
