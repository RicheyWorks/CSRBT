# Changelog — 2026-08-30 — ADR-105: the canary was lying, and a stamp was platform-dependent

A wrong prediction, measured; a canary that had been accusing working code on
both machines; and a build step whose output hashed differently per platform.

## Retracted

- ADR-104 predicted **64/64 jobs green** on the Windows host, and that
  `verify_audit_frontend` returning anything but 19/19 there would prove a real
  defect. Measured: **13/64 green**, and `verify_audit_frontend` **6/19 —
  identical to the Linux VM**. The premise was wrong: the host has no playwright
  either, so 51 jobs die on `ModuleNotFoundError` there too. The falsifier fired
  and was right.

## Fixed — `tools/verify/verify_audit_frontend.py`

- The canary ran `audit_frontend` as a subprocess and **never checked its return
  code**, scraping stdout for finding rows. An audit that died on its import line
  produced no rows, so twelve "is this seeded fault caught?" checks reported
  `FAIL … got: []` against a finder that never started, and seven "is a clean
  page left alone?" checks reported PASS off the same emptiness. Six false
  passes and twelve false failures.
- It now latches a reason when the audit exits non-zero with no rows, and every
  check reports `NOT VERIFIED` with it. Reads **0/19 with nineteen declared
  holes** where playwright is absent — `run_all` marks it `ok--` and names it.
  First new client of the ADR-104 machinery.

## Fixed — `tools/publish.py`

- Build output was written with `open(..., "w", encoding="utf-8")` and no
  `newline=""`, so Windows translated `\n` to `\r\n`, while
  `publish_state.sha()` reads those files in binary. The same page built on two
  platforms hashed to two different values.
- Consequence, not just a failing test: the seven pages stamped in ADR-104 were
  stamped from the Linux VM (LF hashes). Regenerating the build on Windows would
  have produced CRLF hashes and reported all seven **BEHIND** — a false drift
  alarm on current pages, decided by who last ran the tool.
- Now writes with `newline=""`. Verified: on-disk sha == in-memory sha for
  `food-web.html`, and the build output carries zero `\r` bytes. **The ADR-104
  stamps are correct as recorded; no re-stamping needed.** This also clears
  `verify_publish_drift` 49/50 on the host.

## Found, not fixed

- **51 of 64 jobs cannot run on either of Richmond's machines** — one
  `pip install playwright ; python -m playwright install chromium` away. Until
  then a local "green" covers 13 of 64 jobs.
- ADR-103's headline *"63 of 64 jobs green, 4461 of 4462 checks"* came from
  neither machine — it came from the autonomous polish container, the only
  environment with playwright. Nothing records which environment produced a green
  run, which is the provenance gap `publish_state.py` was written to close for
  published pages. Named; worth its own slice.

## Not committed

- `tools/verify/counts.json`, again restored to HEAD. It was correctly written by
  the host run and pushed in `2d5b99e`; a ledger rewritten where 50 suites cannot
  run describes the machine, not the kit.
