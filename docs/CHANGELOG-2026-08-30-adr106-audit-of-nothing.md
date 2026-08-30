# Changelog — 2026-08-30 — ADR-106: an audit of nothing reports clean

First full local run of the suite (61/64 jobs, 4383/4385 checks) turned up four
defects that were invisible in the environment the kit's numbers came from.

## Fixed — two audits were examining zero pages

- `tools/audit_targets.py` and `tools/fek_lint.py` hardcoded
  `DOCS = "/tmp/eco/CSRBT/docs/"` — the autonomous polish job's clone path, which
  exists in one container and nowhere else. Everywhere else the glob returned
  `[]`, the page loop never ran, and both printed a clean result and exited 0.
  **Green, on every local run, from an audit of nothing.**
- Both now derive `DOCS` from the script's own location. Measured after:
  `fek_lint` scans 19 FEK consumers (was 0) and is genuinely clean.
- **No pages found is now exit 2 with a loud message**, not a clean report.
  Canaried against a non-existent root.
- `fek_lint` also split basenames on `"/"`, which is not a path separator on
  Windows; now `os.path.basename`.

## Fixed — three hardcoded Linux scratch paths

- `verify_claims_slice` and `verify_print_slice` wrote canary fixtures to
  `/tmp/_ccan/`, `/tmp/_pcan/`, `/tmp/_rdrcan` and navigated to
  `file:///tmp/...`. On Windows the file is written on one path and looked for on
  another, so both suites **crashed** with `net::ERR_FILE_NOT_FOUND` instead of
  reporting. Now `tempfile.mkdtemp()` + `pathlib.Path.as_uri()`.
- `tools/harness.py`'s file-import action wrote `/tmp/_harness_import.json`; now
  `tempfile.gettempdir()`.
- Swept all 97 tool scripts; no hardcoded POSIX scratch paths remain in code.

## Confirmed from ADR-105

- `verify_audit_frontend` 6/19 → **19/19** once the audit could actually run —
  the finder was never broken, exactly as diagnosed.
- `verify_publish_drift` 49/50 → **50/50** with the `newline=""` fix.

## Found, not fixed — one real product defect

- `verify_cs_science` 84/86: `DIV.row2` measures **401px inside a 390px phone**
  on `collection-sheet.html`'s record pane. The suite source is unchanged, and
  ADR-103's only edit to that page was `overflow-wrap:anywhere`, which can only
  *narrow* min-content width — it cannot widen anything. The overflow pre-existed
  and had never been measured; Windows fallback-font metrics expose it where the
  Linux container's did not.
- This is ADR-103's named worklist item (the `row2` flex-chain repair), now with
  a reproducing platform. Deliberately not attempted blind: ADR-103 already tried
  a one-property fix here, regressed three pages, and reverted all fifteen.
