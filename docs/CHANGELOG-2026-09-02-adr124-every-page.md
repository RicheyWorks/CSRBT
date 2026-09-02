# Changelog — 2026-09-02 — ADR-124: every page, walked

## Changed — `tools/harness_walk.py`

`--target page --page all`: every page in `tools/routes.json`, each on its
own child, kept as `csrbt-page/<page>`; a one-line verdict per page and the
coverage matrix. Argument-set pools (a list of argument dicts keyed by the
action alone) are taken whole by `form` and are the first relevant pool of
their action.

## Changed — `tools/harness_contract.py` — protocol **1.3**

`argumentPools` may carry argument sets. `harness_mcp.py` reports 1.3.

## Changed — `tools/harness_plugin_page.py`

- `activate` refuses an anchor whose `href` leaves the document ("use
  open"); same-document links still click.
- `choose-option` publishes `{selector, value}` pairs for every enabled
  select as an argument-set pool (`optionChoices` in the control read).

## Changed — `tools/harness_plugin_fixture.py` (12 actions)

`paired`: accepts only the (a, b) pairs the snapshot publishes as sets.

## Changed — `tools/verify/verify_walk.py` (107 → **120**), `tools/mutate_walk.py` (24 → **26 killed**)

Set pools in the generator and the fixture; section I: every routed page in
the ledger at the bar, every page tool driven somewhere, the leaving-link
refusal and the option pairs pinned live. `verify_contract` at 1.3.

## Ledger — `tools/walk_ledger.json`

41 page entries (first walk: 38 ok, 3 bad — douglas-explorer followed a
link to the internet, ecology-teachers-guide and soil-suite walked other
pages after a link, experiment-guide's choose-option refused six of six;
second walk: 41 ok); page@stdio and page@mcp regenerated.

## Docs

`docs/ADR-124-every-page-walked-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
